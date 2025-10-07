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
- 🔍 **Interactive Mode**: Review and select tasks before export
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

3. **(Windows, for PDF export)** Install WeasyPrint runtime libraries (Cairo, Pango, etc.). The simplest option is the GTK3 bundle:

   ```powershell
   winget install Gnome.Project.Gtk3
   ```

   > Alternatively, download the GTK3 Runtime installer from [tschoonj/GTK-for-Windows-Runtime-Environment-Installer](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases) and let it add the DLLs to your PATH.

4. **Install WeasyPrint inside the virtual environment** (if you plan to export PDFs):

   ```bash
   python -m pip install weasyprint
   ```

5. **Set up your ClickUp API key** (choose one method):
   - Command line: `python main.py --api-key YOUR_API_KEY`
   - Environment variable: `export CLICKUP_API_KEY=YOUR_API_KEY`
   - 1Password: Store in 1Password with reference `op://Home Server/ClickUp personal API token/credential`

> 💡 The CLI auto-relaunches inside `.venv/` when present, so activating the virtualenv manually is optional as long as dependencies live there.

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
| `--output-format` | Export format: `CSV`, `Markdown`, `PDF`, `Both` | `HTML` |
| `--include-completed` | Include completed/archived tasks | `False` |
| `--interactive` | Enable interactive task selection | Prompted |
| `--date-filter` | Date filter: `AllOpen`, `ThisWeek`, `LastWeek` | `AllOpen` |
| `--ai-summary` | Enable AI summaries | Prompted |
| `--gemini-api-key` | Google Gemini API key | From 1Password |

### Authentication Methods (Priority Order)

1. **Command Line Argument**: `--api-key YOUR_KEY`
2. **Environment Variable**: `CLICKUP_API_KEY=YOUR_KEY`
3. **1Password SDK**: Requires `OP_SERVICE_ACCOUNT_TOKEN`
4. **1Password CLI**: Uses `op read`
5. **Manual Prompt**: Rich console input as the final fallback

Store secrets in 1Password for reuse:

- ClickUp API key: `op://Home Server/ClickUp personal API token/credential`
- Gemini API key: `op://Home Server/nftoo3gsi3wpx7z5bdmcsvr7p4/credential`

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
- **`ai_summary.get_ai_summary`**: Talks to `gemini-2.5-flash-lite`, parses retry hints, and falls back to original text if the SDK or key is missing.
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
- Automatic rate limiting and retry logic
- Graceful fallback to original content if AI fails

Enable AI summaries:

```bash
python main.py --ai-summary --gemini-api-key YOUR_KEY
```

Implementation details:

- Uses `gemini-2.5-flash-lite` via the official `google-generativeai` SDK.
- Retries up to three times on 429s, parsing `retryDelay` hints when available and showing Rich progress while waiting.
- Falls back to raw subject/description/resolution text when the SDK is missing or the key is unavailable.

## 🛠️ Requirements

### Core Dependencies

- `requests>=2.25.0` - HTTP client for ClickUp API
- `rich>=14.0.0` - Beautiful console interfaces

### Optional Dependencies

- `onepassword-sdk>=0.3.1` - Secure credential management
- `google-generativeai>=0.8.0` - AI-powered task summaries

## 🐛 Troubleshooting

### Common Issues

**Authentication Errors:**

- Verify your ClickUp API key is valid
- Check 1Password integration setup
- Ensure environment variables are set correctly

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
