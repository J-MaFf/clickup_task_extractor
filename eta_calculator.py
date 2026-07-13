#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ETA Calculator Module for ClickUp Task Extractor

Contains:
- AI-powered ETA calculation for tasks without due dates
- Priority and status-based logic for ETA estimation
- Fallback mechanisms for when AI is unavailable
"""

import os
from datetime import datetime, timedelta
from typing import TypeAlias

from ai_summary import run_claude_cli
from config import AISource

# Rich console imports for beautiful output
try:
    from rich.console import Console

    _console = Console(force_terminal=None, legacy_windows=False)
    RICH_AVAILABLE = True
except ImportError:
    _console = None
    RICH_AVAILABLE = False

# Google GenAI SDK imports (google.genai)
try:
    from google import genai as _genai  # type: ignore
    from google.genai import types as _genai_types  # type: ignore

    _genai_client = None

    def configure(api_key: str) -> None:
        """Configure a shared Google GenAI client."""

        global _genai_client
        _genai_client = _genai.Client(api_key=api_key)

    class GenerativeModel:
        """Compatibility wrapper matching legacy GenerativeModel usage."""

        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def generate_content(self, prompt: str, generation_config=None):
            if _genai_client is None:
                raise RuntimeError("Google GenAI client is not configured")
            return _genai_client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=generation_config,
            )

    class _TypesNamespace:
        GenerationConfig = _genai_types.GenerateContentConfig

    types = _TypesNamespace()
except ImportError:
    configure = None
    GenerativeModel = None
    types = None

# Type aliases
ETAResult: TypeAlias = str

# AI Model configuration.
# Must be a published Google model id. The previous "gemini-flash-lite-latest"
# was not a real model id; "gemini-2.5-flash-lite" is the GA Flash-Lite tier.
# Overridable via the GEMINI_MODEL environment variable.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

# System prompt constraining the Claude CLI to emit only an MM/DD/YYYY date.
_CLAUDE_ETA_SYSTEM_PROMPT = (
    "You estimate a single realistic completion date (ETA) for a task. Reply with "
    "ONLY a date in MM/DD/YYYY format and nothing else — no words, no markdown, "
    "no tool use."
)

# Priority-based default ETA offsets (in days)
PRIORITY_ETA_DAYS = {
    "Urgent": 1,  # 1 day for urgent tasks
    "High": 3,  # 3 days for high priority
    "Normal": 7,  # 1 week for normal priority
    "Low": 14,  # 2 weeks for low priority
    "": 7,  # Default to 1 week if no priority
}

# Status-based ETA adjustments (multipliers)
STATUS_ETA_MULTIPLIER = {
    "in progress": 0.5,  # Reduce ETA by half if already in progress
    "investigating": 0.75,  # Slightly reduce if investigating
    "to do": 1.0,  # No adjustment for to-do
    "": 1.0,  # Default multiplier
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
        if configure is None or GenerativeModel is None or types is None:
            return None

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

        context = (
            "\n".join(context_parts)
            if context_parts
            else "No additional context provided"
        )

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


def _extract_date_token(text: str) -> str | None:
    """Pull a validated M/D/YYYY date out of free text, else None.

    Every candidate token is strptime-validated before being returned, so a
    caller never receives a value the sorter (config.parse_eta) and the sheet
    can't parse as a date — a model reply like ``"12/25/2026."`` (trailing
    punctuation) is salvaged, ``"12/25/26"`` (2-digit year) is normalized to
    four digits, and anything unparseable is rejected rather than passed
    through to overwrite a valid deterministic baseline.
    """
    if not text:
        return None
    candidates = [
        part for part in text.split() if "/" in part and any(ch.isdigit() for ch in part)
    ]
    if not candidates and "/" in text and any(ch.isdigit() for ch in text):
        candidates = [text.strip()]
    for raw in candidates:
        token = raw.strip().strip(".,;:!?()[]{}'\"")
        try:
            datetime.strptime(token, "%m/%d/%Y")
            return token
        except ValueError:
            pass
        try:
            parsed = datetime.strptime(token, "%m/%d/%y")
        except ValueError:
            continue
        from config import format_datetime

        return format_datetime(parsed, "%m/%d/%Y")
    return None


def get_claude_eta(
    task_name: str,
    priority: str,
    status: str,
    description: str = "",
    subject: str = "",
    resolution: str = "",
) -> str | None:
    """
    Estimate an ETA date (MM/DD/YYYY) via the local ``claude`` CLI.

    Uses the shared :func:`ai_summary.run_claude_cli` runner (OAuth/Max
    subscription, no API key; honors the global usage-limit skip flag).

    Returns:
        A date string like ``"12/25/2026"``, or None if the CLI is unavailable,
        errors, hits a usage limit, or returns an unparseable response.
    """
    context_parts = []
    if subject:
        context_parts.append(f"Subject: {subject}")
    if description:
        context_parts.append(f"Description: {description}")
    if resolution:
        context_parts.append(f"Resolution: {resolution}")
    context = (
        "\n".join(context_parts) if context_parts else "No additional context provided"
    )
    today = datetime.now().strftime("%m/%d/%Y")

    prompt = f"""Estimate a realistic completion date (ETA) for this task.

Today's date: {today}

Task: {task_name}
Priority: {priority}
Status: {status}

Context:
{context}

Guidelines: Urgent within 1-2 days; High within 3-5 days; Normal within ~1 week;
Low within ~2 weeks. Tasks already "in progress" or "investigating" may finish
sooner; complex issues may need more time. Respond with ONLY a date in
MM/DD/YYYY format."""

    text, _ = run_claude_cli(prompt, _CLAUDE_ETA_SYSTEM_PROMPT, label="ETA")
    if not text:
        return None

    eta = _extract_date_token(text)
    if eta is None and RICH_AVAILABLE and _console:
        _console.print(f"[yellow]⚠️ Claude returned an unparseable ETA: {text[:60]}[/yellow]")
    return eta


def _source_value(ai_source) -> str | None:
    """Normalize an AISource enum / string / None to its string value."""
    if ai_source is None:
        return None
    if isinstance(ai_source, AISource):
        return ai_source.value
    return str(ai_source)


def calculate_eta(
    task_name: str,
    priority: str,
    status: str,
    description: str = "",
    subject: str = "",
    resolution: str = "",
    gemini_api_key: str | None = None,
    enable_ai: bool = False,
    ai_source=None,
) -> str:
    """
    Calculate ETA for a task without a due date.

    Thin wrapper over :func:`calculate_eta_with_source` for callers that don't
    need to know whether the AI or the deterministic fallback produced the
    date. See that function for the full strategy.

    Returns:
        Formatted ETA date string (MM/DD/YYYY)
    """
    eta, _ = calculate_eta_with_source(
        task_name,
        priority,
        status,
        description=description,
        subject=subject,
        resolution=resolution,
        gemini_api_key=gemini_api_key,
        enable_ai=enable_ai,
        ai_source=ai_source,
    )
    return eta


def calculate_eta_with_source(
    task_name: str,
    priority: str,
    status: str,
    description: str = "",
    subject: str = "",
    resolution: str = "",
    gemini_api_key: str | None = None,
    enable_ai: bool = False,
    ai_source=None,
) -> tuple[str, bool]:
    """
    Calculate ETA for a task without a due date, reporting how it was produced.

    Strategy, in order:
    1. AI-based estimate (when ``enable_ai``), routed by ``ai_source``:
       - Claude / Both (and the default when unspecified) → local ``claude`` CLI
         (OAuth/Max, no key).
       - Gemini → Google Gemini API (requires ``gemini_api_key``).
       - ClickUp → no AI ETA (ClickUp has no ETA field); use the fallback.
    2. Deterministic fallback based on priority and status.

    Args:
        task_name: Name of the task
        priority: Task priority (Urgent, High, Normal, Low)
        status: Current task status
        description: Task description (optional)
        subject: Task subject (optional)
        resolution: Resolution notes (optional)
        gemini_api_key: Google Gemini API key (optional; only for the Gemini source)
        enable_ai: Whether to attempt AI-based calculation
        ai_source: AISource enum/string selecting the provider (defaults to Claude)

    Returns:
        ``(eta, used_ai)`` — the formatted ETA date string (MM/DD/YYYY) and True
        when an AI provider produced it, False for the deterministic fallback
        (so callers can report generated-vs-fallback counts accurately).
    """
    if enable_ai:
        source = _source_value(ai_source)

        # Claude is the default generative source and Both's fallback.
        if source in (None, AISource.CLAUDE.value, AISource.BOTH.value):
            claude_eta = get_claude_eta(
                task_name, priority, status, description, subject, resolution
            )
            if claude_eta:
                return claude_eta, True
        # Gemini path (explicit source + key + SDK available).
        elif source == AISource.GEMINI.value:
            if (
                gemini_api_key
                and GenerativeModel is not None
                and configure is not None
                and types is not None
            ):
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
                    return ai_eta, True
        # AISource.CLICKUP (or any failure) falls through to the deterministic ETA.

        if RICH_AVAILABLE and _console:
            _console.print(
                f"[dim]Using fallback ETA calculation for: {task_name}[/dim]"
            )

    # Fallback calculation based on priority and status
    return _get_fallback_eta(priority, status), False
