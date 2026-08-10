# Spec: Work Location column in the KFI Jefferson weekly sheet

## Goal

The auto-generated "KFI Jefferson current tasks" Google Sheet tab gains a "Work Location"
column that shows whether each task was worked remotely or on-site at Jefferson, sourced
from a ClickUp dropdown custom field.

## Context

- The sheet is produced by `kfj_task_extractor.py` (standalone weekly sync), **not** by the
  main extractor (`main.py`/`extractor.py`). All code changes belong in
  `kfj_task_extractor.py` and its tests.
- Current columns are `HEADER = ["Task", "Company", "Branch", "Priority", "Status", "ETA"]`
  (`kfj_task_extractor.py:200`).
- The existing **Branch** column is the pattern to copy: `task_to_record()`
  (`kfj_task_extractor.py:396`) resolves the "Branch" dropdown custom field via
  `LocationMapper.map_location(value, type_config, options)` and falls back when unset.
- Verified: `get_export_fields()` in `extractor.py:105` derives the main extractor's
  export columns from `TaskRecord.__annotations__`. Therefore the new value must **not**
  be added as a `TaskRecord` dataclass field — that would silently add a column to the
  main extractor's Markdown/HTML/CSV exports. Carry it in `record._metadata` instead
  (the same channel `task_to_record` already uses for `eta_inputs`;
  `_metadata` is excluded from exports by design).
- Verified: `write_to_sheet()` (`kfj_task_extractor.py:603`) sizes the tab with
  `cols=len(HEADER)` (dynamic) but bolds the header with a hardcoded range
  `"A1:F1"` (`kfj_task_extractor.py:639`) — that range must grow with the header.
- Verified: `record_to_row()` (`kfj_task_extractor.py:579`) lowercases Priority and
  Status to match sheet conventions; Branch keeps its display casing. Work Location
  follows Branch: display casing preserved.
- Old weekly tabs are never modified (`write_to_sheet` only writes the new/current tab),
  so the new column appears only on tabs generated after this change. That is accepted.
- **Prerequisite (manual, one-time, outside this spec's code):** a dropdown custom field
  named **"Work Location"** with options **"Remote"** and **"On-site"** must exist on the
  ClickUp "KFI Jefferson" list. The ClickUp v2 API cannot create custom field
  *definitions* (only set values on existing fields), so Joey creates the field in the
  ClickUp UI and sets it per task. The code must behave correctly (blank cell) both
  before the field exists and for tasks where it is unset.
- Decisions already made (interview, 2026-08-10): source = new ClickUp dropdown field;
  header text = "Work Location"; cell values = "Remote" / "On-site" (dropdown option
  names); unset tasks render a **blank** cell (no default guess); column position =
  between Branch and Priority.

## Deliverable

Modified `kfj_task_extractor.py` and extended `tests/test_kfj_task_extractor.py` in this
repository. No other files change (no `config.py`, no `extractor.py`).

## Requirements

- R1. `HEADER` equals `["Task", "Company", "Branch", "Work Location", "Priority",
  "Status", "ETA"]`. [verify: read the constant]
- R2. `task_to_record()` resolves a dropdown custom field named exactly `"Work Location"`
  using the same mechanism as Branch (`LocationMapper.map_location(value, type_config,
  options)`) and stores the resolved string in `record._metadata["work_location"]` —
  not as a `TaskRecord` dataclass field. [verify: read the diff; confirm `TaskRecord`
  in `config.py` is untouched]
- R3. When the "Work Location" custom field is absent from the task, or present with
  `value` of `None`, the stored value is `""` (rendering a blank cell). No fallback
  constant, no inference. [verify: unit test]
- R4. `record_to_row()` emits the work-location value at index 3 (between Branch and
  Priority), preserving the dropdown option's display casing (e.g. "Remote",
  "On-site" — not lowercased). [verify: unit test asserting the full row order]
- R5. The bold-header format range in `write_to_sheet()` covers all 7 columns — either
  computed from `len(HEADER)` or the literal `"A1:G1"`. [verify: read the diff]
- R6. `python -m pytest tests/ -v` passes: all pre-existing tests still green (none
  modified except where they assert the old 6-column shape, which are updated to the
  new shape) plus new tests covering R2–R4: (a) mapped dropdown value appears in the
  record metadata, (b) missing field → `""`, (c) unset value (`value: None`) → `""`,
  (d) row order/casing per R4. [verify: run the suite]
- R7. `python -m ruff check kfj_task_extractor.py tests/test_kfj_task_extractor.py`
  reports no issues (ruff lives in the local venv, deliberately not in
  requirements.txt). [verify: run the command]
- R8. The module docstring's column list (line 9: "Task, Company, Branch, Priority,
  Status, ETA") and any README/`docs/CHANGELOG.md` text enumerating the sheet columns
  are updated to include Work Location; the changelog gains an entry under Keep a
  Changelog conventions. [verify: grep for the old 6-column enumeration returns no
  stale hits in docs/docstrings]

## Out of scope

- Any change to `TaskRecord`, `get_export_fields()`, or the main extractor's
  Markdown/HTML/CSV exports.
- Creating the ClickUp custom field programmatically, or writing/updating values in
  ClickUp (the script stays read-only toward ClickUp).
- AI inference of remote vs on-site from task content.
- Backfilling the new column into previously generated weekly tabs.
- Renaming, reordering, or reformatting any existing column.
- A fallback env var (e.g. `KFJ_FALLBACK_WORK_LOCATION`) — blank is the specified
  behavior for unset.

## Constraints

- Python 3.11+, standard repo style; run tests with `.\.venv\Scripts\python.exe -m
  pytest tests/ -v` on this Windows machine.
- Follow the Branch-handling idiom already in `task_to_record()` rather than inventing a
  new custom-field helper, unless extracting a tiny shared helper for both dropdowns
  keeps the function clearly simpler.
- Repo git conventions apply to the implementation (issue first, `feat/` branch, signed
  commits, PR referencing the issue) but are workflow, not artifact, requirements.

## Acceptance rubric

- C1 (from R1): PASS iff `HEADER` in `kfj_task_extractor.py` is exactly the 7-item list
  with "Work Location" at index 3.
- C2 (from R2): PASS iff the diff shows the dropdown resolved via
  `LocationMapper.map_location` and stored in `_metadata["work_location"]`, and
  `git diff` shows zero changes to `config.py` and `extractor.py`.
- C3 (from R3): PASS iff a test feeds a task with (a) no "Work Location" field and
  (b) the field with `value: None`, and both assert the stored value is `""`.
- C4 (from R4): PASS iff a test builds a record with work location "On-site" and asserts
  `record_to_row()` returns it at index 3 with casing intact, with Branch at 2 and
  lowercased priority at 4.
- C5 (from R5): PASS iff the header-format call's range spans columns A through G (or is
  derived from `len(HEADER)`).
- C6 (from R6): PASS iff the full pytest run exits 0 and the new tests named in R6
  exist and execute.
- C7 (from R7): PASS iff the ruff command exits 0 on both files.
- C8 (from R8): PASS iff no docstring/README/CHANGELOG text still lists the sheet
  columns without "Work Location", and `docs/CHANGELOG.md` has a new entry describing
  the column.
- C-final: PASS iff a domain expert reviewing the diff would accept it without
  substantive changes.

## Open questions

(none)
