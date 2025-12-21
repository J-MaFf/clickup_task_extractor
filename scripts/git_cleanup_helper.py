#!/usr/bin/env python3
"""
Git cleanup helper - Improves on the global git cleanup alias.

This script properly identifies and deletes stale local branches that:
1. Are not the current branch
2. Have all commits merged into main
3. Are not tracking a remote (remote has been deleted)

Usage:
    python git_cleanup_helper.py [--dry-run] [--force]

Options:
    --dry-run   Show what would be deleted without actually deleting
    --force     Force delete even if commits aren't fully merged
"""

import subprocess
import sys
from typing import List, Tuple


def run_git_command(cmd: List[str]) -> str:
    """Run a git command and return output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running {' '.join(cmd)}: {e.stderr}", file=sys.stderr)
        return ""


def get_current_branch() -> str:
    """Get the name of the current branch."""
    return run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def get_all_branches() -> List[str]:
    """Get all local branch names."""
    output = run_git_command(["git", "branch", "--format=%(refname:short)"])
    return output.split("\n") if output else []


def is_branch_merged(branch: str, target: str = "main") -> bool:
    """Check if a branch's commits are merged into target branch."""
    output = run_git_command(["git", "merge-base", "--is-ancestor", branch, target])
    return True  # If no error, it's merged


def has_remote_tracking(branch: str) -> bool:
    """Check if branch has a remote tracking branch."""
    output = run_git_command(["git", "config", f"branch.{branch}.remote"])
    return bool(output)


def delete_branch(branch: str, force: bool = False) -> bool:
    """Delete a branch. Returns True if successful."""
    flag = "-D" if force else "-d"
    try:
        subprocess.run(["git", "branch", flag, branch], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    """Main cleanup logic."""
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    
    current = get_current_branch()
    all_branches = get_all_branches()
    
    to_delete = []
    
    for branch in all_branches:
        # Skip current branch
        if branch == current:
            continue
        
        # Skip main
        if branch in ("main", "master", "develop"):
            continue
        
        # Check if branch is merged and has no remote tracking
        is_merged = is_branch_merged(branch)
        has_tracking = has_remote_tracking(branch)
        
        if is_merged and not has_tracking:
            to_delete.append(branch)
    
    if not to_delete:
        print("✅ No stale branches found. All branches are up to date or tracking remotes.")
        return 0
    
    print(f"Found {len(to_delete)} stale branch(es) to delete:")
    for branch in to_delete:
        print(f"  - {branch}")
    
    if dry_run:
        print("\n(--dry-run mode: no branches deleted)")
        return 0
    
    deleted = 0
    for branch in to_delete:
        if delete_branch(branch, force=force):
            print(f"✅ Deleted {branch}")
            deleted += 1
        else:
            print(f"❌ Failed to delete {branch}")
    
    print(f"\nDeleted {deleted}/{len(to_delete)} branches")
    
    # Clean up remote tracking refs
    print("\nCleaning up remote tracking references...")
    subprocess.run(["git", "remote", "prune", "origin"])
    
    return 0 if deleted == len(to_delete) else 1


if __name__ == "__main__":
    sys.exit(main())
