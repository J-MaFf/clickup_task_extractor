#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Data Mapping and Utilities Module for ClickUp Task Extractor

Contains:
- LocationMapper class for custom field value mapping
- Utility functions for user input, date ranges, and image extraction
"""

import re
from datetime import datetime, timedelta
from typing import TypeAlias

from config import DateFilter


# Type aliases for clarity
DateRange: TypeAlias = tuple[datetime | None, datetime | None]


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


def get_choice_input(prompt: str, choices: list[str], default_index: int = 0) -> str:
    """
    Generic function to get a choice from a list of options with consistent behavior.

    Args:
        prompt: The prompt message to display to the user
        choices: List of available choices
        default_index: Index of the default choice if user interrupts or provides invalid input

    Returns:
        The selected choice string

    Example:
        >>> formats = ['CSV', 'HTML', 'Markdown', 'PDF']
        >>> selected = get_choice_input('Select format:', formats, default_index=1)
    """
    if not choices:
        raise ValueError("Choices list cannot be empty")
    
    if default_index < 0 or default_index >= len(choices):
        default_index = 0
    
    try:
        # Display choices
        for i, choice in enumerate(choices, 1):
            default_marker = " (default)" if i - 1 == default_index else ""
            print(f"  {i}. {choice}{default_marker}")
        
        # Get user input
        response = input(prompt).strip()
        
        # Handle empty input (use default)
        if not response:
            return choices[default_index]
        
        # Try to parse as number
        try:
            choice_num = int(response)
            if 1 <= choice_num <= len(choices):
                return choices[choice_num - 1]
        except ValueError:
            pass
        
        # Try to match by name (case-insensitive)
        response_lower = response.lower()
        for choice in choices:
            if choice.lower() == response_lower:
                return choice
        
        # Invalid input, use default
        print(f"Invalid choice. Using default: {choices[default_index]}")
        return choices[default_index]
        
    except (EOFError, KeyboardInterrupt):
        print(f"\nDefaulting to: {choices[default_index]}")
        return choices[default_index]


def get_date_range(filter_name: DateFilter | str) -> DateRange:
    """
    Get date range for filtering based on filter name.

    Args:
        filter_name: DateFilter enum or string name of the date filter

    Returns:
        Tuple of (start_date, end_date) or (None, None) if no filter
    """
    # Handle both enum and string inputs for backward compatibility
    if isinstance(filter_name, DateFilter):
        filter_str = filter_name.value
    else:
        filter_str = filter_name

    today = datetime.now()
    if filter_str == 'ThisWeek':
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end
    elif filter_str == 'LastWeek':
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return start, end
    return None, None


def extract_images(text: str) -> str:
    """
    Extract image references from text using various patterns.

    Args:
        text: Text content to extract images from

    Returns:
        Semicolon-separated string of image references
    """
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


class LocationMapper:
    """Mapper for ClickUp custom field values to human-readable labels."""

    @staticmethod
    def map_location(val, type_, options) -> str:
        """
        Map ClickUp custom field value to human-readable label.

        Args:
            val: The raw value from ClickUp
            type_: The field type
            options: List of available options for the field

        Returns:
            Human-readable label for the value
        """
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