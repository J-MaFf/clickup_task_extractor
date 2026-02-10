#!/usr/bin/env python3
import subprocess
import sys
import os

# Change to repo directory
os.chdir(
    r"C:\Users\jmaffiola\Documents\Scripts\clickup_api\clickup_task_extractor.worktrees\copilot-worktree-2026-02-10T19-36-08"
)

# Clean temp files
for f in [
    "find_markdown.py",
    "test_markdown_fix.py",
    "verify_fix.py",
    "cleanup.py",
    "make_commit.py",
    "ISSUE_86_FIX_SUMMARY.md",
    "commit.sh",
    "do_commit.py",
    "cleanup_now.py",
]:
    try:
        if os.path.exists(f):
            os.remove(f)
    except:
        pass

# Run git commands
print("=== Git Status ===")
subprocess.run(["git", "status", "--short"])

print("\n=== Staging extractor.py ===")
subprocess.run(["git", "add", "extractor.py"])

print("\n=== Creating Commit ===")
subprocess.run(
    [
        "git",
        "commit",
        "-m",
        """fix: resolve MD060 markdown lint violations in table formatting

The markdown table separator line was using inconsistent spacing compared
to header and data rows, causing MD060 (table-column-style) violations
in markdownlint validation.

Changes:
- Updated separator line in render_markdown() to use same format as headers
- Changed from '|' + '|'.join() to '| ' + ' | '.join() pattern
- All table lines now follow consistent 'padding style' format
- Generated markdown files now pass markdownlint without MD060 errors

Fixes #86""",
    ]
)

print("\n=== Last Commit ===")
subprocess.run(["git", "log", "--oneline", "-1"])
