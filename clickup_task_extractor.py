"""
ClickUp Task Extractor (Python)

A cross-platform Python script for extracting, processing, and exporting tasks from the ClickUp API.
Designed to match the output and features of a PowerShell-based workflow with improved maintainability.

FEATURES:
- Multiple API key authentication methods with 1Password integration
- Cross-platform date formatting without leading zeros
- Interactive task selection and filtering
- Export to styled HTML and/or CSV formats
- Custom field mapping (Branch/Location) to human-readable labels
- Task status filtering and exclusion
- Optional AI summary integration (uses Google Gemini API)
- Image extraction from task descriptions
- Comprehensive error handling and debugging

AUTHENTICATION PRIORITY:
1. Command line argument (--api-key)
2. Environment variable (CLICKUP_API_KEY)
3. 1Password SDK (requires OP_SERVICE_ACCOUNT_TOKEN)
4. 1Password CLI fallback (requires 'op' command)
5. Manual input prompt

1PASSWORD INTEGRATION:
- SDK: Set OP_SERVICE_ACCOUNT_TOKEN environment variable
- CLI: Ensure 'op' command is available in PATH
- ClickUp API secret reference: "op://Home Server/ClickUp personal API token/credential"
- Gemini API secret reference: "op://Home Server/nftoo3gsi3wpx7z5bdmcsvr7p4/credential"

ARCHITECTURE:
- ClickUpConfig: Centralized configuration management with dataclass
- ClickUpAPIClient: HTTP API client following Single Responsibility Principle
- TaskRecord: Dataclass for task export structure
- LocationMapper: Custom field value mapping to human-readable labels
- ClickUpTaskExtractor: Main orchestrator class
- Cross-platform datetime formatting functions

OUTPUT FORMATS:
- HTML: Styled table with summary (default)
- CSV: Standard comma-separated values
- Both: Generate both formats simultaneously

DATE FORMATTING:
- Filenames: Remove leading zeros for cleaner names (e.g., "1-8-2025_3-45PM")
- Display: Remove leading zeros for better readability (e.g., "1/8/2025 at 3:45 PM")
- Cross-platform compatible using standard strftime with post-processing

USAGE:
  python clickup_task_extractor.py [options]

EXAMPLES:
  python clickup_task_extractor.py --interactive
  python clickup_task_extractor.py --workspace "MyWorkspace" --output-format Both
  python clickup_task_extractor.py --api-key YOUR_KEY --include-completed
  python clickup_task_extractor.py --ai-summary --gemini-api-key YOUR_GEMINI_KEY
"""

import os
import sys
import csv
import html
import requests
import argparse
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta

# Date/time formatting constants - cross-platform compatible
TIMESTAMP_FORMAT = '%d-%m-%Y_%I-%M%p'  # For filenames (with leading zeros for compatibility)
DISPLAY_FORMAT = '%d/%m/%Y at %I:%M %p'  # For HTML display (with leading zeros for compatibility)

def format_datetime(dt: datetime, format_string: str) -> str:
    """
    Format datetime removing leading zeros from day, month, and hour.

    Args:
        dt: DateTime object to format
        format_string: strftime format string to use

    Returns:
        Formatted datetime string without leading zeros
    """
    s = dt.strftime(format_string)
    # Remove leading zeros from day and month
    s = s.replace(dt.strftime('%d'), str(dt.day), 1)
    s = s.replace(dt.strftime('%m'), str(dt.month), 1)
    # Handle hour formatting for 12-hour format
    hour_12 = dt.hour % 12
    if hour_12 == 0:
        hour_12 = 12
    s = s.replace(dt.strftime('%I'), str(hour_12), 1)
    return s

def default_output_path() -> str:
    """Generate default output path with timestamp without leading zeros."""
    return f"output/WeeklyTaskList_{format_datetime(datetime.now(), TIMESTAMP_FORMAT)}.csv"
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
    output_path: str = field(default_factory=default_output_path)
    include_completed: bool = False
    date_filter: str = 'AllOpen'  # 'ThisWeek', 'LastWeek', 'AllOpen'
    enable_ai_summary: bool = False
    gemini_api_key: Optional[str] = None
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
def get_yes_no_input(prompt: str, default_on_interrupt: bool = False) -> bool:
    """
    Generic function to get yes/no input from user with consistent behavior.

    Args:
        prompt: The prompt message to display to the user
        default_on_interrupt: What to return if user interrupts (Ctrl+C, EOF)

    Returns:
        True if user answered yes, False if no or interrupted
    """
    try:
        response = input(prompt).strip().lower()
        return response in ['y', 'yes']
    except (EOFError, KeyboardInterrupt):
        print(f"\n{'Defaulting to yes.' if default_on_interrupt else 'Defaulting to no.'}")
        return default_on_interrupt

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
def get_ai_summary(task_name: str, subject: str, description: str, resolution: str, gemini_api_key: str) -> str:
    """
    Generate a concise 1-2 sentence summary about the current status of the task using Google Gemini AI.

    Args:
        task_name: Name of the task
        subject: Subject field content
        description: Description field content
        resolution: Resolution field content
        gemini_api_key: Google Gemini API key for authentication

    Returns:
        AI-generated summary or original content if AI fails
    """
    if not gemini_api_key:
        return f"Subject: {subject}\nDescription: {description}\nResolution: {resolution}".strip()

    try:
        import json

        # Prepare the content for AI analysis
        content_parts = []
        if subject:
            content_parts.append(f"Subject: {subject}")
        if description:
            content_parts.append(f"Description: {description}")
        if resolution:
            content_parts.append(f"Resolution: {resolution}")

        if not content_parts:
            return "No content available for summary."

        full_content = "\n".join(content_parts)

        # Create the prompt for AI summary
        prompt = f"""Please provide a concise 1-2 sentence summary of the current status of this task:

Task: {task_name}

{full_content}

Focus on the current state and what has been done or needs to be done. Be specific and actionable."""

        # Google Gemini API call
        headers = {
            'Content-Type': 'application/json'
        }

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": f"You are a helpful assistant that summarizes task status in 1-2 clear, concise sentences. Focus on current state and next actions.\n\n{prompt}"
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 150,
                "stopSequences": []
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
        }

        # Use Gemini 1.5 Flash for cost-effectiveness
        api_url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}'

        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()

            # Extract the generated text from Gemini response
            if 'candidates' in result and len(result['candidates']) > 0:
                candidate = result['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    summary = candidate['content']['parts'][0]['text'].strip()

                    # Clean up the summary
                    summary = summary.replace('\n', ' ').strip()
                    if summary.endswith('.'):
                        return summary
                    else:
                        return summary + '.'

            print(f"Unexpected Gemini API response structure: {result}")
            return full_content
        else:
            print(f"Gemini AI Summary API failed ({response.status_code}): {response.text}")
            return full_content

    except Exception as e:
        print(f"AI Summary error: {e}")
        # Fallback to original content
        return f"Subject: {subject}\nDescription: {description}\nResolution: {resolution}".strip()

# --- 1Password SDK Integration (SRP) ---
def _load_secret_with_fallback(secret_reference: str, secret_name: str) -> Optional[str]:
    """
    Generic function to load a secret from 1Password using SDK with CLI fallback.

    Args:
        secret_reference: The 1Password secret reference
        secret_name: Human-readable name for the secret (for error messages)

    Returns:
        The secret string if successful, None if failed
    """
    # Try 1Password SDK first
    try:
        secret = get_secret_from_1password(secret_reference, secret_name)
        print(f"✓ {secret_name} loaded from 1Password SDK.")
        return secret
    except ImportError as e:
        print(f"1Password SDK not available for {secret_name}: {e}")
        print(f"Falling back to 1Password CLI for {secret_name}...")
        # Fallback to 1Password CLI
        try:
            import subprocess
            secret = subprocess.check_output([
                'op', 'read', secret_reference
            ], encoding='utf-8').strip()
            print(f"✓ {secret_name} loaded from 1Password CLI.")
            return secret
        except Exception as cli_error:
            print(f"Could not read {secret_name} from 1Password CLI: {cli_error}")
            return None
    except Exception as e:
        print(f"Could not read {secret_name} from 1Password SDK: {e}")
        return None

def get_secret_from_1password(secret_reference: str, secret_type: str = "API key") -> Optional[str]:
    """
    Retrieve a secret from 1Password using the SDK.

    Args:
        secret_reference: The 1Password secret reference (e.g., "op://Home Server/ClickUp personal API token/credential")
        secret_type: Description of the secret type for error messages (default: "API key")

    Returns:
        The secret string if successful, None if failed

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

        async def _get_secret():
            # Ensure OnePasswordClient is not None before using it
            if OnePasswordClient is None:
                raise ImportError("1Password SDK not available. Install with: pip install onepassword-sdk")
            # Authenticate with 1Password using service account token
            client = await OnePasswordClient.authenticate(
                auth=service_token,
                integration_name="ClickUp Task Extractor",
                integration_version="1.0.0"
            )

            # Resolve the secret reference to get the secret
            secret = await client.secrets.resolve(secret_reference)

            if not secret:
                raise ValueError(f"Secret reference '{secret_reference}' resolved to empty value")

            return secret.strip()

        # Run the async function
        return asyncio.run(_get_secret())

    except Exception as e:
        # Re-raise with more context
        error_msg = f"Failed to retrieve {secret_type} from 1Password: {type(e).__name__}: {e}"
        raise RuntimeError(error_msg) from e

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
    return get_secret_from_1password(secret_reference, "ClickUp API key")

def get_gemini_api_key_from_1password(secret_reference: str) -> Optional[str]:
    """
    Retrieve Gemini API key from 1Password using the SDK.

    Args:
        secret_reference: The 1Password secret reference (e.g., "op://Home Server/nftoo3gsi3wpx7z5bdmcsvr7p4/credential")

    Returns:
        The Gemini API key string if successful, None if failed

    Raises:
        Various exceptions for different failure modes (network, auth, not found, etc.)
    """
    return get_secret_from_1password(secret_reference, "Gemini API key")

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
    def __init__(self, config: ClickUpConfig, api_client: ClickUpAPIClient, load_gemini_key_func=None):
        self.config = config
        self.api = api_client
        self.load_gemini_key_func = load_gemini_key_func

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
                    subject_content = ''
                    description_content = ''
                    resolution_content = ''

                    for fname in ['Subject', 'Description', 'Resolution']:
                        f = cf.get(fname)
                        if f and f.get('value'):
                            if fname == 'Subject':
                                subject_content = f['value']
                            elif fname == 'Description':
                                description_content = f['value']
                            elif fname == 'Resolution':
                                resolution_content = f['value']
                            notes_parts.append(f"{fname}: {f['value']}")

                    if not cf.get('Description') and task_detail.get('description'):
                        task_desc = task_detail['description']
                        description_content = task_desc
                        notes_parts.append(f"Task Description: {task_desc}")

                    # Generate AI summary or use original notes
                    if self.config.enable_ai_summary and self.config.gemini_api_key:
                        notes = get_ai_summary(
                            task_detail.get('name', ''),
                            subject_content,
                            description_content,
                            resolution_content,
                            self.config.gemini_api_key
                        )
                    else:
                        notes = '\n'.join(notes_parts)
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

                # After task selection in interactive mode, ask about AI summary if not already set
                if all_tasks and not self.config.enable_ai_summary:
                    print(f"\nYou have selected {len(all_tasks)} task(s) for export.")
                    print("AI summary can generate concise 1-2 sentence summaries of task status using Google Gemini.")
                    if get_yes_no_input('Would you like to enable AI summaries for the selected tasks? (y/n): '):
                        if self.load_gemini_key_func and self.load_gemini_key_func():
                            self.config.enable_ai_summary = True
                            print("✓ AI summary enabled for selected tasks.")
                        else:
                            gemini_key = input('Enter Gemini API Key (or press Enter to skip AI summary): ')
                            if gemini_key:
                                self.config.gemini_api_key = gemini_key.strip()
                                self.config.enable_ai_summary = True
                                print("✓ AI summary enabled with manual API key.")
                            else:
                                print("✓ Proceeding without AI summary.")
                    else:
                        print("✓ Proceeding without AI summary.")

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
            sys.stdout.flush()  # Ensure output is flushed before input
            if get_yes_no_input(f"Would you like to export task '{task.Task}'? (y/n): ", default_on_interrupt=False):
                selected_tasks.append(task)
                print("  ✓ Added to export list")
            else:
                print("  ✗ Skipped")

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
        summary = f'<h1>Weekly Task List</h1><div class="summary"><strong>Generated:</strong> {format_datetime(datetime.now(), DISPLAY_FORMAT)}<br><strong>Total Tasks:</strong> {len(tasks)}<br><strong>Workspace:</strong> {html.escape(self.config.workspace_name)} / {html.escape(self.config.space_name)}</div>'
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
    parser.add_argument('--ai-summary', action='store_true', help='Enable AI summary (requires Gemini API key - will auto-load from 1Password if available)')
    parser.add_argument('--gemini-api-key', type=str, help='Google Gemini API key for AI summary generation (or auto-load from 1Password: "op://Home Server/nftoo3gsi3wpx7z5bdmcsvr7p4/credential")')
    parser.add_argument('--output-format', type=str, choices=['CSV', 'HTML', 'Both'], help='Output format (default: HTML)')
    parser.add_argument('--interactive', action='store_true', help='Enable interactive task selection')
    args = parser.parse_args()

    # 1Password reference for API key: "op://Home Server/ClickUp personal API token/credential"
    api_key = args.api_key or os.environ.get('CLICKUP_API_KEY')

    if not api_key:
        # Try to get API key from 1Password with fallback
        secret_reference = 'op://Home Server/ClickUp personal API token/credential'
        api_key = _load_secret_with_fallback(secret_reference, "ClickUp API key")
        if not api_key:
            print("Please provide via --api-key or CLICKUP_API_KEY.")

    # If still no API key, prompt for manual input
    if not api_key:
        api_key = input('Enter ClickUp API Key: ')

    # Load Gemini API key if AI summary is enabled and no key provided via CLI
    gemini_api_key = args.gemini_api_key

    # Function to load Gemini API key when needed
    def load_gemini_api_key():
        nonlocal gemini_api_key
        if gemini_api_key:
            return True  # Already have the key

        # Try to get Gemini API key from 1Password with fallback
        gemini_secret_reference = 'op://Home Server/nftoo3gsi3wpx7z5bdmcsvr7p4/credential'
        gemini_api_key = _load_secret_with_fallback(gemini_secret_reference, "Gemini API key")
        if gemini_api_key:
            return True
        else:
            print("Please provide via --gemini-api-key.")
            return False

    # If AI summary flag was explicitly used, load the key now
    if args.ai_summary and not gemini_api_key:
        if not load_gemini_api_key():
            # If still no Gemini API key and AI summary is enabled, prompt for manual input
            gemini_api_key = input('Enter Gemini API Key (or press Enter to disable AI summary): ')
            if not gemini_api_key:
                print("No Gemini API key provided. AI summary will be disabled.")
                args.ai_summary = False

    # Check if interactive mode should be enabled when not explicitly set
    interactive_mode = args.interactive
    if not interactive_mode:
        print("\nInteractive mode allows you to review and select which tasks to export.")
        print("Without interactive mode, all tasks will be automatically exported.")
        interactive_mode = get_yes_no_input('Would you like to run in interactive mode? (y/n): ')
        if interactive_mode:
            print("✓ Interactive mode enabled - you'll be able to review each task before export.")
        else:
            print("✓ Running in automatic mode - all tasks will be exported.")

    # If not in interactive mode and AI summary wasn't explicitly set, ask now
    if not interactive_mode and not args.ai_summary:
        print("\nAI summary can generate concise 1-2 sentence summaries of task status using Google Gemini.")
        if get_yes_no_input('Would you like to enable AI summaries for tasks? (y/n): '):
            args.ai_summary = True
            if not load_gemini_api_key():
                gemini_api_key = input('Enter Gemini API Key (or press Enter to disable AI summary): ')
                if not gemini_api_key:
                    print("No Gemini API key provided. AI summary will be disabled.")
                    args.ai_summary = False
                else:
                    print("✓ AI summary enabled with manual API key.")
            else:
                print("✓ AI summary enabled.")
        else:
            print("✓ AI summary disabled.")

    config = ClickUpConfig(
        api_key=api_key,
        workspace_name=args.workspace or 'KMS',
        space_name=args.space or 'Kikkoman',
        output_path=args.output or f"output/WeeklyTaskList_{format_datetime(datetime.now(), TIMESTAMP_FORMAT)}.csv",
        include_completed=args.include_completed,
        date_filter=args.date_filter or 'AllOpen',
        enable_ai_summary=args.ai_summary,
        gemini_api_key=gemini_api_key,
        output_format=args.output_format or 'HTML',
        interactive_selection=interactive_mode
    )
    client = ClickUpAPIClient(api_key)
    extractor = ClickUpTaskExtractor(config, client, load_gemini_api_key)
    extractor.run()

if __name__ == '__main__':
    main()
