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

        with patch.object(main_module, "console", mock_console), \
            patch.object(main_module, "get_yes_no_input", return_value=False) as mock_yes_no, \
            patch.object(main_module, "load_secret_with_fallback") as mock_load_secret, \
            patch.object(main_module, "ClickUpTaskExtractor") as mock_extractor_cls, \
            patch.object(main_module, "ClickUpAPIClient") as mock_api_client_cls:

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
                "--output",
                "output/custom.csv",
                "--include-completed",
                "--date-filter",
                "LastWeek",
                "--ai-summary",
                "--gemini-api-key",
                "gem-key",
                "--output-format",
                "Both",
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
        self.assertEqual(config_arg.output_path, "output/custom.csv")
        self.assertTrue(config_arg.include_completed)
        self.assertEqual(config_arg.date_filter, DateFilter.LAST_WEEK)
        self.assertTrue(config_arg.enable_ai_summary)
        self.assertEqual(config_arg.gemini_api_key, "gem-key")
        self.assertEqual(config_arg.output_format, OutputFormat.BOTH)
        self.assertTrue(config_arg.interactive_selection)

        load_func = mock_extractor_cls.call_args.args[2]
        self.assertTrue(callable(load_func))


if __name__ == "__main__":  # pragma: no cover - manual execution safeguard
    unittest.main()