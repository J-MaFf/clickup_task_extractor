# ClickUp Task Extractor 📋

A powerful, cross-platform Python application for extracting, processing, and exporting tasks from the ClickUp API with beautiful console interfaces and AI-powered summaries.

![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Version](https://img.shields.io/badge/version-1.02-green.svg)
![Rich](https://img.shields.io/badge/rich-14.0%2B-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ Features

- 🔐 **Secure Authentication**: Multiple authentication methods including 1Password integration
- 🎨 **Beautiful UI**: Rich console interfaces with progress bars, panels, and styled output
- 🤖 **AI Summaries**: Optional Google Gemini AI integration for intelligent task summaries
- 📊 **Multiple Export Formats**: CSV, HTML, Markdown, PDF, or combined formats with professional styling
- 🔍 **Interactive Mode**: Review and select tasks before export with user-friendly prompts
- 📄 **Interactive Format Selection**: Choose output format at runtime via intuitive prompt
- 📅 **Flexible Filtering**: Date range filtering (This Week, Last Week, All Open)
- 🌐 **Cross-Platform**: Works on Windows, macOS, and Linux
- ⚡ **Modern Architecture**: Clean, modular design following SOLID principles

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- ClickUp API token
- Optional: 1Password CLI or SDK for secure credential management
- Optional: Google Gemini API key for AI summaries

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/J-MaFf/clickup_task_extractor.git
   cd clickup_task_extractor
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your ClickUp API key** (choose one method):
   - Command line: `python main.py --api-key YOUR_API_KEY`
   - Environment variable: `export CLICKUP_API_KEY=YOUR_API_KEY`
   - 1Password: Store in 1Password with reference `op://Home Server/ClickUp personal API token/credential`

> 💡 The CLI auto-relaunches inside `.venv/` when present, so activating the virtualenv manually is optional as long as dependencies live there.

> 📝 **Note**: PDF export is currently supported via WeasyPrint. A migration to fpdf2 (pure Python, no system dependencies required) is planned in [issue #63](https://github.com/J-MaFf/clickup_task_extractor/issues/63) to eliminate the need for external runtime libraries.

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
   # The executable will automatically try to use 'op read' command
   ClickUpTaskExtractor.exe
   ```

**Example:**

```bash
ClickUpTaskExtractor.exe --output-format Both --interactive
```

### Basic Usage

```bash
# Run with default settings (HTML output, KMS workspace, Kikkoman space)
python main.py

# Interactive mode - review tasks before export
python main.py --interactive

# Export specific formats
python main.py --output-format Markdown
python main.py --output-format PDF
python main.py --output-format Both  # CSV + HTML

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
3. **Output Format**: Asks you to choose your preferred export format (CSV, HTML, Markdown, PDF, or Both)

Each prompt provides clear options and defaults, making it easy to configure the application on-the-fly without remembering all CLI flags.

## 🔧 Development workflow

- Install deps via `pip install -r requirements.txt`; optional features require `onepassword-sdk` and `google-generativeai` which are already listed.
- Run the extractor with `python main.py` (defaults: workspace `KMS`, space `Kikkoman`, HTML export). Override with `--output-format`, `--interactive`, `--include-completed`, `--date-filter`, `--ai-summary`, and `--gemini-api-key`.
- Authentication falls back in this order: CLI flag → env var `CLICKUP_API_KEY` → 1Password SDK (requires `OP_SERVICE_ACCOUNT_TOKEN`) → `op read` CLI → manual prompt.
- Logging comes from `logger_config.setup_logging`; pass `use_rich=False` for plain output or a `log_file` path to persist logs.
- All exports land under `output/`, named with `default_output_path()` which strips leading zeros for cross-platform friendly filenames.

### Extending the extractor

- **Add export fields**: Extend `TaskRecord` in `config.py`, update `get_export_fields()`, and ensure HTML/Markdown renderers display the new column.
- **New output formats**: Add an `OutputFormat` enum value, surface it in CLI choices, and implement the exporter inside `ClickUpTaskExtractor.export()` using `export_file()`.
- **Custom filtering or mapping**: Hook into `_fetch_and_process_tasks()`, reuse `get_date_range()`, and lean on `LocationMapper.map_location()` for dropdowns.
- **Authentication tweaks**: Keep changes inside `load_secret_with_fallback()` so logging and fallback order stay consistent.

## 📖 Documentation

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--api-key` | ClickUp API key | From environment or 1Password |
| `--workspace` | Workspace name | `KMS` |
| `--space` | Space name | `Kikkoman` |
| `--output` | Output file path | Auto-generated timestamp |
| `--output-format` | Export format: `CSV`, `Markdown`, `PDF`, `Both` | Prompted if not specified, defaults to `HTML` |
| `--include-completed` | Include completed/archived tasks | `False` |
| `--interactive` | Enable interactive task selection | Prompted |
| `--date-filter` | Date filter: `AllOpen`, `ThisWeek`, `LastWeek` | `AllOpen` |
| `--ai-summary` | Enable AI summaries | Prompted |
| `--gemini-api-key` | Google Gemini API key | From 1Password |

### Authentication Methods (Priority Order)

#### For Python Users

1. **Command Line Argument**: `--api-key YOUR_KEY`
2. **Environment Variable**: `CLICKUP_API_KEY=YOUR_KEY`
3. **1Password SDK**: Requires `OP_SERVICE_ACCOUNT_TOKEN` environment variable
4. **1Password CLI**: Uses `op read` command
5. **Manual Prompt**: Rich console input as the final fallback

#### For Executable (EXE) Users

1. **Command Line Argument**: `--api-key YOUR_KEY`
2. **Environment Variable**: `CLICKUP_API_KEY=YOUR_KEY`
3. **1Password CLI**: Uses `op read` command (SDK not available in EXE)
4. **Manual Prompt**: Rich console input as the final fallback

**Note**: The 1Password SDK cannot be bundled in the executable due to native dependencies. EXE users should use environment variables, command line arguments, or install the [1Password CLI](https://developer.1password.com/docs/cli/get-started/) separately.

Store secrets in 1Password for reuse:

- ClickUp API key: `op://Home Server/ClickUp personal API token/credential`
- Gemini API key: `op://Home Server/nftoo3gsi3wpx7z5bdmcsvr7p4/credential`

For Python users with 1Password SDK:

```bash
export OP_SERVICE_ACCOUNT_TOKEN=your_service_account_token
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
└── output/                    # Generated reports (HTML/CSV/Markdown/PDF)
```

### Key Components

- **`main.py`**: Builds `ClickUpConfig`, orchestrates auth fallback, and prompts for interactive mode/AI summaries.
- **`ClickUpConfig` & `TaskRecord`**: Enum-backed config (string-friendly fallbacks) plus an export dataclass whose `_metadata` stores raw task content for AI summaries.
- **`ClickUpTaskExtractor`**: Walks workspace → space → lists → tasks, caches custom fields, filters by status/date, and uses `export_file()` for all I/O.
- **`LocationMapper` utilities**: Map dropdown IDs via id → orderindex → name priority, extract images, and provide consistent yes/no prompts.
- **`ai_summary.get_ai_summary`**: Talks to Google Gemini with **tiered model strategy**: tries `gemini-2.5-flash-lite` (500 RPD) first, switches to `gemini-2.5-pro` (1,500 RPD separate bucket) on rate limit, then `gemini-2.0-flash` as fallback. Parses retry hints, shows progress bars during waits, and falls back to original text if SDK or key is missing.
- **`logger_config.setup_logging`**: Installs Rich tracebacks, emits to stdout, and optionally writes to disk.

## 📊 Output Examples

### HTML Export (Default)

- Professional-looking HTML tables with CSS styling
- Task summaries with status, priority, and custom fields
- Cross-platform date formatting (e.g., "10/7/2025 at 3:45 PM" for October 7, 2025 - MM/DD/YYYY format)
- Image extraction from task descriptions

### CSV Export

- Standard CSV format compatible with Excel and other tools
- All task fields including custom field mappings
- Configurable field exclusions

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
- `google-generativeai>=0.8.0` - AI-powered task summaries

## 🐛 Troubleshooting

### PDF Export Issues

**WeasyPrint GTK3 Dependencies:**

Current PDF export uses WeasyPrint which requires system-level GTK3 runtime libraries. This is being addressed in [issue #63](https://github.com/J-MaFf/clickup_task_extractor/issues/63) with a planned migration to fpdf2 (pure Python, no system dependencies).

For now, if you encounter PDF generation errors:

1. Verify dependencies are installed: `pip install -r requirements.txt`
2. On Windows, the GTK3 runtime may be required (though support for this will be removed in the fpdf2 migration)

**Future**: Once issue #63 is resolved, PDF export will work without any system dependencies.

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
