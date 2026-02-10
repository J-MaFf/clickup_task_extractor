#!/usr/bin/env python3
"""Simple script to clean up and commit"""

import subprocess
import os
import sys

os.chdir(
    r"C:\Users\jmaffiola\Documents\Scripts\clickup_api\clickup_task_extractor.worktrees\copilot-worktree-2026-02-10T19-36-08"
)

# Clean up temporary files
temp_files = [
    "find_markdown.py",
    "test_markdown_fix.py",
    "verify_fix.py",
    "cleanup.py",
    "make_commit.py",
    "ISSUE_86_FIX_SUMMARY.md",
    "commit.sh",
]
for f in temp_files:
    try:
        if os.path.exists(f):
            os.remove(f)
            print(f"✓ Removed: {f}")
    except Exception as e:
        print(f"✗ Could not remove {f}: {e}")

print("\n=== Git Status ===")
os.system("git status --short")

print("\n=== Staging extractor.py ===")
os.system("git add extractor.py")

print("\n=== Creating Commit ===")
commit_message = """fix: resolve MD060 markdown lint violations in table formatting

The markdown table separator line was using inconsistent spacing compared
to header and data rows, causing MD060 (table-column-style) violations
in markdownlint validation.

Changes:
- Updated separator line in render_markdown() to use same format as headers
- Changed from '|' + '|'.join() to '| ' + ' | '.join() pattern
- All table lines now follow consistent 'padding style' format
- Generated markdown files now pass markdownlint without MD060 errors

Fixes #86"""

# Use git commit
result = os.system(f'git commit -m "{commit_message}"')

print("\n=== Commit Created ===")
os.system("git log --oneline -1")
