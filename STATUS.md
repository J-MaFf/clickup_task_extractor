# STATUS

## What This Is

Python CLI for extracting, processing, and exporting tasks from the ClickUp API. Supports Markdown, HTML, and CSV output, optional AI summaries (Claude via Max/Pro OAuth by default, or Google Gemini, or the ClickUp Summary field), 1Password-backed authentication, and a Rich console UI with interactive task selection and priority/ETA sorting.

## Current State — 2026-06-26

**v1.05 shipped.** Beads (`bd`) is active as the task/memory layer beneath GitHub Issues. Claude (Max OAuth) is the default AI summary source ([#144](https://github.com/J-MaFf/clickup_task_extractor/pull/145), merged).

**In progress:** `feat/parallel-ai-summaries` ([#147](https://github.com/J-MaFf/clickup_task_extractor/issues/147)) — generate AI summaries concurrently (bounded `ThreadPoolExecutor`, `AI_SUMMARY_CONCURRENCY`, default 4) instead of serially, ~3× faster on large exports. Order preserved; usage-limit short-circuits queued calls. All 302 tests pass.

### Components

| File | Description |
|------|-------------|
| `main.py` | CLI entry, venv handoff, config assembly, auth chain |
| `config.py` | Enums, `TaskRecord` dataclass, datetime helpers, sort logic |
| `auth.py` | Multi-fallback API key loader |
| `api_client.py` | `APIClient` protocol + `ClickUpAPIClient` |
| `extractor.py` | Main workflow, export context manager, interactive UI |
| `ai_summary.py` | AI summaries: Claude CLI path (default, Max OAuth) + Gemini tiered model strategy / quota detection |
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

### Open Issues

- [#147](https://github.com/J-MaFf/clickup_task_extractor/issues/147) — Parallelize AI summary generation (in review on `feat/parallel-ai-summaries`)
- [#146](https://github.com/J-MaFf/clickup_task_extractor/issues/146) — Add Claude as an ETA-calculation source in `eta_calculator.py`

## Natural Next Steps

- #146: let `eta_calculator.py` use the Claude CLI too (currently Gemini-only; falls back to deterministic priority/status ETA when no Gemini key)
- File new beads issues as work is identified (`bd create`)
- Identify any bugs or improvements from v1.05 usage

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
