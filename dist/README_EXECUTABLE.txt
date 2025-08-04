ClickUp Task Extractor - Windows Executable
===============================================

This is a standalone Windows executable that doesn't require Python installation.

🔐 AUTHENTICATION METHODS AVAILABLE:
=====================================

1. Command Line:
   clickup_task_extractor.exe --api-key YOUR_CLICKUP_API_KEY

2. Environment Variable:
   set CLICKUP_API_KEY=YOUR_CLICKUP_API_KEY
   clickup_task_extractor.exe

3. 1Password CLI (if installed):
   - Requires 'op' command in PATH
   - Will automatically attempt to load from 1Password

4. Manual Input:
   - Will prompt for API key if none provided

⚠️  NOTE: 1Password SDK integration is disabled in this executable version.
    For full 1Password SDK support, use the Python script version.

🚀 USAGE EXAMPLES:
==================

# Basic usage (will prompt for API key if needed)
clickup_task_extractor.exe

# Interactive mode
clickup_task_extractor.exe --interactive

# With API key
clickup_task_extractor.exe --api-key pk_123456789_ABCDEFGH

# Custom workspace and space
clickup_task_extractor.exe --workspace "MyWorkspace" --space "MySpace"

# Export both formats
clickup_task_extractor.exe --output-format Both

# Show all options
clickup_task_extractor.exe --help

🔧 TROUBLESHOOTING:
===================

If you get "Windows protected your PC" warning:
- Click "More info" → "Run anyway"
- This is normal for unsigned executables

For full features including 1Password SDK, use the Python version instead.
