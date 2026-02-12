#!/usr/bin/env bash
cd "C:\Users\jmaffiola\Documents\Scripts\clickup_api\clickup_task_extractor.worktrees\copilot-worktree-2026-02-10T19-36-08" || exit 1

# Remove temporary files
rm -f find_markdown.py test_markdown_fix.py verify_fix.py cleanup.py make_commit.py ISSUE_86_FIX_SUMMARY.md

# Check git status
echo "=== Git Status Before ==="
git status --short

# Stage the main fix
echo ""
echo "=== Staging Changes ==="
git add extractor.py
git status --short

# Create commit
echo ""
echo "=== Creating Commit ==="
git commit -m "fix: resolve MD060 markdown lint violations in table formatting

The markdown table separator line was using inconsistent spacing compared
to header and data rows, causing MD060 (table-column-style) violations
in markdownlint validation.

Changes:
- Updated separator line in render_markdown() to use same format as headers
- Changed from '|' + '|'.join() to '| ' + ' | '.join() pattern
- All table lines now follow consistent 'padding style' format
- Generated markdown files now pass markdownlint without MD060 errors

Fixes #86"

echo ""
echo "=== Commit Complete ==="
git log --oneline -1
