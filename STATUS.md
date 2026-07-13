# STATUS

## What This Is

Python CLI for extracting, processing, and exporting tasks from the ClickUp API. Supports Markdown, HTML, and CSV output, optional AI summaries (Claude via Max/Pro OAuth by default, or Google Gemini, or the ClickUp Summary field), 1Password-backed authentication, and a Rich console UI with interactive task selection and priority/ETA sorting.

## Current State — 2026-07-13

**v1.06 in release.** CI now runs the suite on two OSes: hosted Linux (Python 3.11) and the self-hosted `win-test` Windows runner (Python 3.14) ([#156](https://github.com/J-MaFf/clickup_task_extractor/issues/156)). Beads (`bd`) is active as the task/memory layer beneath GitHub Issues. Since v1.05: AI summaries default to Claude (Max OAuth, [#145](https://github.com/J-MaFf/clickup_task_extractor/pull/145)); summaries + ETAs run concurrently ([#148](https://github.com/J-MaFf/clickup_task_extractor/pull/148)); ETAs can use Claude ([#149](https://github.com/J-MaFf/clickup_task_extractor/pull/149)); `main.py` auto-loads a project-local `.env` so configured workspace/space apply ([#151](https://github.com/J-MaFf/clickup_task_extractor/pull/151)); `kfj_task_extractor.py` auto-loads `.env.kfj` secret-safely ([#153](https://github.com/J-MaFf/clickup_task_extractor/pull/153)) — all merged.

**2026-07-13 — Claude CLI login-failure incident fixed.** A logged-out `claude` CLI produced 81 repeated "Not logged in" errors and false success reporting in one run; fixed across [#162](https://github.com/J-MaFf/clickup_task_extractor/pull/162) (pre-flight auth check + fail-fast), [#163](https://github.com/J-MaFf/clickup_task_extractor/pull/163) (real generated-vs-fallback counts), and [#164](https://github.com/J-MaFf/clickup_task_extractor/pull/164) (ClickUp field notice scoped to ClickUp/Both sources). All 355 tests pass.

**In progress:** `release/v1.06` ([#154](https://github.com/J-MaFf/clickup_task_extractor/issues/154)) — version bump (`version.py` → 1.06, README badge, `CHANGELOG.md` `[1.06]`), then tag `v1.06` on `main`.

### Components

| File | Description |
|------|-------------|
| `main.py` | CLI entry, venv handoff, config assembly, auth chain |
| `config.py` | Enums, `TaskRecord` dataclass, datetime helpers, sort logic |
| `auth.py` | Multi-fallback API key loader |
| `api_client.py` | `APIClient` protocol + `ClickUpAPIClient` |
| `extractor.py` | Main workflow, export context manager, interactive UI |
| `ai_summary.py` | AI summaries: Claude CLI path (default, Max OAuth) + Gemini tiered model strategy / quota detection; shared `run_claude_cli` runner |
| `eta_calculator.py` | ETA estimation: Claude CLI (`get_claude_eta`) + Gemini + deterministic priority/status fallback |
| `mappers.py` | Prompts, date filters, custom field mapping, image extraction |
| `kfj_task_extractor.py` | Standalone KFJ weekly Google Sheets sync |
| `logger_config.py` | Rich-enhanced logging setup |
| `.beads/` | Beads (bd) issue tracking — Dolt-backed, syncs via `refs/dolt/data` |

### Resolved Issues

| Issue | Description | PR |
|-------|-------------|-----|
| [#156](https://github.com/J-MaFf/clickup_task_extractor/issues/156) | Run tests on the self-hosted Windows runner | [#157](https://github.com/J-MaFf/clickup_task_extractor/pull/157) |
| [#90](https://github.com/J-MaFf/clickup_task_extractor/issues/90) | Sort tasks by priority then ETA | [#102](https://github.com/J-MaFf/clickup_task_extractor/pull/102) |
| [#104](https://github.com/J-MaFf/clickup_task_extractor/issues/104) | KFJ standalone Google Sheets sync | [#104](https://github.com/J-MaFf/clickup_task_extractor/pull/104) |
| [#105](https://github.com/J-MaFf/clickup_task_extractor/issues/105) | Disable Rich show_locals (secret leak) | [#117](https://github.com/J-MaFf/clickup_task_extractor/pull/117) |
| [#106](https://github.com/J-MaFf/clickup_task_extractor/issues/106) | Move personal identifiers to env vars | [#117](https://github.com/J-MaFf/clickup_task_extractor/pull/117) |
| [#107](https://github.com/J-MaFf/clickup_task_extractor/issues/107) | Guard module-level side effects | [#117](https://github.com/J-MaFf/clickup_task_extractor/pull/117) |
| [#108](https://github.com/J-MaFf/clickup_task_extractor/issues/108) | Pin deps, add requirements.lock | [#117](https://github.com/J-MaFf/clickup_task_extractor/pull/117) |
| [#109](https://github.com/J-MaFf/clickup_task_extractor/issues/109) | Fix invalid Gemini model identifier | [#117](https://github.com/J-MaFf/clickup_task_extractor/pull/117) |
| [#110](https://github.com/J-MaFf/clickup_task_extractor/issues/110) | Make kfj_task_extractor configurable | [#120](https://github.com/J-MaFf/clickup_task_extractor/pull/120) |
| [#119](https://github.com/J-MaFf/clickup_task_extractor/issues/119) | Adopt beads (bd) for AI task tracking | [#121](https://github.com/J-MaFf/clickup_task_extractor/pull/121) |
| [#122](https://github.com/J-MaFf/clickup_task_extractor/issues/122) | Add GitHub Actions CI (pytest on push) | [#123](https://github.com/J-MaFf/clickup_task_extractor/pull/123) |
| [#124](https://github.com/J-MaFf/clickup_task_extractor/issues/124) | Fix null type_config AttributeError | [#126](https://github.com/J-MaFf/clickup_task_extractor/pull/126) |
| [#125](https://github.com/J-MaFf/clickup_task_extractor/issues/125) | Make API timeout configurable | [#127](https://github.com/J-MaFf/clickup_task_extractor/pull/127) |
| [#144](https://github.com/J-MaFf/clickup_task_extractor/issues/144) | Add Claude (Max OAuth) AI summary source, make it default | [#145](https://github.com/J-MaFf/clickup_task_extractor/pull/145) |
| [#147](https://github.com/J-MaFf/clickup_task_extractor/issues/147) | Concurrent AI summary generation | [#148](https://github.com/J-MaFf/clickup_task_extractor/pull/148) |
| [#146](https://github.com/J-MaFf/clickup_task_extractor/issues/146) | Claude (Max OAuth) ETA estimation source | [#149](https://github.com/J-MaFf/clickup_task_extractor/pull/149) |
| [#150](https://github.com/J-MaFf/clickup_task_extractor/issues/150) | Load `.env` at startup so configured workspace/space apply | [#151](https://github.com/J-MaFf/clickup_task_extractor/pull/151) |
| [#152](https://github.com/J-MaFf/clickup_task_extractor/issues/152) | Auto-load `.env.kfj` in `kfj_task_extractor.py`, secret-safe | [#153](https://github.com/J-MaFf/clickup_task_extractor/pull/153) |
| [#159](https://github.com/J-MaFf/clickup_task_extractor/issues/159) | Claude CLI "Not logged in" fail-fast + pre-flight auth check | [#162](https://github.com/J-MaFf/clickup_task_extractor/pull/162) |
| [#160](https://github.com/J-MaFf/clickup_task_extractor/issues/160) | Report real generated-vs-fallback counts in AI passes | [#163](https://github.com/J-MaFf/clickup_task_extractor/pull/163) |
| [#161](https://github.com/J-MaFf/clickup_task_extractor/issues/161) | Limit ClickUp Summary empty-field notice to ClickUp/Both | [#164](https://github.com/J-MaFf/clickup_task_extractor/pull/164) |

### Open Issues

- [#154](https://github.com/J-MaFf/clickup_task_extractor/issues/154) — Release v1.06 (in review on `release/v1.06`)

## Natural Next Steps

- After v1.06 tags: optionally build the PyInstaller exe into `dist/v1.06/` (gitignored; not required for source users)
- Identify any bugs or improvements from real usage

## Prerequisites to Run

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (see .env.example)
cp .env.example .env
# edit .env with your ClickUp API key, workspace/space names

# Run
python main.py
```
