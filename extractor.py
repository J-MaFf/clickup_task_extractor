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
from typing import List

# Import project modules
from config import ClickUpConfig, TaskRecord, DISPLAY_FORMAT, format_datetime
from api_client import ClickUpAPIClient
from ai_summary import get_ai_summary
from mappers import get_yes_no_input, get_date_range, extract_images, LocationMapper


class ClickUpTaskExtractor:
    """Main orchestrator class for extracting and processing ClickUp tasks."""
    
    def __init__(self, config: ClickUpConfig, api_client: ClickUpAPIClient, load_gemini_key_func=None):
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

    def run(self):
        """Main execution method for the task extraction process."""
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
                folder_lists = self.api.get(f"/folder/{folder['id']}/list")['lists']
                lists.extend(folder_lists)
            space_lists = self.api.get(f"/space/{space['id']}/list?archived=false")['lists']
            lists.extend(space_lists)
            print(f"Found {len(lists)} lists to process.")
            all_tasks = []
            custom_fields_cache = {}
            for list_item in lists:
                print(f"Fetching tasks from list: {list_item['name']}")
                tasks_resp = self.api.get(f"/list/{list_item['id']}/task?archived={str(self.config.include_completed).lower()}")
                tasks = tasks_resp.get('tasks', [])
                if not self.config.include_completed:
                    tasks = [t for t in tasks if not t.get('archived') and t.get('status', {}).get('status', '') != 'closed']
                if self.config.exclude_statuses:
                    tasks = [t for t in tasks if t.get('status', {}).get('status', '') not in self.config.exclude_statuses]
                start_date, end_date = get_date_range(self.config.date_filter)
                if start_date and end_date:
                    tasks = [t for t in tasks if start_date <= datetime.fromtimestamp(int(t['date_created']) / 1000) <= end_date]
                print(f"  Found {len(tasks)} tasks in list '{list_item['name']}'")
                # Custom fields
                if list_item['id'] not in custom_fields_cache:
                    list_details = self.api.get(f"/list/{list_item['id']}")
                    list_custom_fields = list_details.get('custom_fields', [])
                    custom_fields_cache[list_item['id']] = list_custom_fields
                list_custom_fields = custom_fields_cache[list_item['id']]
                for task in tasks:
                    task_record = self._process_task(task, list_custom_fields)
                    if task_record:
                        all_tasks.append(task_record)
            print(f"Total tasks found: {len(all_tasks)}")
            
            # Handle AI summary if enabled
            if self.config.enable_ai_summary:
                # Load Gemini API key if not already set
                if not self.config.gemini_api_key and self.load_gemini_key_func:
                    self.config.gemini_api_key = self.load_gemini_key_func()
                
                if self.config.gemini_api_key:
                    if self.config.interactive_selection and all_tasks:
                        if get_yes_no_input("Would you like to generate AI summaries for the selected tasks? This may take time and use API quota (y/n): ", default_on_interrupt=False):
                            print("Generating AI summaries for selected tasks...")
                            for i, task in enumerate(all_tasks, 1):
                                print(f"  Processing task {i}/{len(all_tasks)}: {task.Task}")
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
                            print("✓ AI summaries generated for selected tasks.")
                    else:
                        print("✓ Proceeding without AI summary.")

            elif self.config.interactive_selection and not all_tasks:
                print("Interactive mode enabled but no tasks found to select from.")
            # Export
            self.export(all_tasks)
        except Exception as e:
            print(f"Fatal error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def _process_task(self, task, list_custom_fields) -> TaskRecord:
        """
        Process a single task into a TaskRecord.
        
        Args:
            task: Raw task data from ClickUp API
            list_custom_fields: Custom fields definition for the list
            
        Returns:
            TaskRecord instance or None if task should be skipped
        """
        try:
            task_name = task.get('name', 'Unnamed Task')
            
            # Handle task priority
            priority_map = {1: 'Low', 2: 'Normal', 3: 'High', 4: 'Urgent'}
            priority = priority_map.get(task.get('priority', {}).get('priority'), 'Normal') if task.get('priority') else 'Normal'
            
            # Get task status
            status = task.get('status', {}).get('status', 'Unknown')
            
            # Get due date
            due_date = task.get('due_date')
            eta = ''
            if due_date:
                try:
                    due_dt = datetime.fromtimestamp(int(due_date) / 1000)
                    eta = format_datetime(due_dt, DISPLAY_FORMAT)
                except (ValueError, OSError):
                    eta = 'Invalid Date'
            
            # Initialize custom field values
            company = ''
            branch = ''
            subject = ''
            description = task.get('description', '')
            resolution = ''
            
            # Process custom fields
            task_custom_fields = task.get('custom_fields', [])
            
            for tcf in task_custom_fields:
                field_id = tcf.get('id')
                field_value = tcf.get('value')
                
                # Find the field definition
                field_def = next((f for f in list_custom_fields if f.get('id') == field_id), None)
                if not field_def:
                    continue
                
                field_name = field_def.get('name', '').lower()
                field_type = field_def.get('type_config', {})
                field_options = field_type.get('options', [])
                
                # Map field values based on field name
                if 'company' in field_name:
                    company = str(field_value) if field_value else ''
                elif 'branch' in field_name or 'location' in field_name:
                    branch = LocationMapper.map_location(field_value, field_type, field_options) if field_value else ''
                elif 'subject' in field_name:
                    subject = str(field_value) if field_value else ''
                elif 'resolution' in field_name:
                    resolution = str(field_value) if field_value else ''
            
            # Extract images from description
            images = extract_images(description)
            extra_content = f"Images: {images}" if images else ""
            
            # Create task record
            task_record = TaskRecord(
                Task=task_name,
                Company=company,
                Branch=branch,
                Priority=priority,
                Status=status,
                ETA=eta,
                Notes='',  # Will be filled by AI summary if enabled
                Extra=extra_content
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
            return None

    def interactive_include(self, tasks: List[TaskRecord]) -> List[TaskRecord]:
        """
        Allow user to interactively select which tasks to export.
        
        Args:
            tasks: List of TaskRecord objects
            
        Returns:
            List of selected TaskRecord objects
        """
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
        """
        Export tasks to CSV and/or HTML format.
        
        Args:
            tasks: List of TaskRecord objects to export
        """
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
        table = '<table><thead><tr>' + ''.join(f'<th>{k}</th>' for k in TaskRecord.__annotations__.keys()) + '</tr></thead><tbody>'
        for t in tasks:
            table += '<tr>' + ''.join(f'<td>{html.escape(str(getattr(t, k) or ""))}</td>' for k in TaskRecord.__annotations__.keys()) + '</tr>'
        table += '</tbody></table></body></html>'
        return head + summary + table