#!/usr/bin/env python
"""Run tests for markdown line breaks."""

import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_markdown_line_breaks.py", "-v"],
    cwd=r"C:\Users\jmaffiola\Documents\Scripts\clickup_api\clickup_task_extractor.worktrees\copilot-worktree-2026-02-10T21-46-20",
)
sys.exit(result.returncode)
