# STATUS

## What This Is

Python CLI for extracting, processing, and exporting tasks from the ClickUp API. Supports Markdown, HTML, and CSV output, optional AI summaries (Claude via Max/Pro OAuth by default, or Google Gemini, or the ClickUp Summary field), 1Password-backed authentication, and a Rich console UI with interactive task selection and priority/ETA sorting.

## Current State — 2026-06-26

**v1.05 shipped.** Beads (`bd`) is active as the task/memory layer beneath GitHub Issues. AI summaries default to Claude (Max OAuth, [#145](https://github.com/J-MaFf/clickup_task_extractor/pull/145)); summaries + ETAs run concurrently ([#148](https://github.com/J-MaFf/clickup_task_extractor/pull/148)); ETAs can use Claude ([#149](https://github.com/J-MaFf/clickup_task_extractor/pull/149)); `main.py` auto-loads a project-local `.env` so configured workspace/space apply ([#151](https://github.com/J-MaFf/clickup_task_extractor/pull/151), Fixes [#150](https://github.com/J-MaFf/clickup_task_extractor/issues/150)) — all merged.

**In progress:** `feat/load-dotenv-kfj` ([#152](https://github.com/J-MaFf/clickup_task_extractor/issues/152)) — `kfj_task_extractor.py` now auto-loads `.env.kfj` (same `_load_dotenv` pattern), but **secret-safe**: it skips `op://` values for `CLICKUP_API_KEY`/`GOOGLE_SHEETS_CREDENTIALS_JSON`, leaving them for `op run`/1Password. All 325 tests pass. Next: bump to **v1.06**.

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

### Open Issues

- [#152](https://github.com/J-MaFf/clickup_task_extractor/issues/152) — Auto-load `.env.kfj` in `kfj_task_extractor.py`, secret-safe (in review on `feat/load-dotenv-kfj`)

## Natural Next Steps

- Version bump / release (`1.06`) once #152 lands — four+ user-facing features since 1.05 (Claude summaries, concurrency, Claude ETA, `.env`/`.env.kfj` auto-load)
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
