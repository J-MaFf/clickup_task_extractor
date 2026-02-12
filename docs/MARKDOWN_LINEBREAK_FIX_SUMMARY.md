# Markdown Export Line Break Regression Fix - Implementation Summary

## Problem Statement

The fix for issue #86 (MD060 table separator inconsistency) was successful, but introduced a new regression in markdown exports with multi-line task notes. The line break handling strategy using two trailing spaces (`  \n`) was breaking table structure and causing multiple markdown lint violations:

- **MD055/table-pipe-style**: Missing leading/trailing pipes on continuation lines
- **MD056/table-column-count**: Table column count mismatch
- **MD009/no-trailing-spaces**: Trailing spaces (3-4 instead of 0 or 2)

## Root Cause

The original line break handling in `extractor.py`:
```python
value = value.replace("|", "\\|").replace("\n", "  \n")
```

When task notes contained newlines, the `  \n` replacement created continuation lines that exited the table cell context:
```markdown
| Task | ... | Description with
line break here
```

The second line lacks opening `|` and closing `|`, making it non-table content that violates markdown table structural rules.

## Solution Implemented

**Strategy: Option 1 - Keep Text on Single Line (Simplest)**

Changed the line break handling to replace newlines with single spaces:

```python
# extractor.py, line 1147 (render_markdown method)
value = value.replace("|", "\\|").replace("\n", " ")
```

### Why This Solution?

✅ **Simplest Implementation**: One character change, easy to understand and maintain
✅ **Maintains Table Integrity**: All rows keep same column count (fixes MD055, MD056)
✅ **Eliminates Trailing Spaces**: No more MD009 violations
✅ **Reliable**: Works with all markdown viewers and linters
⚠️ **Trade-off**: Multi-line readability in raw markdown is reduced (but content is still readable on single line)

## Files Changed

### 1. `extractor.py` (Line 1147)
- **Change**: `.replace("\n", "  \n")` → `.replace("\n", " ")`
- **Impact**: All markdown exports with multi-line notes now maintain valid table structure
- **Backwards Compatibility**: No external APIs changed; only output format affected

### 2. `tests/test_markdown_line_breaks.py`
- **Updated**: `test_markdown_line_breaks_use_trailing_spaces()` → `test_markdown_line_breaks_use_spaces()`
- **Updated**: Test assertions to verify newlines are replaced with spaces
- **Updated**: `test_markdown_combined_escaping_and_line_breaks()` to check space-based strategy
- **Verification**: All tests now validate that table structure is maintained

## Testing Results

✅ **Syntax Verification**: Changes compile without errors
✅ **Logic Verification**: Line break handling correctly normalizes newlines to spaces
✅ **Test Coverage**:
  - Multi-line notes are properly normalized
  - Pipe escaping works with space-normalized newlines
  - Table structure integrity is maintained
  - No trailing spaces are introduced

## Expected Improvements

After this fix, markdown exports will:

✅ **Pass markdownlint validation** without MD055, MD056, or MD009 violations
✅ **Maintain valid table structure** with consistent column counts
✅ **Properly escape special characters** (pipes, etc.)
✅ **Be compatible** with all markdown viewers and linters (VSCode, GitHub, etc.)

## Example Output Comparison

### Before Fix (MD055, MD056, MD009 violations):
```markdown
| Task | Notes |
| --- | --- |
| Sample | Description with
line break here |
```

### After Fix (No violations):
```markdown
| Task | Notes |
| --- | --- |
| Sample | Description with line break here |
```

## Related Issues

- **#86**: Original MD060 fix (table separator consistency) - ✅ Still works correctly
- **New Issue**: #<TBD> - Markdown export line break regression (this fix)

## Next Steps

1. ✅ **Code Implementation**: Completed
2. ✅ **Unit Tests**: Updated and verified
3. ⏳ **Manual Validation**: Run markdownlint on generated exports to confirm all violations resolved
4. ⏳ **Documentation**: Update README with markdown export quality notes
5. ⏳ **Release**: Include in next version with changelog entry

## Configuration Notes

No configuration changes required. This fix applies automatically to all markdown exports. The solution is:
- Non-breaking (only affects output format, not API)
- Transparent to users
- Compatible with existing workflows

## Rollback Plan

If needed, the change can be reverted by changing line 1147 in `extractor.py` back to:
```python
value = value.replace("|", "\\|").replace("\n", "  \n")
```

However, this would reintroduce the markdown lint violations. The new approach is strongly recommended.
