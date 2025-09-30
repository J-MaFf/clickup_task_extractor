---
# Copilot Instructions: ClickUp Task Extractor

## Architecture & Data Flow

- **Entry Point:**
  - `main.py`: CLI orchestrates authentication, config, extraction, and export.
- **Core Modules:**
  - `config.py`: Enum-based config (`ClickUpConfig`), `TaskRecord` dataclass, date formatting.
  - `auth.py`: Multi-fallback API key retrieval (CLI → env → 1Password SDK/CLI → prompt).
  - `api_client.py`: Protocol-based ClickUp API client, custom exceptions.
  - `extractor.py`: `ClickUpTaskExtractor` (main logic), context-managed export, interactive selection.
  - `ai_summary.py`: Optional Google Gemini AI summaries, with fallback and rate limiting.
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
- **AI summaries:** Enable with `--ai-summary` and Gemini key; fallback to original content if AI fails.
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
- Markdown export: `python main.py --output-format Markdown`
- PDF export: `python main.py --output-format PDF`
- Both CSV+HTML: `python main.py --output-format Both`
- With API key: `python main.py --api-key YOUR_KEY`

## References

- See `README.md` for full CLI options, troubleshooting, and advanced usage.
- See `.github/Python.prompt.md` for universal Python style/conventions.
- **Adding new features**: Identify the appropriate module based on single responsibility principle from SOLID guidelines
- **New export fields**: Update the `TaskRecord` dataclass in `config.py` and adjust export logic in `extractor.py` (following dataclass best practices)
- **New output formats**: Extend the `export` method in `extractor.py` and add config options (Open/Closed principle)
- **New custom field mappings**: Extend the `LocationMapper` class in `mappers.py` with additional mapping logic
- **New authentication methods**: Extend the authentication chain in `auth.py` and update `main.py` (Strategy pattern)
- **Error handling**: Use specific exception types and proper error chaining as defined in Python guidelines
- **Type hints**: Always use modern syntax (`list[str]`, `str | None`) and create type aliases for clarity
- **File operations**: Use pathlib and context managers for all file I/O operations
- **Date formatting changes**: Update functions in `config.py` for consistency across the application

## Integration Points
- **ClickUp API**: All data is fetched via ClickUp's v2 API with comprehensive error handling and debugging output.
- **1Password**: Secure API key storage and retrieval using SDK (preferred) or CLI fallback. Reference: `"op://Home Server/ClickUp personal API token/credential"`.
- **Cross-platform compatibility**: Date formatting works correctly on Windows, macOS, and Linux without leading zeros.
- **Optional AI summary**: Placeholder for integrating AI summarization via GitHub token (not implemented by default).
- **Image extraction**: Extracts images from task descriptions using regex patterns for various formats.
- **No external storage or DB**: All output is local (CSV/HTML files) with automatic directory creation.

## Key Features
- **Multiple authentication methods**: CLI args, environment variables, 1Password SDK/CLI, manual input
- **Interactive task selection**: Review and filter tasks before export with detailed preview
- **Cross-platform date formatting**: Remove leading zeros for cleaner output (e.g., "1/8/2025 at 3:45 PM")
- **Styled HTML export**: Professional-looking HTML tables with CSS styling and summary information
- **Status filtering**: Configurable task status exclusion (default excludes 'Dormant', 'On Hold', 'Document')
- **Comprehensive error handling**: Detailed debugging information for API failures and edge cases
- **Image extraction**: Automatically extracts image references from task descriptions and custom fields
- **Flexible output**: Support for CSV, HTML, Markdown, PDF, or combined formats

## Configuration Options
- `workspace_name`: ClickUp workspace (default: 'KMS')
- `space_name`: ClickUp space (default: 'Kikkoman')
- `output_format`: Export format - `OutputFormat.CSV`, `OutputFormat.HTML`, `OutputFormat.MARKDOWN`, `OutputFormat.PDF`, or `OutputFormat.BOTH` (default: HTML)
- `include_completed`: Include completed/archived tasks (default: False)
- `interactive_selection`: Enable task review and selection (default: False, prompted if not set)
- `exclude_statuses`: List of task statuses to exclude (default: ['Blocked', 'Dormant', 'On Hold', 'Document'])
- `date_filter`: Date filtering - `DateFilter.ALL_OPEN`, `DateFilter.THIS_WEEK`, `DateFilter.LAST_WEEK` (default: ALL_OPEN)
- `enable_ai_summary`: Enable AI summarization (requires gemini_api_key)

## Examples
- **Basic usage**: `python main.py`
- **Interactive mode**: `python main.py --interactive`
- **Custom workspace**: `python main.py --workspace "MyWorkspace" --space "MySpace"`
- **Markdown export**: `python main.py --output-format Markdown`
- **PDF export**: `python main.py --output-format PDF`
- **Both CSV+HTML**: `python main.py --output-format Both`
- **Include completed**: `python main.py --include-completed`
- **With API key**: `python main.py --api-key YOUR_KEY`

## Key Files
- **`main.py`**: Primary entry point with CLI parsing and orchestration
- **`config.py`**: Configuration dataclasses and constants
- **`auth.py`**: Authentication and 1Password integration
- **`api_client.py`**: ClickUp API HTTP client
- **`ai_summary.py`**: Google Gemini AI integration for task summarization
- **`mappers.py`**: Utilities and custom field mapping
- **`extractor.py`**: Main business logic and export functionality
- **`logger_config.py`**: Logging configuration and setup utilities
- **`.github/copilot-instructions.md`**: This file with project conventions and patterns
- **`requirements.txt`**: Python dependencies (requests, optional: onepassword-sdk, google-genai)
- **`output/`**: Directory for generated CSV and HTML files

## Development Guidelines
- To add a new export field, update the `TaskRecord` dataclass and adjust the export logic in `export` and `render_html` methods.
- To support a new output format, extend the `export` method and add a new config option.
- When adding new custom field mappings, extend the `LocationMapper` class with additional mapping logic.
- For new authentication methods, extend the authentication chain in the `main()` function.
- All date formatting should use the provided `format_datetime` function for consistency.

## 1Password Integration Details
- **SDK Authentication**: Set `OP_SERVICE_ACCOUNT_TOKEN` environment variable
- **CLI Fallback**: Ensure `op` command is available in PATH
- **Secret Reference**: `"op://Home Server/ClickUp personal API token/credential"`
- **Error Handling**: Graceful fallback through authentication chain with informative error messages

---

For questions about project-specific conventions or to propose improvements, please update this file or contact the project maintainer.
