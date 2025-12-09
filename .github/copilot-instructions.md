# Copilot Instructions: ClickUp Task Extractor

## MCP Tools Usage

This project leverages MCP (Model Context Protocol) tools for enhanced development workflows:

### **Memory Graph (`mcp_memory_*` tools)**
- **Persistent Knowledge Graph**: Maintains project context across sessions
- **Automatic Usage**: Copilot proactively searches and reads the graph during conversations
- **On-Demand Updates**: Observes milestones and updates entities without explicit requests
- **How to Use**:
  - Knowledge is automatically consulted for context (no action needed)
  - Significant task completions, architectural decisions, and discoveries are logged automatically
  - Explicitly request updates only for specific information you want recorded
  - Access via `mcp_memory_search_nodes`, `mcp_memory_open_nodes`, `mcp_memory_add_observations`

### **Sequential Thinking (`mcp_sequentialthi_sequentialthinking`)**
- **Complex Problem Solving**: Invoked automatically for intricate multi-step decisions
- **When Used**: Breaking down architectural changes, planning major refactors, debugging complex issues
- **Transparency**: Explicitly request with `#mcp_sequentialthi_sequentialthinking` to see detailed reasoning
- **No Manual Calls Needed**: Copilot judges when reasoning depth is necessary

## Architecture & Data Flow

- **Entry Point:**
  - `main.py`: CLI orchestrates authentication, config, extraction, and export.
- **Core Modules:**
  - `config.py`: Enum-based config (`ClickUpConfig`), `TaskRecord` dataclass, date formatting.
  - `auth.py`: Multi-fallback API key retrieval (CLI → env → 1Password SDK/CLI → prompt).
  - `api_client.py`: Protocol-based ClickUp API client, custom exceptions.
  - `extractor.py`: `ClickUpTaskExtractor` (main logic), context-managed export, interactive selection.
  - `ai_summary.py`: Optional Google Gemini AI summaries with **tiered model fallback on rate limits**, exponential backoff, and field-level fallback when API unavailable or errors occur.
  - `mappers.py`: Custom field mapping (`LocationMapper`), date filtering.
  - `logger_config.py`: Logging setup for debug and file output.
- **Output:**
  - CSV/HTML export (see `output/`), styled with Rich, cross-platform date formatting.

## Key Patterns & Conventions

- **Enum config:** All config uses enums (e.g., `OutputFormat.HTML`), but string fallback is supported for CLI/backward compatibility.
- **Protocol-based API client:** Use `APIClient` protocol for dependency injection/testing; see `api_client.py`.
- **Context manager for export:** All file I/O via `export_file()` context manager in `extractor.py`.
- **1Password auth chain:** API key retrieval order: CLI arg → env var → 1Password SDK → CLI → prompt.
- **Rich UI:** All user interaction (progress, tables, selection) uses Rich; see `extractor.py` and `ai_summary.py`.
- **AI summaries:** Enable with `--ai-summary` and Gemini key; automatically switches between model tiers on rate limits (Tier 1: `gemini-2.5-flash-lite` → Tier 2: `gemini-2.5-pro` → Tier 3: `gemini-2.0-flash`). Falls back to original content if all tiers exhausted.
- **Date formatting:** Use `format_datetime` in `config.py` for all output; removes leading zeros, cross-platform.
- **Custom field mapping:** Use `LocationMapper` in `mappers.py` (id → orderindex → name fallback).
- **Error handling:** Always raise specific exceptions (e.g., `APIError`), never bare except.
- **Type hints:** Use modern Python type hints everywhere (`list[str]`, `str | None`).
- **No external DB:** All output is local files; no persistent storage.

## Developer Workflows

- **Run app:** `python main.py` (default HTML export, interactive if `--interactive`)
- **Export both formats:** `python main.py --output-format Both`
- **Add export field:** Update `TaskRecord` in `config.py`, then update export logic in `extractor.py`.
- **Add output format:** Extend `export` in `extractor.py`, add enum/config.
- **Add custom field mapping:** Extend `LocationMapper` in `mappers.py`.
- **Add authentication method:** Extend chain in `auth.py` and update CLI in `main.py`.
- **Debug:** Use `logger_config.setup_logging()`; set log level to DEBUG for troubleshooting.
- **Dependencies:** Install with `pip install -r requirements.txt` (see `requirements.txt`).
- **Virtualenv:** Auto-detected; ensure `.venv/` is active for cross-platform compatibility.

## Integration Points

- **ClickUp API v2**: All data via ClickUp API, robust error handling in `api_client.py`.
- **1Password**: Secure API key storage/retrieval (SDK preferred, CLI fallback). Reference: `op://Home Server/ClickUp personal API token/credential`.
- **Google Gemini AI**: Optional summaries, requires API key (see `ai_summary.py`).
- **Rich**: All console UI (progress, tables, selection).

## Examples

- Basic: `python main.py`
- Interactive: `python main.py --interactive`
- Custom workspace: `python main.py --workspace "MyWorkspace" --space "MySpace"`
- HTML export: `python main.py --output-format HTML`
- Using executable: `ClickUpTaskExtractor.exe --output-format Both`

## Building Executables

- PyInstaller spec file available: `ClickUpTaskExtractor.spec`
- Build with: `.venv\Scripts\pyinstaller.exe ClickUpTaskExtractor.spec --distpath .\dist\v<version>`
- Requires PyInstaller 6.16+: `pip install pyinstaller`
- Output: Single-file executable with all dependencies bundled (~42 MB)
- **PDF Export**: Currently uses WeasyPrint. Migration to fpdf2 (pure Python, no system dependencies) planned in issue #63 to eliminate GTK3 runtime requirements

# Copilot Instructions: ClickUp Task Extractor

## Architecture quick map
- `main.py` is the CLI entry: re-launches inside `.venv`, builds `ClickUpConfig`, and drives the auth fallback (CLI → env → 1Password SDK via `OP_SERVICE_ACCOUNT_TOKEN` → `op read` → manual prompt). It also seeds Rich prompts for interactive mode and AI summary.
- `extractor.ClickUpTaskExtractor` runs the workflow (workspace → spaces → lists → tasks) with Rich progress bars, uses `TaskRecord._metadata` to store raw task content for later AI notes, and honors default status exclusions from `ClickUpConfig.exclude_statuses`.
- `config.py` holds enums (`OutputFormat`, `DateFilter`, `TaskPriority`), the `ClickUpConfig` dataclass, and `format_datetime`/`default_output_path` which strip leading zeros for cross-platform filenames.
- `api_client.ClickUpAPIClient` satisfies the `APIClient` protocol with `requests`, 30 s timeouts, and raises `AuthenticationError`/`APIError` with detailed context.
- `auth.py` centralizes secret loading and logging; prefer `load_secret_with_fallback` instead of touching 1Password directly.

## UX and utilities
- File output always uses the `export_file` context manager (creates parent dirs, handles IO errors) and `get_export_fields()` to define CSV/HTML column order.
- `mappers.py` supplies Rich-friendly prompts (`get_yes_no_input`), date filters via `get_date_range`, screenshot scraping with `extract_images`, and `LocationMapper.map_location` (id → orderindex → name fallback) for custom fields.
- `ai_summary.get_ai_summary` talks to Google Gemini with **tiered model strategy**: tries `gemini-2.5-flash-lite` (500 RPD) first, switches to `gemini-2.5-pro` (1,500 RPD separate bucket) on rate limit, then `gemini-2.0-flash` as emergency fallback. Detects rate limits via HTTP 429, RESOURCE_EXHAUSTED errors, 'quota'/'rate limit' keywords (case-insensitive), and per-minute/per-day quota patterns. **Daily quota detection** via `_is_daily_quota_error()` sets global `_daily_quota_exhausted` flag to skip AI summaries for rest of day. Uses exponential backoff for same-model retries (2 retries) before switching tiers. Falls back to raw task content when all tiers exhausted or daily quota exceeded.
- **Daily quota exhaustion handling**: When `_daily_quota_exhausted` is set, `get_ai_summary` returns None immediately without API calls. Detected by `_is_daily_quota_error()` which matches "requests per day", "RPD", and "quota" + "day"/"daily" patterns. Reset with `_reset_daily_quota_state()` for testing.
- `logger_config.setup_logging` installs Rich tracebacks and returns the shared `"clickup_extractor"` logger; pass `use_rich=False` for plain logging or supply `log_file` for file output. Console initialization uses `force_terminal=None, legacy_windows=False` for cross-platform Unicode support.

## Developer workflow
- Requirements live in `requirements.txt`; core deps are `requests`, `rich`, `weasyprint` (PDF), with optional `onepassword-sdk` and `google-generativeai`—guard imports accordingly.
- Typical runs: `python main.py` (HTML export, workspace `KMS`, space `Kikkoman`), or override with `--output-format {CSV|HTML|Markdown|PDF|Both}`, `--interactive`, `--include-completed`, `--date-filter {AllOpen|ThisWeek|LastWeek}`, and `--ai-summary/--gemini-api-key`.
- The extractor writes to `output/` using the timestamped path from `config.default_output_path()`; exporters adjust the extension per selected format.
- Version bumps: update `version.py` (`__version__` and related metadata), refresh the README version badge URL, and add a new entry in `CHANGELOG.md` summarizing changes since the previous release.
- Release builds: Create a `release/v<version>` branch, commit version changes, tag with `v<version>`, and build exe with PyInstaller spec pointing to `dist/v<version>`.

## Extension playbook
- Add fields: extend `TaskRecord`, update any renderers that iterate `get_export_fields()`, and make sure `_metadata` keeps AI payloads if needed.
- New output format: add an `OutputFormat` enum value, expose it in CLI choices, and extend `ClickUpTaskExtractor.export()`/render helpers while still using `export_file`.
- Extra API filtering or mapping: hook into `_fetch_and_process_tasks`, reuse `LocationMapper` and `get_date_range`, and surface errors through Rich panels rather than bare prints.
- **Image extraction**: Extracts images from task descriptions using regex patterns for various formats.
- **AI model tiers**: Modify `MODEL_TIERS` in `ai_summary.py` to adjust fallback strategy. Each tier should have separate quotas for rate-limit resilience. Test with `--ai-summary --gemini-api-key <key>` to verify tier switching on rate limits.
- **PDF export migration**: Issue #63 tracks migration from WeasyPrint to fpdf2. When implemented, update `extractor.py` PDF export method and replace `weasyprint>=60.0` with `fpdf2>=2.7.0` in `requirements.txt`. Remove GTK3-specific error handling and simplify imports.
