#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests for the Claude CLI summary path in ai_summary.py.

These mock subprocess.run / shutil.which so no real `claude` CLI call is made.
They cover the happy path, the CLI-missing path, error/timeout handling, and the
usage-limit "skip the rest of the run" behavior.
"""

import subprocess
import unittest
from unittest.mock import patch, MagicMock

import ai_summary
from ai_summary import get_claude_summary


def _completed(returncode=0, stdout="", stderr=""):
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


class ClaudeSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        ai_summary._reset_claude_state()

    def tearDown(self) -> None:
        ai_summary._reset_claude_state()

    def test_model_default_is_a_claude_id(self) -> None:
        self.assertTrue(ai_summary.CLAUDE_SUMMARY_MODEL.startswith("claude-"))

    def test_happy_path_returns_cleaned_summary(self) -> None:
        with patch("ai_summary.shutil.which", return_value="/usr/bin/claude"), patch(
            "ai_summary.subprocess.run",
            return_value=_completed(stdout="I rebooted the printer\nand confirmed it works"),
        ) as mock_run:
            result = get_claude_summary(
                "Fix printer", [("Status", "in progress")]
            )

        # Newlines collapsed to spaces, trailing period added.
        self.assertEqual(result, "I rebooted the printer and confirmed it works.")
        mock_run.assert_called_once()
        # Prompt is passed over stdin, not as an argv element.
        kwargs = mock_run.call_args.kwargs
        self.assertIn("Status: in progress", kwargs["input"])
        cmd = mock_run.call_args.args[0]
        self.assertIn("-p", cmd)
        self.assertIn("--model", cmd)

    def test_empty_fields_short_circuits(self) -> None:
        with patch("ai_summary.subprocess.run") as mock_run:
            result = get_claude_summary("Task", [])
        self.assertEqual(result, "No content available for summary.")
        mock_run.assert_not_called()

    def test_missing_cli_returns_none_without_running(self) -> None:
        with patch("ai_summary.shutil.which", return_value=None), patch(
            "ai_summary.subprocess.run"
        ) as mock_run:
            result = get_claude_summary("Task", [("Status", "open")])
        self.assertIsNone(result)
        mock_run.assert_not_called()

    def test_nonzero_exit_returns_none(self) -> None:
        with patch("ai_summary.shutil.which", return_value="/usr/bin/claude"), patch(
            "ai_summary.subprocess.run",
            return_value=_completed(returncode=1, stderr="some transient error"),
        ):
            result = get_claude_summary("Task", [("Status", "open")])
        self.assertIsNone(result)
        # A generic error should NOT disable Claude for the rest of the run.
        self.assertTrue(ai_summary._claude_available)

    def test_usage_limit_disables_claude_for_run(self) -> None:
        with patch("ai_summary.shutil.which", return_value="/usr/bin/claude"), patch(
            "ai_summary.subprocess.run",
            return_value=_completed(returncode=1, stderr="Claude usage limit reached"),
        ) as mock_run:
            first = get_claude_summary("Task A", [("Status", "open")])
            second = get_claude_summary("Task B", [("Status", "open")])

        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertFalse(ai_summary._claude_available)
        # Second call short-circuits before invoking the CLI again.
        self.assertEqual(mock_run.call_count, 1)

    def test_timeout_returns_none(self) -> None:
        with patch("ai_summary.shutil.which", return_value="/usr/bin/claude"), patch(
            "ai_summary.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=120),
        ):
            result = get_claude_summary("Task", [("Status", "open")])
        self.assertIsNone(result)

    def test_empty_stdout_returns_none(self) -> None:
        with patch("ai_summary.shutil.which", return_value="/usr/bin/claude"), patch(
            "ai_summary.subprocess.run",
            return_value=_completed(stdout="   \n  "),
        ):
            result = get_claude_summary("Task", [("Status", "open")])
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
