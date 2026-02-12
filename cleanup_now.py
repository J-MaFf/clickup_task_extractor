import os
import shutil

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
    "do_commit.py",
]

for f in temp_files:
    try:
        if os.path.exists(f):
            os.remove(f)
    except:
        pass

print("Cleanup complete")
