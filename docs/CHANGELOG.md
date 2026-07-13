# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **The AI summary and ETA passes now report real generated-vs-fallback counts.** A run where every generation call failed previously still ended with `41/41 summaries generated` and a green `✅ AI summaries complete.` — indistinguishable from full success. The passes now count actual AI successes (per-item progress says "processed"), and the final line reports e.g. `AI summaries complete: 38 of 41 generated, 3 fell back to base notes.` / `ETA estimation complete: 12 of 40 AI-estimated, 28 deterministic fallback(s).` — with a yellow warning instead of a green checkmark when nothing was generated. `calculate_eta_with_source()` was added to `eta_calculator.py` (existing `calculate_eta()` is now a thin wrapper) so the ETA pass can tell an AI estimate from the deterministic fallback. ([#160](https://github.com/J-MaFf/clickup_task_extractor/issues/160))
- **Claude CLI login failures now fail fast instead of erroring on every task.** When the `claude` CLI is logged out, a run previously spawned a failing subprocess for every summary and every ETA (81 identical `Not logged in · Please run /login` errors on a 41-task export). Now: `main.py` pre-flights `claude auth status` when the AI source is Claude/Both and warns before extraction starts; the first in-run auth failure disables the Claude path for the rest of the run (mirroring the usage-limit behavior) with a one-time actionable message (`claude auth login`); and the concurrent summary/ETA passes skip entirely — with a single notice — when the Claude provider is already known to be unavailable. ([#159](https://github.com/J-MaFf/clickup_task_extractor/issues/159))
- **The "ClickUp AI summary field is empty" notice no longer appears for Claude/Gemini runs.** The nudge to "ensure automation populates it" only makes sense when the ClickUp `Summary` custom field is the run's content source, so the notice is now limited to the ClickUp and Both AI sources. ([#161](https://github.com/J-MaFf/clickup_task_extractor/issues/161))

### Added

- **ETA calculation in the KFJ weekly sheet sync.** `kfj_task_extractor.py` previously left the ETA column blank for tasks without a ClickUp due date; it now reuses the main extractor's ETA pipeline. Tasks without a due date get a deterministic priority/status baseline in `task_to_record()`, then a bounded-concurrency pass (`apply_ai_etas()`, reusing `AI_SUMMARY_CONCURRENCY`) upgrades the baselines with Claude CLI estimates **before** sorting, so the sheet ordering reflects the final dates. The pass pre-flights `claude auth status` (skipping cleanly to the baselines when the CLI is missing or logged out), cancels queued Claude subprocesses on Ctrl+C, and can be disabled with `--no-ai-eta` / `KFJ_AI_ETA=0`. Claude ETA replies are now also strptime-validated in `eta_calculator._extract_date_token` (trailing punctuation stripped, 2-digit years normalized, unparseable tokens rejected) so an off-format model reply can never overwrite a valid deterministic date with an unsortable string — this hardening benefits the main extractor's ETA pass too. ([#165](https://github.com/J-MaFf/clickup_task_extractor/issues/165))
- **Windows CI on the self-hosted `win-test` runner.** `tests.yml` gains a `pytest-windows` job (`runs-on: [self-hosted, windows]`, Python 3.14) alongside the existing hosted-Linux job (Python 3.11), so the suite now runs on the OS the extractor is primarily used on — with an incidental oldest-Python/newest-Python matrix. The job is gated off fork PRs (public repo + self-hosted runner), blanks all ambient `CLICKUP_*`/`OP_*`/`GEMINI_*` env vars, and mirrors the Linux job's exclusion of the `onepassword` SDK (the suite mocks it). Four test-file `open()` calls gained explicit `encoding="utf-8"` so results don't depend on Windows' cp1252 default. ([#156](https://github.com/J-MaFf/clickup_task_extractor/issues/156))

## [1.06] - 2026-06-26

### Added

- Added **Claude** as an AI summary source that shells out to the local `claude` CLI in headless print mode (`claude -p … --output-format text`), using your Claude Code **OAuth / Max subscription** — no API key required, and not subject to Gemini's free-tier rate limits. Select with `--ai-source Claude` (now the interactive default). The model is overridable via `CLAUDE_SUMMARY_MODEL` (default `claude-haiku-4-5-20251001`) and the per-call timeout via `CLAUDE_SUMMARY_TIMEOUT`. If a usage limit is hit, the CLI is missing, or a call errors, summaries fall back to raw field content (mirroring the Gemini failure path). ([#144](https://github.com/J-MaFf/clickup_task_extractor/issues/144))
- **Concurrent AI summary generation.** Summaries are now generated in a single bounded-concurrency pass (`ThreadPoolExecutor`) after task processing instead of one-at-a-time, cutting wall-clock on large exports by ~3× (e.g. 6 Claude summaries in ~14s vs ~42s serial). Worker count is configurable via `AI_SUMMARY_CONCURRENCY` (default 4, clamped to the task count). Output order is preserved, and once a provider hits a usage/rate limit the remaining queued calls short-circuit. Applies to both interactive (selected tasks) and non-interactive (all tasks) modes. ([#147](https://github.com/J-MaFf/clickup_task_extractor/issues/147))
- **Claude-powered ETA estimation.** Tasks without a due date can now get an AI-estimated ETA from the same source as summaries — Claude via the local CLI (OAuth/Max, no key), Gemini, or the deterministic priority/status fallback (ClickUp source and any AI failure). The ETA estimates run in their own bounded-concurrency pass (reusing `AI_SUMMARY_CONCURRENCY`), so they don't serialize the per-task fetch loop; a deterministic ETA is always computed first as a baseline. ([#146](https://github.com/J-MaFf/clickup_task_extractor/issues/146))
- **`kfj_task_extractor.py` now auto-loads `.env.kfj`** at startup (mirroring `main.py`'s `.env` loader from #150), so the documented `KFJ_*` settings apply on a plain `python kfj_task_extractor.py` without `op run` or a pre-exported shell. The loader is dependency-free, runs only on CLI execution (never on import), and never overrides real env vars / `op run`-injected values. It is **secret-safe**: an `op://` value for the secret-material keys (`CLICKUP_API_KEY`, `GOOGLE_SHEETS_CREDENTIALS_JSON`) is skipped rather than loaded literally, leaving those references for `op run` / the 1Password resolver chain; literal secrets and the `KFJ_*_SECRET_REFERENCE` op:// pointers load normally. ([#152](https://github.com/J-MaFf/clickup_task_extractor/issues/152))

### Changed

- **Claude is now the default AI summary source**, replacing Gemini as the default generative summarizer (Gemini hit free-tier rate limits frequently). `--ai-source Both` now resolves the ClickUp `Summary` field first, then falls back to **Claude**. Gemini remains fully available via `--ai-source Gemini`, and a Gemini API key is only loaded/prompted when that source is selected. ([#144](https://github.com/J-MaFf/clickup_task_extractor/issues/144))

### Fixed

- Fixed configured settings in a `.env` file (and User-scoped env vars not inherited by an already-running shell/IDE) being ignored. `.env.example` documented variables like `CLICKUP_WORKSPACE_NAME` / `CLICKUP_SPACE_NAME`, but nothing actually loaded a `.env`, so a configured default workspace/space was dropped and the run fell back to the picker (defaulting to the first workspace). `main.py` now loads `.env` (from the script directory) at startup via a small dependency-free loader, before the re-exec helpers and config read it; real environment variables and CLI flags still take precedence. ([#150](https://github.com/J-MaFf/clickup_task_extractor/issues/150))
- Fixed startup crash (`unknown flag: --environment`) when `OP_ENVIRONMENT_ID` is set but a **stable** 1Password CLI is installed. The `op run` Environments flag is beta-only; `main.py` now probes `op run --help` and only re-execs under `op run` when the installed CLI actually advertises the flag (using the correct plural `--environments`). On a stable CLI the re-exec is skipped so authentication falls through to the 1Password SDK path instead of aborting. ([#138](https://github.com/J-MaFf/clickup_task_extractor/issues/138))
- Fixed 1Password **Environment** auth being skipped when `CLICKUP_API_SECRET_REFERENCE` is empty (the default, Environment-only setup). The lookup was gated on the `op://` secret reference, but `load_secret_with_fallback()` resolves an Environment from `OP_ENVIRONMENT_ID` + the secret name and needs no reference — so the SDK lookup was never attempted and auth fell through to a manual prompt. `main.py` now performs the lookup when a reference is configured **or** `OP_ENVIRONMENT_ID` is set, for both the ClickUp and Gemini key paths. ([#140](https://github.com/J-MaFf/clickup_task_extractor/issues/140))
- Fixed the interactive run appearing to hang ("loading forever") when no workspace/space is configured. The extractor matched the `/team` list by `workspace_name`; with no name it fell through to a raw "enter Team/Workspace ID" prompt issued **behind** the live `Fetching workspaces…` spinner, so the prompt was obscured. It now offers a workspace **picker** (mirroring the existing space picker — auto-selecting when there's only one workspace), pauses the progress display around all interactive prompts so they're visible, and only shows the manual-ID fallback (with an accurate message) when `/team` genuinely fails. ([#142](https://github.com/J-MaFf/clickup_task_extractor/issues/142))

## [1.05] - 2026-06-23

### Added

- Adopted **beads** (`bd` v1.0.4, Dolt-backed) as the dependency-graph task/memory layer beneath GitHub Issues. `bd init` wires `.beads/` into the repo; `bd dolt push` syncs issue state to `refs/dolt/data` on origin. CLAUDE.md and AGENTS.md reconciled with `git-policies` (feature-branch + `bd dolt push` at session close; merges to main stay human-gated via PR; `bd remember` scoped to repo-level knowledge). ([#119](https://github.com/J-MaFf/clickup_task_extractor/pull/119))
- Added `STATUS.md` — project state snapshot with component table, resolved/open issues, and natural next steps. ([#119](https://github.com/J-MaFf/clickup_task_extractor/pull/119))

- **KFJ Task Extractor** (`kfj_task_extractor.py`): standalone weekly sync that pulls all open tasks from the ClickUp "KFI Jefferson" list into the tracking Google Sheet.
  - Creates a dated tab `KFI Jefferson current tasks (M/D/YY)` at index 0 and renames the workbook title to match; same-day re-runs replace the tab's contents idempotently.
  - Writes `Task | Company | Branch | Priority | Status | ETA` sorted by priority then ETA, normalized to the sheet's conventions (lowercase priority/status, date-only ETA).
  - Resolves both the ClickUp key and Google service-account JSON via env var → 1Password SDK → CLI fallback; credentials are parsed in-memory and never written to disk.
  - Reuses existing components (`ClickUpAPIClient`, `load_secret_with_fallback`, `TaskRecord`, `sort_tasks_by_priority_and_eta`, `LocationMapper`) without modifying the main extraction workflow.
  - Supports `--dry-run`, `--list-id`, `--sheet-id`, and `--date M/D/YY` overrides.
- Added `gspread>=6.1.0` dependency for the Google Sheets integration.
- Added `requirements.lock` — a fully-resolved lock file (`pip freeze` output) for reproducible installs of the exact transitive versions the project is tested against. ([#108](https://github.com/J-MaFf/clickup_task_extractor/pull/108))
- Added GitHub Actions CI workflow (`.github/workflows/tests.yml`) that runs `pytest tests/ -v` on every push and pull request to `main`. ([#123](https://github.com/J-MaFf/clickup_task_extractor/pull/123))
- `ClickUpAPIClient` now accepts an optional `timeout` parameter (default: 30 s) so callers can tune the request deadline without modifying source. ([#127](https://github.com/J-MaFf/clickup_task_extractor/pull/127))

### Changed

- Pinned dependencies with compatible-release (`~=`) specifiers instead of `>=` lower bounds, so breaking major releases of `requests`, `google-genai`, `rich`, or `gspread` cannot be picked up silently. `onepassword-sdk` (still a 0.x beta) is pinned exactly. Use `requirements.lock` for a byte-for-byte reproducible environment (#108).
- Made `kfj_task_extractor.py` configurable instead of single-tenant: the ClickUp list ID, Google Sheet ID, 1Password secret references, and 1Password account name/URL now read from `KFJ_*` environment variables with non-personal (empty) defaults. `--list-id`/`--sheet-id` still override, and `main()` now errors clearly when no list/sheet is configured. Added `.env.kfj.example` and a README **Configuration** subsection documenting every variable and where to find the IDs (#110).

- Updated 1Password authentication to use 1Password Environment loading through the Python SDK for `OP_ENVIRONMENT_ID`.
- Documented the Environment-based flow in the README and setup guidance.
- Added 1Password CLI Environment fallback using `op environment read <environment_id>` when SDK auth is unavailable.
- Moved committed personal identifiers (1Password vault paths/item IDs, ClickUp team ID, and the workspace/space names) out of source into environment variables with non-personal (empty) defaults: `CLICKUP_API_SECRET_REFERENCE`, `GEMINI_API_SECRET_REFERENCE`, `CLICKUP_WORKSPACE_NAME`, `CLICKUP_SPACE_NAME`, `CLICKUP_TEAM_ID`, and `CLICKUP_AI_SUMMARY_FIELD_ID`. When a `*_SECRET_REFERENCE` is unset, `main.py` skips the 1Password lookup and falls back to env var / CLI flag / prompt. Added `.env.example` and a README **Configuration** section documenting the variables (#106).

### Fixed

- Removed the broken legacy vault-only fallback for Environment-based authentication.
- Clarified the supported account selection flow for DesktopAuth and service-account auth.
- Enabled executable workflows with `OP_ENVIRONMENT_ID` by reading Environment variables through 1Password CLI.
- Corrected the Gemini model identifier from the invalid `gemini-flash-lite-latest` to the published `gemini-2.5-flash-lite` in `ai_summary.py` and `eta_calculator.py`; the value is now overridable via the `GEMINI_MODEL` environment variable. Added smoke tests that reject malformed model ids and the known-bad value (#109).
- Guarded module-level side effects in `main.py` and `kfj_task_extractor.py` behind `if __name__ == "__main__"`. The virtualenv re-exec, UTF-8 stdio reconfiguration, and `setup_logging()` no longer run at import time, so the modules can be imported by tests and tooling without triggering a process re-exec, mutating `sys.stdout`/`sys.stderr`, or reconfiguring the shared logger (#107).

### Fixed (continued)

- Guarded `type_config` and `options` access in `extractor.py` against explicit `null` from the ClickUp API. Previously `branch_field.get("type_config", {})` returned `None` when the key was present but null, causing `AttributeError` on the subsequent `.get("options")` call. ([#126](https://github.com/J-MaFf/clickup_task_extractor/pull/126))
- Fixed three pre-existing test failures surfaced by the new CI workflow: `test_interactive_ai_summary` stub endpoint was missing `&subtasks=true`; `test_logger_config` handler isolation broken by module-level `setup_logging()` call in another test file; `test_main` was patching the module-level `None` rather than `_load_runtime_dependencies`. ([#123](https://github.com/J-MaFf/clickup_task_extractor/pull/123))

### Security

- Disabled `show_locals` in the Rich traceback handler (`logger_config.py`) so unhandled exceptions no longer render local variable contents — a stack frame could hold an API key or other secret, which `show_locals=True` would have printed to the console/logs. ([#105](https://github.com/J-MaFf/clickup_task_extractor/pull/105))

## [1.04] - 2026-04-07

### Fixed

- **Markdown Export Regression**: Fixed line break handling in markdown exports
  - Changed newline replacement strategy from two trailing spaces (`\n`) to single spaces (` `)
  - Eliminates markdown lint violations (MD055, MD056, MD009)
  - Maintains consistent, lint-safe markdown rendering
  - Resolves issue regression from #86 fix
  - See `MARKDOWN_LINEBREAK_FIX_SUMMARY.md` for detailed explanation

### Changed

- Removed PDF output support from active export options (project now supports Markdown and HTML outputs only)
- Markdown export now renders per-task wrapped bullet sections instead of tables
  - Multi-line content is preserved but normalized to single lines for safer rendering
  - Example: "Line one\nLine two" → "Line one Line two"
  - Keeps generated files compliant with strict markdownlint rules (notably MD013 and MD034)
  - Converts bare URLs to bracketed form (`<https://...>`) and wraps long content lines

## [1.03] - 2026-01-29

### ✨ Features & Enhancements

- **ETA Automation**: Added AI-powered ETA calculation with robust fallback logic when due dates are missing, including priority-based defaults and status multipliers.
- **Git Cleanup Helper**: Added improved git cleanup helper with better stale-branch detection and documented findings.
- **Daily Quota (RPD) Exhaustion Detection**: Added intelligent detection for Google Gemini API daily quota (Requests Per Day) limits. When all model tiers exhaust their daily quota, AI summaries are automatically disabled for the rest of the day, preventing continued retry attempts on already-exhausted quotas. Includes `_is_daily_quota_error()` detection function and global `_daily_quota_exhausted` state tracking.
- **Tiered Model Switching for AI Summaries**: Implemented intelligent model fallback strategy for Google Gemini API rate limiting. When the primary model (`gemini-2.5-flash-lite`, 500 RPD) hits rate limits, the system automatically switches to `gemini-2.5-pro` (1,500 RPD separate quota bucket) for continued operation with higher quality summaries. Falls back to `gemini-2.0-flash` as emergency alternative. Each tier has its own quota bucket, allowing up to 3x additional capacity when primary is exhausted.
- **Dynamic Model Tier Management**: Refactored `ai_summary.py` with new `MODEL_TIERS` configuration list and helper functions (`_try_ai_summary_with_model`, `_handle_rate_limit_wait`, `_is_daily_quota_error`) for clean separation of concerns. Users are notified which model tier generated their summary via Rich console output.
- **Comprehensive Rate Limit Detection**: Enhanced detection to catch 10+ rate limit error patterns including HTTP 429 status codes, RESOURCE_EXHAUSTED errors, per-minute limits (RPM), and daily quota keywords. Case-insensitive matching ensures all quota-related errors are caught regardless of message format or Google API version.
- **Windows UTF-8 Console Support**: Improved Rich console initialization with proper cross-platform encoding parameters (`force_terminal=None`, `legacy_windows=False`) across all modules to ensure proper Unicode rendering on Windows, macOS, and Linux without breaking existing functionality.
- **Enhanced Rate Limit Handling**: Improved exponential backoff logic and progress bar display during rate limit waits. System attempts same model up to 2 times with exponential backoff before switching tiers, providing better user feedback throughout the process.

### 🐛 Fixes

- **1Password Multi-Account Support**: Improved CLI fallback to handle multiple accounts, added timeouts, and standardized error handling for missing SDK or CLI errors.
- **Auth Logging and Formatting**: Standardized auth logging messages and removed unnecessary f-strings while keeping behavior consistent.
- **Export Path Tests**: Updated export behavior tests and cleanup to match the actual output directory behavior.
- **Timezone-Aware Due Dates**: Fixed due date conversion to use timezone-aware datetimes.

### 🧪 Testing

- Updated auth tests to mock `subprocess.run` and aligned assertions with actual logging behavior.
- Added setup/teardown cleanup for export sorting tests to avoid leftover output files.

### 📚 Documentation

- Added a knowledge graph backup for MCP memory state and expanded 1Password integration details.
- Documented code style, formatting standards, and PR metadata guidance.

## [1.02] - 2025-11-18

### ✨ Features & Enhancements

- **Interactive Output Format Selection**: Added user-friendly interactive prompt for selecting output format (CSV, HTML, Markdown, PDF, or Both) when `--output-format` is not specified via CLI. Users can now choose their preferred export format during runtime with numbered menu options or text input, following the same pattern as existing interactive mode and AI summary prompts.
- **Enhanced User Input Utilities**: Added reusable `get_choice_input()` function in `mappers.py` for multi-choice selection with validation, default handling, and interrupt safety.
- Introduced unified export pipeline that now covers CSV, HTML, Markdown, PDF, and dual-format (`Both`) runs, all powered by the shared `export_file()` context manager for safe writes and automatic directory creation.
- Extended the interactive review experience with Rich tables, list-level progress, and optional AI re-generation so operators can curate exports without losing task metadata.
- **Intelligent Task Sorting**: Tasks are now automatically sorted by priority (Urgent → High → Normal → Low) then alphabetically by name, providing better organization in exports without requiring user configuration.
- **Custom Field Expansion**: Enhanced task record to include and properly map additional custom fields from ClickUp, improving data completeness and field normalization.
- **US Date Format for Filenames**: Output filenames now use MM-DD-YYYY (US format) for better consistency and readability in Windows environments.

### 🤖 AI Summary Improvements

- Hardened Gemini integration with `_normalize_field_entries`, deterministic prompt construction, newline trimming, and automatic punctuation to produce polished 1–2 sentence summarizations.
- Added smart rate-limit handling that parses `retryDelay` hints, surfaces Rich countdowns while waiting, and gracefully falls back to raw task content after exhaustively retrying.
- Ensured fallbacks when the Google SDK or API key is missing now return original field blocks while still logging actionable warnings.
- **First-Person Perspective**: AI-generated summaries now use first-person perspective for more natural and engaging task descriptions.

### 🧰 Developer Experience

- Delivered a reusable `setup_logging()` helper with opt-in Rich handlers, stdout-friendly defaults, and file logging support, accompanied by `get_logger()` for module-level reuse.
- Strengthened 1Password secret loading by wrapping SDK usage with CLI fallback (`op read`), clear logging, and structured error propagation for both ClickUp and Gemini credentials.
- Updated the CLI workflow to auto-bootstrap virtual environments, summarize runtime configuration, and offer guided prompts for interactive mode and AI summaries.

### 📚 Documentation & Guidance

- Refreshed `README.md` with updated architecture overview, development workflow tips, and expanded AI integration details.
- Rewrote `.github/copilot-instructions.md` to provide a concise architecture map, workflow guidance, and extension playbook for coding agents.
- Added `tests/README.md` that catalogs every test module, execution recipe, and coverage goal to help contributors navigate the suite.

### 🧭 Release Management

- Documented the version bump workflow: update `version.py`, refresh the README badge, and capture changes in `CHANGELOG.md` for every release.

### ✅ Testing

- Expanded the automated suite to 133 unit tests spanning AI summaries, extractor edge flows, authentication fallbacks, Rich logging, CLI orchestration, and API client error paths for Windows-friendly reliability.

## [1.01] - 2025-09-17

### 🧹 Maintenance & Cleanup

#### Code Quality Improvements

- **Complete Legacy Entry Point Removal**: Fully removed `clickup_task_extractor.py` and all references
- **Streamlined Architecture**: Single entry point eliminates maintenance overhead
- **Updated All Documentation**: Consistent references to `main.py` across all files
- **Cleaner Examples**: All usage examples now use the primary entry point

## [1.0.0] - 2025-08-04

### 🎉 Initial Release - Modern Python Architecture

This is the first official release of ClickUp Task Extractor, featuring a complete modern Python architecture designed for maintainability, type safety, and exceptional user experience.

### ✨ Added

#### Core Features

- **Modular Architecture**: Clean separation following SOLID principles
- **Type-Safe Configuration**: Enum-based configuration (`TaskPriority`, `OutputFormat`, `DateFilter`)
- **Rich Console Interface**: Beautiful progress bars and styled output using Rich library
- **Interactive Task Selection**: Review and filter tasks before export with detailed preview
- **Multiple Export Formats**: CSV, HTML, or both simultaneously with professional styling
- **Cross-Platform Compatibility**: Full Windows, macOS, and Linux support

#### Security & Authentication

- **1Password Integration**: Secure API key management via SDK (preferred) or CLI fallback
- **Multi-Method Authentication**: CLI args → env vars → 1Password SDK → CLI → manual input
- **Service Account Support**: Full 1Password service account token integration

#### AI & Advanced Features

- **Google Gemini Integration**: Optional AI task summarization with intelligent rate limiting
- **Image Extraction**: Automatic extraction of image references from task descriptions
- **Custom Field Mapping**: Flexible field mapping with id → orderindex → name fallback strategies
- **Date Filtering**: Smart date range filtering (All Open, This Week, Last Week)

#### Developer Experience

- **Modern Type Hints**: Uses `list[T]`, `dict[K,V]`, `str | None` syntax throughout
- **Protocol-Based Design**: `APIClient` protocol for dependency inversion and testability
- **Context Managers**: Safe resource management with `export_file()` context manager
- **Comprehensive Error Handling**: Custom exceptions with proper error chaining
- **Professional Logging**: Structured logging with configurable console/file output

#### Export & Output

- **Professional HTML Export**: CSS-styled tables with summary information and metadata
- **CSV Export**: Clean, structured CSV output with all task data
- **Auto-Generated Filenames**: Timestamped output files with cross-platform date formatting
- **Status Filtering**: Configurable exclusion of task statuses (default: Blocked, Dormant, On Hold, Document)

### 🏗️ Technical Architecture

#### Design Patterns

- **Single Responsibility Principle**: Each module handles one specific concern
- **Dependency Inversion**: Protocol-based interfaces for loose coupling
- **Strategy Pattern**: Multiple authentication and export strategies
- **Factory Pattern**: Logger and client factory functions

#### Modern Python Features

- **Dataclasses**: Type-safe configuration and data models
- **Enums**: Type-safe constants and configuration options
- **Pathlib**: Cross-platform file operations
- **f-strings**: Modern string formatting throughout
- **Union Types**: `str | None` syntax for optional values
- **Generic Types**: `list[str]`, `dict[str, Any]` for better type hints

#### Dependencies

- **Core**: `requests` for HTTP client
- **Optional**: `onepassword-sdk`, `google-genai`, `rich`
- **Python**: Requires Python 3.9+

### 📋 Configuration Options

- `workspace_name`: ClickUp workspace (default: 'KMS')
- `space_name`: ClickUp space (default: 'Kikkoman')
- `output_format`: Export format - CSV, HTML, or Both (default: HTML)
- `include_completed`: Include completed/archived tasks (default: False)
- `interactive_selection`: Enable task review and selection (default: False)
- `exclude_statuses`: Task statuses to exclude (default: ['Blocked', 'Dormant', 'On Hold', 'Document'])
- `date_filter`: Date filtering - AllOpen, ThisWeek, LastWeek (default: AllOpen)
- `enable_ai_summary`: Enable AI summarization (requires gemini_api_key)

### 🚀 Usage Examples

```bash
# Basic usage
python main.py

# Interactive mode with task selection
python main.py --interactive

# Custom workspace and both output formats
python main.py --workspace "MyWorkspace" --space "MySpace" --output-format Both

# Include completed tasks with this week's filter
python main.py --include-completed --date-filter ThisWeek

# With specific API key
python main.py --api-key "your_api_key"
```

### 🔧 Requirements

- Python 3.9 or higher
- Virtual environment recommended (auto-detected and switched)
- ClickUp API access token
- Optional: 1Password CLI or SDK for secure credential management
- Optional: Google Gemini API key for AI features

### 📁 Project Structure

```code
clickup_task_extractor/
├── main.py                    # Primary entry point with CLI
├── config.py                  # Configuration dataclasses and enums
├── version.py                 # Version information and metadata
├── auth.py                    # Authentication and 1Password integration
├── api_client.py              # ClickUp API HTTP client
├── ai_summary.py              # Google Gemini AI integration
├── mappers.py                 # Utilities and custom field mapping
├── extractor.py               # Main business logic and export
├── logger_config.py           # Logging configuration utilities
├── requirements.txt           # Python dependencies
└── output/                    # Generated CSV and HTML files
```

### 🎯 Future Roadmap

- Additional export formats (JSON, Excel)
- Task template creation
- Bulk task operations
- Advanced filtering options
- Dashboard generation
- Team collaboration features

---

**Full diff**: <https://github.com/J-MaFf/clickup_task_extractor/commits/v1.0.0>
