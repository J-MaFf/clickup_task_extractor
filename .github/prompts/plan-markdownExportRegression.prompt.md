# Plan: Handle Markdown Lint Violation Regression from Issue #86 Fix

## Summary

The fix for issue #86 (MD060 table separator inconsistency) was successful in resolving the original violation. However, it introduced new markdown lint violations in the generated markdown exports, and investigation reveals older files still show MD060 violations.

## Root Cause Analysis

The new violations are **caused by the line break handling strategy**, specifically:

- The line break handling (`  \n` for markdown line breaks) **breaks table rows across multiple lines without pipes**
- When a task's notes contain newlines, the `  \n` escape causes the text to continue on the next line as plain text (not a table row)
- This violates MD055 and MD056 (table row integrity), MD009 (trailing spaces), and other rules
- **Critical finding**: Older generated files still show MD060 violations, suggesting the fix may be inconsistently applied

## Actual Violations from Generated Files

### File: `output/WeeklyTaskList_2-10-2026_2-14PM.md` (Current)

**MD055/table-pipe-style** _(Multiple instances on lines 11, 12, etc.)_

- Problem: Table pipe style mismatch — Missing leading/trailing pipes on continuation lines
- Example violation:
  ```
  | Replacement monitor for Michael S | KFI Jefferson | KFJ | normal | confirmation needed | 2/4/2026... | Subject: Replacement monitor...
  Description: Michael's monitor is experiencing...
  ```
  The second line lacks opening `|` and is treated as non-table text

**MD056/table-column-count** _(Multiple instances on lines 11, 12, etc.)_

- Problem: Table column count mismatch — Too few cells in rows
- Root cause: Continuation lines from multi-line notes are not valid table rows
- Expected: 8 columns; Actual: 7 (or fewer) when a line breaks

**MD009/no-trailing-spaces** _(9+ instances)_

- Lines affected: 73, 112, 153, 191, 203, 215, 231, 238, 240, 274
- Problem: Trailing spaces (3-4 spaces instead of 0 or 2)
- Root cause: The `  \n` escape creates trailing spaces, and indentation adds extras

**MD032/blanks-around-lists** _(Line 153)_

- Problem: Lists should be surrounded by blank lines
- Example: "1. Local Administrator Account Issues & Cloning"

**MD034/no-bare-urls** _(Line 215)_

- Problem: Bare URLs should be enclosed in angle brackets
- Example: "Username: ssmith@kikkoman.com"

### File: `output/WeeklyTaskList_2-2-2026_9-28AM.md` (Older file)

**MD060/table-column-style** _(20+ instances on lines 11-19+)_

- Problem: Table pipe has extra space to the right/left for style "compact"
- **CRITICAL**: This is the ORIGINAL issue that issue #86 was supposed to fix
- Indicates either:
  1. The fix wasn't fully applied
  2. The fix is version-dependent or conditional
  3. Older exports weren't regenerated after the fix

## Key Insight: The Core Problem

**The `  \n` escape strategy breaks table structure** when task content contains newlines. Current line break handling in `extractor.py`:

```python
value = value.replace("|", "\\|").replace("\n", "  \n")
```

When task notes contain `\n`, they're replaced with `  \n`, which **exits the table cell context** and makes continuation lines appear as plain text instead of table cells.

## Decision: Create New Issue vs. Update Issue #86

### Recommended Approach: **Verify #86 Status, Then Create New Issue** ✅

**Rationale:**

- The MD060 violations appearing in older files suggest issue #86 may not be fully closed
- The new violations (MD055, MD056, MD009, MD032, MD034) are separate and caused by the line break strategy
- Create a new issue to track the line break regression, referencing #86
- Clean separation of concerns: #86 for table format, new issue for line break handling

## Implementation Plan

### Step 1: Verify Issue #86 Status

Before proceeding, investigate:

- [ ] Which generated files have MD060 violations (newer vs. older)?
- [ ] Was the #86 fix fully applied to the markdown export code?
- [ ] Are there version-specific issues with the fix?
- [ ] Confirm: Does the separator line use consistent formatting in current code?

**Action**: Generate fresh markdown export and check if MD060 violations appear. Compare with older output files.

### Step 2: Create New Issue

**Title:** `Fix markdown export regression: table structure corruption with multi-line notes`

**Body:**

````markdown
## Description

When exporting tasks to markdown format, the current line break handling breaks the table structure, causing multiple markdown lint violations. Continuation lines from multi-line notes appear outside the table context without proper pipe formatting.

## Problem

The markdown export uses `  \n` (two trailing spaces + newline) to create line breaks in multi-line task notes. This causes continuation lines to appear outside the table context, violating markdown table structural rules.

### Current Violations in Generated Output

**File:** `output/WeeklyTaskList_2-10-2026_2-14PM.md`

| Rule  | Lines                                           | Issue                                                | Example                                                 |
| ----- | ----------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------- |
| MD055 | 11, 12, etc.                                    | Missing leading/trailing pipes on continuation lines | Multi-line notes break without `\|`                     |
| MD056 | 11, 12, etc.                                    | Column count mismatch (Expected: 8; Actual: 7)       | Continuation lines lack proper structure                |
| MD009 | 73, 112, 153, 191, 203, 215, 231, 238, 240, 274 | Trailing spaces (3-4 instead of 0 or 2)              | Extra spaces from `  \n` and indentation                |
| MD032 | 153                                             | Lists need blank lines around them                   | No blank line before "1. Local Admin..."                |
| MD034 | 215                                             | Bare URL not enclosed in angle brackets              | `ssmith@kikkoman.com` should be `<ssmith@kikkoman.com>` |

### Root Cause

Current line break code in `extractor.py`:

```python
value = value.replace("|", "\\|").replace("\n", "  \n")
```
````

When task notes contain newlines, the replacement creates continuation lines that exit cell context:

```markdown
| Task | ... | Description with
line break here
```

The second line has no leading `|` and no trailing `|`, making it non-table content.

## Expected Behavior

All generated markdown exports should:

- ✅ Pass `markdownlint` validation without any violations
- ✅ Properly render multi-line content (notes with multiple lines)
- ✅ Maintain valid table structure (all rows have same column count)
- ✅ Comply with all configured markdown lint rules (MD055, MD056, MD009, MD032, MD034)

## Solution

Replace the `  \n` line break strategy with one that **stays within the table cell context**. Recommended approaches:

### Option 1: Keep Text on Single Line (Simplest)

- Replace `\n` with empty string or space
- **Pro**: Simplest, always table-compliant
- **Con**: Loses multi-line readability in generated markdown

### Option 2: Use HTML `<br>` Tags (Preserves Structure)

- Replace `\n` with `<br>`
- **Pro**: Maintains table structure, renders in markdown viewers
- **Con**: May trigger different lint rules, less readable in raw markdown

### Option 3: Soft-Wrap with No Breaks (Viewer Dependent)

- Keep multi-line content as-is without explicit breaks
- Markdown viewers wrap naturally at window width
- **Pro**: Clean output, reader-friendly
- **Con**: Works only with proper markdown viewer support

### Option 4: Escape Newlines Differently (Custom Handling)

- Research valid markdown approaches for multi-line table cells
- Possible: Use entity encoding, Unicode, or placeholder replacements
- **Pro**: Preserves content integrity
- **Con**: May require custom markdown viewers

## Acceptance Criteria

- [ ] Pass `markdownlint` validation without any violations
- [ ] All rows maintain same column count (MD055, MD056 compliant)
- [ ] No trailing spaces (MD009 compliant)
- [ ] Lists properly spaced (MD032 compliant)
- [ ] URLs properly formatted (MD034 compliant)
- [ ] Multi-line notes remain readable in generated markdown
- [ ] Unit tests cover: empty notes, notes with newlines, notes with pipes, special characters

## Files Affected

- `extractor.py` — `render_markdown()` method (line break handling)
- `tests/test_markdown_line_breaks.py` — Update tests for new line break strategy

## Test Case

```bash
# Generate markdown export
python main.py --output-format Markdown

# Validate with markdownlint
markdownlint output/WeeklyTaskList_*.md
```

Expected output: **No violations** in any `.md` files

## Related Issues

- #86: Original MD060 fix (verify if fully applied)

## Risk Assessment

**Severity:** Medium-High

- Blocks markdown export from being usable with linters
- Affects all generated markdown files with multi-line task notes
- Generated markdown fails validation in VSCode Markdown Lint extension

**Complexity:** Medium

- Core issue is clearly identified: line break handling strategy
- Multiple solution paths available (choose best fit)
- May require refactoring of markdown cell formatting

```

### Step 3: Label and Link

- Add labels: `bug`, `regression`, `markdown`, `linting`, `critical`
- Link: "Regression from #86 fix" (reference issue #86 in description)
- Assign to: @J-MaFf

## Additional Notes

- The original MD060 fix is technically solid—the problem is the broader line break handling strategy
- This is a good example of a fix solving one problem while introducing others
- Consider creating a `.markdownlintrc` or `.markdownlint.json` configuration file to standardize lint rules
- Need to decide on line break strategy: simplicity vs. readability trade-off

## Next Steps

1. **Investigate #86 status** — Confirm if MD060 violations are fully resolved in current output
2. **Create new issue** — Use template above for line break regression
3. **Prioritize solution** — Choose line break strategy (Option 1-4) based on requirements
4. **Update code and tests** — Refactor `render_markdown()` and update test coverage
5. **Validate** — Ensure all generated markdown passes markdownlint
6. **Document decision** — Add entry to CHANGELOG.md explaining the solution chosen
```
