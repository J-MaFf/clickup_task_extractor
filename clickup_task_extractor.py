"""
ClickUp Task Extractor (Python)
- Authenticates with ClickUp API using multiple methods:
  1. Command line argument (--api-key)
  2. Environment variable (CLICKUP_API_KEY)
  3. 1Password SDK (requires OP_SERVICE_ACCOUNT_TOKEN)
  4. 1Password CLI fallback (requires 'op' command)
  5. Manual input prompt
- Retrieves tasks for a workspace/space
- Maps Branch (Location) field to human-readable label
- Exports to CSV and HTML
- Supports AI summary (optional), image extraction, and interactive exclusion
- Matches PowerShell output/columns/features
- SOLID principles applied

1Password Integration:
- SDK: Set OP_SERVICE_ACCOUNT_TOKEN environment variable
- CLI: Ensure 'op' command is available in PATH
- Secret reference: "op://Home Server/ClickUp personal API token/credential"
"""

import os
import sys
import json
import csv
import html
import requests
import argparse
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta

# Date/time formatting constant
TIMESTAMP_FORMAT = '%-d-%-m-%Y_%-I-%-M%p'
DISPLAY_FORMAT = '%-d/%-m/%Y at %-I:%-M %p'

# 1Password SDK imports
try:
    from onepassword.client import Client as OnePasswordClient
except ImportError:
    OnePasswordClient = None

# --- Config DataClass ---
@dataclass
class ClickUpConfig:
    api_key: str
    workspace_name: str = 'KMS'
    space_name: str = 'Kikkoman'
    output_path: str = field(default_factory=lambda: f"output/WeeklyTaskList_{datetime.now().strftime(TIMESTAMP_FORMAT)}.csv")
    include_completed: bool = False
    date_filter: str = 'AllOpen'  # 'ThisWeek', 'LastWeek', 'AllOpen'
    enable_ai_summary: bool = False
    github_token: Optional[str] = None
    output_format: str = 'HTML'  # 'CSV', 'HTML', 'Both'
    interactive_selection: bool = False
    # Exclude tasks with these statuses
    exclude_statuses: list = field(default_factory=lambda: ['Dormant', 'On Hold', 'Document'])

# --- Task DataClass ---
@dataclass
class TaskRecord:
    Task: str
    Company: str
    Branch: str
    Priority: str
    Status: str
    ETA: str = ''
    Notes: str = ''
    Extra: str = ''

# --- API Client (SRP) ---
class ClickUpAPIClient:
    BASE_URL = 'https://api.clickup.com/api/v2'

    def __init__(self, api_key: str):
        self.headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json'
        }

    def get(self, endpoint: str) -> Any:
        url = f"{self.BASE_URL}{endpoint}"
        resp = requests.get(url, headers=self.headers)

        # Add debugging information for failed requests
        if not resp.ok:
            print(f"API Request failed:")
            print(f"  URL: {url}")
            print(f"  Status: {resp.status_code}")
            print(f"  Response: {resp.text}")

        resp.raise_for_status()
        return resp.json()

# --- Utility Functions (SRP) ---
def get_date_range(filter_name: str):
    today = datetime.now()
    if filter_name == 'ThisWeek':
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end
    elif filter_name == 'LastWeek':
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return start, end
    return None, None

def extract_images(text: str) -> str:
    import re
    if not text:
        return ''
    patterns = [
        r'!\[.*?\]\(.*?\)',
        r'<img[^>]*>',
        r'https?://[^\s]*\.(jpg|jpeg|png|gif|bmp|webp)',
        r'attachment[s]?[:.]?[^\s]*\.(jpg|jpeg|png|gif|bmp|webp)'
    ]
    images = []
    for pat in patterns:
        images += re.findall(pat, text, re.IGNORECASE)
    return '; '.join(images)

# --- AI Summary (SRP) ---
def get_ai_summary(task_name: str, notes: str, github_token: str) -> str:
    # Placeholder: Implement actual call if needed
    return notes

# --- 1Password SDK Integration (SRP) ---
def get_api_key_from_1password(secret_reference: str) -> Optional[str]:
    """
    Retrieve ClickUp API key from 1Password using the SDK.

    Args:
        secret_reference: The 1Password secret reference (e.g., "op://Home Server/ClickUp personal API token/credential")

    Returns:
        The API key string if successful, None if failed

    Raises:
        Various exceptions for different failure modes (network, auth, not found, etc.)
    """
    if OnePasswordClient is None:
        raise ImportError("1Password SDK not available. Install with: pip install onepassword-sdk")

    # Get service account token from environment
    service_token = os.environ.get('OP_SERVICE_ACCOUNT_TOKEN')
    if not service_token:
        raise ValueError("OP_SERVICE_ACCOUNT_TOKEN environment variable not set. Required for 1Password SDK authentication.")

    try:
        import asyncio

        async def _get_api_key():
            # Ensure OnePasswordClient is not None before using it
            if OnePasswordClient is None:
                raise ImportError("1Password SDK not available. Install with: pip install onepassword-sdk")
            # Authenticate with 1Password using service account token
            client = await OnePasswordClient.authenticate(
                auth=service_token,
                integration_name="ClickUp Task Extractor",
                integration_version="1.0.0"
            )

            # Resolve the secret reference to get the API key
            api_key = await client.secrets.resolve(secret_reference)

            if not api_key:
                raise ValueError(f"Secret reference '{secret_reference}' resolved to empty value")

            return api_key.strip()

        # Run the async function
        return asyncio.run(_get_api_key())

    except Exception as e:
        # Re-raise with more context
        error_msg = f"Failed to retrieve API key from 1Password: {type(e).__name__}: {e}"
        raise RuntimeError(error_msg) from e

# --- Location Mapper (SRP, OCP) ---
class LocationMapper:
    @staticmethod
    def map_location(val, type_, options) -> str:
        if not options:
            return str(val)
        # Always match by id (ClickUp stores dropdown value as option id)
        for opt in options:
            if str(opt.get('id')) == str(val):
                return opt.get('name', str(val))
        # Try to match by orderindex if value is int or str number
        try:
            val_int = int(val)
            for opt in options:
                if 'orderindex' in opt and int(opt['orderindex']) == val_int:
                    return opt.get('name', str(val))
        except Exception:
            pass
        # Try to match by name if value is a string and matches an option name
        for opt in options:
            if str(opt.get('name')) == str(val):
                return opt.get('name', str(val))
        return str(val)

# --- Main Extractor (SRP, DIP) ---
class ClickUpTaskExtractor:
    def __init__(self, config: ClickUpConfig, api_client: ClickUpAPIClient):
        self.config = config
        self.api = api_client

    def run(self):
        import traceback
        try:
            print("Fetching workspaces...")
            teams = self.api.get('/team')['teams']
            team = next((t for t in teams if t['name'] == self.config.workspace_name), None)
            if not team:
                print(f"Error: Workspace '{self.config.workspace_name}' not found.")
                return
            print(f"Workspace found: {team['name']}")
            print("Fetching spaces...")
            spaces = self.api.get(f"/team/{team['id']}/space")['spaces']
            space = next((s for s in spaces if s['name'] == self.config.space_name), None)
            if not space:
                print(f"Error: Space '{self.config.space_name}' not found.")
                return
            print(f"Space found: {space['name']}")
            print("Fetching lists...")
            lists = []
            folder_resp = self.api.get(f"/space/{space['id']}/folder")
            if not folder_resp or not isinstance(folder_resp, dict):
                print(f"  Unexpected folder API response: {folder_resp}")
                folders = []
            else:
                folders = folder_resp.get('folders', [])
            for folder in folders:
                folder_list_resp = self.api.get(f"/folder/{folder['id']}/list")
                if not folder_list_resp or not isinstance(folder_list_resp, dict):
                    print(f"    Unexpected folder list API response for folder {folder.get('name', folder.get('id', ''))}: {folder_list_resp}")
                    continue
                lists += folder_list_resp.get('lists', [])
            space_list_resp = self.api.get(f"/space/{space['id']}/list")
            if not space_list_resp or not isinstance(space_list_resp, dict):
                print(f"  Unexpected space list API response: {space_list_resp}")
            else:
                lists += space_list_resp.get('lists', [])
            print(f"Found {len(lists)} lists.")
            # 4. Get tasks
            all_tasks = []
            for idx, lst in enumerate(lists, 1):
                print(f"Processing list {idx}/{len(lists)}: {lst.get('name', 'Unknown')}")
                params = []
                if not self.config.include_completed:
                    params.append('archived=false')
                # Date filter (not implemented in detail)
                q = '?' + '&'.join(params) if params else ''
                try:
                    resp = self.api.get(f"/list/{lst['id']}/task{q}")
                    if not resp or not isinstance(resp, dict) or 'tasks' not in resp:
                        print(f"  Unexpected API response for list {lst.get('name')}: {resp}")
                        continue
                    tasks = resp.get('tasks', [])
                except Exception as e:
                    print(f"  Error fetching tasks for list {lst}: {e}")
                    continue
                print(f"  Found {len(tasks)} tasks")
                for t in tasks:
                    try:
                        task_detail = self.api.get(f"/task/{t['id']}")
                        if not task_detail or not isinstance(task_detail, dict):
                            print(f"    Unexpected task detail for task {t.get('id')}: {task_detail}")
                            continue
                    except Exception as e:
                        print(f"    Error fetching task {t}: {e}")
                        continue
                    # Exclude tasks by status (from config)
                    try:
                        status_val = task_detail.get('status', {}).get('status')
                    except Exception as e:
                        print(f"    ERROR: Could not get status from task_detail")
                        continue

                    if status_val in self.config.exclude_statuses:

                        continue
                    # Custom fields
                    cf = {f['name']: f for f in task_detail.get('custom_fields', [])}
                    branch_field = cf.get('Branch')
                    branch_name = ''
                    if branch_field:
                        val = branch_field.get('value')
                        type_ = branch_field.get('type')
                        options = branch_field.get('type_config', {}).get('options', [])
                        branch_name = LocationMapper.map_location(val, type_, options)
                    # Notes
                    notes_parts = []
                    for fname in ['Subject', 'Description', 'Resolution']:
                        f = cf.get(fname)
                        if f and f.get('value'):
                            notes_parts.append(f"{fname}: {f['value']}")
                    if not cf.get('Description') and task_detail.get('description'):
                        notes_parts.append(f"Task Description: {task_detail['description']}")
                    notes = '\n'.join(notes_parts)
                    if self.config.enable_ai_summary and self.config.github_token:
                        notes = get_ai_summary(task_detail.get('name', ''), notes, self.config.github_token)
                    # Images
                    desc_img = extract_images(cf.get('Description', {}).get('value', ''))
                    res_img = extract_images(cf.get('Resolution', {}).get('value', ''))
                    task_img = extract_images(task_detail.get('description', ''))
                    extra = ' | '.join([i for i in [desc_img, res_img, task_img] if i])
                    # Build record
                    # Handle priority possibly being None
                    priority_obj = task_detail.get('priority')
                    if isinstance(priority_obj, dict):
                        priority_val = priority_obj.get('priority', '')
                    else:
                        priority_val = ''
                    rec = TaskRecord(
                        Task=task_detail.get('name', ''),
                        Company=lst.get('name', ''),
                        Branch=branch_name,
                        Priority=priority_val,
                        Status=task_detail.get('status', {}).get('status', ''),
                        Notes=notes,
                        Extra=extra
                    )
                    all_tasks.append(rec)
            print(f"Total tasks fetched: {len(all_tasks)}")
            # Interactive selection
            if self.config.interactive_selection and all_tasks:
                print(f"\nInteractive mode enabled - prompting for task selection...")
                all_tasks = self.interactive_include(all_tasks)
            elif self.config.interactive_selection and not all_tasks:
                print("Interactive mode enabled but no tasks found to select from.")
            # Export
            self.export(all_tasks)
        except Exception as e:
            print(f"Fatal error: {e}")
            traceback.print_exc()
            sys.exit(1)

    def interactive_include(self, tasks: List[TaskRecord]) -> List[TaskRecord]:
        print("\nINTERACTIVE TASK SELECTION")
        print("Please select which tasks you would like to export:")
        print("-" * 60)

        selected_tasks = []

        for i, task in enumerate(tasks, 1):
            # Display task details
            print(f"\nTask {i}/{len(tasks)}:")
            print(f"  Name: {task.Task}")
            print(f"  Company: {task.Company}")
            print(f"  Branch: {task.Branch}")
            print(f"  Status: {task.Status}")
            if task.Notes:
                # Show first 100 characters of notes
                notes_preview = task.Notes[:100] + "..." if len(task.Notes) > 100 else task.Notes
                print(f"  Notes: {notes_preview}")

            # Prompt for user input with validation
            while True:
                try:
                    sys.stdout.flush()  # Ensure output is flushed before input
                    response = input(f"Would you like to export task '{task.Task}'? (y/n): ").strip().lower()
                    if response in ['y', 'yes']:
                        selected_tasks.append(task)
                        print("  ✓ Added to export list")
                        break
                    elif response in ['n', 'no']:
                        print("  ✗ Skipped")
                        break
                    else:
                        print("  Please enter 'y' for yes or 'n' for no.")
                except (EOFError, KeyboardInterrupt):
                    print("\n\nOperation cancelled by user.")
                    return []

        # Display summary
        print("\n" + "=" * 60)
        print("SELECTION SUMMARY")
        print("=" * 60)
        if selected_tasks:
            print("The following tasks will be exported:")
            for task in selected_tasks:
                print(f"  • {task.Task}")
        else:
            print("No tasks selected for export.")
        print(f"\nTotal: {len(selected_tasks)} task(s) selected out of {len(tasks)}")
        print("=" * 60)

        return selected_tasks

    def export(self, tasks: List[TaskRecord]):
        if not tasks:
            print('No tasks found to export.')
            return
        # Ensure output dir
        outdir = os.path.dirname(self.config.output_path)
        if outdir and not os.path.exists(outdir):
            os.makedirs(outdir)
        # CSV
        if self.config.output_format in ('CSV', 'Both'):
            with open(self.config.output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=TaskRecord.__annotations__.keys())
                writer.writeheader()
                for t in tasks:
                    writer.writerow(asdict(t))
            print(f"✓ CSV exported: {self.config.output_path}")
        # HTML
        if self.config.output_format in ('HTML', 'Both'):
            html_path = self.config.output_path.replace('.csv', '.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(self.render_html(tasks))
            print(f"✓ HTML exported: {html_path}")

    def render_html(self, tasks: List[TaskRecord]) -> str:
        # Simple HTML table, styled
        head = '''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Weekly Task List</title><style>body{font-family:Arial,sans-serif;margin:20px;}table{border-collapse:collapse;width:100%;margin-top:20px;}th,td{border:1px solid #ddd;padding:12px;text-align:left;vertical-align:top;}th{background-color:#f2f2f2;font-weight:bold;}tr:nth-child(even){background-color:#f9f9f9;}.task-name{font-weight:bold;color:#2c5aa0;}.priority-high{color:#d73502;font-weight:bold;}.priority-normal{color:#0c7b93;}.priority-low{color:#6aa84f;}.notes{max-width:400px;white-space:pre-wrap;line-height:1.4;font-size:0.9em;}.status{padding:4px 8px;border-radius:4px;font-size:0.8em;font-weight:bold;}.status-open{background-color:#e8f4fd;color:#1f4e79;}.status-in-progress{background-color:#fff2cc;color:#7f6000;}.status-review{background-color:#f4cccc;color:#660000;}h1{color:#2c5aa0;}.summary{margin-bottom:20px;padding:15px;background-color:#f0f8ff;border-left:4px solid #2c5aa0;}</style></head><body>'''
        summary = f'<h1>Weekly Task List</h1><div class="summary"><strong>Generated:</strong> {datetime.now().strftime(DISPLAY_FORMAT)}<br><strong>Total Tasks:</strong> {len(tasks)}<br><strong>Workspace:</strong> {html.escape(self.config.workspace_name)} / {html.escape(self.config.space_name)}</div>'
        table = '<table><thead><tr>' + ''.join(f'<th>{k}</th>' for k in TaskRecord.__annotations__.keys()) + '</tr></thead><tbody>'
        for t in tasks:
            table += '<tr>' + ''.join(f'<td>{html.escape(str(getattr(t, k) or ""))}</td>' for k in TaskRecord.__annotations__.keys()) + '</tr>'
        table += '</tbody></table></body></html>'
        return head + summary + table

# --- Entrypoint ---

def main():
    """
    Entrypoint for ClickUp Task Extractor.
    Supports CLI args for config overrides. Example:
      python ClickUpTaskExtractor.py --api-key ... --workspace ... --space ...

    API key 1Password reference: "op://Home Server/ClickUp personal API token/credential"

    Authentication priority:
    1. --api-key command line argument
    2. CLICKUP_API_KEY environment variable
    3. 1Password SDK (requires OP_SERVICE_ACCOUNT_TOKEN env var)
    4. 1Password CLI fallback (requires 'op' command available)
    5. Manual input prompt
    """
    parser = argparse.ArgumentParser(
        description="Extract and export ClickUp tasks to HTML (preferred) or CSV. Default workspace: KMS.\nAPI key 1Password reference: op://Home Server/ClickUp personal API token/credential\nRequires OP_SERVICE_ACCOUNT_TOKEN for 1Password SDK authentication."
    )
    parser.add_argument('--api-key', type=str, default=os.environ.get('CLICKUP_API_KEY'), help='ClickUp API Key (or set CLICKUP_API_KEY env, or use 1Password SDK with OP_SERVICE_ACCOUNT_TOKEN, e.g. from 1Password: "op://Home Server/ClickUp personal API token/credential")')
    parser.add_argument('--workspace', type=str, help='Workspace name (default: KMS)')
    parser.add_argument('--space', type=str, help='Space name (default: Kikkoman)')
    parser.add_argument('--output', type=str, help='Output file path (default: auto-generated)')
    parser.add_argument('--include-completed', action='store_true', help='Include completed/archived tasks')
    parser.add_argument('--date-filter', type=str, choices=['AllOpen', 'ThisWeek', 'LastWeek'], help='Date filter')
    parser.add_argument('--ai-summary', action='store_true', help='Enable AI summary (requires github token)')
    parser.add_argument('--github-token', type=str, help='GitHub token for AI summary')
    parser.add_argument('--output-format', type=str, choices=['CSV', 'HTML', 'Both'], help='Output format (default: HTML)')
    parser.add_argument('--interactive', action='store_true', help='Enable interactive task selection')
    args = parser.parse_args()

    # 1Password reference for API key: "op://Home Server/ClickUp personal API token/credential"
    api_key = args.api_key or os.environ.get('CLICKUP_API_KEY')

    if not api_key:
        # Try to get API key from 1Password SDK
        try:
            secret_reference = 'op://Home Server/ClickUp personal API token/credential'
            api_key = get_api_key_from_1password(secret_reference)
            print("✓ API key loaded from 1Password SDK.")
        except ImportError as e:
            print(f"1Password SDK not available: {e}")
            print("Falling back to 1Password CLI...")
            # Fallback to 1Password CLI
            try:
                import subprocess
                api_key = subprocess.check_output([
                    'op', 'read', 'op://Home Server/ClickUp personal API token/credential'
                ], encoding='utf-8').strip()
                print("✓ API key loaded from 1Password CLI.")
            except Exception as cli_error:
                print(f"Could not read API key from 1Password CLI: {cli_error}")
                api_key = None
        except Exception as e:
            print(f"Could not read API key from 1Password SDK: {e}")
            print("Please provide via --api-key or CLICKUP_API_KEY.")
            api_key = None

    # If still no API key, prompt for manual input
    if not api_key:
        api_key = input('Enter ClickUp API Key: ')

    # Check if interactive mode should be enabled when not explicitly set
    interactive_mode = args.interactive
    if not interactive_mode:
        try:
            print("\nInteractive mode allows you to review and select which tasks to export.")
            print("Without interactive mode, all tasks will be automatically exported.")
            response = input('Would you like to run in interactive mode? (y/n): ').strip().lower()
            interactive_mode = response in ['y', 'yes']
            if interactive_mode:
                print("✓ Interactive mode enabled - you'll be able to review each task before export.")
            else:
                print("✓ Running in automatic mode - all tasks will be exported.")
        except (EOFError, KeyboardInterrupt):
            print("\nDefaulting to automatic mode.")
            interactive_mode = False

    config = ClickUpConfig(
        api_key=api_key,
        workspace_name=args.workspace or 'KMS',
        space_name=args.space or 'Kikkoman',
        output_path=args.output or f"output/WeeklyTaskList_{datetime.now().strftime(TIMESTAMP_FORMAT)}.csv",
        include_completed=args.include_completed,
        date_filter=args.date_filter or 'AllOpen',
        enable_ai_summary=args.ai_summary,
        github_token=args.github_token,
        output_format=args.output_format or 'HTML',
        interactive_selection=interactive_mode
    )
    client = ClickUpAPIClient(api_key)
    extractor = ClickUpTaskExtractor(config, client)
    extractor.run()

if __name__ == '__main__':
    main()
