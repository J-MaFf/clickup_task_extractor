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

Authentication (each secret, in order):
1. Environment variable (CLICKUP_API_KEY / GOOGLE_SHEETS_CREDENTIALS_JSON),
   e.g. injected via `op run --env-file=.env.kfj`
2. 1Password Python SDK via desktop app auth (no token setup needed; the
   unlocked 1Password app approves the access)
3. Repo fallback chain (auth.load_secret_with_fallback): SDK with
   OP_SERVICE_ACCOUNT_TOKEN, then `op read` CLI

Credentials only ever exist in memory and are never written to disk.

Notes:
- ETA dates are converted from ClickUp epoch-ms due dates using UTC (repo
  convention), which can render one day off for late-evening local due times.
- A new tab is added each week; old tabs are left untouched and accumulate.

Usage:
    python kfj_task_extractor.py                       # SDK/CLI auth
    op run --env-file=.env.kfj -- python kfj_task_extractor.py  # env injection
    python kfj_task_extractor.py --dry-run
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timezone

def _reexec_in_venv() -> None:
    """Re-launch inside the project venv when available (same convenience
    pattern as main.py) so dependencies resolve regardless of the invoking
    interpreter.

    No-op when already running from the venv or when the venv does not exist.
    Called only from the ``__main__`` guard so importing this module never
    triggers a process re-exec or re-exec loop.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.name == "nt":
        venv_python = os.path.join(script_dir, ".venv", "Scripts", "python.exe")
    else:
        venv_python = os.path.join(script_dir, ".venv", "bin", "python")

    if not sys.executable.startswith(
        os.path.join(script_dir, ".venv")
    ) and os.path.exists(venv_python):
        print(f"Switching from {sys.executable} to virtual environment: {venv_python}")
        sys.exit(subprocess.call([venv_python] + sys.argv))


def _configure_stdio_encoding() -> None:
    """Force UTF-8 output so Unicode survives redirected/cp1252 consoles
    (e.g. when run under ``op run`` on Windows). Mutates sys.stdout/stderr,
    so it is only invoked from the ``__main__`` guard.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower() not in (
            "utf-8",
            "utf8",
        ):
            stream.reconfigure(encoding="utf-8")


try:
    from rich.console import Console
    from rich.table import Table
except ImportError:
    print("Error: The 'rich' library is required but not installed.")
    print("Please install it using: pip install -r requirements.txt")
    sys.exit(1)

from api_client import APIError, AuthenticationError, ClickUpAPIClient
from auth import load_secret_with_fallback, resolve_secret_with_desktop_sdk
from config import TaskRecord, format_datetime, sort_tasks_by_priority_and_eta
from logger_config import get_logger, setup_logging
from mappers import LocationMapper

console = Console()
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration.
#
# The values below were previously hardcoded as personal defaults (a ClickUp
# list id, a Google Sheet id, 1Password vault/item references, and a 1Password
# account name), which made this script single-tenant. They now read from
# environment variables with non-personal (empty) defaults so the script can be
# pointed at any list/sheet/account — typically via a local .env.kfj file (see
# .env.kfj.example). The list/sheet ids can also be passed on the CLI with
# --list-id / --sheet-id, which take precedence over these defaults.
# ---------------------------------------------------------------------------

# ClickUp list id and Google Sheets workbook id (empty by default).
DEFAULT_LIST_ID = os.environ.get("KFJ_CLICKUP_LIST_ID", "")
DEFAULT_SHEET_ID = os.environ.get("KFJ_GOOGLE_SHEET_ID", "")

TAB_PREFIX = os.environ.get("KFJ_TAB_PREFIX", "KFI Jefferson current tasks")
HEADER = ["Task", "Company", "Branch", "Priority", "Status", "ETA"]
FALLBACK_BRANCH = os.environ.get("KFJ_FALLBACK_BRANCH", "")
PRIORITY_MAP = {1: "Low", 2: "Normal", 3: "High", 4: "Urgent"}
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# 1Password secret references (op:// URIs) for the ClickUp API key and the
# Google service-account JSON. Both default to empty; when unset, the resolver
# falls back to the KFJ_*/standard environment variables (see _resolve_secret).
# References may use vault/item IDs or names; IDs survive renames and work with
# the desktop SDK, op CLI, op run, and service-token SDK.
CLICKUP_SECRET_REFERENCE = os.environ.get("KFJ_CLICKUP_SECRET_REFERENCE", "")
# Service-account JSON item:
GOOGLE_SA_SECRET_REFERENCE = os.environ.get("KFJ_GOOGLE_SA_SECRET_REFERENCE", "")

# 1Password account selectors. DesktopAuth expects the account *display name*
# as shown in the 1Password app; the op CLI expects the account URL.
PERSONAL_ACCOUNT_NAME = os.environ.get("KFJ_OP_ACCOUNT_NAME", "")
PERSONAL_ACCOUNT_URL = os.environ.get("KFJ_OP_ACCOUNT_URL", "my.1password.com")


def read_secret_via_op_cli(
    secret_reference: str, account_url: str, secret_name: str
) -> str | None:
    """
    Last-resort `op read` with an explicit account.

    Exists because auth.load_secret_with_fallback short-circuits to the
    1Password Environment path when OP_ENVIRONMENT_ID is set and never
    reaches its own CLI fallback for vault references.

    Returns:
        The secret string, or None on any failure (never raises)
    """
    try:
        result = subprocess.run(
            ["op", "read", secret_reference, "--account", account_url],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            logger.info(f"✅ {secret_name} loaded from 1Password CLI ({account_url}).")
            return result.stdout.strip()
        logger.debug(
            f"op read failed for {secret_name}: {result.stderr.strip()[:200]}"
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        logger.debug(f"op CLI unavailable for {secret_name}: {e}")
    return None


def _resolve_secret(
    env_var: str,
    secret_reference: str,
    sdk_account_name: str,
    cli_account_url: str,
    secret_name: str,
) -> str | None:
    """
    Resolve a secret through the full chain:

    1. Environment variable (e.g. injected via `op run`)
    2. 1Password Python SDK via desktop app auth
    3. Repo fallback chain (1Password Environment / service-token SDK / CLI)
    4. Direct `op read` with explicit account

    Returns:
        The secret string, or None if every source failed
    """
    value = os.environ.get(env_var)
    if value:
        logger.debug(f"Using {secret_name} from environment variable {env_var}")
        return value
    # Without a configured 1Password reference, skip the 1Password lookups and
    # rely on the environment variable above (e.g. injected via `op run`).
    if not secret_reference:
        logger.debug(
            f"No 1Password reference configured for {secret_name}; "
            f"set {env_var} or KFJ_*_SECRET_REFERENCE to enable 1Password lookup."
        )
        return None
    value = resolve_secret_with_desktop_sdk(
        secret_reference, secret_name, [sdk_account_name] if sdk_account_name else []
    )
    if value:
        return value
    value = load_secret_with_fallback(secret_reference, secret_name)
    if value:
        return value
    return read_secret_via_op_cli(secret_reference, cli_account_url, secret_name)


def resolve_clickup_api_key() -> str | None:
    """Resolve the ClickUp API key (see _resolve_secret for the chain)."""
    return _resolve_secret(
        "CLICKUP_API_KEY",
        CLICKUP_SECRET_REFERENCE,
        PERSONAL_ACCOUNT_NAME,
        PERSONAL_ACCOUNT_URL,
        "ClickUp API key",
    )


def load_google_credentials_json() -> str | None:
    """
    Resolve the Google service account JSON as a string (see _resolve_secret
    for the chain). The credential only ever exists in memory; nothing is
    written to disk.
    """
    return _resolve_secret(
        "GOOGLE_SHEETS_CREDENTIALS_JSON",
        GOOGLE_SA_SECRET_REFERENCE,
        PERSONAL_ACCOUNT_NAME,
        PERSONAL_ACCOUNT_URL,
        "Google sheets credentials JSON",
    )


def load_sheets_client():
    """
    Build an authorized gspread client from in-memory service account JSON.

    Returns:
        Tuple of (authorized gspread.Client, service account email)

    Raises:
        ValueError: If no credential source produced the service account JSON
        json.JSONDecodeError: If the credential is not valid JSON
    """
    import gspread

    raw = load_google_credentials_json()
    if not raw:
        raise ValueError(
            "No Google service account credentials found. Either run via "
            "`op run --env-file=.env.kfj` or ensure the 1Password desktop "
            "app / `op` CLI can resolve "
            f"'{GOOGLE_SA_SECRET_REFERENCE}'."
        )
    creds_dict = json.loads(raw)
    client_email = creds_dict.get("client_email", "<service account email>")
    return gspread.service_account_from_dict(creds_dict, scopes=SCOPES), client_email


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
        help="ClickUp list ID to extract from "
        "(default: KFJ_CLICKUP_LIST_ID env var)",
    )
    parser.add_argument(
        "--sheet-id",
        default=DEFAULT_SHEET_ID,
        help="Google Sheets workbook ID to write to "
        "(default: KFJ_GOOGLE_SHEET_ID env var)",
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

    # The list/sheet ids are no longer hardcoded; require them via --list-id /
    # --sheet-id or the KFJ_CLICKUP_LIST_ID / KFJ_GOOGLE_SHEET_ID env vars.
    if not args.list_id:
        console.print(
            "[red]No ClickUp list ID configured. Pass --list-id or set "
            "KFJ_CLICKUP_LIST_ID (see .env.kfj.example).[/red]"
        )
        return 1
    if not args.sheet_id and not args.dry_run:
        console.print(
            "[red]No Google Sheet ID configured. Pass --sheet-id or set "
            "KFJ_GOOGLE_SHEET_ID (see .env.kfj.example), or use --dry-run.[/red]"
        )
        return 1

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
        gc, client_email = load_sheets_client()
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return 1
    except json.JSONDecodeError as e:
        console.print(
            f"[red]Google service account credential is not valid JSON: {e}[/red]"
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
    # Side effects that must only run when executed as a script, never on import:
    #   1. Re-exec under the project venv if not already running from it.
    #   2. Reconfigure stdio to UTF-8 (mutates sys.stdout/sys.stderr).
    _reexec_in_venv()
    _configure_stdio_encoding()
    sys.exit(main())
