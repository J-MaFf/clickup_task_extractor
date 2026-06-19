"""
Unit tests for kfj_task_extractor.

Covers task->record mapping, row normalization, tab naming, pagination and
closed-task filtering, and sorting integration with date-only ETAs. No
network or Google Sheets calls are made.
"""

import os
import unittest
from datetime import date
from unittest import mock

from config import sort_tasks_by_priority_and_eta
from kfj_task_extractor import (
    FALLBACK_BRANCH,
    HEADER,
    build_tab_name,
    fetch_open_tasks,
    load_google_credentials_json,
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

    def test_missing_due_date_gives_empty_eta(self):
        record = task_to_record(make_task(due_date=None), "KFI Jefferson")
        self.assertEqual(record.ETA, "")

    def test_invalid_due_date_gives_empty_eta(self):
        record = task_to_record(make_task(due_date="not-a-number"), "KFI Jefferson")
        self.assertEqual(record.ETA, "")

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


if __name__ == "__main__":
    unittest.main()
