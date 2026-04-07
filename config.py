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
from datetime import datetime, timezone
from typing import Any
from enum import Enum


# Date/time formatting constants - cross-platform compatible
TIMESTAMP_FORMAT = (
    "%m-%d-%Y_%I-%M%p"  # For filenames (with leading zeros for compatibility)
)
DISPLAY_FORMAT = (
    "%m/%d/%Y at %I:%M %p"  # For HTML display (with leading zeros for compatibility)
)


class TaskPriority(Enum):
    """Enumeration of task priority levels."""

    LOW = "Low"
    NORMAL = "Normal"
    HIGH = "High"
    URGENT = "Urgent"


class AISource(Enum):
    """AI summary source selection."""

    BOTH = "Both"
    CLICKUP = "ClickUp"
    GEMINI = "Gemini"


# Priority sorting order (higher value = higher priority)
PRIORITY_ORDER = {
    "urgent": 4,
    "high": 3,
    "normal": 2,
    "low": 1,
    "": 0,  # Handle empty/missing priority
}


# Default ClickUp AI summary custom field identifier ("Summary")
CLICKUP_AI_SUMMARY_FIELD_ID = "d7426f47-27f0-494b-b3a2-7d254132ee1a"


class OutputFormat(Enum):
    """Enumeration of supported output formats."""

    HTML = "HTML"
    MARKDOWN = "Markdown"


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
    # Parse the format string and build result, handling %m, %d, %I specially
    result = ""
    i = 0

    hour_12 = dt.hour % 12
    if hour_12 == 0:
        hour_12 = 12

    while i < len(format_string):
        if format_string[i] == "%":
            if i + 1 < len(format_string):
                code = format_string[i : i + 2]
                if code == "%m":
                    # Month without leading zero
                    result += str(dt.month)
                    i += 2
                elif code == "%d":
                    # Day without leading zero
                    result += str(dt.day)
                    i += 2
                elif code == "%I":
                    # 12-hour format without leading zero
                    result += str(hour_12)
                    i += 2
                else:
                    # Other format codes - use strftime for this char
                    result += dt.strftime(code)
                    i += 2
            else:
                result += format_string[i]
                i += 1
        else:
            result += format_string[i]
            i += 1

    return result


def default_output_path() -> str:
    """
    Generate default output path with timestamp without leading zeros.

    Returns:
        Default file path for task export using current timestamp

    Example:
        'output/WeeklyTaskList_1-8-2025_3-45PM.md'
    """
    return (
        f"output/WeeklyTaskList_{format_datetime(datetime.now(), TIMESTAMP_FORMAT)}.md"
    )


def sort_tasks_by_priority_and_name(tasks: list["TaskRecord"]) -> list["TaskRecord"]:
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
            -_priority_value(task.Priority),  # Negative for descending order
            task.Task.lower(),  # Case-insensitive alphabetical
        ),
    )


def sort_tasks_by_priority_and_eta(tasks: list["TaskRecord"]) -> list["TaskRecord"]:
    """
    Sort tasks by priority (Urgent → High → Normal → Low) and then by ETA (earliest first).

    This function implements the primary sorting by priority level, with ETA as a secondary
    tiebreaker for tasks with equal priority. Tasks with missing ETAs appear last within
    their priority tier.

    Args:
        tasks: List of TaskRecord objects to sort

    Returns:
        Sorted list of TaskRecord objects

    Example:
        >>> tasks = [
        ...     TaskRecord(Task="Alpha", Priority="Urgent", ETA="2/20/2026 at 3:45 PM", ...),
        ...     TaskRecord(Task="Zebra", Priority="Urgent", ETA="2/15/2026 at 3:45 PM", ...),
        ...     TaskRecord(Task="Beta", Priority="High", ETA="2/10/2026 at 3:45 PM", ...),
        ... ]
        >>> sorted_tasks = sort_tasks_by_priority_and_eta(tasks)
        >>> # Result: [Urgent-Zebra (2/15), Urgent-Alpha (2/20), High-Beta (2/10)]
    """

    def parse_eta(eta_str: str) -> tuple[int, datetime]:
        """
        Parse ETA string to datetime object for comparison.

        Returns a tuple of (sort_priority, datetime_obj):
        - sort_priority: 0 for valid ETA (sorts first), 1 for missing ETA (sorts last)
        - datetime_obj: parsed datetime (always returns datetime.max for invalid/missing)
        """
        if not eta_str or not eta_str.strip():
            return (1, datetime.max)  # Missing ETA sorts last

        eta_normalized = eta_str.strip()

        try:
            # Try parsing with DISPLAY_FORMAT pattern (e.g., "2/15/2026 at 3:45 PM")
            parsed_dt = datetime.strptime(eta_normalized, DISPLAY_FORMAT)
            return (0, parsed_dt)
        except ValueError:
            try:
                # Try parsing with month/day/year format without time (e.g., "2/15/2026")
                parsed_dt = datetime.strptime(eta_normalized, "%m/%d/%Y")
                return (0, parsed_dt)
            except ValueError:
                try:
                    # Try parsing with alternate format (e.g., "2026-02-15")
                    parsed_dt = datetime.strptime(eta_normalized, "%Y-%m-%d")
                    return (0, parsed_dt)
                except ValueError:
                    try:
                        # Normalize trailing Z for fromisoformat compatibility
                        if eta_normalized.endswith("Z"):
                            eta_normalized = eta_normalized[:-1] + "+00:00"

                        # Try ISO format with time (may include timezone)
                        parsed_dt = datetime.fromisoformat(eta_normalized)
                        # Normalize to naive datetime in UTC to avoid comparison issues
                        if parsed_dt.tzinfo is not None:
                            parsed_dt = parsed_dt.astimezone(timezone.utc).replace(
                                tzinfo=None
                            )
                        return (0, parsed_dt)
                    except (ValueError, AttributeError):
                        # If all parsing fails, treat as missing
                        return (1, datetime.max)

    return sorted(
        tasks,
        key=lambda task: (
            -_priority_value(task.Priority),  # Negative for descending priority order
            *parse_eta(task.ETA),  # Unpack (sort_priority, datetime) for ETA sorting
            task.Task.lower(),  # Tertiary sort by task name for deterministic ordering
        ),
    )


def _priority_value(priority: str | None) -> int:
    """Map priority label to numeric order (case-insensitive)."""

    if not priority:
        return 0

    return PRIORITY_ORDER.get(priority.strip().lower(), 0)


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
        team_id: ClickUp Team/Workspace ID (optional, used if /team endpoint fails)
        output_path: File path for exported task data
        include_completed: Whether to include completed/archived tasks
        date_filter: Date range filter (DateFilter enum: ALL_OPEN, THIS_WEEK, LAST_WEEK)
        enable_ai_summary: Whether to generate AI summaries using Gemini
        gemini_api_key: Google Gemini API key for AI functionality
        output_format: Export format (OutputFormat enum: MARKDOWN, HTML)
        interactive_selection: Whether to enable interactive task selection
        exclude_statuses: List of task statuses to exclude from export

    Example:
        >>> config = ClickUpConfig(
        ...     api_key="pk_123456789",
        ...     workspace_name="My Workspace",
        ...     space_name="Development",
        ...     team_id="9014534294"
        ... )
    """

    api_key: str
    workspace_name: str = "KMS"
    space_name: str = "Kikkoman"
    team_id: str = "9014534294"
    output_path: str = field(default_factory=default_output_path)
    include_completed: bool = False
    date_filter: DateFilter = DateFilter.ALL_OPEN
    enable_ai_summary: bool = False
    gemini_api_key: str | None = None
    ai_source: AISource = AISource.BOTH
    ai_clickup_field_id: str | None = CLICKUP_AI_SUMMARY_FIELD_ID
    output_format: OutputFormat = OutputFormat.MARKDOWN
    interactive_selection: bool = False
    # Exclude tasks with these statuses
    exclude_statuses: list[str] = field(
        default_factory=lambda: ["Blocked", "Dormant", "On Hold", "Document"]
    )


@dataclass
class TaskRecord:
    """
    Data structure for task export records.

    This dataclass represents a task record with all the fields that will be
    exported to Markdown/HTML format. It matches the structure expected by the
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
    Priority: str
    Status: str
    ETA: str = ""
    Notes: str = ""
    Extra: str = ""
    _metadata: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
