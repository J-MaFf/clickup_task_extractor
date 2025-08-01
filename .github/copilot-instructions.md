# Copilot Instructions for ClickUp Task Extractor

## Project Overview
This project is a Python script for extracting, processing, and exporting tasks from the ClickUp API. It is designed to match the output and features of a PowerShell-based workflow, with a focus on clarity, maintainability, and adherence to SOLID principles. The script features cross-platform compatibility, 1Password integration for secure API key management, and interactive task selection.

## Architecture & Key Components
- **ClickUpConfig**: Centralizes configuration (API key, workspace/space names, output options, etc.) using a dataclass. Includes advanced features like exclude_statuses list, interactive_selection mode, and multiple authentication methods.
- **ClickUpAPIClient**: Handles all HTTP requests to the ClickUp API with comprehensive error handling and debugging information. All API interactions should go through this class.
- **TaskRecord**: Dataclass representing a single task's exported fields (Task, Company, Branch, Priority, Status, ETA, Notes, Extra). All output (CSV/HTML) is based on this structure.
- **LocationMapper**: Maps ClickUp custom field values (e.g., Branch/Location) to human-readable labels, handling ClickUp's flexible field types with multiple fallback matching strategies.
- **ClickUpTaskExtractor**: Main orchestrator class that discovers workspace/space, fetches lists and tasks, processes custom fields, applies filters, and exports results. Supports interactive task selection and optional AI summarization.
- **Date Formatting Functions**: Cross-platform datetime formatting without leading zeros for cleaner output (`format_timestamp_no_leading_zeros`, `format_display_no_leading_zeros`).
- **1Password Integration**: Secure API key retrieval using SDK (preferred) or CLI fallback with comprehensive error handling.

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
- **Run the script**: `python clickup_task_extractor.py` (supports multiple authentication methods)
- **Interactive mode**: `python clickup_task_extractor.py --interactive`
- **No build step**: Pure Python, no external build system.
- **Dependencies**: Only `requests` is required for basic functionality. Optional: `onepassword-sdk` for 1Password integration.
- **No test suite**: There are currently no automated tests.

## Project-Specific Patterns & Conventions
- **Single-file structure**: All logic is in `clickup_task_extractor.py` for simplicity.
- **SOLID principles**: Each class/function has a single responsibility. Avoid mixing API, config, and export logic.
- **Custom field handling**: Always use the `LocationMapper` for mapping custom fields to user-friendly labels with multiple fallback strategies (id → orderindex → name).
- **Interactive selection**: Use the `interactive_include` method for user-driven task filtering before export.
- **Output formats**: Controlled by `output_format` in config (`CSV`, `HTML`, or `Both`).
- **Date formatting**: Cross-platform compatible without leading zeros using post-processing of strftime output.
- **Status filtering**: Use `exclude_statuses` list in config to filter out unwanted task statuses (default: ['Dormant', 'On Hold', 'Document']).
- **Error handling**: Comprehensive error handling with debugging information for API failures.
- **1Password integration**: Secure credential management with SDK preference and CLI fallback.

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
- `exclude_statuses`: List of task statuses to exclude (default: ['Dormant', 'On Hold', 'Document'])
- `date_filter`: Date filtering - 'AllOpen', 'ThisWeek', 'LastWeek' (default: 'AllOpen')
- `enable_ai_summary`: Enable AI summarization (requires github_token)

## Examples
- **Basic usage**: `python clickup_task_extractor.py`
- **Interactive mode**: `python clickup_task_extractor.py --interactive`
- **Custom workspace**: `python clickup_task_extractor.py --workspace "MyWorkspace" --space "MySpace"`
- **Both outputs**: `python clickup_task_extractor.py --output-format Both`
- **Include completed**: `python clickup_task_extractor.py --include-completed`
- **With API key**: `python clickup_task_extractor.py --api-key YOUR_KEY`

## Development Guidelines
- To add a new export field, update the `TaskRecord` dataclass and adjust the export logic in `export` and `render_html` methods.
- To support a new output format, extend the `export` method and add a new config option.
- When adding new custom field mappings, extend the `LocationMapper` class with additional mapping logic.
- For new authentication methods, extend the authentication chain in the `main()` function.
- All date formatting should use the provided `format_timestamp_no_leading_zeros` and `format_display_no_leading_zeros` functions for consistency.

## Key Files
- `clickup_task_extractor.py`: All logic, configuration, and entrypoint
- `.github/copilot-instructions.md`: This file with project conventions and patterns
- `requirements.txt`: Python dependencies (requests, optional: onepassword-sdk)
- `output/`: Directory for generated CSV and HTML files

## 1Password Integration Details
- **SDK Authentication**: Set `OP_SERVICE_ACCOUNT_TOKEN` environment variable
- **CLI Fallback**: Ensure `op` command is available in PATH
- **Secret Reference**: `"op://Home Server/ClickUp personal API token/credential"`
- **Error Handling**: Graceful fallback through authentication chain with informative error messages

---

For questions about project-specific conventions or to propose improvements, please update this file or contact the project maintainer.
