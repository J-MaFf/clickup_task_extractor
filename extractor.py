#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main Business Logic Module for ClickUp Task Extractor

Contains:
- ClickUpTaskExtractor class for task processing and export
- Interactive task selection functionality
- CSV, HTML, Markdown, and PDF export with styling
"""

import os
import sys
import csv
import html
from datetime import datetime, timezone
from dataclasses import asdict
from typing import TypeAlias
from contextlib import contextmanager
from pathlib import Path

import sys

# Rich imports for beautiful console output
try:
    from rich.console import Console
    from rich.table import Table, Column
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
    )
    from rich.panel import Panel
    from rich.text import Text
    from rich import print as rprint
except ImportError:
    print("Error: The 'rich' library is required but not installed.")
    print("Please install it using: pip install -r requirements.txt")
    print("Or install just rich: pip install rich>=10.0.0")
    sys.exit(1)

# Import project modules
from config import (
    ClickUpConfig,
    TaskRecord,
    DISPLAY_FORMAT,
    format_datetime,
    OutputFormat,
    sort_tasks_by_priority_and_name,
)
from api_client import (
    APIClient,
    ClickUpAPIClient,
    APIError,
    AuthenticationError,
    ShardRoutingError,
)
from ai_summary import get_ai_summary
from mappers import get_yes_no_input, get_date_range, extract_images, LocationMapper
from eta_calculator import calculate_eta

# Get the directory of this script for output path resolution
script_dir = os.path.dirname(os.path.abspath(__file__))

# Initialize Rich console with proper encoding for cross-platform compatibility
# This ensures proper rendering on Windows, macOS, and Linux
console = Console(force_terminal=None, legacy_windows=False)

# Type aliases for clarity
TaskList: TypeAlias = list[TaskRecord]


@contextmanager
def export_file(file_path: str, mode: str = "w", encoding: str = "utf-8"):
    """
    Context manager for safe file operations with automatic cleanup.

    Args:
        file_path: Path to the file to open
        mode: File open mode (default: 'w')
        encoding: File encoding (default: 'utf-8')

    Yields:
        File object for writing

    Example:
        >>> with export_file('output.csv') as f:
        ...     writer = csv.writer(f)
        ...     writer.writerow(['header1', 'header2'])
    """
    # Ensure output directory exists using pathlib
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with output_path.open(mode, newline="", encoding=encoding) as f:
            yield f
    except IOError as e:
        console.print(f"[red]❌ Error writing to {file_path}: {e}[/red]")
        raise


def get_export_fields() -> list[str]:
    """
    Get the list of fields to export, excluding internal fields like _metadata.

    Returns:
        List of field names for export (CSV headers and HTML columns)
    """
    return [
        field
        for field in TaskRecord.__annotations__.keys()
        if not field.startswith("_")
    ]


class ClickUpTaskExtractor:
    """Main orchestrator class for extracting and processing ClickUp tasks."""

    def __init__(
        self, config: ClickUpConfig, api_client: APIClient, load_gemini_key_func=None
    ) -> None:
        """
        Initialize the task extractor.

        Args:
            config: Configuration settings
            api_client: ClickUp API client instance
            load_gemini_key_func: Optional function to load Gemini API key
        """
        self.config = config
        self.api = api_client
        self.load_gemini_key_func = load_gemini_key_func
        self._progress_context: Progress | None = None
        self._pause_progress_callback: callable | None = None

    def run(self) -> None:
        """
        Main execution method for the task extraction process.

        This method orchestrates the entire task extraction workflow:
        1. Fetches workspaces and spaces from ClickUp API
        2. Retrieves task lists and processes tasks
        3. Applies filtering and custom field mapping
        4. Handles interactive selection if enabled
        5. Exports results to specified format(s)

        Raises:
            AuthenticationError: If API authentication fails
            ShardRoutingError: If API encounters shard routing issues
            APIError: If API requests fail
            SystemExit: On critical errors that prevent execution
        """
        try:
            self._fetch_and_process_tasks()
        except AuthenticationError as e:
            console.print(
                Panel(
                    f"[red]🔐 Authentication Failed[/red]\n"
                    f"[bold red]{str(e)}[/bold red]\n\n"
                    f"[dim]Please check your ClickUp API key and try again.[/dim]",
                    title="❌ Authentication Error",
                    style="red",
                )
            )
            sys.exit(1)
        except ShardRoutingError as e:
            console.print(
                Panel(
                    f"[red]🔀 Shard Routing Error[/red]\n[yellow]{str(e)}[/yellow]",
                    title="❌ Workspace Access Error",
                    style="red",
                    padding=(1, 2),
                )
            )
            sys.exit(1)
        except APIError as e:
            console.print(
                Panel(
                    f"[red]🌐 API Error Occurred[/red]\n"
                    f"[bold red]{str(e)}[/bold red]\n\n"
                    f"[dim]Check your internet connection and API key permissions.[/dim]",
                    title="❌ API Error",
                    style="red",
                )
            )
            sys.exit(1)
        except Exception as e:
            console.print(
                Panel(
                    f"[red]💥 Unexpected error occurred:[/red]\n"
                    f"[bold red]{str(e)}[/bold red]\n\n"
                    f"[dim]Check the traceback below for detailed information.[/dim]",
                    title="❌ Critical Error",
                    style="red",
                )
            )
            import traceback

            console.print("[dim]" + traceback.format_exc() + "[/dim]")
            sys.exit(1)

    def _fetch_and_process_tasks(self) -> None:
        """Internal method to handle the main task processing workflow."""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn(
                    "[progress.description]{task.description}",
                    table_column=Column(ratio=1),
                ),
                BarColumn(complete_style="green", finished_style="bold green"),
                TaskProgressColumn(
                    text_format="[progress.percentage]{task.percentage:>3.0f}%"
                ),
                console=console,
                transient=True,
                expand=True,
            ) as progress:
                # Store progress context for use in callbacks (e.g., during AI summary rate limit waits)
                self._progress_context = progress

                # Create a pause/resume callback for rate limit waits
                # This is used by get_ai_summary to hide progress bars during rate limit waits
                def pause_progress_for_rate_limit() -> None:
                    """Pause progress display to avoid visual conflicts during rate limit waits."""
                    if self._progress_context:
                        # Stop updating the progress display during rate limit wait
                        self._progress_context.stop()

                self._pause_progress_callback = pause_progress_for_rate_limit

                # Fetch workspaces
                task = progress.add_task("🏢 Fetching workspaces...", total=None)

                # Since /team endpoint fails with SHARD_006 for this account,
                # we'll use a direct workspace/team ID if provided, or prompt user
                team_id = None
                team = None  # Initialize team variable
                # Try /team endpoint as primary method
                try:
                    teams = self.api.get("/team")["teams"]
                    team = next(
                        (t for t in teams if t["name"] == self.config.workspace_name),
                        None,
                    )
                    if team:
                        team_id = team["id"]
                except (ShardRoutingError, KeyError, StopIteration):
                    # If /team fails, fall back to config/environment
                    team_id = os.environ.get("CLICKUP_TEAM_ID") or self.config.team_id

                # If still no team_id, prompt user
                if not team_id:
                    console.print(
                        "[yellow]⚠️  The /team endpoint is not accessible for this account, and no team ID was found in config or environment.[/yellow]"
                    )
                    console.print("[dim]To find your Team/Workspace ID:[/dim]")
                    console.print("[dim]  1. Go to https://app.clickup.com[/dim]")
                    console.print("[dim]  2. Click on Workspace settings[/dim]")
                    console.print(
                        "[dim]  3. Look for 'Team ID' or 'Workspace ID' in the URL or settings[/dim]"
                    )
                    team_id = console.input(
                        "[bold cyan]Please enter your Team/Workspace ID: [/bold cyan]"
                    )
                    if not team_id:
                        console.print("[red]Team ID is required[/red]")
                        return

                # If team wasn't fetched from /team endpoint, create a minimal team object with workspace name
                if team is None:
                    team = {"name": self.config.workspace_name, "id": team_id}

                console.print(
                    f"✅ [green]Using workspace/team ID:[/green] [bold]{team_id}[/bold]"
                )
                progress.remove_task(task)

                # Fetch spaces
                task = progress.add_task("🌌 Fetching spaces...", total=None)
                spaces = self.api.get(f"/team/{team_id}/space")["spaces"]
                space = next(
                    (s for s in spaces if s["name"] == self.config.space_name), None
                )
                if not space:
                    console.print(
                        Panel(
                            f"[red]Space '{self.config.space_name}' not found.[/red]\n"
                            f"[dim]Available spaces: {', '.join([s['name'] for s in spaces[:3]])}{'...' if len(spaces) > 3 else ''}[/dim]",
                            title="❌ Space Error",
                            style="red",
                        )
                    )
                    return
                console.print(
                    f"✅ [green]Space found:[/green] [bold]{space['name']}[/bold]"
                )
                progress.remove_task(task)

                # Fetch lists
                task = progress.add_task("📋 Fetching lists...", total=None)
                lists = []
                folder_resp = self.api.get(f"/space/{space['id']}/folder")
                if not folder_resp or not isinstance(folder_resp, dict):
                    console.print(
                        f"[yellow]⚠️  Unexpected folder API response: {folder_resp}[/yellow]"
                    )
                    folders = []
                else:
                    folders = folder_resp.get("folders", [])

                for folder in folders:
                    folder_lists = self.api.get(f"/folder/{folder['id']}/list")["lists"]
                    lists.extend(folder_lists)
                space_lists = self.api.get(f"/space/{space['id']}/list?archived=false")[
                    "lists"
                ]
                lists.extend(space_lists)
                progress.remove_task(task)

                console.print(
                    Panel(
                        f"[bold green]📋 Found {len(lists)} lists to process[/bold green]\n"
                        f"[dim]Workspace: {team['name']} → Space: {space['name']}[/dim]",
                        title="📊 Discovery Summary",
                        style="green",
                    )
                )

                # Process tasks from all lists
                all_tasks = []
                custom_fields_cache = {}

                # Create dual progress bars: overall list progress (percentage) and per-list task progress (bar)
                overall_task = progress.add_task(
                    "📊 Overall Progress", total=len(lists)
                )
                current_list_task = None

                for list_index, list_item in enumerate(lists):
                    # Remove previous list task if it exists
                    if current_list_task is not None:
                        progress.remove_task(current_list_task)

                    tasks_resp = self.api.get(
                        f"/list/{list_item['id']}/task?archived={str(self.config.include_completed).lower()}"
                    )
                    tasks = tasks_resp.get("tasks", [])

                    # Apply filtering using list comprehensions for better performance
                    if not self.config.include_completed:
                        tasks = [
                            t
                            for t in tasks
                            if not t.get("archived")
                            and t.get("status", {}).get("status", "") != "closed"
                        ]

                    if self.config.exclude_statuses:
                        # Create lowercase versions of exclude_statuses for case-insensitive comparison
                        exclude_statuses_lower = [
                            status.lower() for status in self.config.exclude_statuses
                        ]
                        tasks = [
                            t
                            for t in tasks
                            if t.get("status", {}).get("status", "").lower()
                            not in exclude_statuses_lower
                        ]

                    start_date, end_date = get_date_range(self.config.date_filter)
                    if start_date and end_date:
                        tasks = [
                            t
                            for t in tasks
                            if start_date
                            <= datetime.fromtimestamp(int(t["date_created"]) / 1000)
                            <= end_date
                        ]

                    console.print(
                        f"  ✅ Found [bold cyan]{len(tasks)}[/bold cyan] tasks in list '[bold]{list_item['name']}[/bold]'"
                    )

                    # Create per-list task progress bar (resets for each list)
                    current_list_task = progress.add_task(
                        f"📝 Processing: [bold]{list_item['name']}[/bold]",
                        total=len(tasks) if tasks else 1,
                    )

                    # Custom fields
                    if list_item["id"] not in custom_fields_cache:
                        list_details = self.api.get(f"/list/{list_item['id']}")
                        list_custom_fields = list_details.get("custom_fields", [])
                        custom_fields_cache[list_item["id"]] = list_custom_fields
                    list_custom_fields = custom_fields_cache[list_item["id"]]

                    # Process tasks with progress feedback
                    task_records = []
                    if tasks:
                        for task_index, task in enumerate(tasks):
                            name = task.get("name", "Unknown Task")
                            task_name = name[:30] + ("..." if len(name) > 30 else "")

                            # Update per-list progress description with current task
                            if (
                                self.config.enable_ai_summary
                                and self.config.gemini_api_key
                            ):
                                progress.update(
                                    current_list_task,
                                    description=f"📝 Processing: [bold]{list_item['name']}[/bold] - 🤖 AI: {task_name}",
                                )
                            else:
                                progress.update(
                                    current_list_task,
                                    description=f"📝 Processing: [bold]{list_item['name']}[/bold] - {task_name}",
                                )

                            record = self._process_task(
                                task, list_custom_fields, list_item
                            )
                            if record is not None:
                                task_records.append(record)

                            # Advance per-list task progress
                            progress.advance(current_list_task)
                    else:
                        # Handle empty list case - complete the progress bar
                        progress.update(
                            current_list_task,
                            description=f"📝 Processing: [bold]{list_item['name']}[/bold] - (no tasks)",
                        )
                        progress.advance(current_list_task)

                    all_tasks.extend(task_records)

                    # Advance overall progress after completing a list
                    progress.advance(overall_task)

                # Clean up final list task
                if current_list_task is not None:
                    progress.remove_task(current_list_task)
                progress.remove_task(overall_task)

            # Create beautiful summary table
            stats_table = Table(
                title="📈 Processing Statistics",
                show_header=True,
                header_style="bold blue",
            )
            stats_table.add_column("Metric", style="cyan", no_wrap=True)
            stats_table.add_column("Count", justify="right", style="green")

            stats_table.add_row("Lists Processed", str(len(lists)))
            stats_table.add_row("Total Tasks Found", str(len(all_tasks)))
            if self.config.include_completed:
                stats_table.add_row(
                    "Filter", "[yellow]Including completed tasks[/yellow]"
                )
            else:
                stats_table.add_row("Filter", "[blue]Open tasks only[/blue]")

            console.print(stats_table)

            # Handle AI summary if enabled
            if (
                self.config.enable_ai_summary
                and not self.config.gemini_api_key
                and self.load_gemini_key_func
            ):
                # Load Gemini API key if not already set
                self.config.gemini_api_key = self.load_gemini_key_func()

            # Interactive selection
            if self.config.interactive_selection and all_tasks:
                console.print(
                    Panel(
                        f"[bold blue]🔍 Interactive Mode Enabled[/bold blue]\n"
                        f"You will now review each of the [bold cyan]{len(all_tasks)}[/bold cyan] tasks found.\n"
                        f"Choose which tasks to include in your export.",
                        title="Interactive Selection",
                        style="blue",
                    )
                )
                all_tasks = self.interactive_include(all_tasks)

                # After task selection in interactive mode, ask about AI summary if not already set
                if all_tasks and not self.config.enable_ai_summary:
                    console.print(
                        Panel(
                            f"[bold blue]🤖 AI Summary Available[/bold blue]\n"
                            f"You have selected [bold cyan]{len(all_tasks)}[/bold cyan] task(s) for export.\n"
                            f"AI summary can generate concise 1-2 sentence summaries using Google Gemini.",
                            title="AI Enhancement",
                            style="blue",
                        )
                    )
                    if get_yes_no_input(
                        "Would you like to enable AI summaries for the selected tasks? (y/n): ",
                        default_on_interrupt=False,
                    ):
                        # Try to load Gemini API key
                        gemini_key_loaded = False
                        if self.load_gemini_key_func:
                            if self.load_gemini_key_func():
                                gemini_key_loaded = True
                                console.print(
                                    "✅ [green]Gemini API key loaded from 1Password.[/green]"
                                )

                        if not gemini_key_loaded:
                            gemini_key = console.input(
                                "[bold cyan]🔑 Enter Gemini API Key (or press Enter to skip): [/bold cyan]"
                            ).strip()
                            if gemini_key:
                                self.config.gemini_api_key = gemini_key
                                gemini_key_loaded = True
                                console.print(
                                    "✅ [green]Manual Gemini API key entered.[/green]"
                                )
                            else:
                                console.print(
                                    "ℹ️ [yellow]Proceeding without AI summary.[/yellow]"
                                )

                        if gemini_key_loaded and self.config.gemini_api_key:
                            self.config.enable_ai_summary = True
                            # Regenerate notes with AI for selected tasks
                            console.print(
                                Panel(
                                    f"[bold green]🧠 Generating AI summaries for {len(all_tasks)} selected tasks...[/bold green]",
                                    title="AI Processing",
                                    style="green",
                                )
                            )
                            for i, task in enumerate(all_tasks, 1):
                                console.print(
                                    f"  [dim]Processing task {i}/{len(all_tasks)}:[/dim] [bold]{task.Task}[/bold]"
                                )
                                if hasattr(task, "_metadata") and task._metadata:
                                    metadata = task._metadata
                                    raw_fields = metadata.get("ai_fields")
                                    task_name = metadata.get("task_name", task.Task)
                                    if raw_fields:
                                        if isinstance(raw_fields, dict):
                                            ai_fields = list(raw_fields.items())
                                        else:
                                            ai_fields = list(raw_fields)
                                        ai_notes = get_ai_summary(
                                            task_name,
                                            ai_fields,
                                            self.config.gemini_api_key,
                                            progress_pause_callback=self._pause_progress_callback,
                                        )
                                    else:
                                        fallback_fields = [
                                            ("Notes", task.Notes or "(not provided)")
                                        ]
                                        ai_notes = get_ai_summary(
                                            task_name,
                                            fallback_fields,
                                            self.config.gemini_api_key,
                                            progress_pause_callback=self._pause_progress_callback,
                                        )
                                    task.Notes = ai_notes
                            console.print(
                                "✅ [bold green]AI summaries generated for all selected tasks.[/bold green]"
                            )
                    else:
                        console.print(
                            "ℹ️ [yellow]Proceeding without AI summary.[/yellow]"
                        )

            elif self.config.interactive_selection and not all_tasks:
                console.print(
                    Panel(
                        "[yellow]⚠️ Interactive mode enabled but no tasks found to select from.[/yellow]",
                        title="No Tasks Found",
                        style="yellow",
                    )
                )
            # Export
            self.export(all_tasks)
        except Exception as e:
            console.print(
                Panel(
                    f"[red]💥 Fatal error occurred:[/red]\n"
                    f"[bold red]{str(e)}[/bold red]\n\n"
                    f"[dim]Check the traceback below for detailed information.[/dim]",
                    title="❌ Critical Error",
                    style="red",
                )
            )
            import traceback

            console.print("[dim]" + traceback.format_exc() + "[/dim]")
            raise  # Re-raise to be caught by the outer try-catch

    def _process_task(self, task, list_custom_fields, list_item) -> TaskRecord | None:
        """
        Process a single task into a TaskRecord.

        Args:
            task: Raw task data from ClickUp API
            list_custom_fields: Custom fields definition for the list
            list_item: The list object containing name and other metadata

        Returns:
            TaskRecord instance or None if task should be skipped
        """
        try:
            # Fetch detailed task information (like original code)
            try:
                task_detail = self.api.get(f"/task/{task['id']}")
                if not task_detail or not isinstance(task_detail, dict):
                    console.print(
                        f"    [yellow]⚠️ Unexpected task detail for task {task.get('id')}: {task_detail}[/yellow]"
                    )
                    return None
            except Exception as e:
                console.print(f"    [red]❌ Error fetching task {task}: {e}[/red]")
                return None

            task_name = task_detail.get("name", "Unnamed Task")

            # Handle task priority (from detailed task data)
            priority_obj = task_detail.get("priority")
            if isinstance(priority_obj, dict):
                priority_val = priority_obj.get("priority")
                if isinstance(priority_val, int):
                    priority_map = {1: "Low", 2: "Normal", 3: "High", 4: "Urgent"}
                    priority = priority_map.get(priority_val, "Normal")
                else:
                    priority = str(priority_val) if priority_val else "Normal"
            else:
                priority = "Normal"

            # Get task status
            status = task_detail.get("status", {}).get("status", "Unknown")

            # Get due date or calculate ETA
            due_date = task_detail.get("due_date")
            eta = ""
            if due_date:
                try:
                    due_dt = datetime.fromtimestamp(int(due_date) / 1000, tz=timezone.utc)
                    eta = format_datetime(due_dt, DISPLAY_FORMAT)
                except (ValueError, OSError):
                    eta = "Invalid Date"
            else:
                # No due date - we'll calculate ETA after gathering all context
                # This will be done later after extracting custom fields
                eta = None  # Marker to calculate later

            # Company is the list name (like original code)
            company = list_item.get("name", "")

            # Initialize other custom field values
            branch_value = ""
            subject = ""
            custom_description = ""
            default_description = task_detail.get("description", "") or ""
            resolution = ""
            notes_parts: list[str] = []

            # Process custom fields from detailed task data
            task_custom_fields = task_detail.get("custom_fields", [])
            cf = {f["name"]: f for f in task_custom_fields}

            # Handle Branch field (like original)
            branch_field = cf.get("Branch")
            if branch_field:
                val = branch_field.get("value")
                type_config = branch_field.get("type_config", {})
                options = type_config.get("options", [])
                branch_value = LocationMapper.map_location(val, type_config, options)

            def extract_field_value(field: dict | None) -> str:
                if not field:
                    return ""
                value = field.get("value")
                if value is None:
                    return ""
                if isinstance(value, str):
                    return value
                if isinstance(value, list):
                    items: list[str] = []
                    for item in value:
                        if item is None:
                            continue
                        if isinstance(item, dict):
                            if "value" in item and item["value"] not in (None, ""):
                                items.append(str(item["value"]))
                            elif "name" in item and item["name"] not in (None, ""):
                                items.append(str(item["name"]))
                            else:
                                items.append(str(item))
                        else:
                            items.append(str(item))
                    return ", ".join(items)
                if isinstance(value, dict):
                    if "value" in value and value["value"] not in (None, ""):
                        nested_value = value["value"]
                        if isinstance(nested_value, list):
                            nested_items = [
                                str(v) for v in nested_value if v not in (None, "")
                            ]
                            return ", ".join(nested_items)
                        return str(nested_value)
                    if "text" in value and value["text"] not in (None, ""):
                        return str(value["text"])
                return str(value)

            # Build base values for key custom fields
            subject_value = extract_field_value(cf.get("Subject"))
            if subject_value:
                subject = subject_value
                notes_parts.append(f"Subject: {subject}")

            description_value = extract_field_value(cf.get("Description"))
            if description_value:
                custom_description = description_value
                notes_parts.append(f"Description: {custom_description}")

            resolution_value = extract_field_value(cf.get("Resolution"))
            if resolution_value:
                resolution = resolution_value
                notes_parts.append(f"Resolution: {resolution}")

            if not custom_description and default_description:
                notes_parts.append(f"Task Description: {default_description}")

            # Prepare AI field collection with placeholders
            def with_placeholder(raw: str | None) -> str:
                if raw is None:
                    return "(not provided)"
                cleaned = raw.strip() if isinstance(raw, str) else str(raw)
                return cleaned if cleaned else "(not provided)"

            ai_field_items: list[tuple[str, str]] = []

            def add_ai_field(label: str, raw_value: str | None) -> None:
                ai_field_items.append((label, with_placeholder(raw_value)))

            custom_name = extract_field_value(cf.get("Name"))
            add_ai_field("Name", custom_name)
            add_ai_field("Branch", branch_value)
            add_ai_field("Phone #", extract_field_value(cf.get("Phone #")))
            add_ai_field("Computer #", extract_field_value(cf.get("Computer #")))
            add_ai_field("Subject", subject_value)
            add_ai_field("Description", custom_description)
            add_ai_field("Resolution", resolution_value)
            add_ai_field(
                "Last time tracked", extract_field_value(cf.get("Last time tracked"))
            )
            add_ai_field("Vendor", extract_field_value(cf.get("Vendor")))
            add_ai_field(
                "Serial Number(s)", extract_field_value(cf.get("Serial Number(s)"))
            )
            add_ai_field("Tracking #", extract_field_value(cf.get("Tracking #")))
            add_ai_field("RMA Number", extract_field_value(cf.get("RMA Number")))
            add_ai_field("Task Description", default_description)

            # Generate AI summary or use original notes
            # Skip AI generation during initial processing if interactive mode is enabled
            # AI summaries will be generated after user selection in interactive mode
            if (
                self.config.enable_ai_summary
                and self.config.gemini_api_key
                and not self.config.interactive_selection
            ):
                from ai_summary import get_ai_summary

                notes = get_ai_summary(
                    task_detail.get("name", ""),
                    ai_field_items,
                    self.config.gemini_api_key,
                    progress_pause_callback=self._pause_progress_callback,
                )
            else:
                notes = "\n".join(notes_parts)

            # Extract images (like original)
            desc_img = extract_images(cf.get("Description", {}).get("value", ""))
            res_img = extract_images(cf.get("Resolution", {}).get("value", ""))
            task_img = extract_images(task_detail.get("description", ""))
            extra = " | ".join([i for i in [desc_img, res_img, task_img] if i])

            # Calculate ETA if not already set from due_date
            if eta is None:
                # Calculate ETA based on task context
                eta = calculate_eta(
                    task_name=task_name,
                    priority=priority,
                    status=status,
                    description=custom_description or default_description,
                    subject=subject_value if subject_value else "",
                    resolution=resolution_value if resolution_value else "",
                    gemini_api_key=self.config.gemini_api_key,
                    enable_ai=self.config.enable_ai_summary,
                )

            # Create task record (matching original structure)
            task_record = TaskRecord(
                Task=task_name,
                Company=company,
                Branch=branch_value,
                Priority=priority,
                Status=status,
                ETA=eta,
                Notes=notes,
                Extra=extra,
            )

            # Store metadata for potential AI processing
            task_record._metadata = {
                "task_name": task_name,
                "ai_fields": tuple(ai_field_items),
            }

            return task_record

        except Exception as e:
            print(f"Error processing task '{task.get('name', 'Unknown')}': {e}")
            import traceback

            traceback.print_exc()
            return None

    def interactive_include(self, tasks: TaskList) -> TaskList:
        """
        Allow user to interactively select which tasks to export.

        Args:
            tasks: List of TaskRecord objects

        Returns:
            List of selected TaskRecord objects
        """
        console.print(
            Panel(
                "[bold blue]INTERACTIVE TASK SELECTION[/bold blue]\n"
                "Please select which tasks you would like to export:",
                title="🔍 Task Selection",
                style="blue",
            )
        )

        selected_tasks = []

        for i, task in enumerate(tasks, 1):
            # Create a rich table for task details
            task_table = Table(show_header=False, box=None, padding=(0, 1))
            task_table.add_column("Field", style="bold cyan", width=12)
            task_table.add_column("Value", style="white")

            task_table.add_row("Name:", f"[bold]{task.Task}[/bold]")
            task_table.add_row("Company:", task.Company)
            task_table.add_row("Branch:", task.Branch)
            task_table.add_row("Status:", f"[yellow]{task.Status}[/yellow]")
            task_table.add_row(
                "Priority:", task.Priority if task.Priority else "[dim]None[/dim]"
            )

            if task.Notes:
                # Show first 150 characters of notes
                notes_preview = (
                    task.Notes[:150] + "..." if len(task.Notes) > 150 else task.Notes
                )
                task_table.add_row("Notes:", f"[dim]{notes_preview}[/dim]")
            else:
                task_table.add_row("Notes:", "[dim]None[/dim]")

            # Display task in a panel
            console.print(
                Panel(task_table, title=f"Task {i}/{len(tasks)}", style="white")
            )

            # Prompt for user input with validation
            if get_yes_no_input(
                f"Would you like to export task '{task.Task}'? (y/n): ",
                default_on_interrupt=False,
            ):
                selected_tasks.append(task)
                console.print("  ✅ [green]Added to export list[/green]")
            else:
                console.print("  ❌ [red]Skipped[/red]")

            console.print()  # Add spacing

        # Display summary
        if selected_tasks:
            summary_table = Table(title="✅ Selected Tasks", show_header=False)
            summary_table.add_column("Task", style="green")

            for task in selected_tasks:
                summary_table.add_row(f"• {task.Task}")

            console.print(summary_table)
        else:
            console.print("[yellow]⚠️  No tasks selected for export.[/yellow]")

        console.print(
            f"\n[bold]📊 Summary:[/bold] [green]{len(selected_tasks)}[/green] task(s) selected out of [blue]{len(tasks)}[/blue] total"
        )

        return selected_tasks

    def export(self, tasks: TaskList) -> None:
        """
        Export tasks to CSV, HTML, Markdown, and/or PDF format.

        Args:
            tasks: List of TaskRecord objects to export
        """
        if not tasks:
            console.print("[yellow]⚠️  No tasks found to export.[/yellow]")
            return

        # Sort tasks by priority (Urgent → High → Normal → Low) and then alphabetically by name
        tasks = sort_tasks_by_priority_and_name(tasks)

        console.print(f"\n[bold blue]📤 Exporting {len(tasks)} tasks...[/bold blue]")

        # Ensure all output files go to clickup_task_extractor/output directory
        # Extract the base filename without extension from the config path
        output_path = Path(self.config.output_path)
        base_filename = output_path.stem  # Get filename without extension
        output_dir = Path(script_dir) / "output"  # clickup_task_extractor/output

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # CSV Export
            if self.config.output_format in (OutputFormat.CSV, OutputFormat.BOTH):
                csv_task = progress.add_task("💾 Generating CSV...", total=None)
                export_fields = get_export_fields()
                csv_path = output_dir / f"{base_filename}.csv"

                with export_file(str(csv_path), "w") as f:
                    writer = csv.DictWriter(f, fieldnames=export_fields)
                    writer.writeheader()
                    for t in tasks:
                        # Get only the export fields, excluding internal fields like _metadata
                        row_data = {
                            field: getattr(t, field, "") for field in export_fields
                        }
                        writer.writerow(row_data)

                progress.remove_task(csv_task)
                console.print(
                    f"✅ [green]CSV exported:[/green] [bold]{csv_path}[/bold]"
                )

            # HTML Export
            if self.config.output_format in (OutputFormat.HTML, OutputFormat.BOTH):
                html_task = progress.add_task("🌐 Generating HTML...", total=None)
                html_path = output_dir / f"{base_filename}.html"

                with export_file(str(html_path), "w") as f:
                    f.write(self.render_html(tasks))

                progress.remove_task(html_task)
                console.print(
                    f"✅ [green]HTML exported:[/green] [bold]{html_path}[/bold]"
                )

            # Markdown Export
            if self.config.output_format == OutputFormat.MARKDOWN:
                markdown_task = progress.add_task(
                    "📝 Generating Markdown...", total=None
                )
                markdown_path = output_dir / f"{base_filename}.md"

                with export_file(str(markdown_path), "w") as f:
                    f.write(self.render_markdown(tasks))

                progress.remove_task(markdown_task)
                console.print(
                    f"✅ [green]Markdown exported:[/green] [bold]{markdown_path}[/bold]"
                )

            # PDF Export
            if self.config.output_format == OutputFormat.PDF:
                pdf_task = progress.add_task("📄 Generating PDF...", total=None)
                pdf_path = output_dir / f"{base_filename}.pdf"

                try:
                    # Import fpdf2 for pure-Python PDF generation
                    from fpdf import FPDF

                    # Ensure output directory exists
                    pdf_path.parent.mkdir(parents=True, exist_ok=True)

                    # Generate HTML first, then convert to PDF using fpdf2
                    html_content = self.render_html(tasks)

                    # Create PDF and parse HTML
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.write_html(html_content)
                    pdf.output(str(pdf_path))

                    progress.remove_task(pdf_task)
                    console.print(
                        f"✅ [green]PDF exported:[/green] [bold]{pdf_path}[/bold]"
                    )

                except ImportError:
                    progress.remove_task(pdf_task)
                    console.print(
                        f"[red]❌ Error: fpdf2 not installed. Install with: pip install fpdf2[/red]"
                    )
                    console.print(f"[yellow]⚠️  PDF export skipped.[/yellow]")
                except Exception as e:
                    progress.remove_task(pdf_task)
                    console.print(f"[red]❌ Error generating PDF: {e}[/red]")
                    console.print(f"[yellow]⚠️  PDF export failed. Please check the HTML output format works correctly.[/yellow]")

        # Final success message
        console.print(
            Panel(
                f"[bold green]🎉 Export completed successfully![/bold green]\n"
                f"📊 Exported [bold cyan]{len(tasks)}[/bold cyan] tasks\n"
                f"📁 Format: [yellow]{self.config.output_format.value}[/yellow]",
                title="Export Complete",
                style="green",
            )
        )

    def render_html(self, tasks: TaskList) -> str:
        """
        Render tasks as styled HTML table.

        Args:
            tasks: List of TaskRecord objects

        Returns:
            Complete HTML document as string
        """
        # Simple HTML table, styled with proper structure for fpdf2 compatibility
        head = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>Weekly Task List</title>
<style>
body{font-family:Arial,sans-serif;margin:20px;}
table{border-collapse:collapse;width:100%;margin-top:20px;}
th,td{border:1px solid #ddd;padding:12px;text-align:left;vertical-align:top;}
th{background-color:#f2f2f2;font-weight:bold;}
tr:nth-child(even){background-color:#f9f9f9;}
.task-name{font-weight:bold;color:#2c5aa0;}
.priority-high{color:#d73502;font-weight:bold;}
.priority-normal{color:#0c7b93;}
.priority-low{color:#6aa84f;}
.notes{max-width:400px;white-space:pre-wrap;line-height:1.4;font-size:0.9em;}
.status{padding:4px 8px;border-radius:4px;font-size:0.8em;font-weight:bold;}
.status-open{background-color:#e8f4fd;color:#1f4e79;}
.status-in-progress{background-color:#fff2cc;color:#7f6000;}
.status-review{background-color:#f4cccc;color:#660000;}
h1{color:#2c5aa0;}
.summary{margin-bottom:20px;padding:15px;background-color:#f0f8ff;border-left:4px solid #2c5aa0;}
</style>
</head>
<body>
"""
        summary = f'<h1>Weekly Task List</h1><div class="summary"><strong>Generated:</strong> {format_datetime(datetime.now(), DISPLAY_FORMAT)}<br><strong>Total Tasks:</strong> {len(tasks)}<br><strong>Workspace:</strong> {html.escape(self.config.workspace_name)} / {html.escape(self.config.space_name)}</div>'

        # Get export fields (excluding internal fields like _metadata)
        export_fields = get_export_fields()
        table = (
            "<table><thead><tr>"
            + "".join(f"<th>{k}</th>" for k in export_fields)
            + "</tr></thead><tbody>"
        )
        for t in tasks:
            table += (
                "<tr>"
                + "".join(
                    f"<td>{html.escape(str(getattr(t, k) or ''))}</td>"
                    for k in export_fields
                )
                + "</tr>"
            )
        table += "</tbody></table></body></html>"
        return head + summary + table

    def render_markdown(self, tasks: TaskList) -> str:
        """
        Render tasks as Markdown table.

        Args:
            tasks: List of TaskRecord objects

        Returns:
            Markdown formatted document as string
        """
        # Generate header with metadata
        header = f"""# Weekly Task List

**Generated:** {format_datetime(datetime.now(), DISPLAY_FORMAT)}
**Total Tasks:** {len(tasks)}
**Workspace:** {self.config.workspace_name} / {self.config.space_name}

## Tasks

"""

        # Get export fields (excluding internal fields like _metadata)
        export_fields = get_export_fields()

        if not tasks:
            return header + "*No tasks found.*\n"

        # Create markdown table header
        table = "| " + " | ".join(export_fields) + " |\n"
        table += "|" + "|".join([" --- " for _ in export_fields]) + "|\n"

        # Add table rows
        for t in tasks:
            row_values = []
            for field in export_fields:
                value = str(getattr(t, field) or "")
                # Escape pipe characters and convert newlines to markdown line breaks (two trailing spaces)
                value = value.replace("|", "\\|").replace("\n", "  \n")
                row_values.append(value)
            table += "| " + " | ".join(row_values) + " |\n"

        return header + table
