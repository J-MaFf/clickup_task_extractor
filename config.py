#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Configuration and Data Models for ClickUp Task Extractor

Contains:
- ClickUpConfig dataclass for application configuration
- TaskRecord dataclass for task export structure
- Date/time formatting constants and utilities
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypeAlias
from enum import Enum


# Date/time formatting constants - cross-platform compatible
TIMESTAMP_FORMAT = '%m-%d-%Y_%I-%M%p'  # For filenames (with leading zeros for compatibility)
DISPLAY_FORMAT = '%m/%d/%Y at %I:%M %p'  # For HTML display (with leading zeros for compatibility)


class TaskPriority(Enum):
    """Enumeration of task priority levels."""
    LOW = "Low"
    NORMAL = "Normal"
    HIGH = "High"
    URGENT = "Urgent"


# Priority sorting order (higher value = higher priority)
PRIORITY_ORDER = {
    "Urgent": 4,
    "High": 3,
    "Normal": 2,
    "Low": 1,
    "": 0,  # Handle empty/missing priority
}


class OutputFormat(Enum):
    """Enumeration of supported output formats."""
    CSV = "CSV"
    HTML = "HTML"
    MARKDOWN = "Markdown"
    PDF = "PDF"
    BOTH = "Both"  # Legacy support for CSV + HTML


class DateFilter(Enum):
    """Enumeration of supported date filter options."""
    ALL_OPEN = "AllOpen"
    THIS_WEEK = "ThisWeek"
    LAST_WEEK = "LastWeek"


def format_datetime(dt: datetime, format_string: str) -> str:
    """
    Format datetime removing leading zeros from day, month, and hour.

    This function provides cross-platform compatible datetime formatting
    by removing leading zeros from day (%d), month (%m), and hour (%I)
    components for cleaner, more natural display.

    Args:
        dt: DateTime object to format
        format_string: strftime format string to use

    Returns:
        Formatted datetime string without leading zeros

    Example:
        >>> dt = datetime(2025, 1, 8, 9, 30, 0)
        >>> format_datetime(dt, '%m/%d/%Y at %I:%M %p')
        '1/8/2025 at 9:30 AM'
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
    """
    Generate default output path with timestamp without leading zeros.

    Returns:
        Default file path for task export using current timestamp

    Example:
        'output/WeeklyTaskList_1-8-2025_3-45PM.csv'
    """
    return f"output/WeeklyTaskList_{format_datetime(datetime.now(), TIMESTAMP_FORMAT)}.csv"


def sort_tasks_by_priority_and_name(tasks: list['TaskRecord']) -> list['TaskRecord']:
    """
    Sort tasks by priority (Urgent → High → Normal → Low) and then alphabetically by task name.

    Args:
        tasks: List of TaskRecord objects to sort

    Returns:
        Sorted list of TaskRecord objects

    Example:
        >>> tasks = [
        ...     TaskRecord(Task="Zebra", Priority="Low", ...),
        ...     TaskRecord(Task="Apple", Priority="High", ...),
        ...     TaskRecord(Task="Banana", Priority="High", ...)
        ... ]
        >>> sorted_tasks = sort_tasks_by_priority_and_name(tasks)
        >>> # Result: [High-Apple, High-Banana, Low-Zebra]
    """
    return sorted(
        tasks,
        key=lambda task: (
            -PRIORITY_ORDER.get(task.Priority, 0),  # Negative for descending order
            task.Task.lower()  # Case-insensitive alphabetical
        )
    )


@dataclass
class ClickUpConfig:
    """
    Configuration settings for ClickUp Task Extractor.

    This dataclass centralizes all configuration options for the task extractor,
    including API authentication, workspace/space selection, output formatting,
    and filtering options.

    Attributes:
        api_key: ClickUp API key for authentication
        workspace_name: Name of the ClickUp workspace to extract from
        space_name: Name of the ClickUp space within the workspace
        output_path: File path for exported task data
        include_completed: Whether to include completed/archived tasks
        date_filter: Date range filter (DateFilter enum: ALL_OPEN, THIS_WEEK, LAST_WEEK)
        enable_ai_summary: Whether to generate AI summaries using Gemini
        gemini_api_key: Google Gemini API key for AI functionality
        output_format: Export format (OutputFormat enum: CSV, HTML, BOTH)
        interactive_selection: Whether to enable interactive task selection
        exclude_statuses: List of task statuses to exclude from export

    Example:
        >>> config = ClickUpConfig(
        ...     api_key="pk_123456789",
        ...     workspace_name="My Workspace",
        ...     space_name="Development"
        ... )
    """
    api_key: str
    workspace_name: str = 'KMS'
    space_name: str = 'Kikkoman'
    output_path: str = field(default_factory=default_output_path)
    include_completed: bool = False
    date_filter: DateFilter = DateFilter.ALL_OPEN
    enable_ai_summary: bool = False
    gemini_api_key: str | None = None
    output_format: OutputFormat = OutputFormat.HTML
    interactive_selection: bool = False
    # Exclude tasks with these statuses
    exclude_statuses: list[str] = field(default_factory=lambda: ['Blocked', 'Dormant', 'On Hold', 'Document'])


@dataclass
class TaskRecord:
    """
    Data structure for task export records.

    This dataclass represents a task record with all the fields that will be
    exported to CSV/HTML format. It matches the structure expected by the
    export functionality and provides a clean interface for task data.

    Attributes:
        Task: Task name/title
        Company: Company/List name where the task belongs
        Branch: Branch/Location information from custom fields
        Priority: Task priority level (Low, Normal, High, Urgent)
        Status: Current task status
        ETA: Estimated completion date/time
        Notes: Task notes, description, or AI-generated summary
        Extra: Additional information like image attachments
        _metadata: Internal metadata for AI processing (not exported)

    Example:
        >>> task = TaskRecord(
        ...     Task="Fix login bug",
        ...     Company="Development",
        ...     Branch="Web App",
        ...     Priority="High",
        ...     Status="In Progress"
        ... )
    """
    Task: str
    Company: str
    Branch: str
    Priority: str  # Keep as string for CSV export compatibility
    Status: str
    ETA: str = ''
    Notes: str = ''
    Extra: str = ''
    _metadata: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
