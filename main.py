#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Entry Point and CLI Module for ClickUp Task Extractor

Contains:
- main() function with CLI argument parsing
- Virtual environment switching logic
- Application orchestration
- Authentication chain management
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

import argparse
from datetime import datetime

# Import project modules
from config import ClickUpConfig, TIMESTAMP_FORMAT, format_datetime
from auth import _load_secret_with_fallback
from api_client import ClickUpAPIClient
from extractor import ClickUpTaskExtractor
from mappers import get_yes_no_input


def main():
    """
    Entrypoint for ClickUp Task Extractor.
    Supports CLI args for config overrides. Example:
      python ClickUpTaskExtractor.py --api-key ... --workspace ... --space ...

    API key 1Password reference: "op://Home Server/ClickUp personal API token/credential"

    Authentication priority:
    1. --api-key command line argument
    2. CLICKUP_API_KEY environment variable
    3. 1Password SDK (requires OP_SERVICE_ACCOUNT_TOKEN env var)
    4. 1Password CLI fallback (requires 'op' command available)
    5. Manual input prompt
    """
    parser = argparse.ArgumentParser(
        description="Extract and export ClickUp tasks to HTML (preferred) or CSV. Default workspace: KMS.\nAPI key 1Password reference: op://Home Server/ClickUp personal API token/credential\nRequires OP_SERVICE_ACCOUNT_TOKEN for 1Password SDK authentication."
    )
    parser.add_argument('--api-key', type=str, default=os.environ.get('CLICKUP_API_KEY'), help='ClickUp API Key (or set CLICKUP_API_KEY env, or use 1Password SDK with OP_SERVICE_ACCOUNT_TOKEN, e.g. from 1Password: "op://Home Server/ClickUp personal API token/credential")')
    parser.add_argument('--workspace', type=str, help='Workspace name (default: KMS)')
    parser.add_argument('--space', type=str, help='Space name (default: Kikkoman)')
    parser.add_argument('--output', type=str, help='Output file path (default: auto-generated)')
    parser.add_argument('--include-completed', action='store_true', help='Include completed/archived tasks')
    parser.add_argument('--date-filter', type=str, choices=['AllOpen', 'ThisWeek', 'LastWeek'], help='Date filter')
    parser.add_argument('--ai-summary', action='store_true', help='Enable AI summary (requires Gemini API key - will auto-load from 1Password if available)')
    parser.add_argument('--gemini-api-key', type=str, help='Google Gemini API key for AI summary generation (or auto-load from 1Password: "op://Home Server/nftoo3gsi3wpx7z5bdmcsvr7p4/credential")')
    parser.add_argument('--output-format', type=str, choices=['CSV', 'HTML', 'Both'], help='Output format (default: HTML)')
    parser.add_argument('--interactive', action='store_true', help='Enable interactive task selection')
    args = parser.parse_args()

    # 1Password reference for API key: "op://Home Server/ClickUp personal API token/credential"
    api_key = args.api_key or os.environ.get('CLICKUP_API_KEY')

    if not api_key:
        # Try to get API key from 1Password with fallback
        secret_reference = 'op://Home Server/ClickUp personal API token/credential'
        api_key = _load_secret_with_fallback(secret_reference, "ClickUp API key")
        if not api_key:
            print("Please provide via --api-key or CLICKUP_API_KEY.")

    # If still no API key, prompt for manual input
    if not api_key:
        api_key = input('Enter ClickUp API Key: ')

    # Load Gemini API key if AI summary is enabled and no key provided via CLI
    gemini_api_key = args.gemini_api_key

    # Function to load Gemini API key when needed
    def load_gemini_api_key():
        nonlocal gemini_api_key
        if gemini_api_key:
            return True  # Already have the key

        # Try to get Gemini API key from 1Password with fallback
        gemini_secret_reference = 'op://Home Server/nftoo3gsi3wpx7z5bdmcsvr7p4/credential'
        gemini_api_key = _load_secret_with_fallback(gemini_secret_reference, "Gemini API key")
        if gemini_api_key:
            return True
        else:
            print("Please provide via --gemini-api-key.")
            return False

    # If AI summary flag was explicitly used, load the key now
    if args.ai_summary and not gemini_api_key:
        if not load_gemini_api_key():
            # If still no Gemini API key and AI summary is enabled, prompt for manual input
            gemini_api_key = input('Enter Gemini API Key (or press Enter to disable AI summary): ')
            if not gemini_api_key:
                print("No Gemini API key provided. AI summary will be disabled.")
                args.ai_summary = False

    # Check if interactive mode should be enabled when not explicitly set
    interactive_mode = args.interactive
    if not interactive_mode:
        print("\nInteractive mode allows you to review and select which tasks to export.")
        print("Without interactive mode, all tasks will be automatically exported.")
        interactive_mode = get_yes_no_input('Would you like to run in interactive mode? (y/n): ')
        if interactive_mode:
            print("✓ Interactive mode enabled - you'll be able to review each task before export.")
        else:
            print("✓ Running in automatic mode - all tasks will be exported.")

    # If not in interactive mode and AI summary wasn't explicitly set, ask now
    if not interactive_mode and not args.ai_summary:
        print("\nAI summary can generate concise 1-2 sentence summaries of task status using Google Gemini.")
        if get_yes_no_input('Would you like to enable AI summaries for tasks? (y/n): '):
            args.ai_summary = True
            if not load_gemini_api_key():
                gemini_api_key = input('Enter Gemini API Key (or press Enter to disable AI summary): ')
                if not gemini_api_key:
                    print("No Gemini API key provided. AI summary will be disabled.")
                    args.ai_summary = False
                else:
                    print("✓ AI summary enabled with manual API key.")
            else:
                print("✓ AI summary enabled.")
        else:
            print("✓ AI summary disabled.")

    config = ClickUpConfig(
        api_key=api_key,
        workspace_name=args.workspace or 'KMS',
        space_name=args.space or 'Kikkoman',
        output_path=args.output or f"output/WeeklyTaskList_{format_datetime(datetime.now(), TIMESTAMP_FORMAT)}.csv",
        include_completed=args.include_completed,
        date_filter=args.date_filter or 'AllOpen',
        enable_ai_summary=args.ai_summary,
        gemini_api_key=gemini_api_key,
        output_format=args.output_format or 'HTML',
        interactive_selection=interactive_mode
    )

    # Function to load Gemini key and update config when needed
    def load_gemini_key_and_update_config():
        nonlocal config
        # Try loading once more from 1Password
        if load_gemini_api_key():
            config.gemini_api_key = gemini_api_key
            return True
        return False

    client = ClickUpAPIClient(api_key)
    extractor = ClickUpTaskExtractor(config, client, load_gemini_key_and_update_config)
    extractor.run()


if __name__ == '__main__':
    main()