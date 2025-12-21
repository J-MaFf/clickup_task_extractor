#!/usr/bin/env python3
"""
Apply formatting standards to all user-owned repositories.
Creates a chore/add-formatting-standards branch and PR on each repo.
"""

import subprocess
import json
import os
import tempfile
import shutil
from pathlib import Path

# Formatting standards content
FORMATTING_STANDARDS = """## Code Style & Formatting Standards

### Commit Messages (Conventional Commits)
Use the following prefixes for all commits:
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `style:` Code style changes (formatting, missing semicolons, etc.)
- `refactor:` Code refactoring without changing behavior
- `perf:` Performance improvements
- `test:` Add or update tests
- `chore:` Maintenance, dependency updates, CI/CD
- `ci:` CI/CD pipeline changes
- `revert:` Revert a previous commit

Example: `feat: Add ETA automation with timezone awareness`

### PR Titles (Emoji Prefix)
Use emoji prefix followed by brief description:
- `✨ Add new feature`
- `🐛 Fix bug or issue`
- `📚 Update documentation`
- `🔧 Maintenance or refactoring`
- `🎯 Refactor or restructure code`
- `🚀 Deploy or release feature`
- `⚡ Performance improvement`
- `🧪 Add or update tests`

Example: `✨ Add interactive task selection with rich UI`

### PR Body (GitHub-Flavored Markdown)
Structure all PR descriptions with these sections:
```markdown
### What does this PR do?
Brief explanation of changes and what was implemented.

### Why are we doing this?
Context, motivation, and reason for the changes.

### How should this be tested?
Testing instructions, test cases, and validation steps.

### Any deployment notes?
Environment variables, migrations, breaking changes, or special instructions.
```

Include related issue references: `Closes #71, #77` (at end of description)

### PR Metadata Requirements
Always ensure the following metadata is set on every PR:
- **Labels**: Assign relevant labels (e.g., `enhancement`, `bug`, `documentation`, `refactor`, `testing`)
- **Assignees**: Assign to yourself (J-MaFf)
- **Issues**: Link all related issues in the PR description and GitHub's linked issues feature
"""


def run_command(cmd, cwd=None, check=True):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=30
        )
        if check and result.returncode != 0:
            print(f"❌ Command failed: {cmd}")
            print(f"Error: {result.stderr}")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"⏱️ Command timed out: {cmd}")
        return None
    except Exception as e:
        print(f"❌ Exception running command: {e}")
        return None


def get_repos():
    """Get list of all user repos."""
    cmd = "gh repo list J-MaFf --limit 100 --json name,url"
    output = run_command(cmd)
    if not output:
        return []
    return json.loads(output)


def repo_has_formatting_standards(owner, repo):
    """Check if repo already has formatting standards in copilot-instructions.md."""
    cmd = f"gh api repos/{owner}/{repo}/contents/.github/copilot-instructions.md"
    result = run_command(cmd, check=False)
    if not result:
        return False

    try:
        data = json.loads(result)
        # Decode the base64 content
        import base64

        content = base64.b64decode(data["content"]).decode("utf-8")
        return "Code Style & Formatting Standards" in content
    except:
        return False


def apply_standards_to_repo(owner, repo):
    """Apply formatting standards to a single repo."""
    print(f"\n📦 Processing {owner}/{repo}...")

    # Check if standards already exist
    if repo_has_formatting_standards(owner, repo):
        print(f"✅ {repo} already has formatting standards, skipping.")
        return True

    # Create temp directory for repo
    temp_dir = tempfile.mkdtemp(prefix=f"{repo}_")
    try:
        print(f"  📂 Cloning to {temp_dir}...")
        clone_url = f"https://github.com/{owner}/{repo}.git"

        if not run_command(f'git clone "{clone_url}" "{temp_dir}"'):
            return False

        # Check if .github directory exists
        github_dir = Path(temp_dir) / ".github"
        github_dir.mkdir(exist_ok=True)

        instructions_file = github_dir / "copilot-instructions.md"

        # Check if file exists and read its content
        if instructions_file.exists():
            with open(instructions_file, "r", encoding="utf-8") as f:
                content = f.read()
            # Append standards if not already there
            if "Code Style & Formatting Standards" not in content:
                content += f"\n\n{FORMATTING_STANDARDS}"
        else:
            # Create new file with standards
            content = f"# Copilot Instructions: {repo}\n\n{FORMATTING_STANDARDS}"

        # Write the file
        with open(instructions_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Create and push branch
        print(f"  🌿 Creating branch...")
        if not run_command(
            "git checkout -b chore/add-formatting-standards", cwd=temp_dir
        ):
            return False

        if not run_command("git add .github/copilot-instructions.md", cwd=temp_dir):
            return False

        commit_msg = "docs: Add code style and formatting standards"
        if not run_command(f'git commit -m "{commit_msg}"', cwd=temp_dir):
            print(f"  ⚠️ Nothing to commit for {repo}")
            return True

        if not run_command(
            "git push origin chore/add-formatting-standards", cwd=temp_dir
        ):
            print(f"  ⚠️ Push failed for {repo}")
            return False

        print(f"  ✅ Branch pushed for {repo}")

        # Create PR
        print(f"  🔄 Creating PR...")
        pr_body = """### What does this PR do?
Adds a 'Code Style & Formatting Standards' section to .github/copilot-instructions.md defining consistent formatting guidelines for the project.

### Why are we doing this?
Establish clear, consistent standards for:
- Conventional Commits (feat:, fix:, docs:, chore:, etc.)
- PR titles with emoji prefixes (✨, 🐛, 📚, 🔧, 🎯, 🚀, ⚡, 🧪)
- PR body structure using GitHub-flavored markdown with 4 standard sections
- PR metadata requirements (labels, assignees, linked issues)

This ensures all team members and Copilot follow the same formatting conventions.

### How should this be tested?
1. Review the 'Code Style & Formatting Standards' section in .github/copilot-instructions.md
2. Verify the formatting examples are clear and actionable
3. Confirm the structure matches the style guide

### Any deployment notes?
These standards should be applied consistently across all repositories."""

        # Write PR body to temp file to avoid escaping issues
        pr_body_file = Path(temp_dir) / "pr_body.txt"
        with open(pr_body_file, "w", encoding="utf-8") as f:
            f.write(pr_body)

        pr_cmd = f'gh pr create --repo {owner}/{repo} --title "📚 Add code style and formatting standards" --body-file "{pr_body_file}"'

        if run_command(pr_cmd, check=False):
            print(f"  ✅ PR created for {repo}")
            return True
        else:
            print(f"  ⚠️ PR creation failed for {repo}, but changes are pushed")
            return True

    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    print("🚀 Starting formatting standards application...\n")

    repos = get_repos()
    if not repos:
        print("❌ Failed to get repos")
        return

    print(f"📊 Found {len(repos)} repositories\n")

    # Skip clickup_task_extractor as it already has the standards
    repos = [r for r in repos if r["name"] != "clickup_task_extractor"]

    success_count = 0
    skipped_count = 0
    failed_count = 0

    for repo in repos:
        owner = "J-MaFf"
        repo_name = repo["name"]

        result = apply_standards_to_repo(owner, repo_name)

        if result:
            success_count += 1
        else:
            failed_count += 1

    print(f"\n{'=' * 60}")
    print(f"✅ Completed: {success_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
