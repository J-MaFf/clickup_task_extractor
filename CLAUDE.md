# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ClickUp Task Extractor** is a Python CLI for extracting, processing, and exporting tasks from the ClickUp API with:
- Multiple export formats (Markdown, HTML, CSV)
- AI-powered task summaries via Google Gemini with tiered model fallback
- Secure authentication (1Password integration)
- Rich console UI with progress bars and interactive task selection
- Automated ETA calculation and task sorting by priority/ETA

**Python**: 3.11+ | **Core deps**: `requests`, `rich` | **Optional**: `onepassword-sdk`, `google-genai`

## Directory Structure

```
clickup_task_extractor/
├── main.py                # CLI entry, venv handoff, config assembly, auth chain
├── config.py              # Enums (OutputFormat, DateFilter, TaskPriority)
│                          # TaskRecord dataclass, datetime helpers, sort_tasks_by_priority_and_eta()
├── auth.py                # Multi-fallback API key loader (CLI → env → 1Password SDK → CLI → prompt)
├── api_client.py          # APIClient protocol + ClickUpAPIClient (requests, 30s timeout)
├── extractor.py           # ClickUpTaskExtractor workflow, export context mgr, interactive UI
├── ai_summary.py          # Gemini summaries, tiered model strategy, daily quota detection
├── mappers.py             # Prompts, date filters, custom field mapping, image extraction
├── logger_config.py       # Rich-enhanced logging setup
├── version.py             # Version metadata
├── requirements.txt       # Dependency manifest
├── ClickUpTaskExtractor.spec  # PyInstaller spec for EXE builds
├── tests/                 # Unit tests (pytest)
├── output/                # Generated Markdown/HTML/CSV exports
├── docs/CHANGELOG.md      # Keep a Changelog format, Semantic Versioning
└── .github/
    ├── copilot-instructions.md  # Extended architecture & patterns reference
    └── rulesets/main_branch.json # Branch protection rules
```

## Common Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run extractor (Markdown export; workspace/space from --workspace/--space or
# the CLICKUP_WORKSPACE_NAME/CLICKUP_SPACE_NAME env vars — see .env.example)
python main.py

# Interactive mode (review/select tasks before export)
python main.py --interactive

# Export specific format
python main.py --output-format HTML
python main.py --output-format CSV

# With AI summaries
python main.py --ai-summary --gemini-api-key YOUR_KEY

# Custom workspace/space
python main.py --workspace "MyWorkspace" --space "MySpace"

# Include completed tasks
python main.py --include-completed

# Filter by date range
python main.py --date-filter ThisWeek
python main.py --date-filter LastWeek

# Run tests
.\.venv\Scripts\python.exe -m pytest tests/ -v
.\.venv\Scripts\python.exe -m pytest tests/test_extractor.py -v  # Specific test file
.\.venv\Scripts\python.exe -m pytest tests/test_sorting.py::TestTaskSortingByETA -v  # Specific class

# Build executable
.venv\Scripts\pyinstaller.exe ClickUpTaskExtractor.spec --distpath .\dist\v<version>
```

## Architecture Deep Dive

### Authentication Chain (Priority Order)

The `auth.load_secret_with_fallback()` follows this fallback order:
1. **CLI flag** (`--api-key YOUR_KEY`)
2. **Environment variable** (`CLICKUP_API_KEY=xxx`)
3. **1Password Environment** (requires `OP_ENVIRONMENT_ID`)
   - Primary: Python SDK (DesktopAuth or service token)
   - Fallback: CLI via `op environment read <environment_id>`
4. **1Password SDK** (requires `OP_SERVICE_ACCOUNT_TOKEN`)
5. **1Password CLI** (uses `op read` for legacy secret references)
6. **Manual Prompt** (Rich console input)

**For executables**: SDK is unavailable (native dependencies), so skip to step 2 (environment variables).

All retrieval is logged (DEBUG level); failures don't raise exceptions—they return None and proceed to the next fallback.

### Core Modules

**`main.py`**: CLI orchestrator
- Re-launches inside `.venv` if present (cross-platform compatibility)
- Builds `ClickUpConfig` from CLI args + prompts
- Chains authentication fallback
- Seeds Rich prompts for interactive mode, AI summaries, and output format selection

**`config.py`**: Data models & enums
- `OutputFormat` (CSV, HTML, Markdown)
- `DateFilter` (AllOpen, ThisWeek, LastWeek)
- `TaskPriority` enum (Low, Normal, High, Urgent)
- `TaskRecord` dataclass (export fields: id, name, priority, status, eta, description, assignees, etc.)
- `format_datetime()`: Cross-platform date formatting (removes leading zeros)
- `sort_tasks_by_priority_and_eta()`: Primary sort by priority (desc), secondary by ETA (asc)
- `parse_eta()`: Supports multiple ETA formats (display, ISO date, ISO datetime with UTC)

**`api_client.py`**: HTTP layer
- `APIClient` protocol (dependency injection for testing)
- `ClickUpAPIClient` implementation (requests, 30s timeout)
- Custom exceptions: `AuthenticationError`, `APIError`, `RateLimitError`

**`extractor.py`**: Main workflow
- `ClickUpTaskExtractor`: Walks workspace → spaces → lists → tasks
- Caches custom fields (`get_custom_fields()`)
- Filters by status (excludes by default per `ClickUpConfig.exclude_statuses`)
- Filters by date range (`_fetch_and_process_tasks()`)
- Interactive task selection (Rich panels with checkboxes)
- `export_file()` context manager (creates parent dirs, handles I/O errors)
- Markdown/HTML rendering (uses `get_export_fields()` for column order)

**`ai_summary.py`**: Google Gemini integration
- **Tiered model strategy** (on rate limit, automatically switches tiers):
  - Tier 1: `gemini-2.5-flash-lite` (500 RPD free tier)
  - Tier 2: `gemini-2.5-pro` (1,500 RPD separate bucket)
  - Tier 3: `gemini-2.0-flash` (500 RPD fallback)
- Rate limit detection: HTTP 429, RESOURCE_EXHAUSTED errors, 'quota'/'rate limit' keywords, per-minute (RPM) and per-day (RPD) patterns
- **Daily quota exhaustion**: When detected, sets global `_daily_quota_exhausted` flag; `get_ai_summary()` returns None immediately (skips API calls for rest of day)
- Exponential backoff (2^attempt seconds) for transient errors before switching tiers
- Fallback to original task content if all tiers exhausted or API unavailable
- Progress bar during quota reset wait

**`mappers.py`**: Utilities
- `LocationMapper.map_location()`: Dropdown ID → orderindex → name (priority fallback)
- `get_date_range()`: Converts DateFilter enum to datetime tuple
- `extract_images()`: Regex-based image extraction from task descriptions
- `get_yes_no_input()`: Rich-based yes/no prompts
- `get_choice_input()`: Rich-based single/multi-choice prompts

**`logger_config.py`**: Logging setup
- `setup_logging(level, use_rich, log_file)`: Installs Rich tracebacks, emits to stdout
- Optional file output for persistent logging
- Shared logger name: `"clickup_extractor"`

### Task Sorting (Issue #90)

Use `sort_tasks_by_priority_and_eta()` in `config.py` for all exports:
- **Primary**: Priority (descending): Urgent (4) → High (3) → Normal (2) → Low (1) → missing (0)
- **Secondary**: ETA (ascending): Within same priority, earliest ETAs first
- **Missing ETAs**: Appear last within their priority tier

ETA parsing supports:
- Display format: `"2/15/2026 at 3:45 PM"` (via `"%m/%d/%Y at %I:%M %p"`)
- ISO date: `"2026-02-15"` (via `"%Y-%m-%d"`)
- ISO datetime: `"2026-02-15T15:45:00[Z]"` (Z normalized to +00:00)

Legacy function `sort_tasks_by_priority_and_name()` remains available but is unused.

### Key Patterns & Conventions

**Enum config with string fallback**: All config uses enums (e.g., `OutputFormat.HTML`), but string fallback is supported for CLI/backward compat.

**Protocol-based API client**: Use `APIClient` protocol for dependency injection; `ClickUpAPIClient` implements it.

**Context manager for export**: All file I/O via `export_file()` in `extractor.py` (creates parent dirs, handles errors).

**1Password subprocess best practices**:
- Always use `subprocess.run(capture_output=True, text=True, timeout=10)` for reliability
- Detects "multiple accounts" error; auto-retries with `--account my.1password.com`
- Never use `check_output()`; always handle returncode/stderr explicitly

**Rich UI**: All user interaction uses Rich (progress bars, tables, panels, prompts). No plain print() statements.

**Markdown export wrapped sections**: Multi-line task notes are normalized to single-line content (line breaks replaced by spaces) to keep output lint-safe.

## Extension Playbook

**Add export fields**: Extend `TaskRecord` in `config.py`, update `get_export_fields()`, ensure Markdown/HTML renderers display the column.

**New output format**: Add `OutputFormat` enum value, expose in CLI choices, extend `ClickUpTaskExtractor.export()` and render helpers.

**Custom field mapping**: Extend `LocationMapper` in `mappers.py` (id → orderindex → name priority).

**Authentication method**: Extend chain in `auth.py` and update CLI args in `main.py`.

**Task sorting adjustments**: Modify `PRIORITY_ORDER` in `config.py` or extend `parse_eta()` in `sort_tasks_by_priority_and_eta()`. Add tests to `TestTaskSortingByETA` in `tests/test_sorting.py`.

**AI model tiers**: Modify `MODEL_TIERS` in `ai_summary.py`. Test with `python main.py --ai-summary --gemini-api-key <key>` to verify tier switching.

**Daily quota reset** (for testing): Call `_reset_daily_quota_state()` in `ai_summary.py`.

## Testing

**Script-based testing (preferred for quick validation)**:
- Create a `.py` script file
- Run with `.\.venv\Scripts\python.exe script_name.py`
- Avoids PowerShell parsing issues

**Unit tests** (pytest):
```bash
# Full suite
.\.venv\Scripts\python.exe -m pytest tests/ -v

# With coverage
.\.venv\Scripts\python.exe -m pytest tests/ --cov=. --cov-report=html

# Specific test class
.\.venv\Scripts\python.exe -m pytest tests/test_sorting.py::TestTaskSortingByETA -v
```

Key test files:
- `test_sorting.py`: Task sorting by priority/ETA (comprehensive edge cases)
- `test_ai_summary.py`: Gemini integration, rate limiting, daily quota
- `test_api_client.py`: ClickUp API client, error handling
- `test_logger_config.py`: Logging setup

## Building Executables

```bash
# Install PyInstaller (if not present)
pip install pyinstaller>=6.16

# Build exe
.venv\Scripts\pyinstaller.exe ClickUpTaskExtractor.spec --distpath .\dist\v1.05

# Output: Single-file exe (~42 MB) with all dependencies bundled
# Note: 1Password SDK excluded (native dependencies); users fall back to env vars or CLI
```

## Version Bumping & Releases

1. Update `version.py` (`__version__`, related metadata)
2. Update README version badge
3. Add entry to `docs/CHANGELOG.md` (Keep a Changelog format, Semantic Versioning)
4. Create `release/v<version>` branch, commit, tag with `v<version>`
5. Build exe per above, store in `dist/v<version>/`
6. Push tag to trigger GitHub Actions (if configured)

## Integration Points

- **ClickUp API v2**: All data fetched via `api_client.py`; robust error handling with custom exceptions
- **1Password**: Secure API key storage/retrieval (SDK primary, CLI fallback)
- **Google Gemini AI**: Optional summaries, requires API key (see `ai_summary.py`)
- **Rich**: All console UI (progress, tables, panels, selection)

## Debugging

Enable detailed logging:
```python
from logger_config import setup_logging
import logging

logger = setup_logging(logging.DEBUG, log_file="debug.log")
```

Set breakpoints, inspect `ClickUpConfig` state, and check Rich console output.

## Commit Message & PR Style

Use **Conventional Commits**:
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation
- `refactor:` Code refactoring
- `test:` Test additions/updates
- `chore:` Maintenance/deps
- `perf:` Performance improvements

Example: `feat: Add ETA automation with timezone awareness`

Use **emoji prefixes** in PR titles:
- `✨ Add feature`
- `🐛 Fix bug`
- `📚 Update docs`
- `🔧 Refactor`
- `🚀 Deploy/release`

## Key References

- **README.md**: Full feature list, quick start, CLI options, troubleshooting
- **.github/copilot-instructions.md**: Extended architecture, developer workflows, building executables
- **docs/CHANGELOG.md**: Semantic versioning, release history


<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
bd dolt push          # Sync beads data to remote
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for **repo-level** persistent knowledge; the global `~/.claude/` MEMORY.md remains for cross-repo and user-level context

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Completion

**When ending a work session**, make work durable without merging to main:

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Push the feature branch** (NOT main — merges stay human-gated via PR):
   ```bash
   git push -u origin <feature-branch>
   bd dolt push
   ```
5. **Open or update the PR** referencing `Fixes #N` — then stop; wait for human approval to merge
6. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Push the *feature branch* + `bd dolt push` at session close; never push directly to main
- Merges to main require a PR and human approval — never auto-merge
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
