#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main Business Logic Module for ClickUp Task Extractor

Contains:
- ClickUpTaskExtractor class for task processing and export
- Interactive task selection functionality
- CSV and HTML export with styling
"""

import os
import sys
import csv
import html
from datetime import datetime
from dataclasses import asdict
from typing import TypeAlias
from contextlib import contextmanager
from pathlib import Path

import sys

# Rich imports for beautiful console output
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import print as rprint
except ImportError:
    print("Error: The 'rich' library is required but not installed.")
    print("Please install it using: pip install -r requirements.txt")
    print("Or install just rich: pip install rich>=10.0.0")
    sys.exit(1)

# Import project modules
from config import ClickUpConfig, TaskRecord, DISPLAY_FORMAT, format_datetime, OutputFormat
from api_client import APIClient, ClickUpAPIClient, APIError, AuthenticationError
from ai_summary import get_ai_summary
from mappers import get_yes_no_input, get_date_range, extract_images, LocationMapper

# Initialize Rich console
console = Console()

# Type aliases for clarity
TaskList: TypeAlias = list[TaskRecord]


@contextmanager
def export_file(file_path: str, mode: str = 'w', encoding: str = 'utf-8'):
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
        with output_path.open(mode, newline='', encoding=encoding) as f:
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
    return [field for field in TaskRecord.__annotations__.keys() if not field.startswith('_')]


class ClickUpTaskExtractor:
    """Main orchestrator class for extracting and processing ClickUp tasks."""

    def __init__(self, config: ClickUpConfig, api_client: APIClient, load_gemini_key_func=None) -> None:
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
            APIError: If API requests fail
            SystemExit: On critical errors that prevent execution
        """
        try:
            self._fetch_and_process_tasks()
        except AuthenticationError as e:
            console.print(Panel(
                f"[red]🔐 Authentication Failed[/red]\n"
                f"[bold red]{str(e)}[/bold red]\n\n"
                f"[dim]Please check your ClickUp API key and try again.[/dim]",
                title="❌ Authentication Error",
                style="red"
            ))
            sys.exit(1)
        except APIError as e:
            console.print(Panel(
                f"[red]🌐 API Error Occurred[/red]\n"
                f"[bold red]{str(e)}[/bold red]\n\n"
                f"[dim]Check your internet connection and API key permissions.[/dim]",
                title="❌ API Error",
                style="red"
            ))
            sys.exit(1)
        except Exception as e:
            console.print(Panel(
                f"[red]💥 Unexpected error occurred:[/red]\n"
                f"[bold red]{str(e)}[/bold red]\n\n"
                f"[dim]Check the traceback below for detailed information.[/dim]",
                title="❌ Critical Error",
                style="red"
            ))
            import traceback
            console.print("[dim]" + traceback.format_exc() + "[/dim]")
            sys.exit(1)

    def _fetch_and_process_tasks(self) -> None:
        """Internal method to handle the main task processing workflow."""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(complete_style="green", finished_style="bold green"),
                TaskProgressColumn(),
                console=console,
                transient=True
            ) as progress:

                # Fetch workspaces
                task = progress.add_task("🏢 Fetching workspaces...", total=None)
                teams = self.api.get('/team')['teams']
                team = next((t for t in teams if t['name'] == self.config.workspace_name), None)
                if not team:
                    console.print(Panel(
                        f"[red]Workspace '{self.config.workspace_name}' not found.[/red]\n"
                        f"[dim]Available workspaces: {', '.join([t['name'] for t in teams[:3]])}{'...' if len(teams) > 3 else ''}[/dim]",
                        title="❌ Workspace Error",
                        style="red"
                    ))
                    return
                console.print(f"✅ [green]Workspace found:[/green] [bold]{team['name']}[/bold]")
                progress.remove_task(task)

                # Fetch spaces
                task = progress.add_task("🌌 Fetching spaces...", total=None)
                spaces = self.api.get(f"/team/{team['id']}/space")['spaces']
                space = next((s for s in spaces if s['name'] == self.config.space_name), None)
                if not space:
                    console.print(Panel(
                        f"[red]Space '{self.config.space_name}' not found.[/red]\n"
                        f"[dim]Available spaces: {', '.join([s['name'] for s in spaces[:3]])}{'...' if len(spaces) > 3 else ''}[/dim]",
                        title="❌ Space Error",
                        style="red"
                    ))
                    return
                console.print(f"✅ [green]Space found:[/green] [bold]{space['name']}[/bold]")
                progress.remove_task(task)

                # Fetch lists
                task = progress.add_task("📋 Fetching lists...", total=None)
                lists = []
                folder_resp = self.api.get(f"/space/{space['id']}/folder")
                if not folder_resp or not isinstance(folder_resp, dict):
                    console.print(f"[yellow]⚠️  Unexpected folder API response: {folder_resp}[/yellow]")
                    folders = []
                else:
                    folders = folder_resp.get('folders', [])

                for folder in folders:
                    folder_lists = self.api.get(f"/folder/{folder['id']}/list")['lists']
                    lists.extend(folder_lists)
                space_lists = self.api.get(f"/space/{space['id']}/list?archived=false")['lists']
                lists.extend(space_lists)
                progress.remove_task(task)

                console.print(Panel(
                    f"[bold green]📋 Found {len(lists)} lists to process[/bold green]\n"
                    f"[dim]Workspace: {team['name']} → Space: {space['name']}[/dim]",
                    title="📊 Discovery Summary",
                    style="green"
                ))

                # Process tasks from all lists
                all_tasks = []
                custom_fields_cache = {}

                # Create progress bar for lists
                list_task = progress.add_task("📝 Processing tasks from lists...", total=len(lists))

                for list_item in lists:
                    progress.update(list_task, description=f"📝 Processing: [bold]{list_item['name']}[/bold]")

                    tasks_resp = self.api.get(f"/list/{list_item['id']}/task?archived={str(self.config.include_completed).lower()}")
                    tasks = tasks_resp.get('tasks', [])

                    # Apply filtering using list comprehensions for better performance
                    if not self.config.include_completed:
                        tasks = [
                            t for t in tasks
                            if not t.get('archived') and t.get('status', {}).get('status', '') != 'closed'
                        ]

                    if self.config.exclude_statuses:
                        # Create lowercase versions of exclude_statuses for case-insensitive comparison
                        exclude_statuses_lower = [status.lower() for status in self.config.exclude_statuses]
                        tasks = [
                            t for t in tasks
                            if t.get('status', {}).get('status', '').lower() not in exclude_statuses_lower
                        ]

                    start_date, end_date = get_date_range(self.config.date_filter)
                    if start_date and end_date:
                        tasks = [
                            t for t in tasks
                            if start_date <= datetime.fromtimestamp(int(t['date_created']) / 1000) <= end_date
                        ]

                    console.print(f"  ✅ Found [bold cyan]{len(tasks)}[/bold cyan] tasks in list '[bold]{list_item['name']}[/bold]'")

                    # Custom fields
                    if list_item['id'] not in custom_fields_cache:
                        list_details = self.api.get(f"/list/{list_item['id']}")
                        list_custom_fields = list_details.get('custom_fields', [])
                        custom_fields_cache[list_item['id']] = list_custom_fields
                    list_custom_fields = custom_fields_cache[list_item['id']]

                    # Process tasks using list comprehension and filter out None values
                    task_records = [
                        self._process_task(task, list_custom_fields, list_item)
                        for task in tasks
                    ]
                    all_tasks.extend(record for record in task_records if record is not None)

                    progress.advance(list_task)

                progress.remove_task(list_task)

            # Create beautiful summary table
            stats_table = Table(title="📈 Processing Statistics", show_header=True, header_style="bold blue")
            stats_table.add_column("Metric", style="cyan", no_wrap=True)
            stats_table.add_column("Count", justify="right", style="green")

            stats_table.add_row("Lists Processed", str(len(lists)))
            stats_table.add_row("Total Tasks Found", str(len(all_tasks)))
            if self.config.include_completed:
                stats_table.add_row("Filter", "[yellow]Including completed tasks[/yellow]")
            else:
                stats_table.add_row("Filter", "[blue]Open tasks only[/blue]")

            console.print(stats_table)

            # Handle AI summary if enabled
            if self.config.enable_ai_summary and not self.config.gemini_api_key and self.load_gemini_key_func:
                # Load Gemini API key if not already set
                self.config.gemini_api_key = self.load_gemini_key_func()

            # Interactive selection
            if self.config.interactive_selection and all_tasks:
                console.print(Panel(
                    f"[bold blue]🔍 Interactive Mode Enabled[/bold blue]\n"
                    f"You will now review each of the [bold cyan]{len(all_tasks)}[/bold cyan] tasks found.\n"
                    f"Choose which tasks to include in your export.",
                    title="Interactive Selection",
                    style="blue"
                ))
                all_tasks = self.interactive_include(all_tasks)

                # After task selection in interactive mode, ask about AI summary if not already set
                if all_tasks and not self.config.enable_ai_summary:
                    console.print(Panel(
                        f"[bold blue]🤖 AI Summary Available[/bold blue]\n"
                        f"You have selected [bold cyan]{len(all_tasks)}[/bold cyan] task(s) for export.\n"
                        f"AI summary can generate concise 1-2 sentence summaries using Google Gemini.",
                        title="AI Enhancement",
                        style="blue"
                    ))
                    if get_yes_no_input('Would you like to enable AI summaries for the selected tasks? (y/n): ', default_on_interrupt=False):
                        # Try to load Gemini API key
                        gemini_key_loaded = False
                        if self.load_gemini_key_func:
                            if self.load_gemini_key_func():
                                gemini_key_loaded = True
                                console.print("✅ [green]Gemini API key loaded from 1Password.[/green]")

                        if not gemini_key_loaded:
                            gemini_key = console.input('[bold cyan]🔑 Enter Gemini API Key (or press Enter to skip): [/bold cyan]').strip()
                            if gemini_key:
                                self.config.gemini_api_key = gemini_key
                                gemini_key_loaded = True
                                console.print("✅ [green]Manual Gemini API key entered.[/green]")
                            else:
                                console.print("ℹ️ [yellow]Proceeding without AI summary.[/yellow]")

                        if gemini_key_loaded and self.config.gemini_api_key:
                            self.config.enable_ai_summary = True
                            # Regenerate notes with AI for selected tasks
                            console.print(Panel(
                                f"[bold green]🧠 Generating AI summaries for {len(all_tasks)} selected tasks...[/bold green]",
                                title="AI Processing",
                                style="green"
                            ))
                            for i, task in enumerate(all_tasks, 1):
                                console.print(f"  [dim]Processing task {i}/{len(all_tasks)}:[/dim] [bold]{task.Task}[/bold]")
                                if hasattr(task, '_metadata') and task._metadata:
                                    metadata = task._metadata
                                    ai_notes = get_ai_summary(
                                        metadata['task_name'],
                                        metadata['subject'],
                                        metadata['description'],
                                        metadata['resolution'],
                                        self.config.gemini_api_key
                                    )
                                    task.Notes = ai_notes
                            console.print("✅ [bold green]AI summaries generated for all selected tasks.[/bold green]")
                    else:
                        console.print("ℹ️ [yellow]Proceeding without AI summary.[/yellow]")

            elif self.config.interactive_selection and not all_tasks:
                console.print(Panel(
                    "[yellow]⚠️ Interactive mode enabled but no tasks found to select from.[/yellow]",
                    title="No Tasks Found",
                    style="yellow"
                ))
            # Export
            self.export(all_tasks)
        except Exception as e:
            console.print(Panel(
                f"[red]💥 Fatal error occurred:[/red]\n"
                f"[bold red]{str(e)}[/bold red]\n\n"
                f"[dim]Check the traceback below for detailed information.[/dim]",
                title="❌ Critical Error",
                style="red"
            ))
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
                    console.print(f"    [yellow]⚠️ Unexpected task detail for task {task.get('id')}: {task_detail}[/yellow]")
                    return None
            except Exception as e:
                console.print(f"    [red]❌ Error fetching task {task}: {e}[/red]")
                return None

            task_name = task_detail.get('name', 'Unnamed Task')

            # Handle task priority (from detailed task data)
            priority_obj = task_detail.get('priority')
            if isinstance(priority_obj, dict):
                priority_val = priority_obj.get('priority')
                if isinstance(priority_val, int):
                    priority_map = {1: 'Low', 2: 'Normal', 3: 'High', 4: 'Urgent'}
                    priority = priority_map.get(priority_val, 'Normal')
                else:
                    priority = str(priority_val) if priority_val else 'Normal'
            else:
                priority = 'Normal'

            # Get task status
            status = task_detail.get('status', {}).get('status', 'Unknown')

            # Get due date
            due_date = task_detail.get('due_date')
            eta = ''
            if due_date:
                try:
                    due_dt = datetime.fromtimestamp(int(due_date) / 1000)
                    eta = format_datetime(due_dt, DISPLAY_FORMAT)
                except (ValueError, OSError):
                    eta = 'Invalid Date'

            # Company is the list name (like original code)
            company = list_item.get('name', '')

            # Initialize other custom field values
            branch = ''
            subject = ''
            description = task_detail.get('description', '')
            resolution = ''

            # Process custom fields from detailed task data
            task_custom_fields = task_detail.get('custom_fields', [])
            cf = {f['name']: f for f in task_custom_fields}

            # Handle Branch field (like original)
            branch_field = cf.get('Branch')
            if branch_field:
                val = branch_field.get('value')
                type_config = branch_field.get('type_config', {})
                options = type_config.get('options', [])
                branch = LocationMapper.map_location(val, type_config, options)

            # Build notes from custom fields (like original)
            notes_parts = []
            for fname in ['Subject', 'Description', 'Resolution']:
                f = cf.get(fname)
                if f and f.get('value'):
                    if fname == 'Subject':
                        subject = f['value']
                    elif fname == 'Description':
                        description = f['value']
                    elif fname == 'Resolution':
                        resolution = f['value']
                    notes_parts.append(f"{fname}: {f['value']}")

            # Add task description if no custom Description field
            if not cf.get('Description') and task_detail.get('description'):
                task_desc = task_detail['description']
                description = task_desc
                notes_parts.append(f"Task Description: {task_desc}")

            # Generate AI summary or use original notes
            if self.config.enable_ai_summary and self.config.gemini_api_key:
                from ai_summary import get_ai_summary
                notes = get_ai_summary(
                    task_detail.get('name', ''),
                    subject,
                    description,
                    resolution,
                    self.config.gemini_api_key
                )
            else:
                notes = '\n'.join(notes_parts)

            # Extract images (like original)
            desc_img = extract_images(cf.get('Description', {}).get('value', ''))
            res_img = extract_images(cf.get('Resolution', {}).get('value', ''))
            task_img = extract_images(task_detail.get('description', ''))
            extra = ' | '.join([i for i in [desc_img, res_img, task_img] if i])

            # Create task record (matching original structure)
            task_record = TaskRecord(
                Task=task_name,
                Company=company,
                Branch=branch,
                Priority=priority,
                Status=status,
                ETA=eta,
                Notes=notes,
                Extra=extra
            )

            # Store metadata for potential AI processing
            task_record._metadata = {
                'task_name': task_name,
                'subject': subject,
                'description': description,
                'resolution': resolution
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
        console.print(Panel(
            "[bold blue]INTERACTIVE TASK SELECTION[/bold blue]\n"
            "Please select which tasks you would like to export:",
            title="🔍 Task Selection",
            style="blue"
        ))

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
            task_table.add_row("Priority:", task.Priority if task.Priority else "[dim]None[/dim]")

            if task.Notes:
                # Show first 150 characters of notes
                notes_preview = task.Notes[:150] + "..." if len(task.Notes) > 150 else task.Notes
                task_table.add_row("Notes:", f"[dim]{notes_preview}[/dim]")
            else:
                task_table.add_row("Notes:", "[dim]None[/dim]")

            # Display task in a panel
            console.print(Panel(
                task_table,
                title=f"Task {i}/{len(tasks)}",
                style="white"
            ))

            # Prompt for user input with validation
            if get_yes_no_input(f"Would you like to export task '{task.Task}'? (y/n): ", default_on_interrupt=False):
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

        console.print(f"\n[bold]📊 Summary:[/bold] [green]{len(selected_tasks)}[/green] task(s) selected out of [blue]{len(tasks)}[/blue] total")

        return selected_tasks

    def export(self, tasks: TaskList) -> None:
        """
        Export tasks to CSV and/or HTML format.

        Args:
            tasks: List of TaskRecord objects to export
        """
        if not tasks:
            console.print('[yellow]⚠️  No tasks found to export.[/yellow]')
            return

        console.print(f"\n[bold blue]📤 Exporting {len(tasks)} tasks...[/bold blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:

            # CSV Export
            if self.config.output_format in (OutputFormat.CSV, OutputFormat.BOTH):
                csv_task = progress.add_task("💾 Generating CSV...", total=None)
                export_fields = get_export_fields()

                with export_file(self.config.output_path, 'w') as f:
                    writer = csv.DictWriter(f, fieldnames=export_fields)
                    writer.writeheader()
                    for t in tasks:
                        # Get only the export fields, excluding internal fields like _metadata
                        row_data = {field: getattr(t, field, '') for field in export_fields}
                        writer.writerow(row_data)

                progress.remove_task(csv_task)
                console.print(f"✅ [green]CSV exported:[/green] [bold]{self.config.output_path}[/bold]")

            # HTML Export
            if self.config.output_format in (OutputFormat.HTML, OutputFormat.BOTH):
                html_task = progress.add_task("🌐 Generating HTML...", total=None)
                html_path = self.config.output_path.replace('.csv', '.html')

                with export_file(html_path, 'w') as f:
                    f.write(self.render_html(tasks))

                progress.remove_task(html_task)
                console.print(f"✅ [green]HTML exported:[/green] [bold]{html_path}[/bold]")

        # Final success message
        console.print(Panel(
            f"[bold green]🎉 Export completed successfully![/bold green]\n"
            f"📊 Exported [bold cyan]{len(tasks)}[/bold cyan] tasks\n"
            f"📁 Format: [yellow]{self.config.output_format.value}[/yellow]",
            title="Export Complete",
            style="green"
        ))

    def render_html(self, tasks: TaskList) -> str:
        """
        Render tasks as styled HTML table.

        Args:
            tasks: List of TaskRecord objects

        Returns:
            Complete HTML document as string
        """
        # Simple HTML table, styled
        head = '''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Weekly Task List</title><style>body{font-family:Arial,sans-serif;margin:20px;}table{border-collapse:collapse;width:100%;margin-top:20px;}th,td{border:1px solid #ddd;padding:12px;text-align:left;vertical-align:top;}th{background-color:#f2f2f2;font-weight:bold;}tr:nth-child(even){background-color:#f9f9f9;}.task-name{font-weight:bold;color:#2c5aa0;}.priority-high{color:#d73502;font-weight:bold;}.priority-normal{color:#0c7b93;}.priority-low{color:#6aa84f;}.notes{max-width:400px;white-space:pre-wrap;line-height:1.4;font-size:0.9em;}.status{padding:4px 8px;border-radius:4px;font-size:0.8em;font-weight:bold;}.status-open{background-color:#e8f4fd;color:#1f4e79;}.status-in-progress{background-color:#fff2cc;color:#7f6000;}.status-review{background-color:#f4cccc;color:#660000;}h1{color:#2c5aa0;}.summary{margin-bottom:20px;padding:15px;background-color:#f0f8ff;border-left:4px solid #2c5aa0;}</style></head><body>'''
        summary = f'<h1>Weekly Task List</h1><div class="summary"><strong>Generated:</strong> {format_datetime(datetime.now(), DISPLAY_FORMAT)}<br><strong>Total Tasks:</strong> {len(tasks)}<br><strong>Workspace:</strong> {html.escape(self.config.workspace_name)} / {html.escape(self.config.space_name)}</div>'

        # Get export fields (excluding internal fields like _metadata)
        export_fields = get_export_fields()
        table = '<table><thead><tr>' + ''.join(f'<th>{k}</th>' for k in export_fields) + '</tr></thead><tbody>'
        for t in tasks:
            table += '<tr>' + ''.join(f'<td>{html.escape(str(getattr(t, k) or ""))}</td>' for k in export_fields) + '</tr>'
        table += '</tbody></table></body></html>'
        return head + summary + table