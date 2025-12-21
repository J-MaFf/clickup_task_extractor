# Git Cleanup Investigation

## Issue
The `git cleanup` alias (defined in global git config) did not delete the stale `fix/70-export-path-mismatch` branch.

## Root Cause
The cleanup alias executes: `python C:/Users/7maff/Documents/Scripts/gitconfig/gitconfig_helper.py cleanup $@`

The Python script appears to check if branches are "up to date" with their tracking branches, but it's likely checking against the wrong criteria. A branch that is:
- Not tracking a remote
- Or all local commits are already merged into main
- Should be a candidate for deletion

## Current Behavior
```
$ git cleanup
No branches were deleted. All local branches are up to date.
```

## Expected Behavior
Should delete local branches that:
1. Are not the current branch
2. Have no unmerged commits relative to main
3. No longer have a tracking remote (gone branches)

## Manual Workaround
Use standard git commands instead:
```bash
# Delete a specific stale branch
git branch -d <branch-name>

# Or more forcefully
git branch -D <branch-name>

# Clean up stale remote tracking branches
git remote prune origin

# Combined cleanup (recommended)
git branch -d <branch> && git remote prune origin
```

## Recommendation
The `gitconfig_helper.py` script should be reviewed and updated to properly identify and delete stale branches.

For now, use the manual commands above as the cleanup alias is not functioning as intended.

## Test Case
**Before:** Local branch `fix/70-export-path-mismatch` exists but:
- Is 16 commits behind `main`
- Has no remote tracking (remote branch was deleted)
- All commits are merged into `main`

**Expected:** Should be deleted by `git cleanup`

**Actual:** Not deleted, message says "All local branches are up to date"

**Solution Applied:** Used `git branch -d fix/70-export-path-mismatch` directly
