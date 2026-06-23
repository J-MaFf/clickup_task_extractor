# ClickUp Task Extractor 📋

A powerful, cross-platform Python application for extracting, processing, and exporting tasks from the ClickUp API with beautiful console interfaces and AI-powered summaries.

![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Version](https://img.shields.io/badge/version-1.05-green.svg)
![Rich](https://img.shields.io/badge/rich-14.0%2B-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ Features

- 🔐 **Secure Authentication**: Multiple authentication methods including 1Password integration
- 🎨 **Beautiful UI**: Rich console interfaces with progress bars, panels, and styled output
- 🤖 **AI Summaries**: Optional Google Gemini AI integration for intelligent task summaries
- 📅 **Automated ETA Calculation**: Intelligent ETA population for tasks without due dates
  - Uses existing due dates when available
  - AI-powered ETA estimation based on task context
  - Fallback calculation using priority and status
- 📊 **Multiple Export Formats**: Markdown (default) and HTML with professional styling
- 🔍 **Interactive Mode**: Review and select tasks before export with user-friendly prompts
- 📄 **Interactive Format Selection**: Choose output format at runtime via intuitive prompt
- 📅 **Flexible Filtering**: Date range filtering (This Week, Last Week, All Open)
- 🌐 **Cross-Platform**: Works on Windows, macOS, and Linux
- ⚡ **Modern Architecture**: Clean, modular design following SOLID principles

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- ClickUp API token
- Optional: 1Password Environment support for Python, or 1Password CLI for legacy secret references
- Optional: Google Gemini API key for AI summaries

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/J-MaFf/clickup_task_extractor.git
   cd clickup_task_extractor
   ```

2. **Install dependencies:**

   ```bash
   # Normal install — compatible-release (`~=`) pins
   pip install -r requirements.txt

   # Reproducible install — exact transitive versions this project is tested against
   pip install -r requirements.lock
   ```

3. **Set up your ClickUp API key** (choose one method):
   - Command line: `python main.py --api-key YOUR_API_KEY`
   - Environment variable: `export CLICKUP_API_KEY=YOUR_API_KEY`
   - 1Password Environment: store `CLICKUP_API_KEY` in a 1Password Environment and set `OP_ENVIRONMENT_ID`

> 💡 The CLI auto-relaunches inside `.venv/` when present, so activating the virtualenv manually is optional as long as dependencies live there.

### ⚙️ Configuration

Account-specific settings are read from environment variables (no personal
identifiers are hardcoded in source). Copy the example file and fill in your own
values:

```bash
cp .env.example .env
# then edit .env
```

`.env` is gitignored. The supported variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `CLICKUP_WORKSPACE_NAME` | Workspace (team) name to extract from | empty (use `--workspace` or be prompted) |
| `CLICKUP_SPACE_NAME` | Space name within the workspace | empty (use `--space` or be prompted) |
| `CLICKUP_TEAM_ID` | Numeric team ID; fallback when the workspace name can't be resolved | empty (prompted) |
| `CLICKUP_API_KEY` | ClickUp API key | empty |
| `CLICKUP_API_SECRET_REFERENCE` | `op://` reference for the ClickUp key in 1Password | empty (1Password lookup skipped) |
| `GEMINI_API_SECRET_REFERENCE` | `op://` reference for the Gemini key in 1Password | empty (1Password lookup skipped) |
| `CLICKUP_AI_SUMMARY_FIELD_ID` | Override the "Summary" custom-field ID | built-in field ID |
| `OP_ENVIRONMENT_ID` | 1Password Environment ID, if you use Environments | empty |

When the `*_SECRET_REFERENCE` variables are empty, the tool skips the 1Password
lookup and relies on the `CLICKUP_API_KEY` env var, the `--api-key` /
`--gemini-api-key` flags, or an interactive prompt.

### Using the Executable

For users who prefer not to install Python, pre-built executables are available:

1. Download `ClickUpTaskExtractor.exe` from the latest [release](https://github.com/J-MaFf/clickup_task_extractor/releases)
2. Run directly: `ClickUpTaskExtractor.exe` or from command line with options
3. No Python installation required—all dependencies are bundled

**Authentication for Executable Users:**

The executable version does **not** include the 1Password SDK (due to bundling limitations). You have three options:

1. **Environment Variable** (Recommended):

   ```bash
   set CLICKUP_API_KEY=your_api_key_here
   ClickUpTaskExtractor.exe
   ```

2. **Command Line Argument**:

   ```bash
   ClickUpTaskExtractor.exe --api-key your_api_key_here
   ```

3. **1Password CLI** (Advanced):
   Install the [1Password CLI](https://developer.1password.com/docs/cli/get-started/) and ensure it's in your PATH:

   ```bash
   # Environment mode (if OP_ENVIRONMENT_ID is set): op environment read <id>
   # Legacy secret references: op read <secret_reference>
   ClickUpTaskExtractor.exe
   ```

**Example:**

```bash
ClickUpTaskExtractor.exe --output-format Markdown --interactive
```

### Basic Usage

```bash
# Run with default settings (Markdown output). The workspace and space come
# from --workspace/--space or the CLICKUP_WORKSPACE_NAME/CLICKUP_SPACE_NAME
# environment variables (see Configuration below).
python main.py

# Interactive mode - review tasks before export
python main.py --interactive

# Export specific formats
python main.py --output-format Markdown
python main.py --output-format HTML

# Include completed tasks
python main.py --include-completed

# Filter by date range
python main.py --date-filter ThisWeek

# Custom workspace and space
python main.py --workspace "MyWorkspace" --space "MySpace"
```

### Interactive Prompts

When certain options are not specified via CLI arguments, the application will prompt you interactively:

1. **Interactive Mode**: Asks if you want to review and select which tasks to export
2. **AI Summary**: Asks if you want to enable AI-powered task summaries (requires Gemini API key)
3. **Output Format**: Asks you to choose your preferred export format (Markdown or HTML)

Each prompt provides clear options and defaults, making it easy to configure the application on-the-fly without remembering all CLI flags.

## 📅 Weekly KFI Jefferson Sheet Sync

`kfj_task_extractor.py` is a standalone helper that pulls all open tasks from the
ClickUp **KFI Jefferson** list and writes them into the weekly tracking Google
Sheet. It reuses the main extractor's components (API client, sorting, branch
mapping) but runs independently — the standard `main.py` workflow is untouched.

Each run creates a new tab named `KFI Jefferson current tasks (M/D/YY)` (today's
date, no leading zeros), writes the header and task rows
(`Task | Company | Branch | Priority | Status | ETA`) sorted by priority then
ETA, and renames the workbook title to match. Re-running on the same day is
idempotent — the existing tab's contents are replaced rather than duplicated.

### Configuration

This script has **no hardcoded list, sheet, or account** — point it at your own
by setting environment variables (copy the template and edit it):

```bash
cp .env.kfj.example .env.kfj
# then edit .env.kfj
```

`.env.kfj` is gitignored. Supported variables (see `.env.kfj.example` for the
full list):

| Variable | Purpose | Required? |
| --- | --- | --- |
| `KFJ_CLICKUP_LIST_ID` | ClickUp list ID to pull open tasks from (also `--list-id`) | Yes |
| `KFJ_GOOGLE_SHEET_ID` | Google Sheets workbook ID to write to (also `--sheet-id`) | Yes (unless `--dry-run`) |
| `KFJ_TAB_PREFIX` | Worksheet tab name prefix | No (default `KFI Jefferson current tasks`) |
| `KFJ_FALLBACK_BRANCH` | Branch label when a task has no Branch field | No |
| `CLICKUP_API_KEY` | ClickUp API key (resolved before 1Password) | Provide this or a 1Password reference |
| `GOOGLE_SHEETS_CREDENTIALS_JSON` | Google service-account JSON (single line) | Provide this or a 1Password reference |
| `KFJ_CLICKUP_SECRET_REFERENCE` | `op://` reference for the ClickUp key | No (skips 1Password if empty) |
| `KFJ_GOOGLE_SA_SECRET_REFERENCE` | `op://` reference for the service-account JSON | No (skips 1Password if empty) |
| `KFJ_OP_ACCOUNT_NAME` / `KFJ_OP_ACCOUNT_URL` | 1Password account display name / URL | No |

> Finding the IDs: the **list ID** is the number in the ClickUp list URL; the
> **sheet ID** is the long ID in the Google Sheets URL
> (`https://docs.google.com/spreadsheets/d/<ID>/edit`).

```bash
# Standard weekly run (reads .env.kfj from your shell; 1Password resolves secrets)
python kfj_task_extractor.py

# Preview the rows without touching Google Sheets (no sheet ID required)
python kfj_task_extractor.py --dry-run

# Override the list/sheet on the CLI
python kfj_task_extractor.py --list-id <LIST_ID> --sheet-id <SHEET_ID>

# Inject secrets explicitly via op run (fallback path)
op run --account my.1password.com --env-file=.env.kfj -- python kfj_task_extractor.py
```

| Option | Description | Default |
| --- | --- | --- |
| `--list-id` | ClickUp list ID to extract from | `KFJ_CLICKUP_LIST_ID` env var |
| `--sheet-id` | Google Sheets workbook ID to write to | `KFJ_GOOGLE_SHEET_ID` env var |
| `--dry-run` | Fetch and print rows without writing to Sheets | `False` |
| `--date M/D/YY` | Override the date used in the tab name (for backfill) | Today |

**Authentication:** ClickUp uses `CLICKUP_API_KEY` from the environment first,
then (if `KFJ_CLICKUP_SECRET_REFERENCE` is set) the 1Password SDK and the repo's
fallback chain. The Google service account JSON is resolved the same way (env
var `GOOGLE_SHEETS_CREDENTIALS_JSON` → 1Password if `KFJ_GOOGLE_SA_SECRET_REFERENCE`
is set) and parsed in-memory — credentials are never written to disk.

**One-time setup** before the first real run:

1. Enable the **Google Sheets API** in the service account's GCP project.
2. Share the spreadsheet with the service account's `client_email` as **Editor**.
3. Make the ClickUp key and Google SA JSON available to 1Password (SDK desktop
   auth, or an `op run` env file referencing the vault items).
4. `pip install -r requirements.txt` to pick up `gspread`.

## 🔧 Development workflow

- Install deps via `pip install -r requirements.txt` (compatible-release `~=` pins) or `pip install -r requirements.lock` for the exact tested versions; optional features require `onepassword-sdk` and `google-genai` which are already listed. Regenerate `requirements.lock` with `pip freeze` from a clean venv after changing `requirements.txt`.
- Run the extractor with `python main.py` (Markdown export by default). Set the workspace and space via `--workspace`/`--space` or the `CLICKUP_WORKSPACE_NAME`/`CLICKUP_SPACE_NAME` environment variables (see [Configuration](#-configuration)). Other flags: `--output-format`, `--interactive`, `--include-completed`, `--date-filter`, `--ai-summary`, and `--gemini-api-key`.
- Authentication falls back in this order: CLI flag → env var `CLICKUP_API_KEY` → 1Password Environment (`OP_ENVIRONMENT_ID`: SDK first, then `op environment read`) → 1Password SDK secret references → `op read` CLI → manual prompt.
- Logging comes from `logger_config.setup_logging`; pass `use_rich=False` for plain output or a `log_file` path to persist logs.
- All exports land under `output/`, named with `default_output_path()` which strips leading zeros for cross-platform friendly filenames.

### Extending the extractor

- **Add export fields**: Extend `TaskRecord` in `config.py`, update `get_export_fields()`, and ensure Markdown/HTML renderers display the new column.
- **Custom filtering or mapping**: Hook into `_fetch_and_process_tasks()`, reuse `get_date_range()`, and lean on `LocationMapper.map_location()` for dropdowns.
- **Authentication tweaks**: Keep changes inside `load_secret_with_fallback()` so logging and fallback order stay consistent.

## 📖 Documentation

### Command Line Options

| Option | Description | Default |
| --- | --- | --- |
| `--api-key` | ClickUp API key | From environment or 1Password |
| `--workspace` | Workspace name | `CLICKUP_WORKSPACE_NAME` env var (else prompted) |
| `--space` | Space name | `CLICKUP_SPACE_NAME` env var (else prompted) |
| `--output` | Output file path | Auto-generated timestamp |
| `--output-format` | Export format: `Markdown` or `HTML` | Prompted if not specified, defaults to `Markdown` |
| `--include-completed` | Include completed/archived tasks | `False` |
| `--interactive` | Enable interactive task selection | Prompted |
| `--date-filter` | Date filter: `AllOpen`, `ThisWeek`, `LastWeek` | `AllOpen` |
| `--ai-summary` | Enable AI summaries | Prompted |
| `--gemini-api-key` | Google Gemini API key | From 1Password |

### Authentication Methods (Priority Order)

#### For Python Users

1. **Command Line Argument**: `--api-key YOUR_KEY`
2. **Environment Variable**: `CLICKUP_API_KEY=YOUR_KEY`
3. **1Password Environment**: Requires `OP_ENVIRONMENT_ID` and a 1Password Environment containing `CLICKUP_API_KEY`
   - Primary: Python SDK (DesktopAuth or service token)
   - Fallback: 1Password CLI via `op environment read <environment_id>`
4. **1Password SDK**: Requires `OP_SERVICE_ACCOUNT_TOKEN` environment variable for legacy secret references
5. **1Password CLI**: Uses `op read` command for legacy secret references
6. **Manual Prompt**: Rich console input as the final fallback

#### For Executable (EXE) Users

1. **Command Line Argument**: `--api-key YOUR_KEY`
2. **Environment Variable**: `CLICKUP_API_KEY=YOUR_KEY`
3. **1Password Environment via CLI**: If `OP_ENVIRONMENT_ID` is set, uses `op environment read <environment_id>` (SDK not available in EXE)
4. **1Password CLI**: Uses `op read` command for legacy secret references
5. **Manual Prompt**: Rich console input as the final fallback

**Note**: The 1Password SDK cannot be bundled in the executable due to native dependencies. EXE users should use environment variables, command line arguments, or install the [1Password CLI](https://developer.1password.com/docs/cli/get-started/) separately.

Store secrets in 1Password for reuse:

- ClickUp API key: `CLICKUP_API_KEY` in a 1Password Environment
- Gemini API key: `GEMINI_API_KEY` in the same 1Password Environment

For Python users with 1Password Environment SDK:

```bash
export OP_ENVIRONMENT_ID=your_environment_id
export OP_ACCOUNT_NAME=my.1password.com
```

## 🏗️ Architecture

```text
clickup_task_extractor/
├── main.py                    # CLI entry, venv handoff, config assembly, auth chain
├── config.py                  # Enum config, TaskRecord dataclass, datetime helpers
├── auth.py                    # 1Password SDK/CLI loader with structured logging
├── api_client.py              # APIClient protocol + ClickUpAPIClient (requests, 30 s timeout)
├── extractor.py               # ClickUpTaskExtractor workflow, exports, interactive UI
├── ai_summary.py              # Gemini summaries with retry/backoff and graceful fallback
├── mappers.py                 # Prompts, date filters, dropdown mapping, image extraction
├── logger_config.py           # Rich-enhanced logging setup and helper accessor
├── requirements.txt           # Dependency manifest
└── output/                    # Generated reports (Markdown/HTML)
```

### Key Components

- **`main.py`**: Builds `ClickUpConfig`, orchestrates auth fallback, and prompts for interactive mode/AI summaries.
- **`ClickUpConfig` & `TaskRecord`**: Enum-backed config (string-friendly fallbacks) plus an export dataclass whose `_metadata` stores raw task content for AI summaries.
- **`ClickUpTaskExtractor`**: Walks workspace → space → lists → tasks, caches custom fields, filters by status/date, and uses `export_file()` for all I/O.
- **`LocationMapper` utilities**: Map dropdown IDs via id → orderindex → name priority, extract images, and provide consistent yes/no prompts.
- **`ai_summary.get_ai_summary`**: Talks to Google Gemini with **tiered model strategy**: tries `gemini-2.5-flash-lite` (500 RPD) first, switches to `gemini-2.5-pro` (1,500 RPD separate bucket) on rate limit, then `gemini-2.0-flash` as fallback. Parses retry hints, shows progress bars during waits, and falls back to original text if SDK or key is missing.
- **`logger_config.setup_logging`**: Installs Rich tracebacks, emits to stdout, and optionally writes to disk.

## 📊 Output Examples

### Markdown Export (Default)

- Structured Markdown sections optimized for readability and lint compliance
- Task details with status, priority, and custom fields
- Cross-platform date formatting (e.g., "10/7/2025 at 3:45 PM" for October 7, 2025 - MM/DD/YYYY format)
- Image extraction from task descriptions

### HTML Export

- Professional-looking HTML tables with CSS styling
- Task summaries with status, priority, and custom fields
- Cross-platform date formatting (e.g., "10/7/2025 at 3:45 PM" for October 7, 2025 - MM/DD/YYYY format)
- Image extraction from task descriptions

### Interactive Mode

- Rich console interface for task review
- Filter and select specific tasks before export
- Real-time progress indicators

## 🤖 AI Integration

Optional Google Gemini AI integration provides:

- Intelligent 1-2 sentence task summaries
- Automatic rate limiting and retry logic with tiered model fallback
- Daily quota exhaustion detection to prevent wasted API calls
- Graceful fallback to original content if AI fails

Enable AI summaries:

```bash
python main.py --ai-summary --gemini-api-key YOUR_KEY
```

### Model Tiering & Rate Limiting

The AI integration uses a **tiered model strategy** to handle rate limits gracefully:

**Tier 1 (Primary)**: `gemini-2.5-flash-lite`

- 500 requests/day (free tier)
- Fastest and most cost-effective
- Best for routine task summarization

**Tier 2 (Fallback)**: `gemini-2.5-pro`

- 1,500 requests/day (separate quota bucket)
- Better quality reasoning
- Activated when Tier 1 hits rate limits

**Tier 3 (Emergency)**: `gemini-2.0-flash`

- 500 requests/day
- Stable alternative if Tier 2 unavailable

**Rate Limit Handling**:

The system automatically switches to the next tier when rate limit is detected via:

- HTTP 429 status codes
- RESOURCE_EXHAUSTED errors from Google API
- 'quota' or 'rate limit' keywords in error messages (case-insensitive)
- Per-minute (RPM) quota detection for fine-grained control
- Per-day (RPD) quota detection for daily limit tracking

Additional features:

- Shows progress bar while waiting for quota to reset
- Applies exponential backoff (2^attempt seconds) for transient errors before switching tiers
- Logs which model tier was used for transparency
- Falls back to original task fields if all tiers exhausted

### Daily Quota (RPD) Exhaustion

When all model tiers exhaust their daily quota (usually around midnight Pacific time):

1. System detects "requests per day" or "RPD" errors
2. Sets a global `_daily_quota_exhausted` flag
3. **Skips AI summaries for remaining tasks without making API calls**
4. Displays: `[⊘] Daily quota exhausted - skipping AI summary for: Task Name`
5. Returns to original task content automatically

This prevents repeated failed API attempts throughout the rest of the day when daily limits are exhausted. The quota limit resets at midnight Pacific time for free tier accounts.

**Manual Reset (For Testing)**:

If you need to manually reset the daily quota state:

```python
from ai_summary import _reset_daily_quota_state
_reset_daily_quota_state()
```

## 🛠️ Requirements

### Core Dependencies

- `requests>=2.25.0` - HTTP client for ClickUp API
- `rich>=14.0.0` - Beautiful console interfaces

### Optional Dependencies

- `onepassword-sdk>=0.3.1` - Secure credential management
- `google-genai>=1.0.0` - AI-powered task summaries

## 🐛 Troubleshooting

### Common Issues

**Authentication Errors:**

- Verify your ClickUp API key is valid
- Check 1Password integration setup
- Ensure environment variables are set correctly

**1Password Integration (Executable Users):**

If you see errors like "1Password SDK not available" or "op command not found" when using the executable:

1. **Using Environment Variables (Easiest)**:

   ```bash
   # Windows Command Prompt
   set CLICKUP_API_KEY=your_api_key_here
   ClickUpTaskExtractor.exe

   # Windows PowerShell
   $env:CLICKUP_API_KEY="your_api_key_here"
   .\ClickUpTaskExtractor.exe
   ```

2. **Using Command Line Argument**:

   ```bash
   ClickUpTaskExtractor.exe --api-key your_api_key_here
   ```

3. **Using 1Password CLI** (if you prefer 1Password):
   - Install 1Password CLI from: <https://developer.1password.com/docs/cli/get-started/>
   - Ensure `op` command is in your PATH
   - The executable will automatically use it

**Note**: The 1Password SDK is only available when running the Python version, not the compiled executable. This is a known limitation due to native dependencies.

**Import Errors:**

- Install dependencies: `pip install -r requirements.txt`
- Check Python version (3.11+ required)
- Verify virtual environment activation

**API Rate Limiting:**

- AI summaries include automatic retry logic
- Reduce concurrent requests if needed

### Debug Mode

Enable detailed logging:

```python
from logger_config import setup_logging
import logging

logger = setup_logging(logging.DEBUG, "debug.log")
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/new-feature`
3. Follow the existing code style and architecture patterns
4. Add tests for new functionality
5. Update documentation as needed
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Rich](https://github.com/Textualize/rich) for beautiful console output
- Uses [1Password SDK](https://github.com/1Password/onepassword-sdk-python) for secure credential management
- Powered by [Google Gemini AI](https://ai.google.dev/) for intelligent summaries
- Integrates with [ClickUp API v2](https://clickup.com/api) for task management

---

Made with ❤️ for productivity and beautiful code
