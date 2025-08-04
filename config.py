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
from typing import Optional


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


@dataclass
class ClickUpConfig:
    """Configuration settings for ClickUp Task Extractor."""
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
    exclude_statuses: list = field(default_factory=lambda: ['Blocked', 'Dormant', 'On Hold', 'Document'])


@dataclass
class TaskRecord:
    """Data structure for task export records."""
    Task: str
    Company: str
    Branch: str
    Priority: str
    Status: str
    ETA: str = ''
    Notes: str = ''
    Extra: str = ''
    _metadata: dict = field(default_factory=dict, init=False, repr=False)