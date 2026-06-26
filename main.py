#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Entry Point and CLI Module for ClickUp Task Extractor

Contains:
- main() function with CLI argument parsing
- Virtual environment switching logic
- Application orchestration
- Authentication chain management
"""

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime

# Rich imports for beautiful console output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    print("Error: The 'rich' library is required but not installed.")
    print("Please install it using: pip install -r requirements.txt")
    print("Or install just rich: pip install rich>=10.0.0")
    sys.exit(1)

# Import project modules
from ai_summary import claude_cli_available
from auth import load_secret_with_fallback
from config import (
    ClickUpConfig,
    TIMESTAMP_FORMAT,
    DateFilter,
    OutputFormat,
    AISource,
    format_datetime,
    CLICKUP_AI_SUMMARY_FIELD_ID,
    CLICKUP_API_SECRET_REFERENCE,
    GEMINI_API_SECRET_REFERENCE,
)
from logger_config import setup_logging
from mappers import get_choice_input, get_yes_no_input
from version import __description__, __version__

# Lazily imported runtime dependencies.
# These are loaded in main() to make startup resilient when VS Code's
# "Run Python File" interrupts a reused terminal process.
ClickUpAPIClient = None
ClickUpTaskExtractor = None


def _load_runtime_dependencies() -> tuple:
    """Import runtime dependencies only when needed.

    Returns:
        tuple: (ClickUpAPIClient class, ClickUpTaskExtractor class)

    Raises:
        ImportError: If runtime dependencies cannot be loaded
    """
    try:
        from api_client import ClickUpAPIClient as _ClickUpAPIClient
        from extractor import ClickUpTaskExtractor as _ClickUpTaskExtractor

        return _ClickUpAPIClient, _ClickUpTaskExtractor
    except ImportError as e:
        console.print(
            Panel(
                f"[red]Error loading runtime dependencies: {e}[/red]\n"
                "[yellow]Please ensure all dependencies are installed:[/yellow]\n"
                "[dim]pip install -r requirements.txt[/dim]",
                title="Import Error",
                style="red",
            )
        )
        raise


def _configure_stdio_encoding() -> None:
    """Use UTF-8 for stdio when supported to avoid Windows cp1252 encode failures."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                # Some stream wrappers do not allow reconfiguration.
                continue


# Initialize Rich console with proper encoding for cross-platform compatibility.
# This ensures proper rendering on Windows, macOS, and Linux. Constructing a
# Console is a side-effect-free object instantiation (no I/O, no subprocess),
# so it is safe to do at import time and lets the module's helper functions
# reference `console` as a module global.
console = Console(force_terminal=True, legacy_windows=False)

# Logging is configured lazily in main() rather than at import time, because
# setup_logging() mutates the shared "clickup_extractor" logger (clearing and
# re-adding handlers) and may open a file handler — side effects that should
# not fire merely from importing this module (e.g. under test/tooling).
logger = None


def _load_dotenv(env_path: str | None = None) -> None:
    """Load KEY=VALUE pairs from a project-local ``.env`` into ``os.environ``.

    Called from the ``__main__`` guard before the re-exec helpers and before
    ``main()`` reads ``CLICKUP_WORKSPACE_NAME`` / ``CLICKUP_SPACE_NAME`` /
    ``OP_ENVIRONMENT_ID`` / API keys, so those settings apply without relying on
    the shell or IDE having inherited them. It only runs on real CLI execution
    (never on import), so tests are unaffected.

    Precedence: real environment variables win — an already-set key is never
    overwritten. Dependency-free; supports blank lines, ``#`` comments, an
    optional ``export `` prefix, and single/double-quoted values.

    Args:
        env_path: Path to the .env file; defaults to ``.env`` next to this script.
    """
    if env_path is None:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return  # No .env present — nothing to load.
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _reexec_in_venv() -> None:
    """Re-launch this script under the project's virtualenv interpreter.

    No-op when already running from the venv or when the venv does not exist.
    Called only from the ``__main__`` guard so that importing this module
    (for tests/tooling) never triggers a process re-exec or re-exec loop.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.name == "nt":
        venv_python = os.path.join(script_dir, ".venv", "Scripts", "python.exe")
    else:
        venv_python = os.path.join(script_dir, ".venv", "bin", "python")

    if not sys.executable.lower().startswith(
        os.path.join(script_dir, ".venv").lower()
    ) and os.path.exists(venv_python):
        print(f"Switching from {sys.executable} to virtual environment: {venv_python}")
        # Re-execute the script with the virtual environment Python
        sys.exit(subprocess.call([venv_python] + sys.argv))


def _op_run_environments_flag():
    """Return the flag `op run` accepts for 1Password Environments, else None.

    The Environments feature ships only in beta builds of the 1Password CLI;
    stable releases (e.g. 2.34.x) reject the flag with "unknown flag" and exit
    non-zero, which would abort the re-exec before the normal auth chain runs.
    Probe the fast, auth-free ``op run --help`` output so we re-exec only when
    the installed CLI actually supports it. Prefer the documented plural
    ``--environments``; accept the singular spelling for compatibility.
    """
    try:
        proc = subprocess.run(
            ["op", "run", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    help_text = (proc.stdout or "") + (proc.stderr or "")
    for flag in ("--environments", "--environment"):
        if flag in help_text:
            return flag
    return None


def _reexec_under_op_run() -> None:
    """Re-launch under 'op run --environments' to inject 1Password secrets.

    When OP_ENVIRONMENT_ID is set, the 1Password CLI beta hangs when called
    from Python subprocess with any handle redirection (STARTF_USESTDHANDLES
    strips console attachment, which op requires for authentication). Using
    subprocess.call (no handle redirection) lets op authenticate and inject
    env vars into the child process, where os.environ picks them up directly.

    The Environments flag is beta-only, so this re-exec is gated on
    ``_op_run_environments_flag()``: on a stable CLI that lacks the flag we
    skip the re-exec and fall through to the SDK-based auth chain in auth.py
    rather than crashing on an unknown flag.

    A sentinel env var (_OP_RUN_INJECTED) prevents re-exec loops in case
    CLICKUP_API_KEY is not defined in the 1Password environment.
    """
    if os.environ.get("_OP_RUN_INJECTED") or os.environ.get("CLICKUP_API_KEY"):
        return
    environment_id = os.environ.get("OP_ENVIRONMENT_ID")
    if not environment_id:
        return
    import shutil
    if not shutil.which("op"):
        return
    op_env_flag = _op_run_environments_flag()
    if not op_env_flag:
        # Stable `op` builds lack the Environments feature; don't re-exec into a
        # flag the CLI will reject. Fall through to the normal auth chain, which
        # resolves OP_ENVIRONMENT_ID via the 1Password SDK (DesktopAuth /
        # service token) in auth.py instead.
        return
    # Preserve terminal dimensions so Rich renders correctly in the child
    # process. op run on Windows doesn't propagate console size to its child,
    # causing Rich to fall back to the 80-column default and strip color markup.
    if "COLUMNS" not in os.environ:
        cols, lines = shutil.get_terminal_size(fallback=(0, 0))
        if cols:
            os.environ["COLUMNS"] = str(cols)
        if lines:
            os.environ["LINES"] = str(lines)
    os.environ["_OP_RUN_INJECTED"] = "1"
    sys.exit(subprocess.call(
        ["op", "run", op_env_flag, environment_id, "--", sys.executable] + sys.argv
    ))


def main():
    """
    Entrypoint for ClickUp Task Extractor.
    Supports CLI args for config overrides. Example:
      python ClickUpTaskExtractor.py --api-key ... --workspace ... --space ...

    Authentication priority (for API keys):
    1. --api-key command line argument
    2. CLICKUP_API_KEY environment variable
    3. 1Password Environment (requires OP_ENVIRONMENT_ID env var)
    4. 1Password SDK (requires OP_SERVICE_ACCOUNT_TOKEN env var)
    5. 1Password CLI fallback (requires 'op' command and desktop app)
    6. Manual input prompt

    1Password Environment setup:
    - Create an Environment in 1Password desktop app (Developer > View Environments)
    - Add variable: CLICKUP_API_KEY = your ClickUp API key
    - Copy Environment ID and set: export OP_ENVIRONMENT_ID=<environment_id>
    """
    global logger
    # Configure logging on first entry into main() rather than at import time.
    if logger is None:
        logger = setup_logging(logging.INFO, use_rich=True)

    try:
        _ClickUpAPIClient, _ClickUpTaskExtractor = _load_runtime_dependencies()
    except (KeyboardInterrupt, ImportError):
        # VS Code's Run Python File may reuse a terminal and emit Ctrl+C once.
        # Retry one time so startup does not fail from a transient interrupt.
        if isinstance(sys.exc_info()[1], KeyboardInterrupt):
            console.print(
                "[yellow]Startup interrupted while loading dependencies. Retrying once...[/yellow]"
            )
            try:
                _ClickUpAPIClient, _ClickUpTaskExtractor = _load_runtime_dependencies()
            except (KeyboardInterrupt, ImportError) as e:
                console.print(f"[red]Failed to load dependencies: {e}[/red]")
                sys.exit(1)
        else:
            raise

    # Beautiful header
    header_text = Text()
    header_text.append("ClickUp Task Extractor", style="bold blue")
    header_text.append(f" v{__version__}", style="dim blue")
    header_text.append(" [TASKS]", style="dim blue")

    console.print(
        Panel(
            header_text,
            subtitle="Extract, process, and export ClickUp tasks with style!",
            style="blue",
            border_style="bright_blue",
        )
    )

    parser = argparse.ArgumentParser(
        description=f"ClickUp Task Extractor v{__version__} - {__description__}\n\nExtract and export ClickUp tasks to Markdown (default) or HTML. The workspace and space are configured via --workspace/--space or the CLICKUP_WORKSPACE_NAME/CLICKUP_SPACE_NAME environment variables.\nAPI keys can be provided via: 1Password Environment (OP_ENVIRONMENT_ID), environment variables (CLICKUP_API_KEY), or command-line arguments.\n\n1Password Environment Setup: Developer > View Environments > Create new > Add CLICKUP_API_KEY variable > Copy Environment ID > export OP_ENVIRONMENT_ID=<id>",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"ClickUp Task Extractor v{__version__}"
    )
    parser.add_argument(
        "--environment-id",
        type=str,
        default=os.environ.get("OP_ENVIRONMENT_ID"),
        help="1Password Environment ID (or set OP_ENVIRONMENT_ID env var). Automatically tries to load CLICKUP_API_KEY and GEMINI_API_KEY from the Environment.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.environ.get("CLICKUP_API_KEY"),
        help="ClickUp API Key (or set CLICKUP_API_KEY env var). Falls back to 1Password Environment or 1Password SDK (requires OP_SERVICE_ACCOUNT_TOKEN).",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        help="Workspace name (overrides the CLICKUP_WORKSPACE_NAME env var)",
    )
    parser.add_argument(
        "--space",
        type=str,
        help="Space name (overrides the CLICKUP_SPACE_NAME env var)",
    )
    parser.add_argument(
        "--list", type=str, help="Optional list name to extract from within the space"
    )
    parser.add_argument(
        "--output", type=str, help="Output file path (default: auto-generated)"
    )
    parser.add_argument(
        "--include-completed",
        action="store_true",
        help="Include completed/archived tasks",
    )
    parser.add_argument(
        "--date-filter",
        type=str,
        choices=["AllOpen", "ThisWeek", "LastWeek"],
        help="Date filter",
    )
    parser.add_argument(
        "--ai-summary",
        action="store_true",
        help="Enable AI summary (defaults to the Claude source, which needs no API key; Gemini source auto-loads a key from 1Password Environment/SDK if available)",
    )
    parser.add_argument(
        "--ai-source",
        type=str,
        choices=["Both", "ClickUp", "Gemini", "Claude"],
        help=(
            "AI summary source: Claude (default; uses the local 'claude' CLI via "
            "your Claude Max OAuth - no API key, no Gemini quota), Gemini (Google "
            "API key), ClickUp (the task's Summary field only), or Both (ClickUp "
            "field first, then Claude). Default: Claude"
        ),
    )
    parser.add_argument(
        "--ai-clickup-field-id",
        type=str,
        help="Custom field ID for ClickUp AI summary (default: Summary field)",
    )
    parser.add_argument(
        "--gemini-api-key",
        type=str,
        help="Google Gemini API key for AI summary generation (or auto-load from 1Password Environment via GEMINI_API_KEY variable or 1Password SDK)",
    )
    parser.add_argument(
        "--output-format",
        type=str,
        choices=["CSV", "HTML", "Markdown"],
        help="Output format: CSV, HTML, or Markdown - default: Markdown",
    )
    parser.add_argument(
        "--interactive", action="store_true", help="Enable interactive task selection"
    )
    args = parser.parse_args()

    # The 1Password secret reference for the API key is configured via the
    # CLICKUP_API_SECRET_REFERENCE environment variable (config module). It is
    # empty by default so no personal vault path is baked into source.
    api_key = args.api_key or os.environ.get("CLICKUP_API_KEY")

    if not api_key:
        # Try to get API key from 1Password with fallback
        is_frozen = getattr(sys, "frozen", False)
        environment_id = os.environ.get("OP_ENVIRONMENT_ID")

        # Build informative authentication panel message
        auth_msg = (
            "[yellow]🔐 Attempting to load ClickUp API key from 1Password...[/yellow]\n"
        )
        if environment_id:
            auth_msg += f"[dim]Environment ID: {environment_id}[/dim]\n"
            auth_msg += (
                "[dim]Method: 1Password Environment (SDK/DesktopAuth or CLI beta)[/dim]"
            )
            auth_msg += "\n[dim]SDK auth can use OP_ACCOUNT_NAME; automation can use OP_SERVICE_ACCOUNT_TOKEN[/dim]"
        else:
            auth_msg += "[dim]Methods: 1Password SDK, then 1Password CLI[/dim]\n"
            auth_msg += "[dim]💡 Tip: Set OP_ENVIRONMENT_ID for 1Password Environment auth[/dim]"

        if is_frozen:
            auth_msg += "\n[dim]Note: Executable version uses 1Password CLI only (SDK not available)[/dim]"

        console.print(
            Panel(
                auth_msg,
                title="Authentication",
                style="yellow",
            )
        )
        secret_reference = CLICKUP_API_SECRET_REFERENCE
        # The Environment path inside load_secret_with_fallback() is keyed on
        # OP_ENVIRONMENT_ID and needs no op:// reference. Attempt the lookup
        # whenever a secret reference is configured OR an Environment ID is set;
        # gating on secret_reference alone skipped Environment auth entirely for
        # the recommended OP_ENVIRONMENT_ID-only setup.
        if secret_reference or environment_id:
            api_key = load_secret_with_fallback(secret_reference, "ClickUp API key")
        if not api_key:
            if is_frozen:
                console.print(
                    Panel(
                        "[red][FAIL] Could not load API key from 1Password.[/red]\n\n"
                        "[yellow]For executable users, we recommend:[/yellow]\n"
                        "  • Set environment variable: [cyan]CLICKUP_API_KEY=your_key[/cyan]\n"
                        "  • Or use command line: [cyan]--api-key your_key[/cyan]\n"
                        "  • Or install 1Password CLI: [cyan]https://developer.1password.com/docs/cli/[/cyan]",
                        title="Authentication Failed",
                        style="red",
                    )
                )
            else:
                help_msg = "[red][FAIL] Could not load API key from 1Password.[/red]\n\n[yellow]Options:[/yellow]\n"
                help_msg += "  • Set environment variable: [cyan]CLICKUP_API_KEY=your_key[/cyan]\n"
                help_msg += "  • Or use: [cyan]--api-key your_key[/cyan]\n"
                if environment_id:
                    help_msg += f"  • Check 1Password Environment: [cyan]{environment_id}[/cyan] has [cyan]CLICKUP_API_KEY[/cyan] variable\n"
                    help_msg += "  • For SDK auth, you can set [cyan]OP_ACCOUNT_NAME[/cyan] to target a specific account\n"
                    help_msg += "  • For automation, set [cyan]OP_SERVICE_ACCOUNT_TOKEN[/cyan]\n"
                    help_msg += "  • For CLI auth, upgrade to a beta 1Password CLI that supports [cyan]op run --environments[/cyan]\n"
                help_msg += "  • Verify 1Password CLI is installed and your account is signed in"
                console.print(
                    Panel(
                        help_msg,
                        title="Authentication Failed",
                        style="red",
                    )
                )

    # If still no API key, prompt for manual input
    if not api_key:
        api_key = console.input("[bold cyan]🔑 Enter ClickUp API Key: [/bold cyan]")

    # Load Gemini API key if AI summary is enabled and no key provided via CLI
    gemini_api_key = args.gemini_api_key

    # Function to load Gemini API key when needed
    def load_gemini_api_key():
        nonlocal gemini_api_key
        if gemini_api_key:
            return True  # Already have the key

        # Check env var directly — op run --environments injects GEMINI_API_KEY
        # into os.environ, and load_secret_with_fallback would hang on Windows
        # trying op environment read from subprocess.
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if gemini_api_key:
            return True

        # Try to get Gemini API key from 1Password with fallback. The secret
        # reference comes from GEMINI_API_SECRET_REFERENCE (config module) and is
        # empty by default so no personal vault path is baked into source.
        gemini_secret_reference = GEMINI_API_SECRET_REFERENCE
        # As with the ClickUp key, the Environment lookup is keyed on
        # OP_ENVIRONMENT_ID and needs no op:// reference. Attempt it when either
        # is configured (compute the ID locally — this nested function can run
        # even when the enclosing api_key branch was skipped).
        if gemini_secret_reference or os.environ.get("OP_ENVIRONMENT_ID"):
            gemini_api_key = load_secret_with_fallback(
                gemini_secret_reference, "Gemini API key"
            )
        if gemini_api_key:
            return True
        else:
            console.print("Please provide via --gemini-api-key.")
            return False

    def ai_source_includes_gemini(source_value: str | None) -> bool:
        # Only the Gemini source needs a Google API key. The default (Claude) and
        # Both (ClickUp field -> Claude) sources use the keyless claude CLI.
        try:
            src = AISource(source_value) if source_value else AISource.CLAUDE
        except ValueError:
            src = AISource.CLAUDE
        return src == AISource.GEMINI

    # If AI summary flag was explicitly used, load the key now when Gemini is required
    if (
        args.ai_summary
        and ai_source_includes_gemini(args.ai_source)
        and not gemini_api_key
    ):
        if not load_gemini_api_key():
            # If still no Gemini API key and AI summary is enabled, prompt for manual input
            gemini_api_key = console.input(
                "🤖 [bold cyan]Enter Gemini API Key (or press Enter to disable AI summary): [/bold cyan]"
            )
            if not gemini_api_key:
                console.print(
                    "[yellow]⚠️  No Gemini API key provided. AI summary will be disabled.[/yellow]"
                )
                args.ai_summary = False

    # Check if interactive mode should be enabled when not explicitly set
    interactive_mode = args.interactive
    if not interactive_mode:
        console.print("\n[bold blue][SEARCH] Interactive Mode[/bold blue]")
        console.print(
            "Interactive mode allows you to review and select which tasks to export."
        )
        console.print(
            "Without interactive mode, all tasks will be automatically exported."
        )
        interactive_mode = get_yes_no_input(
            "Would you like to run in interactive mode? (y/n): "
        )
        if interactive_mode:
            console.print(
                "[OK] [green]Interactive mode enabled[/green] - you'll be able to review each task before export."
            )
        else:
            console.print(
                "[RUN] [green]Running in automatic mode[/green] - all tasks will be exported."
            )

    # Ask about AI summary right after interactive mode (regardless of mode chosen)
    if not args.ai_summary:
        console.print("\n[bold blue]🤖 AI Summary[/bold blue]")
        console.print(
            "AI summary can generate concise 1-2 sentence summaries of task status. "
            "By default this uses Claude via your Max subscription (no API key); "
            "Gemini and the ClickUp Summary field are also available."
        )
        if get_yes_no_input("Would you like to enable AI summaries for tasks? (y/n): "):
            args.ai_summary = True
            if not args.ai_source:
                console.print(
                    "Select which AI to use. Claude is option 1 (default; uses your "
                    "Claude Max subscription, no API key), Gemini is option 2, "
                    "ClickUp AI is option 3, and Both (ClickUp field then Claude) is "
                    "option 4."
                )
                ai_source_choice = get_choice_input(
                    "Choose AI source (1-4) [default: Claude]: ",
                    [
                        AISource.CLAUDE.value,
                        AISource.GEMINI.value,
                        AISource.CLICKUP.value,
                        AISource.BOTH.value,
                    ],
                    default_index=0,
                )
                args.ai_source = ai_source_choice

            if ai_source_includes_gemini(args.ai_source):
                if not load_gemini_api_key():
                    gemini_api_key = console.input(
                        "[bold cyan]🤖 Enter Gemini API Key (or press Enter to disable AI summary): [/bold cyan]"
                    )
                    if not gemini_api_key:
                        console.print(
                            "[yellow]⚠️  No Gemini API key provided. AI summary will be disabled.[/yellow]"
                        )
                        args.ai_summary = False
                    else:
                        console.print(
                            "✅ [green]AI summary enabled with manual API key.[/green]"
                        )
                else:
                    console.print(
                        "✅ [green]AI summary enabled with Gemini.[/green]"
                    )
            else:
                console.print(
                    f"✅ [green]AI summary enabled using {args.ai_source or AISource.CLAUDE.value}.[/green]"
                )
        else:
            console.print("✅ [green]AI summary disabled.[/green]")

    # Ask about output format if not explicitly set via CLI
    if not args.output_format:
        console.print("\n[bold blue]📄 Output Format[/bold blue]")
        console.print("Choose the format for your exported task list:")
        console.print("  • [cyan]CSV[/cyan] - Spreadsheet-friendly table output")
        console.print("  • [cyan]HTML[/cyan] - Rich formatted web page with styling")
        console.print("  • [cyan]Markdown[/cyan] - Lightweight markup format")

        format_choices = ["Markdown", "HTML", "CSV"]
        selected_format = get_choice_input(
            "Enter your choice (1-3) or format name [default: Markdown]: ",
            format_choices,
            default_index=0,
        )
        args.output_format = selected_format
        console.print(f"✅ [green]Output format set to: {selected_format}[/green]")

    # Convert string values to enums with fallback
    date_filter = DateFilter.ALL_OPEN
    if args.date_filter:
        try:
            date_filter = DateFilter(args.date_filter)
        except ValueError:
            # Fallback for old string values
            date_filter_map = {
                "AllOpen": DateFilter.ALL_OPEN,
                "ThisWeek": DateFilter.THIS_WEEK,
                "LastWeek": DateFilter.LAST_WEEK,
            }
            date_filter = date_filter_map.get(args.date_filter, DateFilter.ALL_OPEN)

    output_format = OutputFormat.MARKDOWN
    if args.output_format:
        try:
            output_format = OutputFormat(args.output_format)
        except ValueError:
            # Fallback for old string values
            output_format_map = {
                "CSV": OutputFormat.CSV,
                "HTML": OutputFormat.HTML,
                "Markdown": OutputFormat.MARKDOWN,
            }
            output_format = output_format_map.get(
                args.output_format, OutputFormat.MARKDOWN
            )

    ai_source = AISource.CLAUDE
    if args.ai_source:
        try:
            ai_source = AISource(args.ai_source)
        except ValueError:
            ai_source = AISource.CLAUDE

    # The Claude source (and Both's fallback) shells out to the local `claude`
    # CLI. Warn early if it isn't installed so the user understands why summaries
    # may fall back to raw field content.
    if (
        args.ai_summary
        and ai_source in (AISource.CLAUDE, AISource.BOTH)
        and not claude_cli_available()
    ):
        console.print(
            Panel(
                "[yellow]⚠️  The 'claude' CLI was not found on PATH.[/yellow]\n"
                "[dim]The Claude AI source needs Claude Code installed and signed in "
                "(Max/Pro OAuth). Without it, summaries fall back to raw task content.[/dim]\n"
                "[dim]Install: https://docs.claude.com/en/docs/claude-code  •  "
                "or use [cyan]--ai-source Gemini[/cyan] with a Google API key.[/dim]",
                title="Claude CLI Not Found",
                style="yellow",
            )
        )

    ai_clickup_field_id = args.ai_clickup_field_id or CLICKUP_AI_SUMMARY_FIELD_ID

    config = ClickUpConfig(
        api_key=api_key,
        # Read the env vars here (not config's import-time defaults) so values
        # loaded from .env by _load_dotenv() in the __main__ guard take effect.
        workspace_name=args.workspace or os.environ.get("CLICKUP_WORKSPACE_NAME", ""),
        space_name=args.space or os.environ.get("CLICKUP_SPACE_NAME", ""),
        list_name=args.list,
        output_path=args.output
        or f"output/WeeklyTaskList_{format_datetime(datetime.now(), TIMESTAMP_FORMAT)}.md",
        include_completed=args.include_completed,
        date_filter=date_filter,
        enable_ai_summary=args.ai_summary,
        gemini_api_key=gemini_api_key,
        ai_source=ai_source,
        ai_clickup_field_id=ai_clickup_field_id,
        output_format=output_format,
        interactive_selection=interactive_mode,
    )

    # Display beautiful configuration summary
    config_table = Table(
        title="⚙️ Configuration Summary", show_header=True, header_style="bold cyan"
    )
    config_table.add_column("Setting", style="blue", no_wrap=True)
    config_table.add_column("Value", style="green")

    config_table.add_row("Workspace", config.workspace_name)
    config_table.add_row("Space", config.space_name)
    if config.list_name:
        config_table.add_row("List", config.list_name)
    config_table.add_row("Output Format", config.output_format.value)
    config_table.add_row("Date Filter", config.date_filter.value)
    config_table.add_row(
        "Include Completed", "[OK] Yes" if config.include_completed else "[NO] No"
    )
    config_table.add_row(
        "Interactive Mode", "[OK] Yes" if config.interactive_selection else "[NO] No"
    )
    config_table.add_row(
        "AI Summary", "[OK] Yes" if config.enable_ai_summary else "[NO] No"
    )
    if config.enable_ai_summary:
        config_table.add_row("AI Source", config.ai_source.value)

    console.print(config_table)

    # Function to load Gemini key and update config when needed
    def load_gemini_key_and_update_config():
        nonlocal config
        # Try loading once more from 1Password
        if load_gemini_api_key():
            config.gemini_api_key = gemini_api_key
            return True
        return False

    client = _ClickUpAPIClient(api_key)
    extractor = _ClickUpTaskExtractor(config, client, load_gemini_key_and_update_config)
    extractor.run()


if __name__ == "__main__":
    # Side effects that must only run when executed as a script, never on import:
    #   1. Reconfigure stdio to UTF-8 (mutates sys.stdout/sys.stderr).
    #   2. Load .env so configured vars apply before the re-exec helpers and
    #      main() read them (workspace/space names, OP_ENVIRONMENT_ID, keys).
    #   3. Re-exec under the project venv if not already running from it.
    #   4. Re-exec under 'op run' to inject 1Password env vars without
    #      handle redirection (which would hang the op CLI on Windows).
    _configure_stdio_encoding()
    _load_dotenv()
    _reexec_in_venv()
    _reexec_under_op_run()
    main()
