#!/usr/bin/env python3
"""Direct commit without PowerShell"""

import subprocess
import os
import glob

os.chdir(
    r"C:\Users\jmaffiola\Documents\Scripts\clickup_api\clickup_task_extractor.worktrees\copilot-worktree-2026-02-10T19-36-08"
)

# First, show what we're about to commit
print("FILES TO COMMIT:")
result = subprocess.run(
    ["git", "diff", "--cached", "--name-only"],
    capture_output=True,
    text=True,
    timeout=5,
)
if result.stdout.strip():
    print(result.stdout)
else:
    print("(nothing staged yet)")

# Stage the fix
print("\nSTAGING extractor.py...")
subprocess.run(["git", "add", "extractor.py"], timeout=5)

print("\nCHECKING STAGED CHANGES:")
result = subprocess.run(
    ["git", "diff", "--cached"], capture_output=True, text=True, timeout=5
)
print(
    result.stdout[:500] + "...(truncated)"
    if len(result.stdout) > 500
    else result.stdout
)

# Create the commit
print("\nCREATING COMMIT...")
commit_result = subprocess.run(
    [
        "git",
        "commit",
        "-m",
        "fix: resolve MD060 markdown lint violations in table formatting\n\nThe markdown table separator line was using inconsistent spacing compared to header and data rows, causing MD060 violations.\n\nFixed render_markdown() to use consistent formatting for all table lines.\n\nFixes #86",
    ],
    capture_output=True,
    text=True,
    timeout=5,
)

if commit_result.returncode == 0:
    print("✓ COMMIT SUCCESSFUL")
    print(commit_result.stdout)
else:
    print("✗ COMMIT FAILED")
    print(commit_result.stderr)

# Show the commit
print("\nCOMMIT DETAILS:")
result = subprocess.run(
    ["git", "log", "--oneline", "-1"], capture_output=True, text=True, timeout=5
)
print(result.stdout)

result = subprocess.run(
    ["git", "show", "--stat"], capture_output=True, text=True, timeout=5
)
print(result.stdout[:500])

# Cleanup all temp files
print("\nCLEANING UP TEMPORARY FILES...")
temp_files = glob.glob("*.py")
to_remove = [
    "find_markdown.py",
    "test_markdown_fix.py",
    "verify_fix.py",
    "cleanup.py",
    "make_commit.py",
    "do_commit.py",
    "cleanup_now.py",
    "final_commit.py",
]
for f in to_remove:
    fpath = os.path.join(os.getcwd(), f)
    if os.path.exists(fpath) and f in temp_files:
        try:
            os.remove(fpath)
            print(f"✓ Removed {f}")
        except Exception as e:
            print(f"✗ Could not remove {f}: {e}")

# Also remove shell script if exists
if os.path.exists("commit.sh"):
    try:
        os.remove("commit.sh")
        print("✓ Removed commit.sh")
    except:
        pass

if os.path.exists("ISSUE_86_FIX_SUMMARY.md"):
    try:
        os.remove("ISSUE_86_FIX_SUMMARY.md")
        print("✓ Removed ISSUE_86_FIX_SUMMARY.md")
    except:
        pass

print("\nDONE!")
