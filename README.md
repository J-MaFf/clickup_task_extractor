# ClickUp Task Extractor 📋

A powerful, cross-platform Python application for extracting, processing, and exporting tasks from the ClickUp API with beautiful console interfaces and AI-powered summaries.

![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Rich](https://img.shields.io/badge/rich-14.0%2B-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ Features

- 🔐 **Secure Authentication**: Multiple authentication methods including 1Password integration
- 🎨 **Beautiful UI**: Rich console interfaces with progress bars, panels, and styled output
- 🤖 **AI Summaries**: Optional Google Gemini AI integration for intelligent task summaries
- 📊 **Multiple Export Formats**: CSV, HTML, or both with professional styling
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

3. **Set up your ClickUp API key** (choose one method):
   - Command line: `python main.py --api-key YOUR_API_KEY`
   - Environment variable: `export CLICKUP_API_KEY=YOUR_API_KEY`
   - 1Password: Store in 1Password with reference `op://Home Server/ClickUp personal API token/credential`

### Basic Usage

```bash
# Run with default settings (HTML output, KMS workspace, Kikkoman space)
python main.py

# Interactive mode - review tasks before export
python main.py --interactive

# Export both CSV and HTML formats
python main.py --output-format Both

# Include completed tasks
python main.py --include-completed

# Filter by date range
python main.py --date-filter ThisWeek

# Custom workspace and space
python main.py --workspace "MyWorkspace" --space "MySpace"
```

## 📖 Documentation

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--api-key` | ClickUp API key | From environment or 1Password |
| `--workspace` | Workspace name | `KMS` |
| `--space` | Space name | `Kikkoman` |
| `--output` | Output file path | Auto-generated timestamp |
| `--output-format` | Export format: `CSV`, `HTML`, `Both` | `HTML` |
| `--include-completed` | Include completed/archived tasks | `False` |
| `--interactive` | Enable interactive task selection | Prompted |
| `--date-filter` | Date filter: `AllOpen`, `ThisWeek`, `LastWeek` | `AllOpen` |
| `--ai-summary` | Enable AI summaries | Prompted |
| `--gemini-api-key` | Google Gemini API key | From 1Password |

### Authentication Methods (Priority Order)

1. **Command Line Argument**: `--api-key YOUR_KEY`
2. **Environment Variable**: `CLICKUP_API_KEY=YOUR_KEY`
3. **1Password SDK**: Requires `OP_SERVICE_ACCOUNT_TOKEN` environment variable
4. **1Password CLI**: Requires `op` command in PATH
5. **Manual Input**: Prompted during execution

### 1Password Integration

For secure credential management, store your API keys in 1Password:

- **ClickUp API Key**: `op://Home Server/ClickUp personal API token/credential`
- **Gemini API Key**: `op://Home Server/nftoo3gsi3wpx7z5bdmcsvr7p4/credential`

Set up 1Password SDK:

```bash
export OP_SERVICE_ACCOUNT_TOKEN=your_service_account_token
```

## 🏗️ Architecture

The project follows a clean, modular architecture:

```text
clickup_task_extractor/
├── main.py                    # Entry point and CLI parsing
├── clickup_task_extractor.py  # Legacy entry point (backward compatibility)
├── config.py                  # Configuration and data models
├── auth.py                    # Authentication and 1Password integration
├── api_client.py              # ClickUp API client with error handling
├── extractor.py               # Main business logic and export functionality
├── ai_summary.py              # Google Gemini AI integration
├── mappers.py                 # Data mapping and utility functions
├── logger_config.py           # Logging configuration
├── requirements.txt           # Python dependencies
└── output/                    # Generated export files
```

### Key Components

- **`ClickUpConfig`**: Type-safe configuration with enum-based options
- **`TaskRecord`**: Structured data model for exported tasks
- **`APIClient`**: Protocol-based HTTP client for ClickUp API
- **`ClickUpTaskExtractor`**: Main orchestrator following single responsibility principle
- **Rich Console Integration**: Beautiful progress bars, tables, and panels

## 🔧 Development

### Project Structure

```python
# Type-safe configuration pattern
config = ClickUpConfig(
    output_format=OutputFormat.HTML,  # Enum-based for type safety
    date_filter=DateFilter.THIS_WEEK
)

# Protocol-based dependency injection
def process_tasks(client: APIClient) -> list[TaskRecord]:
    return client.get("/tasks")

# Context manager for safe file operations
with export_file(output_path, 'w') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
```

### Development Guidelines

- **SOLID Principles**: Modular architecture with single responsibility
- **Modern Type Hints**: Uses `list[T]`, `dict[K,V]`, `str | None` syntax
- **Error Handling**: Specific exceptions with proper chaining
- **Resource Management**: Context managers for file operations
- **Cross-Platform**: Uses `pathlib` for file operations

### Adding New Features

- **New export fields**: Update `TaskRecord` dataclass in `config.py`
- **New output formats**: Extend `export` method in `extractor.py`
- **New authentication methods**: Extend authentication chain in `auth.py`
- **New custom field mappings**: Extend `LocationMapper` class in `mappers.py`

## 📊 Output Examples

### HTML Export (Default)

- Professional-looking HTML tables with CSS styling
- Task summaries with status, priority, and custom fields
- Cross-platform date formatting (e.g., "8/1/2025 at 3:45 PM")
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
