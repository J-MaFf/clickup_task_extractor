"""
Unit tests for kfj_task_extractor.

Covers task->record mapping, row normalization, tab naming, pagination and
closed-task filtering, sorting integration with date-only ETAs, ETA
calculation for due-date-less tasks (baseline + AI pass), and the .env.kfj
loader. No network, Google Sheets, or Claude CLI calls are made.
"""

import os
import tempfile
import unittest
from datetime import date
from unittest import mock

from config import TaskRecord, sort_tasks_by_priority_and_eta
from kfj_task_extractor import (
    FALLBACK_BRANCH,
    HEADER,
    _env_flag,
    _eta_concurrency,
    _load_dotenv,
    apply_ai_etas,
    build_records,
    build_tab_name,
    fetch_open_tasks,
    load_google_credentials_json,
    parse_args,
    record_to_row,
    resolve_clickup_api_key,
    task_to_record,
)


class MockAPIClient:
    """Minimal APIClient returning canned responses keyed by endpoint."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[str] = []

    def get(self, endpoint: str):
        self.calls.append(endpoint)
        return self.responses[endpoint]


def make_task(**overrides) -> dict:
    """Build a raw task dict in the list-endpoint shape."""
    task = {
        "name": "Sample task",
        "status": {"status": "to do", "type": "open"},
        "priority": {"id": "3", "priority": "normal"},
        "due_date": None,
        "custom_fields": [],
    }
    task.update(overrides)
    return task


class TestTaskToRecord(unittest.TestCase):
    """Test suite for task_to_record mapping."""

    def test_basic_fields(self):
        record = task_to_record(make_task(name="Fix printer"), "KFI Jefferson")
        self.assertEqual(record.Task, "Fix printer")
        self.assertEqual(record.Company, "KFI Jefferson")
        self.assertEqual(record.Status, "to do")

    def test_priority_int_mapping(self):
        for val, label in [(1, "Low"), (2, "Normal"), (3, "High"), (4, "Urgent")]:
            record = task_to_record(
                make_task(priority={"priority": val}), "KFI Jefferson"
            )
            self.assertEqual(record.Priority, label)

    def test_priority_string_passthrough(self):
        record = task_to_record(
            make_task(priority={"priority": "high"}), "KFI Jefferson"
        )
        self.assertEqual(record.Priority, "high")

    def test_priority_missing_defaults_to_normal(self):
        record = task_to_record(make_task(priority=None), "KFI Jefferson")
        self.assertEqual(record.Priority, "Normal")

    def test_due_date_converts_to_date_only(self):
        # 2026-05-05 12:00:00 UTC in epoch milliseconds
        record = task_to_record(make_task(due_date="1777982400000"), "KFI Jefferson")
        self.assertEqual(record.ETA, "5/5/2026")

    def test_missing_due_date_gets_baseline_eta(self):
        with mock.patch(
            "kfj_task_extractor.calculate_eta", return_value="7/20/2026"
        ) as calc:
            record = task_to_record(make_task(due_date=None), "KFI Jefferson")
        self.assertEqual(record.ETA, "7/20/2026")
        calc.assert_called_once()
        self.assertIn("eta_inputs", record._metadata)

    def test_invalid_due_date_gets_baseline_eta(self):
        with mock.patch(
            "kfj_task_extractor.calculate_eta", return_value="7/20/2026"
        ):
            record = task_to_record(
                make_task(due_date="not-a-number"), "KFI Jefferson"
            )
        self.assertEqual(record.ETA, "7/20/2026")
        self.assertIn("eta_inputs", record._metadata)

    def test_branch_dropdown_resolved_by_option_id(self):
        branch_field = {
            "name": "Branch",
            "value": "opt-123",
            "type_config": {
                "options": [
                    {"id": "opt-123", "name": "KFJ (213)", "orderindex": 0},
                    {"id": "opt-456", "name": "KFW (101)", "orderindex": 1},
                ]
            },
        }
        record = task_to_record(
            make_task(custom_fields=[branch_field]), "KFI Jefferson"
        )
        self.assertEqual(record.Branch, "KFJ (213)")

    def test_branch_missing_uses_fallback(self):
        record = task_to_record(make_task(custom_fields=[]), "KFI Jefferson")
        self.assertEqual(record.Branch, FALLBACK_BRANCH)

    def test_branch_with_null_value_uses_fallback(self):
        branch_field = {"name": "Branch", "value": None, "type_config": {}}
        record = task_to_record(
            make_task(custom_fields=[branch_field]), "KFI Jefferson"
        )
        self.assertEqual(record.Branch, FALLBACK_BRANCH)


class TestRecordToRow(unittest.TestCase):
    """Test suite for record_to_row normalization."""

    def test_lowercases_priority_and_status(self):
        record = task_to_record(
            make_task(
                priority={"priority": 3},
                status={"status": "Investigating", "type": "custom"},
            ),
            "KFI Jefferson",
        )
        row = record_to_row(record)
        self.assertEqual(row[3], "high")
        self.assertEqual(row[4], "investigating")

    def test_column_order_matches_header(self):
        record = task_to_record(
            make_task(name="Task A", due_date="1777982400000"), "KFI Jefferson"
        )
        row = record_to_row(record)
        self.assertEqual(len(row), len(HEADER))
        self.assertEqual(row[0], "Task A")  # Task
        self.assertEqual(row[1], "KFI Jefferson")  # Company
        self.assertEqual(row[2], FALLBACK_BRANCH)  # Branch
        self.assertEqual(row[5], "5/5/2026")  # ETA


class TestBuildTabName(unittest.TestCase):
    """Test suite for tab name generation."""

    def test_standard_date(self):
        self.assertEqual(
            build_tab_name(date(2026, 6, 10)),
            "KFI Jefferson current tasks (6/10/26)",
        )

    def test_no_leading_zeros(self):
        self.assertEqual(
            build_tab_name(date(2026, 4, 5)),
            "KFI Jefferson current tasks (4/5/26)",
        )

    def test_two_digit_year(self):
        self.assertEqual(
            build_tab_name(date(2030, 12, 25)),
            "KFI Jefferson current tasks (12/25/30)",
        )


class TestFetchOpenTasks(unittest.TestCase):
    """Test suite for fetch_open_tasks pagination and filtering."""

    LIST_ID = "901413205844"

    def _endpoint(self, page: int) -> str:
        return f"/list/{self.LIST_ID}/task?archived=false&subtasks=true&page={page}"

    def test_single_page(self):
        client = MockAPIClient(
            {
                self._endpoint(0): {
                    "tasks": [make_task(name="A"), make_task(name="B")],
                    "last_page": True,
                }
            }
        )
        tasks = fetch_open_tasks(client, self.LIST_ID)
        self.assertEqual([t["name"] for t in tasks], ["A", "B"])
        self.assertEqual(len(client.calls), 1)

    def test_pagination_terminates(self):
        client = MockAPIClient(
            {
                self._endpoint(0): {
                    "tasks": [make_task(name="A")],
                    "last_page": False,
                },
                self._endpoint(1): {
                    "tasks": [make_task(name="B")],
                    "last_page": True,
                },
            }
        )
        tasks = fetch_open_tasks(client, self.LIST_ID)
        self.assertEqual([t["name"] for t in tasks], ["A", "B"])
        self.assertEqual(len(client.calls), 2)

    def test_empty_page_terminates(self):
        client = MockAPIClient(
            {self._endpoint(0): {"tasks": [], "last_page": False}}
        )
        tasks = fetch_open_tasks(client, self.LIST_ID)
        self.assertEqual(tasks, [])

    def test_closed_tasks_filtered(self):
        client = MockAPIClient(
            {
                self._endpoint(0): {
                    "tasks": [
                        make_task(name="Open task"),
                        make_task(
                            name="Closed task",
                            status={"status": "complete", "type": "closed"},
                        ),
                    ],
                    "last_page": True,
                }
            }
        )
        tasks = fetch_open_tasks(client, self.LIST_ID)
        self.assertEqual([t["name"] for t in tasks], ["Open task"])


class TestSortingIntegration(unittest.TestCase):
    """Date-only ETAs sort correctly through the shared sorter."""

    def test_priority_then_eta(self):
        # The baseline calculation is stubbed to "" so the no-due-date record
        # keeps exercising the sorter's missing-ETA branch deterministically.
        with mock.patch("kfj_task_extractor.calculate_eta", return_value=""):
            records = [
                task_to_record(
                    make_task(
                        name="Normal later",
                        priority={"priority": 2},
                        due_date="1778414400000",  # 5/10/2026
                    ),
                    "KFI Jefferson",
                ),
                task_to_record(
                    make_task(
                        name="High",
                        priority={"priority": 3},
                        due_date="1777982400000",  # 5/5/2026
                    ),
                    "KFI Jefferson",
                ),
                task_to_record(
                    make_task(
                        name="Normal sooner",
                        priority={"priority": 2},
                        due_date="1777982400000",  # 5/5/2026
                    ),
                    "KFI Jefferson",
                ),
                task_to_record(
                    make_task(name="Normal no ETA", priority={"priority": 2}),
                    "KFI Jefferson",
                ),
            ]
        sorted_records = sort_tasks_by_priority_and_eta(records)
        self.assertEqual(
            [r.Task for r in sorted_records],
            ["High", "Normal sooner", "Normal later", "Normal no ETA"],
        )


def _record_with_eta_inputs(name: str, eta: str = "7/20/2026") -> TaskRecord:
    """Build a record carrying eta_inputs metadata, like a due-date-less task."""
    record = TaskRecord(
        Task=name,
        Company="KFI Jefferson",
        Branch="",
        Priority="Normal",
        Status="to do",
        ETA=eta,
    )
    record._metadata["eta_inputs"] = {
        "task_name": name,
        "priority": "Normal",
        "status": "to do",
        "description": "",
        "subject": "",
        "resolution": "",
    }
    return record


class TestEtaInputs(unittest.TestCase):
    """eta_inputs metadata carries the right AI context (issue #165)."""

    def test_due_date_task_has_no_eta_inputs(self):
        record = task_to_record(
            make_task(due_date="1777982400000"), "KFI Jefferson"
        )
        self.assertNotIn("eta_inputs", record._metadata)

    def test_eta_inputs_content_and_baseline_call(self):
        fields = [
            {"name": "Subject", "value": "Printer offline"},
            {"name": "Description", "value": "Custom description"},
            {"name": "Resolution", "value": "Pending parts"},
        ]
        with mock.patch(
            "kfj_task_extractor.calculate_eta", return_value="7/20/2026"
        ) as calc:
            record = task_to_record(
                make_task(
                    name="Fix printer",
                    priority={"priority": "high"},
                    status={"status": "in progress", "type": "custom"},
                    custom_fields=fields,
                    description="Native description",
                ),
                "KFI Jefferson",
            )
        inputs = record._metadata["eta_inputs"]
        self.assertEqual(inputs["task_name"], "Fix printer")
        # Capitalized to match eta_calculator.PRIORITY_ETA_DAYS keys.
        self.assertEqual(inputs["priority"], "High")
        self.assertEqual(inputs["status"], "in progress")
        self.assertEqual(inputs["description"], "Custom description")
        self.assertEqual(inputs["subject"], "Printer offline")
        self.assertEqual(inputs["resolution"], "Pending parts")
        calc.assert_called_once_with(**inputs, enable_ai=False)

    def test_description_falls_back_to_native_description(self):
        with mock.patch("kfj_task_extractor.calculate_eta", return_value="x"):
            record = task_to_record(
                make_task(description="Native description"), "KFI Jefferson"
            )
        self.assertEqual(
            record._metadata["eta_inputs"]["description"], "Native description"
        )

    def test_unmocked_baseline_is_a_date(self):
        # The real deterministic fallback must produce M/D/YYYY, never blank.
        record = task_to_record(make_task(due_date=None), "KFI Jefferson")
        self.assertRegex(record.ETA, r"^\d{1,2}/\d{1,2}/\d{4}$")


class TestApplyAiEtas(unittest.TestCase):
    """The concurrent AI ETA pass (apply_ai_etas) and its pre-flight."""

    def _cli_ready(self):
        return (
            mock.patch(
                "kfj_task_extractor.claude_cli_available", return_value=True
            ),
            mock.patch(
                "kfj_task_extractor.claude_cli_authenticated", return_value=True
            ),
        )

    def test_upgrades_candidates_and_skips_due_date_records(self):
        candidate = _record_with_eta_inputs("A")
        with_due = TaskRecord(
            Task="B",
            Company="KFI Jefferson",
            Branch="",
            Priority="Normal",
            Status="to do",
            ETA="5/5/2026",
        )
        available, authenticated = self._cli_ready()
        with (
            available,
            authenticated,
            mock.patch(
                "kfj_task_extractor.calculate_eta_with_source",
                return_value=("12/25/2026", True),
            ) as calc,
        ):
            apply_ai_etas([candidate, with_due])
        self.assertEqual(candidate.ETA, "12/25/2026")
        self.assertEqual(with_due.ETA, "5/5/2026")
        calc.assert_called_once_with(
            **candidate._metadata["eta_inputs"], enable_ai=True
        )

    def test_no_candidates_skips_preflight(self):
        with_due = TaskRecord(
            Task="B",
            Company="KFI Jefferson",
            Branch="",
            Priority="Normal",
            Status="to do",
            ETA="5/5/2026",
        )
        with mock.patch("kfj_task_extractor.claude_cli_available") as available:
            apply_ai_etas([with_due])
        available.assert_not_called()

    def test_cli_missing_keeps_baselines(self):
        candidate = _record_with_eta_inputs("A")
        with (
            mock.patch(
                "kfj_task_extractor.claude_cli_available", return_value=False
            ),
            mock.patch("kfj_task_extractor.calculate_eta_with_source") as calc,
        ):
            apply_ai_etas([candidate])
        self.assertEqual(candidate.ETA, "7/20/2026")
        calc.assert_not_called()

    def test_logged_out_marks_unavailable_and_keeps_baselines(self):
        candidate = _record_with_eta_inputs("A")
        with (
            mock.patch(
                "kfj_task_extractor.claude_cli_available", return_value=True
            ),
            mock.patch(
                "kfj_task_extractor.claude_cli_authenticated", return_value=False
            ),
            mock.patch("kfj_task_extractor.mark_claude_unavailable") as marker,
            mock.patch("kfj_task_extractor.calculate_eta_with_source") as calc,
        ):
            apply_ai_etas([candidate])
        marker.assert_called_once()
        calc.assert_not_called()
        self.assertEqual(candidate.ETA, "7/20/2026")

    def test_unknown_auth_state_proceeds(self):
        # claude_cli_authenticated() -> None means "unknown" and must not skip.
        candidate = _record_with_eta_inputs("A")
        with (
            mock.patch(
                "kfj_task_extractor.claude_cli_available", return_value=True
            ),
            mock.patch(
                "kfj_task_extractor.claude_cli_authenticated", return_value=None
            ),
            mock.patch(
                "kfj_task_extractor.calculate_eta_with_source",
                return_value=("12/25/2026", True),
            ),
        ):
            apply_ai_etas([candidate])
        self.assertEqual(candidate.ETA, "12/25/2026")

    def test_exception_keeps_baseline_for_that_record_only(self):
        rec_ok = _record_with_eta_inputs("OK")
        rec_bad = _record_with_eta_inputs("BAD")

        def side_effect(**kwargs):
            if kwargs["task_name"] == "BAD":
                raise RuntimeError("boom")
            return ("12/25/2026", True)

        available, authenticated = self._cli_ready()
        with (
            available,
            authenticated,
            mock.patch(
                "kfj_task_extractor.calculate_eta_with_source",
                side_effect=side_effect,
            ),
        ):
            apply_ai_etas([rec_ok, rec_bad])
        self.assertEqual(rec_ok.ETA, "12/25/2026")
        self.assertEqual(rec_bad.ETA, "7/20/2026")

    def test_deterministic_result_still_applied(self):
        # (eta, used_ai=False) — the in-call deterministic fallback is applied.
        candidate = _record_with_eta_inputs("A")
        available, authenticated = self._cli_ready()
        with (
            available,
            authenticated,
            mock.patch(
                "kfj_task_extractor.calculate_eta_with_source",
                return_value=("8/1/2026", False),
            ),
        ):
            apply_ai_etas([candidate])
        self.assertEqual(candidate.ETA, "8/1/2026")


class TestEnvFlagAndArgs(unittest.TestCase):
    """KFJ_AI_ETA parsing and the --no-ai-eta flag default wiring."""

    def test_env_flag_falsy_values(self):
        for value in ("0", "false", "False", "NO", " off "):
            with mock.patch.dict(os.environ, {"KFJ_AI_ETA": value}):
                self.assertFalse(_env_flag("KFJ_AI_ETA"), value)

    def test_env_flag_truthy_values(self):
        for value in ("1", "true", "yes", "on", "anything"):
            with mock.patch.dict(os.environ, {"KFJ_AI_ETA": value}):
                self.assertTrue(_env_flag("KFJ_AI_ETA"), value)

    def test_env_flag_unset_uses_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(_env_flag("KFJ_AI_ETA"))
            self.assertFalse(_env_flag("KFJ_AI_ETA", default="0"))

    def test_no_ai_eta_flag_parses(self):
        # parse_args reads the module global at call time, so patching
        # AI_ETA_DEFAULT exercises both defaults regardless of the ambient env.
        with mock.patch("kfj_task_extractor.AI_ETA_DEFAULT", True):
            self.assertFalse(parse_args([]).no_ai_eta)
            self.assertTrue(parse_args(["--no-ai-eta"]).no_ai_eta)

    def test_kfj_ai_eta_env_default_disables_ai(self):
        with mock.patch("kfj_task_extractor.AI_ETA_DEFAULT", False):
            self.assertTrue(parse_args([]).no_ai_eta)


class TestBuildRecords(unittest.TestCase):
    """build_records composition: AI pass gated by ai_eta and run pre-sort."""

    def test_ai_disabled_skips_ai_pass(self):
        with (
            mock.patch("kfj_task_extractor.apply_ai_etas") as ai_pass,
            mock.patch("kfj_task_extractor.calculate_eta", return_value=""),
        ):
            build_records([make_task()], "KFI Jefferson", ai_eta=False)
        ai_pass.assert_not_called()

    def test_ai_enabled_runs_ai_pass(self):
        with (
            mock.patch("kfj_task_extractor.apply_ai_etas") as ai_pass,
            mock.patch("kfj_task_extractor.calculate_eta", return_value=""),
        ):
            build_records([make_task()], "KFI Jefferson", ai_eta=True)
        ai_pass.assert_called_once()

    def test_ai_etas_applied_before_sorting(self):
        # Two same-priority tasks without due dates share an identical
        # baseline; the AI dates invert their input order, so the sorted
        # output proves the AI pass ran before the sorter.
        ai_dates = {"Task early": "8/1/2026", "Task late": "9/1/2026"}

        def fake_source(**kwargs):
            return (ai_dates[kwargs["task_name"]], True)

        with (
            mock.patch(
                "kfj_task_extractor.calculate_eta", return_value="7/20/2026"
            ),
            mock.patch(
                "kfj_task_extractor.claude_cli_available", return_value=True
            ),
            mock.patch(
                "kfj_task_extractor.claude_cli_authenticated", return_value=True
            ),
            mock.patch(
                "kfj_task_extractor.calculate_eta_with_source",
                side_effect=fake_source,
            ),
        ):
            records = build_records(
                [make_task(name="Task late"), make_task(name="Task early")],
                "KFI Jefferson",
                ai_eta=True,
            )
        self.assertEqual([r.Task for r in records], ["Task early", "Task late"])
        self.assertEqual([r.ETA for r in records], ["8/1/2026", "9/1/2026"])


class TestEtaConcurrency(unittest.TestCase):
    """Worker-count resolution for the AI ETA pass."""

    def test_default_clamped_to_task_count(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_eta_concurrency(2), 2)
            self.assertEqual(_eta_concurrency(10), 4)

    def test_env_override(self):
        with mock.patch.dict(os.environ, {"AI_SUMMARY_CONCURRENCY": "8"}):
            self.assertEqual(_eta_concurrency(10), 8)

    def test_invalid_env_uses_default(self):
        with mock.patch.dict(os.environ, {"AI_SUMMARY_CONCURRENCY": "lots"}):
            self.assertEqual(_eta_concurrency(10), 4)

    def test_minimum_one_worker(self):
        with mock.patch.dict(os.environ, {"AI_SUMMARY_CONCURRENCY": "0"}):
            self.assertEqual(_eta_concurrency(10), 1)


class TestCredentialResolution(unittest.TestCase):
    """Secrets resolve in order: env var -> desktop SDK -> fallback chain."""

    def test_clickup_key_env_var_wins(self):
        with mock.patch.dict(os.environ, {"CLICKUP_API_KEY": "pk_from_env"}):
            with mock.patch(
                "kfj_task_extractor.resolve_secret_with_desktop_sdk"
            ) as sdk:
                self.assertEqual(resolve_clickup_api_key(), "pk_from_env")
                sdk.assert_not_called()

    def test_clickup_key_sdk_before_fallback(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with (
                mock.patch(
                    "kfj_task_extractor.CLICKUP_SECRET_REFERENCE",
                    "op://vault/item/credential",
                ),
                mock.patch(
                    "kfj_task_extractor.resolve_secret_with_desktop_sdk",
                    return_value="pk_from_sdk",
                ) as sdk,
                mock.patch(
                    "kfj_task_extractor.load_secret_with_fallback"
                ) as fallback,
            ):
                self.assertEqual(resolve_clickup_api_key(), "pk_from_sdk")
                sdk.assert_called_once()
                fallback.assert_not_called()

    def test_clickup_key_falls_back_when_sdk_fails(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with (
                mock.patch(
                    "kfj_task_extractor.CLICKUP_SECRET_REFERENCE",
                    "op://vault/item/credential",
                ),
                mock.patch(
                    "kfj_task_extractor.resolve_secret_with_desktop_sdk",
                    return_value=None,
                ),
                mock.patch(
                    "kfj_task_extractor.load_secret_with_fallback",
                    return_value="pk_from_cli",
                ) as fallback,
            ):
                self.assertEqual(resolve_clickup_api_key(), "pk_from_cli")
                fallback.assert_called_once()

    def test_google_creds_env_var_wins(self):
        with mock.patch.dict(
            os.environ, {"GOOGLE_SHEETS_CREDENTIALS_JSON": '{"a": 1}'}
        ):
            with mock.patch(
                "kfj_task_extractor.resolve_secret_with_desktop_sdk"
            ) as sdk:
                self.assertEqual(load_google_credentials_json(), '{"a": 1}')
                sdk.assert_not_called()

    def test_google_creds_sdk_before_fallback(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with (
                mock.patch(
                    "kfj_task_extractor.GOOGLE_SA_SECRET_REFERENCE",
                    "op://vault/item/credential",
                ),
                mock.patch(
                    "kfj_task_extractor.resolve_secret_with_desktop_sdk",
                    return_value='{"type": "service_account"}',
                ) as sdk,
                mock.patch(
                    "kfj_task_extractor.load_secret_with_fallback"
                ) as fallback,
            ):
                self.assertEqual(
                    load_google_credentials_json(), '{"type": "service_account"}'
                )
                sdk.assert_called_once()
                fallback.assert_not_called()

    def test_google_creds_all_sources_fail(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with (
                mock.patch(
                    "kfj_task_extractor.GOOGLE_SA_SECRET_REFERENCE",
                    "op://vault/item/credential",
                ),
                mock.patch(
                    "kfj_task_extractor.resolve_secret_with_desktop_sdk",
                    return_value=None,
                ),
                mock.patch(
                    "kfj_task_extractor.load_secret_with_fallback",
                    return_value=None,
                ),
                mock.patch(
                    "kfj_task_extractor.read_secret_via_op_cli",
                    return_value=None,
                ) as op_cli,
            ):
                self.assertIsNone(load_google_credentials_json())
                op_cli.assert_called_once()

    def test_clickup_key_skips_1password_when_reference_unset(self):
        """With no env var and an empty secret reference, the 1Password chain is
        skipped and resolution returns None (issue #110)."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with (
                mock.patch("kfj_task_extractor.CLICKUP_SECRET_REFERENCE", ""),
                mock.patch(
                    "kfj_task_extractor.resolve_secret_with_desktop_sdk",
                    return_value="should_not_be_used",
                ) as sdk,
                mock.patch(
                    "kfj_task_extractor.load_secret_with_fallback",
                    return_value="should_not_be_used",
                ) as fallback,
            ):
                self.assertIsNone(resolve_clickup_api_key())
                sdk.assert_not_called()
                fallback.assert_not_called()


class LoadDotenvTests(unittest.TestCase):
    """Test suite for the .env.kfj loader (_load_dotenv)."""

    def _write_env(self, contents: str) -> str:
        """Write contents to a temp .env file and return its path."""
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".env.kfj", delete=False, encoding="utf-8"
        )
        handle.write(contents)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_loads_plain_config_vars(self):
        path = self._write_env(
            "KFJ_CLICKUP_LIST_ID=12345\n"
            "# a comment\n"
            "\n"
            "export KFJ_GOOGLE_SHEET_ID=abcDEF\n"
            'KFJ_TAB_PREFIX="My Tasks"\n'
            "KFJ_FALLBACK_BRANCH='HQ'\n"
        )
        with mock.patch.dict(os.environ, {}, clear=True):
            _load_dotenv(path)
            self.assertEqual(os.environ["KFJ_CLICKUP_LIST_ID"], "12345")
            self.assertEqual(os.environ["KFJ_GOOGLE_SHEET_ID"], "abcDEF")
            self.assertEqual(os.environ["KFJ_TAB_PREFIX"], "My Tasks")
            self.assertEqual(os.environ["KFJ_FALLBACK_BRANCH"], "HQ")

    def test_does_not_override_existing_env(self):
        path = self._write_env("KFJ_CLICKUP_LIST_ID=from_file\n")
        with mock.patch.dict(
            os.environ, {"KFJ_CLICKUP_LIST_ID": "from_env"}, clear=True
        ):
            _load_dotenv(path)
            self.assertEqual(os.environ["KFJ_CLICKUP_LIST_ID"], "from_env")

    def test_skips_op_reference_for_secret_material_keys(self):
        path = self._write_env(
            "CLICKUP_API_KEY=op://vault/item/credential\n"
            "GOOGLE_SHEETS_CREDENTIALS_JSON=op://vault/sa/credential\n"
        )
        with mock.patch.dict(os.environ, {}, clear=True):
            _load_dotenv(path)
            # Left unset so op run / the 1Password resolver chain handles them.
            self.assertNotIn("CLICKUP_API_KEY", os.environ)
            self.assertNotIn("GOOGLE_SHEETS_CREDENTIALS_JSON", os.environ)

    def test_loads_literal_secret_material_value(self):
        # A non-op:// literal secret is loaded (matches .env.kfj.example option).
        path = self._write_env("CLICKUP_API_KEY=pk_literal_123\n")
        with mock.patch.dict(os.environ, {}, clear=True):
            _load_dotenv(path)
            self.assertEqual(os.environ["CLICKUP_API_KEY"], "pk_literal_123")

    def test_loads_op_reference_for_reference_pointer_keys(self):
        # *_SECRET_REFERENCE values are *meant* to be op:// URIs the resolver reads.
        path = self._write_env(
            "KFJ_CLICKUP_SECRET_REFERENCE=op://vault/item/credential\n"
        )
        with mock.patch.dict(os.environ, {}, clear=True):
            _load_dotenv(path)
            self.assertEqual(
                os.environ["KFJ_CLICKUP_SECRET_REFERENCE"],
                "op://vault/item/credential",
            )

    def test_skips_empty_and_malformed_lines(self):
        path = self._write_env(
            "KFJ_CLICKUP_LIST_ID=\n"  # empty value -> skipped
            "no_equals_sign\n"  # malformed -> skipped
            "KFJ_GOOGLE_SHEET_ID=ok\n"
        )
        with mock.patch.dict(os.environ, {}, clear=True):
            _load_dotenv(path)
            self.assertNotIn("KFJ_CLICKUP_LIST_ID", os.environ)
            self.assertEqual(os.environ["KFJ_GOOGLE_SHEET_ID"], "ok")

    def test_missing_file_is_noop(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            _load_dotenv(os.path.join(tempfile.gettempdir(), "does-not-exist.env.kfj"))
            self.assertEqual(dict(os.environ), {})


if __name__ == "__main__":
    unittest.main()
