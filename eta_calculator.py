#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ETA Calculator Module for ClickUp Task Extractor

Contains:
- AI-powered ETA calculation for tasks without due dates
- Priority and status-based logic for ETA estimation
- Fallback mechanisms for when AI is unavailable
"""

from datetime import datetime, timedelta
from typing import TypeAlias

# Rich console imports for beautiful output
try:
    from rich.console import Console

    _console = Console(force_terminal=None, legacy_windows=False)
    RICH_AVAILABLE = True
except ImportError:
    _console = None
    RICH_AVAILABLE = False

# Google GenAI SDK imports
try:
    from google.generativeai.client import configure  # type: ignore
    from google.generativeai.generative_models import GenerativeModel  # type: ignore
    from google.generativeai import types  # type: ignore
except ImportError:
    configure = None
    GenerativeModel = None
    types = None

# Type aliases
ETAResult: TypeAlias = str

# AI Model configuration
GEMINI_MODEL = "gemini-flash-lite-latest"

# Priority-based default ETA offsets (in days)
PRIORITY_ETA_DAYS = {
    "Urgent": 1,    # 1 day for urgent tasks
    "High": 3,      # 3 days for high priority
    "Normal": 7,    # 1 week for normal priority
    "Low": 14,      # 2 weeks for low priority
    "": 7,          # Default to 1 week if no priority
}

# Status-based ETA adjustments (multipliers)
STATUS_ETA_MULTIPLIER = {
    "in progress": 0.5,      # Reduce ETA by half if already in progress
    "investigating": 0.75,   # Slightly reduce if investigating
    "to do": 1.0,            # No adjustment for to-do
    "": 1.0,                 # Default multiplier
}


def _get_fallback_eta(priority: str, status: str) -> str:
    """
    Calculate fallback ETA based on priority and status when AI is unavailable.
    
    Args:
        priority: Task priority (Urgent, High, Normal, Low)
        status: Task status
        
    Returns:
        Formatted ETA date string (MM/DD/YYYY)
    """
    # Get base days from priority
    base_days = PRIORITY_ETA_DAYS.get(priority, 7)
    
    # Apply status multiplier
    status_lower = status.lower()
    multiplier = STATUS_ETA_MULTIPLIER.get(status_lower, 1.0)
    
    # Calculate final days
    final_days = int(base_days * multiplier)
    if final_days < 1:
        final_days = 1  # At least 1 day
    
    # Calculate ETA date
    eta_date = datetime.now() + timedelta(days=final_days)
    
    # Format as MM/DD/YYYY (without leading zeros handled by format_datetime in config.py)
    from config import format_datetime
    return format_datetime(eta_date, "%m/%d/%Y")


def _try_ai_eta_calculation(
    task_name: str,
    priority: str,
    status: str,
    description: str,
    subject: str,
    resolution: str,
    gemini_api_key: str,
) -> str | None:
    """
    Attempt to calculate ETA using AI based on task context.
    
    Args:
        task_name: Name of the task
        priority: Task priority level
        status: Current task status
        description: Task description
        subject: Task subject
        resolution: Resolution notes
        gemini_api_key: Google Gemini API key
        
    Returns:
        AI-calculated ETA date string or None if AI fails
    """
    try:
        configure(api_key=gemini_api_key)
        model = GenerativeModel(GEMINI_MODEL)
        
        # Build context for AI
        context_parts = []
        if subject:
            context_parts.append(f"Subject: {subject}")
        if description:
            context_parts.append(f"Description: {description}")
        if resolution:
            context_parts.append(f"Resolution: {resolution}")
        
        context = "\n".join(context_parts) if context_parts else "No additional context provided"
        
        # Current date for reference
        today = datetime.now().strftime("%m/%d/%Y")
        
        prompt = f"""You are helping estimate a completion date (ETA) for a task. Based on the task details below, suggest a realistic completion date.

Today's date: {today}

Task: {task_name}
Priority: {priority}
Status: {status}

Context:
{context}

Consider:
- Urgent tasks should be completed within 1-2 days
- High priority tasks within 3-5 days
- Normal priority tasks within 1 week
- Low priority tasks within 2 weeks
- Tasks already "in progress" or "investigating" may complete sooner
- Complex issues described may need more time

Respond with ONLY a date in MM/DD/YYYY format, nothing else. Do not include any explanations or additional text."""

        config = types.GenerationConfig(
            temperature=0.3,
            max_output_tokens=50,
        )
        
        response = model.generate_content(prompt, generation_config=config)
        
        if response and hasattr(response, "text") and response.text:
            # Extract date from response
            eta_text = response.text.strip()
            
            # Try to validate it's a date format
            # Simple validation: should contain / and numbers
            if "/" in eta_text and any(c.isdigit() for c in eta_text):
                # Take only the date part if there's additional text
                date_parts = eta_text.split()
                for part in date_parts:
                    if "/" in part:
                        return part
                return eta_text
            else:
                if RICH_AVAILABLE and _console:
                    _console.print(
                        f"[yellow]⚠️ AI returned invalid date format: {eta_text}[/yellow]"
                    )
                return None
        else:
            return None
            
    except Exception as e:
        if RICH_AVAILABLE and _console:
            _console.print(f"[dim]ETA calculation error: {str(e)[:100]}[/dim]")
        return None


def calculate_eta(
    task_name: str,
    priority: str,
    status: str,
    description: str = "",
    subject: str = "",
    resolution: str = "",
    gemini_api_key: str | None = None,
    enable_ai: bool = False,
) -> str:
    """
    Calculate ETA for a task without a due date.
    
    This function attempts to calculate an intelligent ETA using either:
    1. AI-based calculation using task context (if enabled and API key provided)
    2. Fallback calculation based on priority and status
    
    Args:
        task_name: Name of the task
        priority: Task priority (Urgent, High, Normal, Low)
        status: Current task status
        description: Task description (optional)
        subject: Task subject (optional)
        resolution: Resolution notes (optional)
        gemini_api_key: Google Gemini API key (optional)
        enable_ai: Whether to attempt AI-based calculation
        
    Returns:
        Formatted ETA date string (MM/DD/YYYY)
    """
    # If AI is enabled and we have the necessary components
    if (
        enable_ai
        and gemini_api_key
        and GenerativeModel is not None
        and configure is not None
        and types is not None
    ):
        # Try AI calculation
        ai_eta = _try_ai_eta_calculation(
            task_name,
            priority,
            status,
            description,
            subject,
            resolution,
            gemini_api_key,
        )
        
        if ai_eta:
            return ai_eta
        
        # If AI fails, fall through to fallback
        if RICH_AVAILABLE and _console:
            _console.print(
                f"[dim]Using fallback ETA calculation for: {task_name}[/dim]"
            )
    
    # Fallback calculation based on priority and status
    return _get_fallback_eta(priority, status)
