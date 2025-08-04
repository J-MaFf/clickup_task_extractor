# Copilot Instructions for ClickUp Task Extractor

## Core Development Guidelines

**IMPORTANT**: Follow the comprehensive Python development guidelines specified in `.github/Python.prompt.md`. This includes:
- SOLID principles and modular architecture
- Modern type hints and type safety
- Proper error handling with specific exceptions
- Context managers for resource management
- Protocol-based design over inheritance
- Pathlib for cross-platform file operations
- Comprehensive docstrings and code documentation

The guidelines in `.github/Python.prompt.md` provide the foundation for all Python code in this project. The instructions below specify project-specific patterns and conventions that build upon those universal principles.

## Project Overview
This project is a Python script for extracting, processing, and exporting tasks from the ClickUp API. It is designed to match the output and features of a PowerShell-based workflow, with a focus on clarity, maintainability, and adherence to SOLID principles. The script features cross-platform compatibility, 1Password integration for secure API key management, and interactive task selection.

## Architecture & Key Components

### **Modular Architecture (Post-Refactoring)**
The project now follows a clean modular architecture with single responsibility principle:

- **`config.py`**: Configuration & Data Models
  - `ClickUpConfig` dataclass: Centralizes configuration (API key, workspace/space names, output options, etc.)
  - `TaskRecord` dataclass: Represents exported task fields (Task, Company, Branch, Priority, Status, ETA, Notes, Extra)
  - Date formatting constants and utilities (`TIMESTAMP_FORMAT`, `DISPLAY_FORMAT`, `format_datetime`)

- **`auth.py`**: Authentication & Security
  - 1Password SDK/CLI integration functions (`_load_secret_with_fallback`, `get_secret_from_1password`)
  - Secure API key retrieval with multiple fallback methods
  - Gemini API key management for AI features

- **`api_client.py`**: ClickUp API Integration
  - `ClickUpAPIClient` class: Handles all HTTP requests with comprehensive error handling
  - Debugging information for failed requests
  - All API interactions go through this class

- **`ai_summary.py`**: AI Integration
  - `get_ai_summary()` function: Google Gemini API integration for task summarization
  - Rate limiting and retry logic with intelligent progress bars
  - Fallback handling for API failures

- **`mappers.py`**: Data Mapping & Utilities
  - `LocationMapper` class: Maps ClickUp custom field values to human-readable labels
  - Utility functions: `get_yes_no_input()`, `get_date_range()`, `extract_images()`
  - Multiple fallback matching strategies (id → orderindex → name)

- **`extractor.py`**: Main Business Logic
  - `ClickUpTaskExtractor` class: Main orchestrator for task processing and export
  - Interactive task selection functionality (`interactive_include`)
  - CSV and HTML export with styled output

- **`main.py`**: Entry Point & CLI
  - `main()` function: CLI argument parsing and application orchestration
  - Virtual environment switching logic for cross-platform compatibility
  - Authentication chain management

- **`clickup_task_extractor.py`**: Legacy Compatibility
  - Backward-compatible entry point that delegates to the new modular architecture
  - Preserves existing command-line interface for users

## Data Flow
1. **Authentication**: Multiple fallback methods for API key retrieval (CLI args → env vars → 1Password SDK → 1Password CLI → manual input).
2. **Config** is loaded with comprehensive defaults and CLI argument overrides.
3. **API Client** fetches workspace, space, lists (from folders and space-level), and tasks with error handling.
4. **Task filtering** by status (exclude_statuses) and completion state.
5. **Custom fields** are mapped and processed (notably Branch/Location using LocationMapper).
6. **TaskRecord** objects are created for each task with comprehensive field mapping.
7. **Interactive selection** (optional) allows user to review and filter tasks before export.
8. **Export** to CSV and/or HTML with styled HTML output and cross-platform date formatting without leading zeros.

## Authentication Priority
1. Command line argument (`--api-key`)
2. Environment variable (`CLICKUP_API_KEY`)
3. 1Password SDK (requires `OP_SERVICE_ACCOUNT_TOKEN`)
4. 1Password CLI fallback (requires `op` command)
5. Manual input prompt

## Developer Workflows
- **Run the script**: `python clickup_task_extractor.py` or `python main.py` (supports multiple authentication methods)
- **Interactive mode**: `python clickup_task_extractor.py --interactive`
- **No build step**: Pure Python, no external build system.
- **Dependencies**: Only `requests` is required for basic functionality. Optional: `onepassword-sdk` for 1Password integration, `google-genai` for AI summaries.
- **No test suite**: There are currently no automated tests.

## Development Setup

### Python Guidelines Symlink
This project references centralized Python development guidelines via a symlink to `.github/Python.prompt.md`. To set up the symlink on Windows:

```powershell
# From the project root directory
New-Item -ItemType SymbolicLink -Path ".github\Python.prompt.md" -Target "C:\Users\[USERNAME]\AppData\Roaming\Code\User\profiles\[PROFILE]\prompts\Python.prompt.md"
```

This ensures the project always uses the most up-to-date Python development standards while keeping them centrally managed.

## Project-Specific Patterns & Conventions

**Note**: These patterns implement the SOLID principles and modern Python practices from `.github/Python.prompt.md` in ClickUp-specific ways:

- **Modular architecture**: Each module has a single, well-defined responsibility following SOLID principles
- **Clean imports**: No circular dependencies; each module imports only what it needs
- **Type safety**: Uses modern type hints (`list[str]`, `str | None`) and type aliases (`TaskList`, `DateRange`, `SecretValue`)
- **Protocol-based design**: `APIClient` protocol enables dependency inversion and easier testing
- **Comprehensive error handling**: Specific exceptions (`APIError`, `AuthenticationError`) with proper chaining
- **Context managers**: `export_file()` context manager for safe file operations with automatic cleanup
- **Pathlib usage**: All file operations use `pathlib.Path` for cross-platform compatibility
- **Backward compatibility**: Original `clickup_task_extractor.py` interface preserved for existing users
- **Custom field handling**: Always use the `LocationMapper` for mapping custom fields to user-friendly labels with multiple fallback strategies (id → orderindex → name)
- **Interactive selection**: Use the `interactive_include` method for user-driven task filtering before export
- **Output formats**: Controlled by `output_format` in config (`CSV`, `HTML`, or `Both`)
- **Date formatting**: Cross-platform compatible without leading zeros using post-processing of strftime output
- **Status filtering**: Use `exclude_statuses` list in config to filter out unwanted task statuses (default: ['Blocked', 'Dormant', 'On Hold', 'Document'])
- **1Password integration**: Secure credential management with SDK preference and CLI fallback

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
- `output_format`: Export format - 'CSV', 'HTML', or 'Both' (default: 'HTML')
- `include_completed`: Include completed/archived tasks (default: False)
- `interactive_selection`: Enable task review and selection (default: False, prompted if not set)
- `exclude_statuses`: List of task statuses to exclude (default: ['Blocked', 'Dormant', 'On Hold', 'Document'])
- `date_filter`: Date filtering - 'AllOpen', 'ThisWeek', 'LastWeek' (default: 'AllOpen')
- `enable_ai_summary`: Enable AI summarization (requires github_token)

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
