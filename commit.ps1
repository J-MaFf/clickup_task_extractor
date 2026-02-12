# PowerShell script to commit the fix
Set-Location "C:\Users\jmaffiola\Documents\Scripts\clickup_api\clickup_task_extractor.worktrees\copilot-worktree-2026-02-10T19-36-08"

Write-Host "=== Cleaning up temporary files ===" -ForegroundColor Green
$tempFiles = @("find_markdown.py", "test_markdown_fix.py", "verify_fix.py", "cleanup.py",
    "make_commit.py", "ISSUE_86_FIX_SUMMARY.md", "commit.sh", "do_commit.py",
    "cleanup_now.py", "final_commit.py", "commit_and_cleanup.py")

foreach ($file in $tempFiles) {
    if (Test-Path $file) {
        Remove-Item $file -Force
        Write-Host "✓ Removed $file" -ForegroundColor Yellow
    }
}

Write-Host "`n=== Git Status ===" -ForegroundColor Green
& git status --short

Write-Host "`n=== Staging extractor.py ===" -ForegroundColor Green
& git add extractor.py

Write-Host "`n=== Creating Commit ===" -ForegroundColor Green
$commitMsg = @"
fix: resolve MD060 markdown lint violations in table formatting

The markdown table separator line was using inconsistent spacing compared
to header and data rows, causing MD060 (table-column-style) violations
in markdownlint validation.

Changes:
- Updated separator line in render_markdown() to use same format as headers
- Changed from '|' + '|'.join() to '| ' + ' | '.join() pattern
- All table lines now follow consistent 'padding style' format
- Generated markdown files now pass markdownlint without MD060 errors

Fixes #86
"@

& git commit -m $commitMsg

Write-Host "`n=== Commit Complete ===" -ForegroundColor Green
& git log --oneline -1

# Final cleanup of script itself
if (Test-Path "commit.ps1") {
    Remove-Item "commit.ps1" -Force
}
