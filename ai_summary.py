#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Integration Module for ClickUp Task Extractor

Contains:
- AI summary generation using Google Gemini Flash-Latest API
- Rate limiting and retry logic
- Progress bar functionality for wait times
"""

import re
import time
from typing import Callable, Mapping, Sequence, TypeAlias

# Use Gemini Flash-Lite-Latest for AI summaries (paid tier)
GEMINI_MODEL = "gemini-flash-lite-latest"

# Rich console imports - create singleton instance with proper encoding for Windows
try:
    from rich.console import Console
    from rich.progress import Progress, TimeRemainingColumn, BarColumn, TextColumn
    from rich.status import Status

    # Create a singleton console instance with proper configuration for cross-platform compatibility
    # This ensures proper rendering on Windows, macOS, and Linux
    _console = Console(force_terminal=None, legacy_windows=False)
    RICH_AVAILABLE = True
except ImportError:
    _console = None
    RICH_AVAILABLE = False
    Progress = None
    TimeRemainingColumn = None
    BarColumn = None
    TextColumn = None
    Status = None

# Type aliases for clarity
SummaryResult: TypeAlias = str

# Global state for tracking API availability
_api_available = True
_last_error_message = ""

# Google GenAI SDK imports
try:
    from google.generativeai.client import configure  # type: ignore
    from google.generativeai.generative_models import GenerativeModel  # type: ignore
    from google.generativeai import types  # type: ignore
except ImportError:
    configure = None
    GenerativeModel = None
    types = None


def _is_rate_limit_error(error_str: str) -> bool:
    """
    Detect if error indicates a rate limit or quota issue.

    Rate limit errors typically contain:
    - "429" HTTP status code
    - "RESOURCE_EXHAUSTED" exception
    - "quota" or "rate limit" keywords
    - Google API specific error types ("overload", "unavailable")
    - RPM/per-minute quota messages

    Args:
        error_str: Error message string

    Returns:
        True if this is a rate limit error, False otherwise
    """
    error_lower = error_str.lower()

    return (
        "429" in error_str
        or "RESOURCE_EXHAUSTED" in error_str
        or "quota" in error_lower
        or "rate limit" in error_lower
        or "rate_limit" in error_lower
        or "overload" in error_lower
        or "unavailable" in error_lower
        or "too_many_requests" in error_lower
        or "limit_exceeded" in error_lower
        or "requests per minute" in error_lower
        or "rpm" in error_lower
    )


def _reset_api_state() -> None:
    """Reset API state (for testing or manual reset)."""
    global _api_available, _last_error_message
    _api_available = True
    _last_error_message = ""


def _normalize_field_entries(
    field_entries: Sequence[tuple[str, str]] | Mapping[str, str],
) -> list[tuple[str, str]]:
    """Normalize field entries into an ordered list of label/value pairs."""
    if isinstance(field_entries, Mapping):
        return [(str(label), str(value)) for label, value in field_entries.items()]
    return [(str(label), str(value)) for label, value in field_entries]


def _try_ai_summary(
    task_name: str, field_block: str, gemini_api_key: str
) -> tuple[str | None, bool]:
    """
    Attempt to generate AI summary using Gemini Flash-Latest.

    Args:
        task_name: Name of the task
        field_block: Formatted field content
        gemini_api_key: Google Gemini API key

    Returns:
        Tuple of (summary_text or None, is_rate_limit_error)
    """
    try:
        configure(api_key=gemini_api_key)
        model = GenerativeModel(GEMINI_MODEL)

        prompt = f"""Please provide a concise 1-2 sentence summary of the current status of this task using the available fields, written as if you are the user describing your own work (use first-person voice, e.g., "I completed...", "I need to..."):

Task: {task_name}

Here are the available fields (values may be "(not provided)" when absent):

{field_block}

Focus on the current state and what you have done or need to do. Be specific and actionable. Ignore any fields marked "(not provided)"."""

        config = types.GenerationConfig(
            temperature=0.3,
            max_output_tokens=150,
        )

        response = model.generate_content(prompt, generation_config=config)

        if response and hasattr(response, "text") and response.text:
            summary = response.text.strip()
            summary = summary.replace("\n", " ").strip()
            if not summary.endswith("."):
                summary += "."
            return summary, False
        else:
            if RICH_AVAILABLE and _console:
                _console.print(
                    f"⚠️ [yellow]Warning: No text response from Gemini API for task: {task_name}[/yellow]"
                )
            else:
                print(
                    f"Warning: No text response from Gemini API for task: {task_name}"
                )
            return None, False

    except Exception as e:
        global _api_available, _last_error_message

        error_str = str(e)
        is_rate_limit = _is_rate_limit_error(error_str)
        _last_error_message = error_str[:150]

        if is_rate_limit:
            _api_available = False
            if RICH_AVAILABLE and _console:
                _console.print(f"\u23f3 [yellow]Rate limit: {error_str[:100]}[/yellow]")
            else:
                print(f"Rate limit: {error_str}")
        else:
            if RICH_AVAILABLE and _console:
                _console.print(f"\u274c [red]Error: {error_str[:100]}[/red]")
            else:
                print(f"Error: {error_str}")

        return None, is_rate_limit


def _handle_rate_limit_wait(
    attempt: int,
    max_retries: int,
    initial_delay: int,
    progress_pause_callback: Callable[[], None] | None = None,
) -> None:
    """
    Handle wait period during rate limit with simple sleep (no progress bar).

    Args:
        attempt: Current attempt number (0-indexed)
        max_retries: Total number of retries allowed
        initial_delay: Base delay in seconds
        progress_pause_callback: Optional callback to pause main progress bars
    """
    exponential_delay = initial_delay * (2**attempt)
    retry_delay = exponential_delay

    if progress_pause_callback:
        progress_pause_callback()

    if RICH_AVAILABLE and _console:
        _console.print(
            f"⏳ [dim]Rate limit hit. Waiting {retry_delay}s before retry...[/dim]"
        )
    else:
        print(f"Rate limit hit. Waiting {retry_delay}s before retry...")

    time.sleep(retry_delay)


def get_ai_summary(
    task_name: str,
    field_entries: Sequence[tuple[str, str]] | Mapping[str, str],
    gemini_api_key: str,
    progress_pause_callback: Callable[[], None] | None = None,
) -> SummaryResult:
    """
    Generate a concise 1-2 sentence summary about the current status of the task using Google Gemini Flash-Latest.
    Includes retry logic with exponential backoff for rate limits.

    Args:
        task_name: Name of the task
        field_entries: Iterable of (field label, value) pairs to include in prompt
        gemini_api_key: Google Gemini API key for authentication
        progress_pause_callback: Optional callback to pause/resume main progress bars during rate limit wait

    Returns:
        AI-generated summary or original content if AI fails
    """
    global _api_available

    # Check if API is currently unavailable due to rate limiting
    if not _api_available:
        if RICH_AVAILABLE and _console:
            _console.print(
                f"[dim][⊘] API rate limited - skipping AI summary for: {task_name}[/dim]"
            )
        return None  # Return None to signal API unavailability (caller will skip this task)

    normalized_entries = _normalize_field_entries(field_entries)
    field_block = "\n".join(
        f"{label}: {value}" for label, value in normalized_entries if label
    )

    if not field_block:
        return "No content available for summary."

    if not gemini_api_key:
        return field_block

    if GenerativeModel is None or configure is None or types is None:
        if RICH_AVAILABLE and _console:
            _console.print(
                "[yellow]Warning: Google GenAI SDK not available - install with: pip install google-generativeai[/yellow]"
            )
        else:
            print(
                "Warning: Google GenAI SDK not available - install with: pip install google-generativeai"
            )
        return field_block

    # Try with retries and exponential backoff
    max_retries = 2
    initial_delay = 1

    for attempt in range(max_retries + 1):
        summary, is_rate_limit = _try_ai_summary(task_name, field_block, gemini_api_key)

        # Success case
        if summary is not None:
            return summary

        # Rate limit error
        if is_rate_limit:
            if attempt < max_retries:
                # Retry with exponential backoff
                _handle_rate_limit_wait(
                    attempt, max_retries, initial_delay, progress_pause_callback
                )
                continue
            else:
                # All retries exhausted
                _api_available = False
                if RICH_AVAILABLE and _console:
                    _console.print(
                        "[red]Rate limit - AI summaries will be skipped for this extraction.[/red]"
                    )
                else:
                    print(
                        "Rate limit - AI summaries will be skipped for this extraction."
                    )
                return field_block
        else:
            # Non-retryable error
            if RICH_AVAILABLE and _console:
                _console.print(
                    f"⚠️ [yellow]Unable to generate summary. Using fallback content.[/yellow]"
                )
            else:
                print(f"Unable to generate summary. Using fallback content.")
            return field_block

    # Fallback (should not reach here, but safety net)
    return field_block
