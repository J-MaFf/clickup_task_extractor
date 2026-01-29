# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 1.03 - 2026-01-29

### ✨ Features & Enhancements

- **ETA Automation**: Added AI-powered ETA calculation with robust fallback logic when due dates are missing, including priority-based defaults and status multipliers.
- **PDF Export Without System Dependencies**: Replaced WeasyPrint with fpdf2 for PDF export to eliminate GTK3 requirements.
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
