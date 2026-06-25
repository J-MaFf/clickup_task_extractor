import importlib
import sys
from pathlib import Path
from typing import Any, Sequence
import unittest
from unittest.mock import MagicMock, patch

from config import DateFilter, OutputFormat


class MainEntrypointTests(unittest.TestCase):
    def _import_main_module(self) -> Any:
        project_root = Path(__file__).resolve().parents[1]
        sys.modules.pop("main", None)
        mocked_executable = str(project_root / ".venv" / "Scripts" / "python.exe")
        with patch.object(sys, "executable", mocked_executable):
            module = importlib.import_module("main")
        return module

    def _run_main_with_args(self, module: Any, argv: Sequence[str]) -> None:
        with patch.object(module.sys, "argv", list(argv)):
            module.main()

    def test_main_honors_cli_arguments_and_runs_extractor(self) -> None:
        main_module = self._import_main_module()

        mock_console = MagicMock()
        mock_console.input.return_value = ""
        mock_api_client_cls = MagicMock()
        mock_extractor_cls = MagicMock()

        with (
            patch.object(main_module, "console", mock_console),
            patch.object(
                main_module, "get_yes_no_input", return_value=False
            ) as mock_yes_no,
            patch.object(
                main_module, "get_choice_input", return_value="HTML"
            ) as mock_choice_input,
            patch.object(main_module, "load_secret_with_fallback") as mock_load_secret,
            patch.object(
                main_module,
                "_load_runtime_dependencies",
                return_value=(mock_api_client_cls, mock_extractor_cls),
            ),
        ):
            extractor_instance = mock_extractor_cls.return_value
            extractor_instance.run = MagicMock()

            argv = [
                str(Path(__file__).resolve().parents[1] / "main.py"),
                "--api-key",
                "test-key",
                "--workspace",
                "Acme Workspace",
                "--space",
                "Ops",
                "--list",
                "KFI Jefferson",
                "--output",
                "output/custom.md",
                "--include-completed",
                "--date-filter",
                "LastWeek",
                "--ai-summary",
                "--gemini-api-key",
                "gem-key",
                "--output-format",
                "HTML",
                "--interactive",
            ]

            self._run_main_with_args(main_module, argv)

        mock_yes_no.assert_not_called()
        mock_load_secret.assert_not_called()
        mock_console.input.assert_not_called()

        mock_api_client_cls.assert_called_once_with("test-key")
        mock_extractor_cls.assert_called_once()
        extractor_instance.run.assert_called_once()

        config_arg = mock_extractor_cls.call_args.args[0]
        self.assertEqual(config_arg.api_key, "test-key")
        self.assertEqual(config_arg.workspace_name, "Acme Workspace")
        self.assertEqual(config_arg.space_name, "Ops")
        self.assertEqual(config_arg.list_name, "KFI Jefferson")
        self.assertEqual(config_arg.output_path, "output/custom.md")
        self.assertTrue(config_arg.include_completed)
        self.assertEqual(config_arg.date_filter, DateFilter.LAST_WEEK)
        self.assertTrue(config_arg.enable_ai_summary)
        self.assertEqual(config_arg.gemini_api_key, "gem-key")
        self.assertEqual(config_arg.output_format, OutputFormat.HTML)
        self.assertTrue(config_arg.interactive_selection)

        load_func = mock_extractor_cls.call_args.args[2]
        self.assertTrue(callable(load_func))

    def test_main_prompts_for_output_format_when_not_provided(self) -> None:
        """Test that main prompts for output format when not provided via CLI."""
        main_module = self._import_main_module()

        mock_console = MagicMock()
        mock_console.input.return_value = ""
        mock_api_client_cls = MagicMock()
        mock_extractor_cls = MagicMock()

        with (
            patch.object(main_module, "console", mock_console),
            patch.object(
                main_module, "get_yes_no_input", return_value=False
            ) as mock_yes_no,
            patch.object(
                main_module, "get_choice_input", return_value="CSV"
            ) as mock_choice_input,
            patch.object(main_module, "load_secret_with_fallback") as mock_load_secret,
            patch.object(
                main_module,
                "_load_runtime_dependencies",
                return_value=(mock_api_client_cls, mock_extractor_cls),
            ),
        ):
            extractor_instance = mock_extractor_cls.return_value
            extractor_instance.run = MagicMock()

            # Note: NOT providing --output-format argument
            argv = [
                str(Path(__file__).resolve().parents[1] / "main.py"),
                "--api-key",
                "test-key",
                "--workspace",
                "TestWorkspace",
            ]

            self._run_main_with_args(main_module, argv)

        # Verify the choice input function was called for output format
        mock_choice_input.assert_called_once()
        call_args = mock_choice_input.call_args
        self.assertIn("Markdown", call_args.args[1])
        self.assertIn("HTML", call_args.args[1])
        self.assertIn("CSV", call_args.args[1])
        self.assertEqual(len(call_args.args[1]), 3)

        # Verify config was set with the selected format
        config_arg = mock_extractor_cls.call_args.args[0]
        self.assertEqual(config_arg.output_format, OutputFormat.CSV)

    def test_environment_auth_attempted_without_secret_reference(self) -> None:
        """Regression: an OP_ENVIRONMENT_ID-only setup must still attempt 1Password.

        With CLICKUP_API_SECRET_REFERENCE empty (the default), the lookup was
        previously gated on the secret reference, so load_secret_with_fallback
        was never called and Environment auth was skipped entirely.
        """
        main_module = self._import_main_module()

        mock_console = MagicMock()
        mock_console.input.return_value = ""
        mock_api_client_cls = MagicMock()
        mock_extractor_cls = MagicMock()

        with (
            patch.dict(
                main_module.os.environ, {"OP_ENVIRONMENT_ID": "envid"}, clear=True
            ),
            patch.object(main_module, "CLICKUP_API_SECRET_REFERENCE", ""),
            patch.object(main_module, "console", mock_console),
            patch.object(main_module, "get_yes_no_input", return_value=False),
            patch.object(main_module, "get_choice_input", return_value="Markdown"),
            patch.object(
                main_module, "load_secret_with_fallback", return_value="env-key"
            ) as mock_load_secret,
            patch.object(
                main_module,
                "_load_runtime_dependencies",
                return_value=(mock_api_client_cls, mock_extractor_cls),
            ),
        ):
            extractor_instance = mock_extractor_cls.return_value
            extractor_instance.run = MagicMock()

            argv = [
                str(Path(__file__).resolve().parents[1] / "main.py"),
                "--workspace",
                "WS",
            ]
            self._run_main_with_args(main_module, argv)

        # The Environment lookup is keyed on OP_ENVIRONMENT_ID and needs no
        # op:// reference, so it must be attempted with an empty reference.
        mock_load_secret.assert_called_once_with("", "ClickUp API key")
        # Key resolved from the Environment — no manual prompt, key flows through.
        mock_console.input.assert_not_called()
        mock_api_client_cls.assert_called_once_with("env-key")

    def test_no_op_lookup_when_no_reference_and_no_environment(self) -> None:
        """Without a reference or OP_ENVIRONMENT_ID, skip 1Password and prompt."""
        main_module = self._import_main_module()

        mock_console = MagicMock()
        mock_console.input.return_value = "typed-key"
        mock_api_client_cls = MagicMock()
        mock_extractor_cls = MagicMock()

        with (
            patch.dict(main_module.os.environ, {}, clear=True),
            patch.object(main_module, "CLICKUP_API_SECRET_REFERENCE", ""),
            patch.object(main_module, "console", mock_console),
            patch.object(main_module, "get_yes_no_input", return_value=False),
            patch.object(main_module, "get_choice_input", return_value="Markdown"),
            patch.object(
                main_module, "load_secret_with_fallback", return_value=None
            ) as mock_load_secret,
            patch.object(
                main_module,
                "_load_runtime_dependencies",
                return_value=(mock_api_client_cls, mock_extractor_cls),
            ),
        ):
            extractor_instance = mock_extractor_cls.return_value
            extractor_instance.run = MagicMock()

            argv = [
                str(Path(__file__).resolve().parents[1] / "main.py"),
                "--workspace",
                "WS",
            ]
            self._run_main_with_args(main_module, argv)

        mock_load_secret.assert_not_called()
        mock_console.input.assert_called_once()
        mock_api_client_cls.assert_called_once_with("typed-key")


class OpRunReexecTests(unittest.TestCase):
    """Cover the op-run re-exec gating (issue #138).

    The 1Password Environments flag is beta-only; on a stable `op` CLI the
    re-exec must be skipped instead of crashing with "unknown flag".
    """

    def setUp(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        sys.modules.pop("main", None)
        mocked_executable = str(project_root / ".venv" / "Scripts" / "python.exe")
        with patch.object(sys, "executable", mocked_executable):
            self.main = importlib.import_module("main")

    # --- _op_run_environments_flag --------------------------------------

    def test_flag_probe_prefers_plural(self) -> None:
        proc = MagicMock(stdout="Flags:\n  --environments\n  --environment", stderr="")
        with patch.object(self.main.subprocess, "run", return_value=proc):
            self.assertEqual(self.main._op_run_environments_flag(), "--environments")

    def test_flag_probe_accepts_singular(self) -> None:
        proc = MagicMock(stdout="usage: op run --environment <id>", stderr="")
        with patch.object(self.main.subprocess, "run", return_value=proc):
            self.assertEqual(self.main._op_run_environments_flag(), "--environment")

    def test_flag_probe_returns_none_on_stable_cli(self) -> None:
        # Stable op 2.34.x: only --env-file / --no-masking, no Environments flag.
        proc = MagicMock(stdout="Flags:\n  --env-file\n  --no-masking", stderr="")
        with patch.object(self.main.subprocess, "run", return_value=proc):
            self.assertIsNone(self.main._op_run_environments_flag())

    def test_flag_probe_returns_none_when_op_missing(self) -> None:
        with patch.object(
            self.main.subprocess, "run", side_effect=FileNotFoundError("op")
        ):
            self.assertIsNone(self.main._op_run_environments_flag())

    # --- _reexec_under_op_run -------------------------------------------

    def test_reexec_skipped_when_flag_unsupported(self) -> None:
        """The fix for #138: no crash, no re-exec on a stable CLI."""
        with (
            patch.dict(self.main.os.environ, {"OP_ENVIRONMENT_ID": "envid"}, clear=True),
            patch("shutil.which", return_value="C:/op.exe"),
            patch.object(self.main, "_op_run_environments_flag", return_value=None),
            patch.object(self.main.subprocess, "call") as mock_call,
        ):
            # Must return normally — not raise SystemExit.
            self.main._reexec_under_op_run()
        mock_call.assert_not_called()

    def test_reexec_runs_with_detected_flag(self) -> None:
        with (
            patch.dict(self.main.os.environ, {"OP_ENVIRONMENT_ID": "envid"}, clear=True),
            patch.object(self.main.sys, "argv", ["main.py", "--workspace", "X"]),
            patch("shutil.which", return_value="C:/op.exe"),
            patch.object(
                self.main, "_op_run_environments_flag", return_value="--environments"
            ),
            patch.object(self.main.subprocess, "call", return_value=0) as mock_call,
        ):
            with self.assertRaises(SystemExit):
                self.main._reexec_under_op_run()
        cmd = mock_call.call_args.args[0]
        self.assertEqual(cmd[:4], ["op", "run", "--environments", "envid"])
        self.assertIn("--", cmd)

    def test_reexec_skipped_when_api_key_present(self) -> None:
        with (
            patch.dict(
                self.main.os.environ,
                {"OP_ENVIRONMENT_ID": "envid", "CLICKUP_API_KEY": "key"},
                clear=True,
            ),
            patch.object(self.main.subprocess, "call") as mock_call,
        ):
            self.main._reexec_under_op_run()
        mock_call.assert_not_called()

    def test_reexec_skipped_when_no_environment_id(self) -> None:
        with (
            patch.dict(self.main.os.environ, {}, clear=True),
            patch.object(self.main.subprocess, "call") as mock_call,
        ):
            self.main._reexec_under_op_run()
        mock_call.assert_not_called()


if __name__ == "__main__":  # pragma: no cover - manual execution safeguard
    unittest.main()
