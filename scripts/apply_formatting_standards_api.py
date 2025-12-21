#!/usr/bin/env python3
"""
Apply formatting standards to all user-owned repositories via GitHub API.
Creates PRs without needing to clone repos.
"""

import subprocess
import json
import time

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


def run_command(cmd, check=True):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        if check and result.returncode != 0:
            return None
        return result.stdout.strip()
    except:
        return None


def get_repos():
    """Get list of all user repos."""
    cmd = "gh repo list J-MaFf --limit 100 --json name"
    output = run_command(cmd)
    if not output:
        return []
    return [r["name"] for r in json.loads(output)]


def get_file_sha(owner, repo, path):
    """Get SHA of a file if it exists."""
    cmd = f"gh api repos/{owner}/{repo}/contents/{path}"
    result = run_command(cmd, check=False)
    if result:
        try:
            data = json.loads(result)
            return data.get("sha")
        except:
            pass
    return None


def file_has_standards(owner, repo, path):
    """Check if file already has formatting standards."""
    cmd = f"gh api repos/{owner}/{repo}/contents/{path}"
    result = run_command(cmd, check=False)
    if result:
        try:
            import base64

            data = json.loads(result)
            content = base64.b64decode(data["content"]).decode("utf-8")
            return "Code Style & Formatting Standards" in content
        except:
            pass
    return False


def create_or_update_file(owner, repo, path, content, message):
    """Create or update a file in a repo."""
    import base64

    sha = get_file_sha(owner, repo, path)
    encoded_content = base64.b64encode(content.encode()).decode()

    if sha:
        cmd = f'gh api repos/{owner}/{repo}/contents/{path} -X PUT -f message="{message}" -f content="{encoded_content}" -f sha="{sha}"'
    else:
        cmd = f'gh api repos/{owner}/{repo}/contents/{path} -X PUT -f message="{message}" -f content="{encoded_content}"'

    result = run_command(cmd, check=False)
    return result is not None


def create_branch(owner, repo, branch_name, from_branch="main"):
    """Create a new branch from the default branch."""
    # Get the SHA of the default branch
    cmd = f"gh api repos/{owner}/{repo}/git/refs/heads/{from_branch}"
    result = run_command(cmd, check=False)
    if not result:
        return False

    try:
        data = json.loads(result)
        sha = data["object"]["sha"]
    except:
        return False

    # Create new branch
    cmd = f'gh api repos/{owner}/{repo}/git/refs -X POST -f ref="refs/heads/{branch_name}" -f sha="{sha}"'
    result = run_command(cmd, check=False)

    if result and "already exists" in result.lower():
        # Branch already exists, that's OK
        return True

    return result is not None


def create_pull_request(owner, repo, branch, title, body):
    """Create a pull request."""
    # Escape the title and body for shell
    title_escaped = title.replace('"', '\\"')

    # Write body to temp file
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(body)
        body_file = f.name

    try:
        cmd = f'gh pr create --repo {owner}/{repo} --title "{title_escaped}" --body-file "{body_file}" --base main --head {branch}'
        result = run_command(cmd, check=False)
        return result is not None and "pull" in result.lower()
    finally:
        import os

        try:
            os.unlink(body_file)
        except:
            pass


def apply_standards_to_repo(owner, repo):
    """Apply formatting standards to a repo via API."""
    print(f"\n📦 {repo}...", end=" ", flush=True)

    path = ".github/copilot-instructions.md"

    # Check if already has standards
    if file_has_standards(owner, repo, path):
        print("✅ Already has standards")
        return True

    # Check if file exists
    sha = get_file_sha(owner, repo, path)

    if sha:
        # File exists, append standards
        cmd = f"gh api repos/{owner}/{repo}/contents/{path}"
        result = run_command(cmd, check=False)
        if result:
            try:
                import base64

                data = json.loads(result)
                old_content = base64.b64decode(data["content"]).decode("utf-8")
                new_content = old_content + f"\n\n{FORMATTING_STANDARDS}"
            except:
                return False
        else:
            return False
    else:
        # Create new file
        new_content = f"# Copilot Instructions: {repo}\n\n{FORMATTING_STANDARDS}"

    # Try to create branch first
    if not create_branch(owner, repo, "chore/add-formatting-standards"):
        print("⚠️ Could not create branch")
        return False

    # Update file on the branch
    if not create_or_update_file(
        owner, repo, path, new_content, "docs: Add code style and formatting standards"
    ):
        print("⚠️ Could not update file")
        return False

    # Create PR
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

    if create_pull_request(
        owner,
        repo,
        "chore/add-formatting-standards",
        "📚 Add code style and formatting standards",
        pr_body,
    ):
        print("✅ PR created")
        return True
    else:
        print("⚠️ PR creation failed (may already exist)")
        return True


def main():
    print("🚀 Starting formatting standards application via API...\n")

    repos = get_repos()
    if not repos:
        print("❌ Failed to get repos")
        return

    print(f"📊 Found {len(repos)} repositories\n")

    # Skip clickup_task_extractor as it already has the standards
    repos = [r for r in repos if r != "clickup_task_extractor"]

    success = 0
    failed = 0

    for repo in repos:
        if apply_standards_to_repo("J-MaFf", repo):
            success += 1
        else:
            failed += 1

        # Rate limiting - GitHub API has limits
        time.sleep(0.5)

    print(f"\n{'=' * 60}")
    print(f"✅ Processed: {success}")
    print(f"❌ Failed: {failed}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
