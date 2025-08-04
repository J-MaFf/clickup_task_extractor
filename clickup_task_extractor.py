#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ClickUp Task Extractor (Python) - Legacy Entry Point

A cross-platform Python script for extracting, processing, and exporting tasks from the ClickUp API.
This file serves as a backward-compatible entry point that delegates to the new modular architecture.

For the main application logic, see the individual modules:
- config.py: Configuration and data models
- auth.py: Authentication and 1Password integration
- api_client.py: ClickUp API client
- ai_summary.py: AI integration with Google Gemini
- mappers.py: Utilities and data mapping
- extractor.py: Main business logic
- main.py: Entry point and CLI parsing

USAGE:
    python clickup_task_extractor.py [options]

AUTHENTICATION PRIORITY:
1. Command line argument (--api-key)
2. Environment variable (CLICKUP_API_KEY)
3. 1Password SDK (requires OP_SERVICE_ACCOUNT_TOKEN)
4. 1Password CLI fallback (requires 'op' command)
5. Manual input prompt

1PASSWORD INTEGRATION:
- SDK: Set OP_SERVICE_ACCOUNT_TOKEN environment variable
- CLI: Ensure 'op' command is available in PATH
- ClickUp API secret reference: "op://Home Server/ClickUp personal API token/credential"
- Gemini API secret reference: "op://Home Server/nftoo3gsi3wpx7z5bdmcsvr7p4/credential"
"""

import os
import sys

# Ensure we're using the virtual environment
script_dir = os.path.dirname(os.path.abspath(__file__))
venv_python = os.path.join(script_dir, '.venv', 'Scripts', 'python.exe')

# If we're not running from the venv and the venv exists, restart with the venv Python
if not sys.executable.startswith(os.path.join(script_dir, '.venv')) and os.path.exists(venv_python):
    import subprocess
    print(f"Switching from {sys.executable} to virtual environment: {venv_python}")
    # Re-execute the script with the virtual environment Python
    sys.exit(subprocess.call([venv_python] + sys.argv))

# Import the main function from the new modular architecture
from main import main

if __name__ == '__main__':
    main()