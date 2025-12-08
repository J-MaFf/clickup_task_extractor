#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Integration Module for ClickUp Task Extractor

Contains:
- AI summary generation using Google Gemini API
- Rate limiting and retry logic
- Progress bar functionality for wait times
"""

import re
import time
from typing import Mapping, Sequence, TypeAlias

# Rich console imports - create singleton instance
try:
    from rich.console import Console
    from rich.progress import Progress, TimeRemainingColumn, BarColumn, TextColumn
    from rich.status import Status

    # Create a singleton console instance to avoid repeated imports
    _console = Console()
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

# Google GenAI SDK imports
try:
    from google.generativeai.client import configure  # type: ignore
    from google.generativeai.generative_models import GenerativeModel  # type: ignore
    from google.generativeai import types  # type: ignore
except ImportError:
    configure = None
    GenerativeModel = None
    types = None


def _normalize_field_entries(field_entries: Sequence[tuple[str, str]] | Mapping[str, str]) -> list[tuple[str, str]]:
    """Normalize field entries into an ordered list of label/value pairs."""
    if isinstance(field_entries, Mapping):
        return [(str(label), str(value)) for label, value in field_entries.items()]
    return [(str(label), str(value)) for label, value in field_entries]


def get_ai_summary(
    task_name: str,
    field_entries: Sequence[tuple[str, str]] | Mapping[str, str],
    gemini_api_key: str
) -> SummaryResult:
    """
    Generate a concise 1-2 sentence summary about the current status of the task using Google Gemini AI.
    Automatically handles rate limiting with intelligent retry logic.

    Args:
        task_name: Name of the task
        field_entries: Iterable of (field label, value) pairs to include in prompt
        gemini_api_key: Google Gemini API key for authentication

    Returns:
        AI-generated summary or original content if AI fails
    """
    normalized_entries = _normalize_field_entries(field_entries)

    field_block = "\n".join(f"{label}: {value}" for label, value in normalized_entries if label)
    if not field_block:
        return "No content available for summary."

    if not gemini_api_key:
        return field_block

    # Check if Google GenAI SDK is available
    if GenerativeModel is None or configure is None or types is None:
        if RICH_AVAILABLE and _console:
            _console.print("[yellow]Warning: Google GenAI SDK not available - install with: pip install google-generativeai[/yellow]")
        else:
            print("Warning: Google GenAI SDK not available - install with: pip install google-generativeai")
        return field_block

    max_retries = 3
    base_delay = 30  # Increased base delay to 30 seconds for rate limiting

    for attempt in range(max_retries + 1):
        try:
            # Initialize the Google GenAI client
            configure(api_key=gemini_api_key)
            model = GenerativeModel('gemini-flash-lite-latest')

            full_content = field_block

            # Create the prompt for AI summary
            prompt = f"""Please provide a concise 1-2 sentence summary of the current status of this task using the available fields, written as if you are the user describing your own work (use first-person voice, e.g., "I completed...", "I need to..."):

Task: {task_name}

Here are the available fields (values may be "(not provided)" when absent):

{full_content}

Focus on the current state and what you have done or need to do. Be specific and actionable. Ignore any fields marked "(not provided)"."""

            # Use the official Google GenAI SDK with proper configuration
            config = types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=150,
            )

            # Make API call without status indicator to avoid progress bar conflicts
            # The main progress bar will handle the visual feedback
            response = model.generate_content(
                prompt,
                generation_config=config
            )

            if response and hasattr(response, 'text') and response.text:
                summary = response.text.strip()

                # Clean up the summary
                summary = summary.replace('\n', ' ').strip()
                if not summary.endswith('.'):
                    summary += '.'

                return summary
            else:
                if RICH_AVAILABLE and _console:
                    _console.print(f"⚠️ [yellow]Warning: No text response from Gemini API for task: {task_name}[/yellow]")
                else:
                    print(f"Warning: No text response from Gemini API for task: {task_name}")
                return field_block

        except Exception as e:
            error_str = str(e)

            # Check if this is a rate limit error (429 or quota exceeded)
            is_rate_limit = (
                "429" in error_str or
                "RESOURCE_EXHAUSTED" in error_str or
                "quota" in error_str.lower() or
                "rate limit" in error_str.lower()
            )

            if is_rate_limit:
                # Extract retry delay from error message if available
                retry_delay = base_delay
                try:
                    # Try to parse the retry delay from the error message
                    if "retryDelay" in error_str:
                        # Look for patterns like '"retryDelay": "20s"'
                        delay_match = re.search(r'"retryDelay":\s*"(\d+)s"', error_str)
                        if delay_match:
                            retry_delay = int(delay_match.group(1))
                        else:
                            # Fallback: extract quota value and calculate delay
                            quota_match = re.search(r'"quotaValue":\s*"(\d+)"', error_str)
                            if quota_match:
                                quota_value = int(quota_match.group(1))
                                # Calculate delay based on quota (60 seconds / quota = delay per request)
                                retry_delay = max(60 // quota_value, base_delay)
                except (ValueError, AttributeError):
                    # If parsing fails, use exponential backoff
                    retry_delay = base_delay * (2 ** attempt)

                if attempt < max_retries:
                    # Use Rich console for better styling
                    if RICH_AVAILABLE and _console and Progress and TextColumn and BarColumn and TimeRemainingColumn:
                        _console.print(f"⏳ [yellow]Rate limit hit for task '{task_name}'. Waiting {retry_delay} seconds before retry (attempt {attempt + 1}/{max_retries})...[/yellow]")

                        # Rich progress bar for wait time
                        with Progress(
                            TextColumn("[bold blue]⏱️  Rate limit wait"),
                            BarColumn(bar_width=40),
                            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                            TimeRemainingColumn(),
                            console=_console,
                            transient=True  # Progress bar disappears when done
                        ) as progress:
                            task = progress.add_task("Waiting...", total=retry_delay)
                            for _ in range(retry_delay):
                                time.sleep(1)
                                progress.update(task, advance=1)

                        _console.print("✅ [green]Wait complete - retrying API call...[/green]")
                    else:
                        # Fallback to plain print
                        print(f"Rate limit hit for task '{task_name}'. Waiting {retry_delay} seconds before retry (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(retry_delay)
                        print("Wait complete - retrying API call...")
                    continue
                if RICH_AVAILABLE and _console:
                    _console.print(f"❌ [red]Rate limit retry failed for task '{task_name}' after {max_retries} attempts.[/red]")
                else:
                    print(f"Rate limit retry failed for task '{task_name}' after {max_retries} attempts.")

            else:
                # Non-rate-limit error
                if RICH_AVAILABLE and _console:
                    _console.print(f"⚠️ [yellow]AI Summary error for task '{task_name}': {e}[/yellow]")
                else:
                    print(f"AI Summary error for task '{task_name}': {e}")

            # Final attempt failed or non-retryable error - return fallback
            return field_block

    # Should never reach here, but just in case
    return field_block
