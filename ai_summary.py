#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Integration Module for ClickUp Task Extractor

Contains:
- AI summary generation using Google Gemini API
- Rate limiting and retry logic with tiered model fallback
- Progress bar functionality for wait times
"""

import re
import time
from typing import Callable, Mapping, Sequence, TypeAlias

# Tiered model strategy for rate limit handling
# Tier 1: Primary (cheapest/fastest)
# Tier 2: Better quality with separate quota bucket
# Tier 3: Emergency fallback
MODEL_TIERS = [
    "gemini-2.5-flash-lite",  # 500 RPD, fastest and cheapest
    "gemini-2.5-pro",         # 1,500 RPD separate bucket, better reasoning
    "gemini-2.0-flash",       # 500 RPD, stable alternative
]

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


def _try_ai_summary_with_model(
    model_name: str,
    task_name: str,
    field_block: str,
    gemini_api_key: str
) -> tuple[str | None, bool]:
    """
    Attempt to generate AI summary with a specific model.

    Args:
        model_name: Gemini model to use (e.g., 'gemini-2.5-flash-lite')
        task_name: Name of the task
        field_block: Formatted field content
        gemini_api_key: Google Gemini API key

    Returns:
        Tuple of (summary_text or None, is_rate_limit_error)
    """
    try:
        configure(api_key=gemini_api_key)
        model = GenerativeModel(model_name)

        prompt = f"""Please provide a concise 1-2 sentence summary of the current status of this task using the available fields, written as if you are the user describing your own work (use first-person voice, e.g., "I completed...", "I need to..."):

Task: {task_name}

Here are the available fields (values may be "(not provided)" when absent):

{field_block}

Focus on the current state and what you have done or need to do. Be specific and actionable. Ignore any fields marked "(not provided)"."""

        config = types.GenerationConfig(
            temperature=0.3,
            max_output_tokens=150,
        )

        response = model.generate_content(
            prompt,
            generation_config=config
        )

        if response and hasattr(response, 'text') and response.text:
            summary = response.text.strip()
            summary = summary.replace('\n', ' ').strip()
            if not summary.endswith('.'):
                summary += '.'
            return summary, False
        else:
            if RICH_AVAILABLE and _console:
                _console.print(f"⚠️ [yellow]Warning: No text response from Gemini API for task: {task_name}[/yellow]")
            else:
                print(f"Warning: No text response from Gemini API for task: {task_name}")
            return None, False

    except Exception as e:
        error_str = str(e)
        is_rate_limit = (
            "429" in error_str or
            "RESOURCE_EXHAUSTED" in error_str or
            "quota" in error_str.lower() or
            "rate limit" in error_str.lower()
        )
        return None, is_rate_limit


def _handle_rate_limit_wait(
    task_name: str,
    attempt: int,
    max_retries: int,
    initial_delay: int,
    progress_pause_callback: Callable[[], None] | None = None
) -> None:
    """
    Handle wait period during rate limit, showing progress to user.

    Args:
        task_name: Name of the task
        attempt: Current attempt number (0-indexed)
        max_retries: Total number of retries allowed
        initial_delay: Base delay in seconds
        progress_pause_callback: Optional callback to pause main progress bars
    """
    exponential_delay = initial_delay * (2 ** attempt)
    retry_delay = exponential_delay

    if progress_pause_callback:
        progress_pause_callback()

    if RICH_AVAILABLE and _console and Progress and TextColumn and BarColumn and TimeRemainingColumn:
        _console.print(f"⏳ [yellow]Rate limit hit. Waiting {retry_delay}s before retry (attempt {attempt + 1}/{max_retries})...[/yellow]")

        with Progress(
            TextColumn("[bold blue]⏱️  Rate limit wait"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=_console,
            transient=True
        ) as progress:
            task = progress.add_task("Waiting...", total=retry_delay)
            for _ in range(retry_delay):
                time.sleep(1)
                progress.update(task, advance=1)

        _console.print("✅ [green]Retry ready - attempting next model tier...[/green]")
    else:
        print(f"Rate limit hit. Waiting {retry_delay}s before retry (attempt {attempt + 1}/{max_retries})...")
        time.sleep(retry_delay)
        print("Retry ready - attempting next model tier...")


def get_ai_summary(
    task_name: str,
    field_entries: Sequence[tuple[str, str]] | Mapping[str, str],
    gemini_api_key: str,
    progress_pause_callback: Callable[[], None] | None = None
) -> SummaryResult:
    """
    Generate a concise 1-2 sentence summary about the current status of the task using Google Gemini AI.
    Automatically handles rate limiting by switching to higher-quota model tiers.

    Args:
        task_name: Name of the task
        field_entries: Iterable of (field label, value) pairs to include in prompt
        gemini_api_key: Google Gemini API key for authentication
        progress_pause_callback: Optional callback to pause/resume main progress bars during rate limit wait

    Returns:
        AI-generated summary or original content if AI fails
    """
    normalized_entries = _normalize_field_entries(field_entries)
    field_block = "\n".join(f"{label}: {value}" for label, value in normalized_entries if label)

    if not field_block:
        return "No content available for summary."

    if not gemini_api_key:
        return field_block

    if GenerativeModel is None or configure is None or types is None:
        if RICH_AVAILABLE and _console:
            _console.print("[yellow]Warning: Google GenAI SDK not available - install with: pip install google-generativeai[/yellow]")
        else:
            print("Warning: Google GenAI SDK not available - install with: pip install google-generativeai")
        return field_block

    # Try each model tier in order, switching on rate limit errors
    for model_tier_idx, model_name in enumerate(MODEL_TIERS):
        max_retries = 2  # Retry same model up to 2 times with exponential backoff
        initial_delay = 1

        for attempt in range(max_retries + 1):
            summary, is_rate_limit = _try_ai_summary_with_model(
                model_name, task_name, field_block, gemini_api_key
            )

            # Success case
            if summary is not None:
                if model_tier_idx > 0:
                    # Log which tier was used
                    if RICH_AVAILABLE and _console:
                        _console.print(f"📝 [cyan]Generated summary using model tier {model_tier_idx + 1}: {model_name}[/cyan]")
                    else:
                        print(f"Generated summary using model tier {model_tier_idx + 1}: {model_name}")
                return summary

            # Rate limit error
            if is_rate_limit:
                if model_tier_idx < len(MODEL_TIERS) - 1:
                    # Switch to next tier instead of retrying current one
                    if RICH_AVAILABLE and _console:
                        _console.print(f"⚠️ [yellow]Rate limit on {model_name}. Switching to next model tier...[/yellow]")
                    else:
                        print(f"Rate limit on {model_name}. Switching to next model tier...")
                    break  # Break retry loop and move to next model tier

                elif attempt < max_retries:
                    # On last tier, try retrying with exponential backoff
                    _handle_rate_limit_wait(task_name, attempt, max_retries, initial_delay, progress_pause_callback)
                    continue

                else:
                    # All tiers and retries exhausted
                    if RICH_AVAILABLE and _console:
                        _console.print(f"❌ [red]Rate limit error on all model tiers. Using fallback content.[/red]")
                    else:
                        print(f"Rate limit error on all model tiers. Using fallback content.")
                    return field_block

            else:
                # Non-rate-limit error on this model, move to next tier
                if model_tier_idx < len(MODEL_TIERS) - 1:
                    if RICH_AVAILABLE and _console:
                        _console.print(f"⚠️ [yellow]Error with {model_name}. Trying next model tier...[/yellow]")
                    else:
                        print(f"Error with {model_name}. Trying next model tier...")
                    break
                else:
                    # Non-retryable error on last tier
                    if RICH_AVAILABLE and _console:
                        _console.print(f"⚠️ [yellow]Unable to generate summary with any model tier. Using fallback content.[/yellow]")
                    else:
                        print(f"Unable to generate summary with any model tier. Using fallback content.")
                    return field_block

    # Fallback (should not reach here, but safety net)
    return field_block
