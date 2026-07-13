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

    def test_subprocess_env_scrubs_api_key(self) -> None:
        """The CLI runs without ANTHROPIC_API_KEY so it uses the OAuth subscription."""
        with patch.dict(
            "os.environ",
            {"ANTHROPIC_API_KEY": "sk-should-be-removed", "PATH": "x"},
            clear=False,
        ), patch("ai_summary.shutil.which", return_value="/usr/bin/claude"), patch(
            "ai_summary.subprocess.run",
            return_value=_completed(stdout="ok"),
        ) as mock_run:
            get_claude_summary("Task", [("Status", "open")])

        env = mock_run.call_args.kwargs["env"]
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", env)

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

    def test_auth_error_disables_claude_for_run(self) -> None:
        """'Not logged in' is terminal: one failure disables the rest of the run."""
        with patch("ai_summary.shutil.which", return_value="/usr/bin/claude"), patch(
            "ai_summary.subprocess.run",
            return_value=_completed(
                returncode=1, stderr="Not logged in · Please run /login"
            ),
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


class ClaudeAuthProbeTests(unittest.TestCase):
    """Tests for the `claude auth status` pre-flight probe and skip-flag setters."""

    def setUp(self) -> None:
        ai_summary._reset_claude_state()

    def tearDown(self) -> None:
        ai_summary._reset_claude_state()

    def test_logged_in_returns_true(self) -> None:
        with patch("ai_summary.shutil.which", return_value="/usr/bin/claude"), patch(
            "ai_summary.subprocess.run",
            return_value=_completed(stdout='{"loggedIn": true, "authMethod": "oauth"}'),
        ) as mock_run:
            self.assertTrue(ai_summary.claude_cli_authenticated())
        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd[1:3], ["auth", "status"])

    def test_logged_out_returns_false(self) -> None:
        with patch("ai_summary.shutil.which", return_value="/usr/bin/claude"), patch(
            "ai_summary.subprocess.run",
            return_value=_completed(
                returncode=1,
                stdout='{"loggedIn": false, "authMethod": "none"}',
            ),
        ):
            self.assertFalse(ai_summary.claude_cli_authenticated())

    def test_missing_cli_returns_none(self) -> None:
        with patch("ai_summary.shutil.which", return_value=None), patch(
            "ai_summary.subprocess.run"
        ) as mock_run:
            self.assertIsNone(ai_summary.claude_cli_authenticated())
        mock_run.assert_not_called()

    def test_unparseable_output_returns_none(self) -> None:
        """Older CLIs without `auth status` print usage text, not JSON."""
        with patch("ai_summary.shutil.which", return_value="/usr/bin/claude"), patch(
            "ai_summary.subprocess.run",
            return_value=_completed(returncode=1, stdout="Usage: claude [options]"),
        ):
            self.assertIsNone(ai_summary.claude_cli_authenticated())

    def test_timeout_returns_none(self) -> None:
        with patch("ai_summary.shutil.which", return_value="/usr/bin/claude"), patch(
            "ai_summary.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=15),
        ):
            self.assertIsNone(ai_summary.claude_cli_authenticated())

    def test_mark_claude_unavailable_short_circuits_cli(self) -> None:
        self.assertTrue(ai_summary.claude_generation_available())
        ai_summary.mark_claude_unavailable()
        self.assertFalse(ai_summary.claude_generation_available())
        with patch("ai_summary.subprocess.run") as mock_run:
            result = get_claude_summary("Task", [("Status", "open")])
        self.assertIsNone(result)
        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
