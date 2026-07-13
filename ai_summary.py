#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Integration Module for ClickUp Task Extractor

Contains:
- AI summary generation using the Google Gemini API
- Rate limiting and retry logic
- Progress bar functionality for wait times
"""

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Callable, Mapping, Sequence, TypeAlias

# Gemini model used for AI summaries.
#
# Must be a published Google model id (see
# https://ai.google.dev/gemini-api/docs/models). The previous value
# "gemini-flash-lite-latest" was not a real model id and returned an
# invalid-model error at runtime. "gemini-2.5-flash-lite" is the GA,
# cost-efficient Flash-Lite tier documented in the README.
#
# Overridable via the GEMINI_MODEL environment variable so the model can be
# bumped without a code change.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

# Claude model used for AI summaries via the local `claude` CLI (headless print
# mode). This path uses the user's Claude Code OAuth / Max subscription rather
# than an API key, so it sidesteps Gemini's free-tier rate limits.
#
# Defaults to Haiku for speed and light subscription usage on short summaries;
# overridable via CLAUDE_SUMMARY_MODEL (accepts a full id or a CLI alias like
# "haiku"/"sonnet"/"opus").
CLAUDE_SUMMARY_MODEL = os.environ.get(
    "CLAUDE_SUMMARY_MODEL", "claude-haiku-4-5-20251001"
)

# System prompt that constrains the CLI to a plain-text, first-person summary
# with no tool use or markdown. Replacing the default system prompt (and
# excluding dynamic sections) also stops the CLI from loading the surrounding
# project's CLAUDE.md/git context, keeping calls fast and clean.
_CLAUDE_SUMMARY_SYSTEM_PROMPT = (
    "You are a task-status summarizer. Given a task's fields, reply with ONLY a "
    "concise 1-2 sentence summary of the task's current status, written in the "
    "first person (e.g. 'I completed...', 'I need to...'). Output plain text "
    "with no markdown, no preamble, and no tool use."
)

# Seconds to allow a single `claude` CLI summary call before giving up.
_CLAUDE_TIMEOUT_SECONDS = int(os.environ.get("CLAUDE_SUMMARY_TIMEOUT", "120"))

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
SummaryResult: TypeAlias = str | None

# Global state for tracking API availability
_api_available = True
_last_error_message = ""

# Global state for the Claude CLI path. Once a usage/rate limit is hit we stop
# calling the CLI for the rest of the run (mirrors Gemini's _api_available),
# since the Max subscription limit won't clear within a single extraction.
# The lock makes the flag flip + one-time message atomic across the concurrent
# summary/ETA workers (several may already be past the entry gate when the
# first failure lands).
_claude_available = True
_claude_missing_warned = False
_claude_state_lock = threading.Lock()

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


def _is_auth_error(error_str: str) -> bool:
    """
    Detect if a Claude CLI error indicates an authentication failure.

    Auth failures ("Not logged in · Please run /login", expired OAuth tokens)
    are terminal for the whole run — unlike transient errors, they cannot
    resolve until the user logs in again.

    Args:
        error_str: Error message string (CLI stderr/stdout)

    Returns:
        True if this is an authentication error, False otherwise
    """
    error_lower = error_str.lower()

    return (
        "not logged in" in error_lower
        or "please run /login" in error_lower
        or "please log in" in error_lower
        or "oauth token has expired" in error_lower
        or "authentication_error" in error_lower
        or "invalid bearer token" in error_lower
    )


def _reset_api_state() -> None:
    """Reset API state (for testing or manual reset)."""
    global _api_available, _last_error_message
    _api_available = True
    _last_error_message = ""


def _reset_claude_state() -> None:
    """Reset Claude CLI availability state (for testing or manual reset)."""
    global _claude_available, _claude_missing_warned
    _claude_available = True
    _claude_missing_warned = False


def _normalize_field_entries(
    field_entries: Sequence[tuple[str, str]] | Mapping[str, str],
) -> list[tuple[str, str]]:
    """Normalize field entries into an ordered list of label/value pairs."""
    if isinstance(field_entries, Mapping):
        return [(str(label), str(value)) for label, value in field_entries.items()]
    return [(str(label), str(value)) for label, value in field_entries]


def _try_ai_summary(
    task_name: str, field_block: str, gemini_api_key: str
) -> tuple[SummaryResult, bool]:
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
        if configure is None or GenerativeModel is None or types is None:
            return None, False

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
            # Don't set _api_available = False here - let get_ai_summary() handle it after retries
            # This allows retries to proceed without skipping
            pass
        else:
            if RICH_AVAILABLE and _console:
                _console.print(f"❌ [red]Error: {error_str[:100]}[/red]")
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
    Pauses progress bars during wait, then resumes them after.

    Args:
        attempt: Current attempt number (0-indexed)
        max_retries: Total number of retries allowed
        initial_delay: Base delay in seconds
        progress_pause_callback: Optional callback to pause main progress bars
    """
    exponential_delay = initial_delay * (2**attempt)
    retry_delay = exponential_delay

    # Pause progress bars during rate limit wait
    if progress_pause_callback:
        progress_pause_callback()

    # Only print once per wait period (not repeatedly)
    if RICH_AVAILABLE and _console:
        _console.print(
            f"⏳ [yellow]Rate limit hit. Waiting {retry_delay}s before retry (attempt {attempt + 1}/{max_retries + 1})...[/yellow]"
        )
    else:
        print(
            f"Rate limit hit. Waiting {retry_delay}s before retry (attempt {attempt + 1}/{max_retries + 1})..."
        )

    time.sleep(retry_delay)

    # Print completion message
    if RICH_AVAILABLE and _console:
        _console.print("✅ [green]Wait complete - retrying API call...[/green]")
    else:
        print("Wait complete - retrying API call...")


def get_ai_summary(
    task_name: str,
    field_entries: Sequence[tuple[str, str]] | Mapping[str, str],
    gemini_api_key: str,
    progress_pause_callback: Callable[[], None] | None = None,
) -> SummaryResult:
    """
    Generate a concise 1-2 sentence summary about the current status of the task using Google Gemini Flash-Latest.
    Includes retry logic with exponential backoff for rate limits.

    Thin wrapper over :func:`get_ai_summary_with_status` for callers that don't
    need to know whether the return is a real AI summary or fallback content.

    Args:
        task_name: Name of the task
        field_entries: Iterable of (field label, value) pairs to include in prompt
        gemini_api_key: Google Gemini API key for authentication
        progress_pause_callback: Optional callback to pause/resume main progress bars during rate limit wait

    Returns:
        AI-generated summary or original content if AI fails
    """
    text, _ = get_ai_summary_with_status(
        task_name, field_entries, gemini_api_key, progress_pause_callback
    )
    return text


def get_ai_summary_with_status(
    task_name: str,
    field_entries: Sequence[tuple[str, str]] | Mapping[str, str],
    gemini_api_key: str,
    progress_pause_callback: Callable[[], None] | None = None,
) -> tuple[SummaryResult, bool]:
    """
    Like :func:`get_ai_summary`, but also reports whether Gemini generated the
    text. Every failure path here returns content (the raw field block) rather
    than None, so callers counting real successes need the flag — issue #160.

    Returns:
        ``(text, generated)`` — ``generated`` is True only when Gemini actually
        produced the summary; False for every fallback (no key, SDK missing,
        rate limit exhausted, non-retryable error, or the rate-limited skip
        where ``text`` is None).
    """
    global _api_available

    # Check if API is currently unavailable due to rate limiting
    if not _api_available:
        if RICH_AVAILABLE and _console:
            _console.print(
                f"[dim][⊘] API rate limited - skipping AI summary for: {task_name}[/dim]"
            )
        # None signals API unavailability (caller will skip this task)
        return None, False

    normalized_entries = _normalize_field_entries(field_entries)
    field_block = "\n".join(
        f"{label}: {value}" for label, value in normalized_entries if label
    )

    if not field_block:
        return "No content available for summary.", False

    if not gemini_api_key:
        return field_block, False

    if GenerativeModel is None or configure is None or types is None:
        if RICH_AVAILABLE and _console:
            _console.print(
                "[yellow]Warning: Google GenAI SDK not available - install with: pip install google-genai[/yellow]"
            )
        else:
            print(
                "Warning: Google GenAI SDK not available - install with: pip install google-genai"
            )
        return field_block, False

    # Try with retries and exponential backoff
    max_retries = 2
    initial_delay = 1

    for attempt in range(max_retries + 1):
        summary, is_rate_limit = _try_ai_summary(task_name, field_block, gemini_api_key)

        # Success case
        if summary is not None:
            return summary, True

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
                return field_block, False
        else:
            # Non-retryable error
            if RICH_AVAILABLE and _console:
                _console.print(
                    "⚠️ [yellow]Unable to generate summary. Using fallback content.[/yellow]"
                )
            else:
                print("Unable to generate summary. Using fallback content.")
            return field_block, False

    # Fallback (should not reach here, but safety net)
    return field_block, False


def claude_cli_available() -> bool:
    """Return True when the `claude` CLI is resolvable on PATH."""
    return shutil.which("claude") is not None


def _subscription_env() -> dict[str, str]:
    """Environment for `claude` subprocesses with the API-key vars scrubbed.

    Forces OAuth/subscription auth (no-op when the vars are absent). Used by
    both the generation calls and the auth-status probe so the probe reports
    the same auth state the generation calls will actually run under — an
    exported ANTHROPIC_API_KEY must not mask a logged-out OAuth state.
    """
    return {
        k: v
        for k, v in os.environ.items()
        if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
    }


def claude_cli_authenticated(timeout: int = 15) -> bool | None:
    """
    Probe ``claude auth status`` for the CLI's login state.

    A cheap pre-flight check (no inference call) so callers can warn the user
    before queueing a run's worth of doomed generation calls.

    Returns:
        True when the CLI reports it is logged in, False when it confidently
        reports it is not, and None when the state is unknown (CLI missing,
        older CLI without the subcommand, timeout, or unparseable output).
        Callers should treat None as "proceed as usual".
    """
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return None

    try:
        proc = subprocess.run(
            [claude_bin, "auth", "status", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=tempfile.gettempdir(),
            env=_subscription_env(),
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

    try:
        payload = json.loads(proc.stdout or "")
    except ValueError:
        return None

    if isinstance(payload, dict) and isinstance(payload.get("loggedIn"), bool):
        return payload["loggedIn"]
    return None


def _disable_claude_once() -> bool:
    """Atomically disable the Claude CLI path; True only for the caller that
    performed the flip. Several concurrent workers can be past run_claude_cli's
    entry gate when the first terminal failure lands — only the first one
    should print the run-wide message."""
    global _claude_available
    with _claude_state_lock:
        was_available = _claude_available
        _claude_available = False
    return was_available


def mark_claude_unavailable() -> None:
    """Disable the Claude CLI path for the rest of the run (e.g. after a
    failed pre-flight auth check). Mirrors the in-run flip in run_claude_cli."""
    _disable_claude_once()


def claude_generation_available() -> bool:
    """Return True while the Claude CLI path is still usable this run."""
    return _claude_available


def _emit(message: str) -> None:
    """Print a message via Rich when available, else plain print."""
    if RICH_AVAILABLE and _console:
        _console.print(message)
    else:
        # Strip Rich markup for the plain fallback.
        import re

        print(re.sub(r"\[/?[^\]]*\]", "", message))


def run_claude_cli(
    prompt: str,
    system_prompt: str,
    *,
    model: str | None = None,
    timeout: int | None = None,
    label: str = "task",
) -> tuple[str | None, bool]:
    """
    Run ``claude -p`` headless and return ``(stdout_text_or_None, usage_limited)``.

    Shared low-level runner for all Claude CLI calls (summaries, ETA, …). It uses
    the user's Claude Code OAuth / Max subscription (no API key), supplies the
    prompt over stdin (avoiding Windows command-line length/quoting limits), runs
    from a temp directory with a replacement system prompt (so the surrounding
    project's context is not loaded and no tools are used), and scrubs
    ``ANTHROPIC_API_KEY`` / ``ANTHROPIC_AUTH_TOKEN`` so the subscription — not the
    API — is billed.

    Honors the global ``_claude_available`` skip flag and flips it off when a
    usage/rate limit or an authentication failure ("Not logged in") is
    detected, so callers in a loop stop issuing new calls — neither condition
    can resolve within a single extraction.

    Args:
        prompt: The user prompt (sent on stdin).
        system_prompt: Replacement system prompt constraining the output.
        model: Model id/alias (defaults to ``CLAUDE_SUMMARY_MODEL``).
        timeout: Per-call timeout in seconds (defaults to ``CLAUDE_SUMMARY_TIMEOUT``).
        label: Short noun used in user-facing messages (e.g. "summary", "ETA").

    Returns:
        ``(text, unavailable)``. ``text`` is the stripped stdout, or ``None`` if
        the CLI is missing, errored, timed out, was usage-limited, not logged
        in, or produced no output. ``unavailable`` is True only when a terminal
        condition was hit (usage/rate limit or auth failure, or one was already
        in effect), signalling callers to stop further calls.
    """
    global _claude_available, _claude_missing_warned, _last_error_message

    if not _claude_available:
        return None, True

    claude_bin = shutil.which("claude")
    if not claude_bin:
        if not _claude_missing_warned:
            _claude_missing_warned = True
            _emit(
                "[yellow]Warning: 'claude' CLI not found on PATH - install Claude Code "
                "or choose a different --ai-source. Using fallback content.[/yellow]"
            )
        return None, False

    cmd = [
        claude_bin,
        "-p",
        "--model",
        model or CLAUDE_SUMMARY_MODEL,
        "--system-prompt",
        system_prompt,
        "--exclude-dynamic-system-prompt-sections",
        "--output-format",
        "text",
    ]

    # Force OAuth/subscription auth: scrub API-key env vars (no-op when absent).
    child_env = _subscription_env()

    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout or _CLAUDE_TIMEOUT_SECONDS,
            cwd=tempfile.gettempdir(),
            env=child_env,
        )
    except subprocess.TimeoutExpired:
        _emit(
            f"⚠️ [yellow]Claude {label} timed out. Using fallback content.[/yellow]"
        )
        return None, False
    except OSError as exc:
        _emit(f"❌ [red]Error launching 'claude' CLI: {str(exc)[:100]}[/red]")
        return None, False

    if proc.returncode != 0:
        error_str = (proc.stderr or proc.stdout or "").strip()
        _last_error_message = error_str[:150]
        if _is_auth_error(error_str):
            if _disable_claude_once():
                _emit(
                    "[red]Claude CLI is not logged in - AI generation will be skipped "
                    "for the rest of this extraction.[/red]\n"
                    "[dim]Fix: run [cyan]claude auth login[/cyan] in a terminal (or "
                    "/login inside Claude Code), then re-run the extractor.[/dim]"
                )
            return None, True
        if _is_rate_limit_error(error_str) or "usage limit" in error_str.lower():
            if _disable_claude_once():
                _emit(
                    "[red]Claude usage limit reached - AI generation will be skipped "
                    "for the rest of this extraction.[/red]"
                )
            return None, True
        _emit(f"❌ [red]Claude CLI error: {error_str[:100]}[/red]")
        return None, False

    text = (proc.stdout or "").strip()
    return (text or None), False


def get_claude_summary(
    task_name: str,
    field_entries: Sequence[tuple[str, str]] | Mapping[str, str],
    progress_pause_callback: Callable[[], None] | None = None,
) -> SummaryResult:
    """
    Generate a concise 1-2 sentence task summary via the local ``claude`` CLI.

    Thin wrapper over :func:`run_claude_cli` (which handles OAuth/subscription
    auth, isolation, and usage-limit detection).

    Args:
        task_name: Name of the task.
        field_entries: Iterable of (field label, value) pairs to summarize.
        progress_pause_callback: Optional callback to pause/resume progress bars
            (unused for now; accepted for parity with get_ai_summary()).

    Returns:
        The summary string, or None if the CLI is unavailable, errors, hits a
        usage limit, or returns no text (callers fall back to base content).
    """
    normalized_entries = _normalize_field_entries(field_entries)
    field_block = "\n".join(
        f"{label}: {value}" for label, value in normalized_entries if label
    )
    if not field_block:
        return "No content available for summary."

    prompt = f"""Summarize the current status of this task in 1-2 first-person sentences.

Task: {task_name}

Here are the available fields (ignore any marked "(not provided)"):

{field_block}

Focus on what I have done or still need to do. Be specific and actionable. Output only the summary sentence(s)."""

    text, _ = run_claude_cli(
        prompt, _CLAUDE_SUMMARY_SYSTEM_PROMPT, label="summary"
    )
    if not text:
        return None

    summary = text.replace("\n", " ").strip()
    if not summary.endswith("."):
        summary += "."
    return summary
