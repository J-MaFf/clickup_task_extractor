"""Tests for resolving API keys through the op-secret service-account wrapper."""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from auth import load_secret_via_op_secret


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.stdout = stdout
    proc.stderr = stderr
    proc.returncode = returncode
    return proc


class TestLoadSecretViaOpSecret(unittest.TestCase):
    def setUp(self) -> None:
        env = patch.dict(
            "os.environ",
            {"CLICKUP_API_OP_SECRET_NAME": "", "GEMINI_API_OP_SECRET_NAME": ""},
        )
        env.start()
        self.addCleanup(env.stop)

    def test_resolves_default_logical_name(self) -> None:
        with patch("auth.shutil.which", return_value="C:/bin/op-secret.cmd"), patch(
            "auth.subprocess.run", return_value=_completed(stdout="pk_secret\n")
        ) as mock_run:
            self.assertEqual(load_secret_via_op_secret("ClickUp API key"), "pk_secret")
        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd, ["C:/bin/op-secret.cmd", "clickup-api-key"])
        self.assertTrue(mock_run.call_args.kwargs["capture_output"])

    def test_gemini_default_logical_name(self) -> None:
        with patch("auth.shutil.which", return_value="op-secret"), patch(
            "auth.subprocess.run", return_value=_completed(stdout="g-key")
        ) as mock_run:
            self.assertEqual(load_secret_via_op_secret("Gemini API key"), "g-key")
        self.assertEqual(mock_run.call_args.args[0][1], "gemini-api-key")

    def test_env_overrides_logical_name(self) -> None:
        with patch.dict(
            "os.environ", {"CLICKUP_API_OP_SECRET_NAME": "clickup-work-key"}
        ), patch("auth.shutil.which", return_value="op-secret"), patch(
            "auth.subprocess.run", return_value=_completed(stdout="k")
        ) as mock_run:
            load_secret_via_op_secret("ClickUp API key")
        self.assertEqual(mock_run.call_args.args[0][1], "clickup-work-key")

    def test_missing_wrapper_returns_none_without_running(self) -> None:
        with patch("auth.shutil.which", return_value=None), patch(
            "auth.subprocess.run"
        ) as mock_run:
            self.assertIsNone(load_secret_via_op_secret("ClickUp API key"))
        mock_run.assert_not_called()

    def test_unknown_name_returns_none(self) -> None:
        with patch("auth.shutil.which", return_value="op-secret"), patch(
            "auth.subprocess.run",
            return_value=_completed(
                stderr="op-secret: unknown secret 'clickup-api-key'", returncode=1
            ),
        ):
            self.assertIsNone(load_secret_via_op_secret("ClickUp API key"))

    def test_empty_output_returns_none(self) -> None:
        with patch("auth.shutil.which", return_value="op-secret"), patch(
            "auth.subprocess.run", return_value=_completed(stdout="  \n")
        ):
            self.assertIsNone(load_secret_via_op_secret("ClickUp API key"))

    def test_timeout_returns_none(self) -> None:
        with patch("auth.shutil.which", return_value="op-secret"), patch(
            "auth.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="op-secret", timeout=30),
        ):
            self.assertIsNone(load_secret_via_op_secret("ClickUp API key"))

    def test_unsafe_logical_name_rejected(self) -> None:
        """op-secret is a .cmd shim on Windows; never hand cmd.exe metacharacters."""
        with patch.dict(
            "os.environ", {"CLICKUP_API_OP_SECRET_NAME": "x & calc"}
        ), patch("auth.shutil.which", return_value="op-secret"), patch(
            "auth.subprocess.run"
        ) as mock_run:
            self.assertIsNone(load_secret_via_op_secret("ClickUp API key"))
        mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
