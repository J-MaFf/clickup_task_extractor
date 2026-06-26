#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests for the concurrent AI-summary pass (_generate_summaries_concurrently).

Covers: order/mapping preservation across workers, per-task call count,
concurrency clamping, the ClickUp-only no-op, and that a mid-run provider
usage-limit short-circuits remaining calls.
"""

import unittest
from unittest.mock import patch

import ai_summary
from config import AISource, ClickUpConfig, OutputFormat, TaskRecord
from extractor import ClickUpTaskExtractor


class _DummyAPIClient:
    def get(self, endpoint):  # pragma: no cover - not used by these tests
        return {}


def _make_record(name: str) -> TaskRecord:
    """A TaskRecord with the _metadata the concurrent pass reads."""
    rec = TaskRecord(
        Task=name,
        Company="Co",
        Branch="",
        Priority="Normal",
        Status="Open",
        ETA="",
        Notes="base notes for " + name,
        Extra="",
    )
    rec._metadata = {
        "task_name": name,
        "ai_fields": (("Name", name), ("Status", "Open")),
        "base_notes": "base notes for " + name,
        "clickup_ai_summary": None,
    }
    return rec


def _make_eta_record(name: str, *, with_inputs: bool = True) -> TaskRecord:
    """A TaskRecord carrying eta_inputs (an AI-ETA candidate) when requested."""
    rec = _make_record(name)
    rec.ETA = "01/01/2026"  # deterministic baseline already set by _process_task
    rec._metadata["eta_inputs"] = (
        {
            "task_name": name,
            "priority": "Normal",
            "status": "to do",
            "description": "",
            "subject": "",
            "resolution": "",
        }
        if with_inputs
        else None
    )
    return rec


def _config(source: AISource = AISource.CLAUDE) -> ClickUpConfig:
    return ClickUpConfig(
        api_key="k",
        workspace_name="W",
        space_name="S",
        output_format=OutputFormat.MARKDOWN,
        output_path="out.md",
        enable_ai_summary=True,
        ai_source=source,
    )


class SummaryConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        ai_summary._reset_claude_state()
        ai_summary._reset_api_state()

    def tearDown(self) -> None:
        ai_summary._reset_claude_state()
        ai_summary._reset_api_state()

    def test_each_task_gets_its_own_summary_in_order(self) -> None:
        """Results map back to the correct task regardless of completion order."""
        extractor = ClickUpTaskExtractor(_config(AISource.CLAUDE), _DummyAPIClient())
        records = [_make_record(f"Task {i}") for i in range(12)]

        # Return a summary derived from the task name so we can verify mapping.
        def fake_claude(task_name, fields, progress_pause_callback=None):
            return f"summary::{task_name}"

        with patch("extractor.get_claude_summary", side_effect=fake_claude) as mock_claude, patch(
            "extractor.console"
        ):
            extractor._generate_summaries_concurrently(records)

        self.assertEqual(mock_claude.call_count, 12)
        for i, rec in enumerate(records):
            self.assertEqual(rec.Notes, f"summary::Task {i}")

    def test_concurrency_is_clamped_to_task_count(self) -> None:
        extractor = ClickUpTaskExtractor(_config(), _DummyAPIClient())
        with patch.dict("os.environ", {"AI_SUMMARY_CONCURRENCY": "8"}, clear=False):
            self.assertEqual(extractor._summary_concurrency(3), 3)
            self.assertEqual(extractor._summary_concurrency(20), 8)
        with patch.dict("os.environ", {"AI_SUMMARY_CONCURRENCY": "0"}, clear=False):
            self.assertEqual(extractor._summary_concurrency(5), 1)
        with patch.dict("os.environ", {"AI_SUMMARY_CONCURRENCY": "notanint"}, clear=False):
            self.assertEqual(extractor._summary_concurrency(10), 4)  # default

    def test_clickup_source_makes_no_calls(self) -> None:
        extractor = ClickUpTaskExtractor(_config(AISource.CLICKUP), _DummyAPIClient())
        records = [_make_record("A"), _make_record("B")]
        with patch("extractor.get_claude_summary") as mock_claude, patch(
            "extractor.get_ai_summary"
        ) as mock_gemini, patch("extractor.console"):
            extractor._generate_summaries_concurrently(records)
        mock_claude.assert_not_called()
        mock_gemini.assert_not_called()

    def test_disabled_ai_is_noop(self) -> None:
        config = _config(AISource.CLAUDE)
        config.enable_ai_summary = False
        extractor = ClickUpTaskExtractor(config, _DummyAPIClient())
        records = [_make_record("A")]
        with patch("extractor.get_claude_summary") as mock_claude, patch("extractor.console"):
            extractor._generate_summaries_concurrently(records)
        mock_claude.assert_not_called()

    def test_usage_limit_short_circuits_remaining_calls(self) -> None:
        """Real get_claude_summary: a usage limit disables further CLI calls."""
        extractor = ClickUpTaskExtractor(_config(AISource.CLAUDE), _DummyAPIClient())
        records = [_make_record(f"T{i}") for i in range(6)]

        def completed(returncode=0, stdout="", stderr=""):
            class P:
                pass

            p = P()
            p.returncode = returncode
            p.stdout = stdout
            p.stderr = stderr
            return p

        # First CLI call reports a usage limit -> flips the global skip flag;
        # subsequent calls short-circuit before spawning a subprocess.
        with patch("ai_summary.shutil.which", return_value="/usr/bin/claude"), patch(
            "ai_summary.subprocess.run",
            return_value=completed(returncode=1, stderr="Claude usage limit reached"),
        ) as mock_run, patch("extractor.console"):
            # Force serial execution so the flag is set before later items run.
            with patch.dict("os.environ", {"AI_SUMMARY_CONCURRENCY": "1"}, clear=False):
                extractor._generate_summaries_concurrently(records)

        self.assertFalse(ai_summary._claude_available)
        # Far fewer than 6 subprocesses ran (ideally 1); the rest short-circuited.
        self.assertLess(mock_run.call_count, 6)
        # All tasks keep their base notes (fallback).
        for rec in records:
            self.assertTrue(rec.Notes.startswith("base notes for "))


class ETAConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        ai_summary._reset_claude_state()
        ai_summary._reset_api_state()

    def tearDown(self) -> None:
        ai_summary._reset_claude_state()
        ai_summary._reset_api_state()

    def test_ai_eta_applied_to_candidates_only(self) -> None:
        extractor = ClickUpTaskExtractor(_config(AISource.CLAUDE), _DummyAPIClient())
        # Two candidates (no due date) + one with a due date (no eta_inputs).
        candidates = [_make_eta_record("A"), _make_eta_record("B")]
        with_due = _make_eta_record("C", with_inputs=False)
        tasks = [candidates[0], with_due, candidates[1]]

        def fake_eta(**kwargs):
            return f"12/31/2026"  # AI estimate

        with patch("extractor.calculate_eta", side_effect=fake_eta) as mock_eta, patch(
            "extractor.console"
        ):
            extractor._generate_etas_concurrently(tasks)

        # Only the two candidates got the AI ETA; the due-date task is untouched.
        self.assertEqual(mock_eta.call_count, 2)
        self.assertEqual(candidates[0].ETA, "12/31/2026")
        self.assertEqual(candidates[1].ETA, "12/31/2026")
        self.assertEqual(with_due.ETA, "01/01/2026")  # baseline kept

    def test_eta_pass_noop_for_clickup_source(self) -> None:
        extractor = ClickUpTaskExtractor(_config(AISource.CLICKUP), _DummyAPIClient())
        tasks = [_make_eta_record("A")]
        with patch("extractor.calculate_eta") as mock_eta, patch("extractor.console"):
            extractor._generate_etas_concurrently(tasks)
        mock_eta.assert_not_called()

    def test_eta_pass_noop_when_no_candidates(self) -> None:
        extractor = ClickUpTaskExtractor(_config(AISource.CLAUDE), _DummyAPIClient())
        tasks = [_make_eta_record("A", with_inputs=False)]
        with patch("extractor.calculate_eta") as mock_eta, patch("extractor.console"):
            extractor._generate_etas_concurrently(tasks)
        mock_eta.assert_not_called()

    def test_eta_pass_disabled_when_ai_off(self) -> None:
        config = _config(AISource.CLAUDE)
        config.enable_ai_summary = False
        extractor = ClickUpTaskExtractor(config, _DummyAPIClient())
        tasks = [_make_eta_record("A")]
        with patch("extractor.calculate_eta") as mock_eta, patch("extractor.console"):
            extractor._generate_etas_concurrently(tasks)
        mock_eta.assert_not_called()


if __name__ == "__main__":
    unittest.main()
