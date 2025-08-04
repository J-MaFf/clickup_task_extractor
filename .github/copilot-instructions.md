# Copilot Instructions for ClickUp Task Extractor

## Core Development Guidelines

**IMPORTANT**: Follow the comprehensive Python development guidelines specified in `.github/Python.prompt.md`. This includes:
- SOLID principles and modular architecture
- Modern type hints and type safety (uses `list[T]`, `dict[K,V]`, `str | None` syntax)
- Proper error handling with specific exceptions (no bare `except:`)
- Context managers for resource management
- Protocol-based design over inheritance
- Pathlib for cross-platform file operations
- Comprehensive docstrings and code documentation
- Enum classes for type-safe constants

The guidelines in `.github/Python.prompt.md` provide the foundation for all Python code in this project. The instructions below specify project-specific patterns and conventions that build upon those universal principles.

## Project Overview
This project is a Python script for extracting, processing, and exporting tasks from the ClickUp API. It features modern Python architecture following SOLID principles, cross-platform compatibility, 1Password integration for secure API key management, interactive task selection, and Rich console interfaces with progress bars and styled output.

## Architecture & Key Components

### **Modular Architecture**
The project follows clean modular architecture with single responsibility principle:

- **`config.py`**: Configuration & Data Models ⭐ **Recently Modernized**
  - `ClickUpConfig` dataclass: Type-safe configuration with Enum fields
  - `TaskRecord` dataclass: Exported task structure with modern type hints
  - **Enums**: `TaskPriority`, `OutputFormat`, `DateFilter` for type safety
  - Date formatting utilities (`format_datetime`) with cross-platform compatibility

- **`logger_config.py`**: Logging Infrastructure ⭐ **New Addition**
  - `setup_logging()`: Configurable console/file logging with proper formatting
  - `get_logger()`: Logger factory function for consistent logging across modules
  - Professional logging patterns following Python best practices

- **`auth.py`**: Authentication & Security
  - 1Password SDK/CLI integration with fallback chain
  - Secure API key retrieval: CLI args → env vars → 1Password SDK → CLI → manual input
  - Gemini API key management for AI features

- **`api_client.py`**: ClickUp API Integration
  - `APIClient` protocol: Structural typing interface for dependency inversion
  - `ClickUpAPIClient` class: HTTP client with comprehensive error handling
  - Custom exceptions: `APIError`, `AuthenticationError` with proper chaining

- **`ai_summary.py`**: AI Integration
  - Google Gemini API integration with intelligent rate limiting
  - Progress bars for long-running AI operations
  - Graceful fallback handling for API failures

- **`mappers.py`**: Data Mapping & Utilities
  - `LocationMapper` class: Custom field mapping with multiple fallback strategies
  - `get_date_range()`: Enum-aware date filtering (supports both DateFilter enums and strings)
  - Utility functions with proper type hints and error handling

- **`extractor.py`**: Main Business Logic
  - `ClickUpTaskExtractor` class: Main orchestrator following Single Responsibility
  - `export_file()` context manager: Safe file operations with automatic cleanup
  - Interactive task selection with Rich console interfaces
  - Type-safe CSV/HTML export supporting enum-based configuration

- **`main.py`**: Entry Point & CLI
  - Enum-aware argument parsing with backward compatibility
  - Virtual environment auto-switching for cross-platform compatibility
  - Beautiful Rich console interfaces with configuration summaries

- **`clickup_task_extractor.py`**: Legacy Compatibility
  - Backward-compatible entry point preserving existing CLI interface
  - Interactive task selection functionality (`interactive_include`)
  - CSV and HTML export with styled output

- **`main.py`**: Entry Point & CLI
  - `main()` function: CLI argument parsing and application orchestration
  - Virtual environment switching logic for cross-platform compatibility
  - Authentication chain management

- **`clickup_task_extractor.py`**: Legacy Compatibility
  - Backward-compatible entry point that delegates to the new modular architecture
  - Preserves existing command-line interface for users

## Data Flow & Processing Pipeline
1. **Authentication Chain**: Multi-fallback API key retrieval (CLI → env → 1Password SDK → CLI → manual)
2. **Configuration**: Type-safe enum-based config with backward compatibility for string inputs
3. **API Client**: Protocol-based HTTP client fetches workspaces, spaces, lists, and tasks
4. **Task Processing**: Status filtering → custom field mapping → TaskRecord creation
5. **Interactive Selection** (optional): Rich console interface for task review/filtering
6. **Export**: Context manager-based file operations with enum-aware format selection (CSV/HTML/Both)

## Critical Developer Patterns

### **Type-Safe Configuration Pattern**
```python
# Always use enums for configuration - provides intellisense and prevents typos
config = ClickUpConfig(
    output_format=OutputFormat.HTML,  # Not string "HTML"
    date_filter=DateFilter.THIS_WEEK  # Not string "ThisWeek"
)

# But backward compatibility is maintained for string inputs
if isinstance(filter_input, str):
    date_filter = DateFilter(filter_input)  # Auto-converts
```

### **Protocol-Based Dependency Injection**
```python
# Use APIClient protocol for testing and flexibility
def process_tasks(client: APIClient) -> list[TaskRecord]:
    # Depends on protocol, not concrete implementation
    return client.get("/tasks")

# Concrete implementation
client = ClickUpAPIClient(api_key)
```

### **Context Manager Resource Pattern**
```python
# All file I/O uses the export_file context manager
with export_file(output_path, 'w') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    # Automatic cleanup and error handling
```

### **Custom Field Mapping Strategy**
```python
# LocationMapper uses id → orderindex → name fallback strategy
mapper = LocationMapper()
location = mapper.map_field_value(custom_field_data, 'location')
# Always check all three mapping strategies before falling back
```

### **Rich Console Integration Pattern**
```python
# Use Rich for all user interfaces - progress bars, panels, tables
with Progress() as progress:
    task = progress.add_task("Processing...", total=len(items))
    # Rich provides beautiful cross-platform console output
```

## Authentication Priority
1. Command line argument (`--api-key`)
2. Environment variable (`CLICKUP_API_KEY`)
3. 1Password SDK (requires `OP_SERVICE_ACCOUNT_TOKEN`)
4. 1Password CLI fallback (requires `op` command)
5. Manual input prompt

## Developer Workflows & Commands
- **Run application**: `python main.py` or `python clickup_task_extractor.py`
- **Interactive mode**: `python main.py --interactive`
- **Test imports**: `python -c "import config; print('✅ Config loaded')"`
- **Type checking**: All modules use modern type hints - no external type checker needed
- **Virtual environment**: Auto-switches on startup (cross-platform)
- **Dependencies**: Core=`requests`; Optional=`onepassword-sdk`, `google-genai`, `rich`
- **No build/test commands**: Pure Python script with no external build system

## Development Setup & Environment
- **Python Guidelines**: Uses centralized guidelines via `.github/Python.prompt.md` symlink
- **Logging**: Use `logger_config.setup_logging()` for consistent logging across modules
- **Cross-platform**: All paths use `pathlib.Path`, date formatting removes leading zeros
- **Virtual Environment**: Automatically detected and switched to `.venv/` on startup

## Project-Specific Conventions & Patterns

**Following .github/Python.prompt.md principles in ClickUp-specific ways:**

- **Enum-based configuration**: All config options use type-safe enums with backward compatibility
- **Protocol patterns**: `APIClient` protocol enables dependency inversion and testing
- **Context managers**: `export_file()` handles all file I/O with automatic cleanup
- **Multi-strategy mapping**: `LocationMapper` tries id → orderindex → name fallback
- **Rich UI patterns**: All user interaction uses Rich console (progress bars, panels, tables)
- **Date formatting**: Cross-platform compatibility without leading zeros via post-processing
- **Authentication chain**: Multiple fallback methods in priority order
- **Export flexibility**: Single method handles CSV/HTML/Both via enum configuration
- **Interactive selection**: Built-in task review/filtering before export
- **Type safety**: Modern syntax (`list[str]`, `str | None`) with meaningful type aliases
- **Error specificity**: Custom exceptions (`APIError`, `AuthenticationError`) with proper chaining
- **Resource safety**: Pathlib for all file operations, context managers for resources

## Development Guidelines

**Following .github/Python.prompt.md principles in this project:**

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
- **Flexible output**: Support for CSV, HTML, or both formats simultaneously

## Configuration Options
- `workspace_name`: ClickUp workspace (default: 'KMS')
- `space_name`: ClickUp space (default: 'Kikkoman')
- `output_format`: Export format - `OutputFormat.CSV`, `OutputFormat.HTML`, or `OutputFormat.BOTH` (default: HTML)
- `include_completed`: Include completed/archived tasks (default: False)
- `interactive_selection`: Enable task review and selection (default: False, prompted if not set)
- `exclude_statuses`: List of task statuses to exclude (default: ['Blocked', 'Dormant', 'On Hold', 'Document'])
- `date_filter`: Date filtering - `DateFilter.ALL_OPEN`, `DateFilter.THIS_WEEK`, `DateFilter.LAST_WEEK` (default: ALL_OPEN)
- `enable_ai_summary`: Enable AI summarization (requires gemini_api_key)

## Examples
- **Basic usage**: `python clickup_task_extractor.py`
- **Interactive mode**: `python clickup_task_extractor.py --interactive`
- **Custom workspace**: `python clickup_task_extractor.py --workspace "MyWorkspace" --space "MySpace"`
- **Both outputs**: `python clickup_task_extractor.py --output-format Both`
- **Include completed**: `python clickup_task_extractor.py --include-completed`
- **With API key**: `python clickup_task_extractor.py --api-key YOUR_KEY`

## Key Files
- **`main.py`**: Primary entry point with CLI parsing and orchestration
- **`clickup_task_extractor.py`**: Legacy entry point for backward compatibility
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
