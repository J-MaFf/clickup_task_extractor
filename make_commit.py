#!/usr/bin/env python
"""Git commit script for issue 86 fix"""

import subprocess
import os

os.chdir(
    r"C:\Users\jmaffiola\Documents\Scripts\clickup_api\clickup_task_extractor.worktrees\copilot-worktree-2026-02-10T19-36-08"
)

# Check status
result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
print("Git Status:")
print(result.stdout)

# Stage the main fix
subprocess.run(["git", "add", "extractor.py"], capture_output=True, text=True)
print("✓ Staged extractor.py")

# Remove temporary files that shouldn't be committed
temp_files = ["find_markdown.py", "test_markdown_fix.py", "verify_fix.py", "cleanup.py"]
for f in temp_files:
    if os.path.exists(f):
        os.remove(f)
        print(f"✓ Removed temporary file: {f}")

# Commit
commit_msg = """fix: resolve MD060 markdown lint violations in table formatting

The markdown table separator line was using inconsistent spacing compared
to header and data rows, causing MD060 (table-column-style) violations
in markdownlint validation.

Changes:
- Updated separator line in render_markdown() to use same format as headers
- Changed from '|' + '|'.join() to '| ' + ' | '.join() pattern
- All table lines now follow consistent 'padding style' format
- Generated markdown files now pass markdownlint without MD060 errors

Fixes #86"""

result = subprocess.run(
    ["git", "commit", "-m", commit_msg], capture_output=True, text=True
)
if result.returncode == 0:
    print("✓ Commit created successfully")
    print(result.stdout)
else:
    print("✗ Commit failed:")
    print(result.stderr)

# Show the commit
subprocess.run(["git", "show", "--stat"], capture_output=True, text=True)
print("\n✓ Commit complete")
