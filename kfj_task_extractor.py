#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
KFJ Task Extractor - Weekly ClickUp -> Google Sheets sync

Standalone entry point that pulls all open tasks from the "KFI Jefferson"
ClickUp list and writes them into the weekly tracking Google Sheet:
- Creates a new worksheet tab named "KFI Jefferson current tasks (M/D/YY)"
- Writes header + task rows (Task, Company, Branch, Priority, Status, ETA)
- Renames the workbook title to match the new tab

This script does not modify the main extractor workflow (main.py /
extractor.py); it only imports shared components (API client, auth chain,
TaskRecord, sorting, logging).

Authentication:
- ClickUp: CLICKUP_API_KEY env var (injected via `op run`), falling back to
  the repo's 1Password chain in auth.load_secret_with_fallback.
- Google Sheets: GOOGLE_SHEETS_CREDENTIALS_JSON env var containing the full
  service account JSON as a string (injected via `op run`). The credentials
  are passed directly to gspread from memory and never written to disk.

Notes:
- ETA dates are converted from ClickUp epoch-ms due dates using UTC (repo
  convention), which can render one day off for late-evening local due times.
- A new tab is added each week; old tabs are left untouched and accumulate.

Usage:
    op run --env-file=<env> -- python kfj_task_extractor.py
    python kfj_task_extractor.py --dry-run
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timezone

# Re-launch inside the project venv when available (same convenience pattern
# as main.py) so dependencies resolve regardless of the invoking interpreter.
script_dir = os.path.dirname(os.path.abspath(__file__))
if os.name == "nt":
    venv_python = os.path.join(script_dir, ".venv", "Scripts", "python.exe")
else:
    venv_python = os.path.join(script_dir, ".venv", "bin", "python")

if not sys.executable.startswith(os.path.join(script_dir, ".venv")) and os.path.exists(
    venv_python
):
    print(f"Switching from {sys.executable} to virtual environment: {venv_python}")
    sys.exit(subprocess.call([venv_python] + sys.argv))

try:
    from rich.console import Console
    from rich.table import Table
except ImportError:
    print("Error: The 'rich' library is required but not installed.")
    print("Please install it using: pip install -r requirements.txt")
    sys.exit(1)

from api_client import APIError, AuthenticationError, ClickUpAPIClient
from auth import load_secret_with_fallback
from config import TaskRecord, format_datetime, sort_tasks_by_priority_and_eta
from logger_config import get_logger, setup_logging
from mappers import LocationMapper

console = Console()
logger = get_logger(__name__)

DEFAULT_LIST_ID = "901413205844"  # ClickUp list "KFI Jefferson"
DEFAULT_SHEET_ID = "13plvMvZDvF5qIEhdDzJIhgoM1TdNoe9KZ1673AiAJ50"
TAB_PREFIX = "KFI Jefferson current tasks"
HEADER = ["Task", "Company", "Branch", "Priority", "Status", "ETA"]
FALLBACK_BRANCH = "KFJ (213)"
PRIORITY_MAP = {1: "Low", 2: "Normal", 3: "High", 4: "Urgent"}
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CLICKUP_SECRET_REFERENCE = "op://Home Server/ClickUp personal API token/credential"


def resolve_clickup_api_key() -> str | None:
    """
    Resolve the ClickUp API key: env var first (op run), then 1Password chain.

    Returns:
        API key string, or None if no source produced one
    """
    api_key = os.environ.get("CLICKUP_API_KEY")
    if api_key:
        logger.debug("Using ClickUp API key from environment variable")
        return api_key
    return load_secret_with_fallback(CLICKUP_SECRET_REFERENCE, "ClickUp API key")


def load_sheets_client():
    """
    Build an authorized gspread client from in-memory service account JSON.

    Reads GOOGLE_SHEETS_CREDENTIALS_JSON from the environment (injected via
    `op run`) and passes the parsed dict directly to gspread - the private
    key is never written to the local filesystem.

    Returns:
        Authorized gspread.Client

    Raises:
        KeyError: If GOOGLE_SHEETS_CREDENTIALS_JSON is not set
        json.JSONDecodeError: If the env var does not contain valid JSON
    """
    import gspread

    creds_dict = json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS_JSON"])
    return gspread.service_account_from_dict(creds_dict, scopes=SCOPES)


def fetch_open_tasks(client: ClickUpAPIClient, list_id: str) -> list[dict]:
    """
    Fetch all open tasks from a ClickUp list, following pagination.

    The list endpoint excludes closed tasks by default; a defensive filter on
    status type is applied as well.

    Args:
        client: ClickUp API client
        list_id: ClickUp list ID to fetch tasks from

    Returns:
        List of raw task dicts
    """
    tasks: list[dict] = []
    page = 0
    while True:
        response = client.get(
            f"/list/{list_id}/task?archived=false&subtasks=true&page={page}"
        )
        page_tasks = response.get("tasks", [])
        if not page_tasks:
            break
        tasks.extend(
            t for t in page_tasks if t.get("status", {}).get("type") != "closed"
        )
        if response.get("last_page", True):
            break
        page += 1
    return tasks


def task_to_record(task: dict, company: str) -> TaskRecord:
    """
    Map a raw ClickUp task dict (list endpoint shape) to a TaskRecord.

    Args:
        task: Raw task dict from the ClickUp list tasks endpoint
        company: Company name (the ClickUp list name)

    Returns:
        TaskRecord with the fields needed for the sheet
    """
    # Priority handling mirrors extractor._process_task
    priority_obj = task.get("priority")
    if isinstance(priority_obj, dict):
        priority_val = priority_obj.get("priority")
        if isinstance(priority_val, int):
            priority = PRIORITY_MAP.get(priority_val, "Normal")
        else:
            priority = str(priority_val) if priority_val else "Normal"
    else:
        priority = "Normal"

    status = task.get("status", {}).get("status", "")

    # ETA: epoch-ms due date -> date-only string (UTC, repo convention)
    eta = ""
    due_date = task.get("due_date")
    if due_date:
        try:
            due_dt = datetime.fromtimestamp(int(due_date) / 1000, tz=timezone.utc)
            eta = format_datetime(due_dt, "%m/%d/%Y")
        except (ValueError, OSError):
            eta = ""

    # Branch: resolve the dropdown custom field, falling back to the
    # constant used by the KFI Jefferson list
    branch = FALLBACK_BRANCH
    custom_fields = {f.get("name"): f for f in task.get("custom_fields", [])}
    branch_field = custom_fields.get("Branch")
    if branch_field and branch_field.get("value") is not None:
        type_config = branch_field.get("type_config", {})
        options = type_config.get("options", [])
        branch = LocationMapper.map_location(
            branch_field["value"], type_config, options
        )

    return TaskRecord(
        Task=task.get("name", ""),
        Company=company,
        Branch=branch,
        Priority=priority,
        Status=status,
        ETA=eta,
    )


def record_to_row(record: TaskRecord) -> list[str]:
    """
    Convert a TaskRecord to a sheet row, normalized to match the existing
    sheet's conventions (lowercase priority/status, date-only ETA).
    """
    return [
        record.Task,
        record.Company,
        record.Branch,
        record.Priority.lower(),
        record.Status.lower(),
        record.ETA,
    ]


def build_tab_name(d: date) -> str:
    """
    Build the weekly tab/workbook name, e.g. "KFI Jefferson current tasks (6/10/26)".

    Month and day have no leading zeros; year is two digits.
    """
    return f"{TAB_PREFIX} ({d.month}/{d.day}/{d.strftime('%y')})"


def write_to_sheet(gc, sheet_id: str, tab_name: str, rows: list[list[str]]) -> None:
    """
    Write header + rows into a fresh tab and rename the workbook.

    Creates a new worksheet at index 0 named tab_name (or clears and reuses
    it if a same-named tab already exists, making same-day re-runs
    idempotent). Existing tabs are never modified.

    Args:
        gc: Authorized gspread client
        sheet_id: Spreadsheet (workbook) ID
        tab_name: Name for the new tab and the workbook title
        rows: Data rows (without header)
    """
    import gspread

    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(tab_name)
        ws.clear()
        logger.info(f"Reusing existing tab '{tab_name}' (same-day re-run)")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(
            title=tab_name,
            rows=max(len(rows) + 10, 50),
            cols=len(HEADER),
            index=0,
        )
        logger.info(f"Created new tab '{tab_name}'")

    # USER_ENTERED so ETA strings are parsed as real dates by Sheets
    ws.update(
        values=[HEADER] + rows,
        range_name="A1",
        value_input_option="USER_ENTERED",
    )
    ws.format("A1:F1", {"textFormat": {"bold": True}})
    sh.update_title(tab_name)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract open KFI Jefferson tasks from ClickUp into the weekly Google Sheet"
    )
    parser.add_argument(
        "--list-id",
        default=DEFAULT_LIST_ID,
        help=f"ClickUp list ID to extract from (default: {DEFAULT_LIST_ID})",
    )
    parser.add_argument(
        "--sheet-id",
        default=DEFAULT_SHEET_ID,
        help="Google Sheets workbook ID to write to",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and print rows without touching Google Sheets",
    )
    parser.add_argument(
        "--date",
        default=None,
        metavar="M/D/YY",
        help="Override the date used in the tab name (e.g. 6/10/26)",
    )
    return parser.parse_args()


def main() -> int:
    """Run the extraction and sheet update. Returns process exit code."""
    setup_logging(logging.INFO)
    args = parse_args()

    if args.date:
        try:
            tab_date = datetime.strptime(args.date, "%m/%d/%y").date()
        except ValueError:
            console.print(f"[red]Invalid --date '{args.date}', expected M/D/YY[/red]")
            return 1
    else:
        tab_date = date.today()
    tab_name = build_tab_name(tab_date)

    api_key = resolve_clickup_api_key()
    if not api_key:
        console.print(
            "[red]No ClickUp API key found. Set CLICKUP_API_KEY (e.g. via `op run`) "
            "or configure the 1Password fallback.[/red]"
        )
        return 1

    client = ClickUpAPIClient(api_key)
    try:
        list_info = client.get(f"/list/{args.list_id}")
        company = list_info.get("name", "KFI Jefferson")
        raw_tasks = fetch_open_tasks(client, args.list_id)
    except AuthenticationError as e:
        console.print(f"[red]ClickUp authentication failed: {e}[/red]")
        return 1
    except APIError as e:
        console.print(f"[red]ClickUp API error: {e}[/red]")
        return 1

    records = sort_tasks_by_priority_and_eta(
        [task_to_record(t, company) for t in raw_tasks]
    )
    rows = [record_to_row(r) for r in records]
    logger.info(f"Fetched {len(rows)} open task(s) from list '{company}'")

    if args.dry_run:
        table = Table(title=f"Dry run - would write to tab '{tab_name}'")
        for col in HEADER:
            table.add_column(col)
        for row in rows:
            table.add_row(*row)
        console.print(table)
        return 0

    try:
        gc = load_sheets_client()
    except KeyError:
        console.print(
            "[red]GOOGLE_SHEETS_CREDENTIALS_JSON is not set. Run via "
            "`op run` with the service account JSON injected.[/red]"
        )
        return 1
    except json.JSONDecodeError as e:
        console.print(
            f"[red]GOOGLE_SHEETS_CREDENTIALS_JSON is not valid JSON: {e}[/red]"
        )
        return 1

    import gspread

    try:
        write_to_sheet(gc, args.sheet_id, tab_name, rows)
    except gspread.exceptions.SpreadsheetNotFound:
        console.print(
            f"[red]Spreadsheet '{args.sheet_id}' not found or not shared with "
            "the service account.[/red]"
        )
        return 1
    except gspread.exceptions.APIError as e:
        console.print(f"[red]Google Sheets API error: {e}[/red]")
        if e.response.status_code == 403:
            try:
                client_email = json.loads(
                    os.environ["GOOGLE_SHEETS_CREDENTIALS_JSON"]
                ).get("client_email", "<service account email>")
            except (KeyError, json.JSONDecodeError):
                client_email = "<service account email>"
            console.print(
                f"[yellow]Hint: share the sheet with {client_email} as Editor.[/yellow]"
            )
        return 1

    console.print(
        f"[green]✓ Wrote {len(rows)} task(s) to tab '{tab_name}' and renamed "
        f"the workbook.[/green]"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
