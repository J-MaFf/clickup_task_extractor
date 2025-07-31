# Copilot Instructions for ClickUp Task Extractor

## Project Overview
This project is a Python script for extracting, processing, and exporting tasks from the ClickUp API. It is designed to match the output and features of a PowerShell-based workflow, with a focus on clarity, maintainability, and adherence to SOLID principles.

## Architecture & Key Components
- **ClickUpConfig**: Centralizes configuration (API key, workspace/space names, output options, etc.) using a dataclass. Defaults are set for common use.
- **ClickUpAPIClient**: Handles all HTTP requests to the ClickUp API. All API interactions should go through this class.
- **TaskRecord**: Dataclass representing a single task's exported fields. All output (CSV/HTML) is based on this structure.
- **LocationMapper**: Maps ClickUp custom field values (e.g., Branch/Location) to human-readable labels, handling ClickUp's flexible field types.
- **ClickUpTaskExtractor**: Orchestrates the workflow: discovers workspace/space, fetches lists and tasks, processes custom fields, applies filters, and exports results. Supports interactive exclusion and optional AI summarization.

## Data Flow
1. **Config** is loaded (from env or prompt).
2. **API Client** fetches workspace, space, lists, and tasks.
3. **Custom fields** are mapped and processed (notably Branch/Location).
4. **TaskRecord** objects are created for each task.
5. **Interactive exclusion** (optional) allows user to filter tasks before export.
6. **Export** to CSV and/or HTML, with styled HTML output, with Day/Month/Year and Hour:Minute AM/PM formatting.

## Developer Workflows
- **Run the script**: `python ClickUpTaskExtractor.py` (ensure `CLICKUP_API_KEY` is set or provide interactively)
- **No build step**: Pure Python, no external build system.
- **Dependencies**: Only `requests` is required (install with `pip install requests`).
- **No test suite**: There are currently no automated tests.

## Project-Specific Patterns & Conventions
- **Single-file structure**: All logic is in `ClickUpTaskExtractor.py` for simplicity.
- **SOLID principles**: Each class/function has a single responsibility. Avoid mixing API, config, and export logic.
- **Custom field handling**: Always use the `LocationMapper` for mapping custom fields to user-friendly labels.
- **Interactive exclusion**: Use the `interactive_exclude` method for user-driven filtering before export.
- **Output formats**: Controlled by `output_format` in config (`CSV`, `HTML`, or `Both`).
- **Date filtering**: Implemented via `get_date_range`, but not fully integrated into API queries (room for improvement).

## Integration Points
- **ClickUp API**: All data is fetched via ClickUp's v2 API. API key is required.
- **Optional AI summary**: Placeholder for integrating AI summarization (not implemented by default).
- **No external storage or DB**: All output is local (CSV/HTML files).

## Examples
- To add a new export field, update the `TaskRecord` dataclass and adjust the export logic in `export` and `render_html`.
- To support a new output format, extend the `export` method and add a new config option.

## Key File
- `ClickUpTaskExtractor.py`: All logic, configuration, and entrypoint.

---

For questions about project-specific conventions or to propose improvements, please update this file or contact the project maintainer.
