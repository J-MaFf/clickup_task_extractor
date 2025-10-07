import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from config import ClickUpConfig, OutputFormat, TaskRecord, sort_tasks_by_priority_and_name
from extractor import ClickUpTaskExtractor, get_export_fields


class DummyAPIClient:
    """Simple API client stub that returns pre-seeded responses."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self._responses = responses

    def get(self, endpoint: str) -> Any:  # noqa: D401 - matches protocol signature
        return self._responses[endpoint]


class DummyProgress:
    """Minimal Progress replacement used to bypass Rich dependency in tests."""

    def __init__(self, *args, **kwargs) -> None:
        self._next_id = 0

    def __enter__(self) -> "DummyProgress":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def add_task(self, *args, **kwargs) -> int:
        self._next_id += 1
        return self._next_id

    def remove_task(self, task_id) -> None:
        return None

    def update(self, task_id, **kwargs) -> None:
        return None

    def advance(self, task_id, advance: int = 1) -> None:
        return None


class DummySpinnerColumn:
    def __init__(self, *args, **kwargs) -> None:
        pass


class DummyTextColumn:
    def __init__(self, *args, **kwargs) -> None:
        pass


class DummyBarColumn:
    def __init__(self, *args, **kwargs) -> None:
        pass


class DummyTaskProgressColumn:
    def __init__(self, *args, **kwargs) -> None:
        pass


class ClickUpTaskExtractorProcessTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task_id = "task_123"
        self.task_detail = {
            "name": "Detailed Task",
            "priority": {"priority": 3},
            "status": {"status": "In Progress"},
            "description": "Default description body",
            "custom_fields": [
                {"name": "Branch", "value": "HQ", "type_config": {}, "options": []},
                {"name": "Subject", "value": "Printer outage"},
                {"name": "Description", "value": "Detailed troubleshooting steps"},
                {"name": "Resolution", "value": "Rebooted printer"},
                {"name": "Last time tracked", "value": "2025-10-07"},
                {"name": "Serial Number(s)", "value": ["SN123", "SN456"]},
                {"name": "Tracking #", "value": "TRK-001"},
                {"name": "RMA Number", "value": None},
                {"name": "Computer #", "value": "PC-15"},
                {"name": "Phone #", "value": None},
                {"name": "Name", "value": "Custom Task Name"},
            ],
        }
        responses = {f"/task/{self.task_id}": self.task_detail}
        self.api_client = DummyAPIClient(responses)
        self.config = ClickUpConfig(api_key="dummy", output_path="output/test.csv")
        self.extractor = ClickUpTaskExtractor(self.config, self.api_client)

    def test_get_export_fields_excludes_metadata(self) -> None:
        fields = get_export_fields()
        self.assertIn("Task", fields)
        self.assertNotIn("_metadata", fields)

    def test_process_task_without_ai_summary(self) -> None:
        task = {"id": self.task_id, "name": "Printer outage"}
        list_item = {"name": "Support"}

        record = self.extractor._process_task(task, [], list_item)

        self.assertIsNotNone(record)
        self.assertIsInstance(record, TaskRecord)
        record = cast(TaskRecord, record)
        self.assertEqual(record.Task, "Detailed Task")
        self.assertEqual(record.Company, "Support")
        self.assertEqual(record.Branch, "HQ")
        self.assertEqual(record.Priority, "High")
        self.assertEqual(record.Status, "In Progress")
        self.assertEqual(
            record.Notes,
            "Subject: Printer outage\nDescription: Detailed troubleshooting steps\nResolution: Rebooted printer",
        )
        self.assertEqual(record.Extra, "")

        metadata = record._metadata
        self.assertEqual(metadata["task_name"], "Detailed Task")
        ai_fields = metadata["ai_fields"]
        self.assertEqual(len(ai_fields), 13)
        self.assertIn(("Vendor", "(not provided)"), ai_fields)
        self.assertIn(("Serial Number(s)", "SN123, SN456"), ai_fields)
        self.assertEqual(ai_fields[0], ("Name", "Custom Task Name"))
        self.assertEqual(ai_fields[-1], ("Task Description", "Default description body"))

    def test_process_task_with_ai_summary_enabled(self) -> None:
        self.config.enable_ai_summary = True
        self.config.gemini_api_key = "secret"
        task = {"id": self.task_id, "name": "Printer outage"}
        list_item = {"name": "Support"}

        with patch("ai_summary.get_ai_summary", return_value="AI summary text") as mock_get_summary:
            record = self.extractor._process_task(task, [], list_item)

        self.assertIsNotNone(record)
        self.assertIsInstance(record, TaskRecord)
        record = cast(TaskRecord, record)
        self.assertEqual(record.Notes, "AI summary text")
        mock_get_summary.assert_called_once()
        called_task_name, fields_arg, api_key = mock_get_summary.call_args[0]
        self.assertEqual(called_task_name, "Detailed Task")
        self.assertEqual(api_key, "secret")
        self.assertEqual(len(fields_arg), 13)
        self.assertEqual(fields_arg[0], ("Name", "Custom Task Name"))


class ExportBehaviourTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = TaskRecord(
            Task="Task A",
            Company="Support",
            Branch="HQ",
            Priority="High",
            Status="In Progress",
            ETA="",
            Notes="Sample notes",
            Extra="",
        )

    def test_csv_export_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "tasks.csv"
            config = ClickUpConfig(
                api_key="dummy",
                output_path=str(output_path),
                output_format=OutputFormat.CSV,
            )
            extractor = ClickUpTaskExtractor(config, DummyAPIClient({}))

            extractor.export([self.task])

            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("Task,Company,Branch,Priority,Status,ETA,Notes,Extra", content.splitlines()[0])
            self.assertIn("Task A", content)

    def test_html_export_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.csv"
            config = ClickUpConfig(
                api_key="dummy",
                output_path=str(output_path),
                output_format=OutputFormat.HTML,
            )
            extractor = ClickUpTaskExtractor(config, DummyAPIClient({}))

            extractor.export([self.task])

            html_path = output_path.with_suffix(".html")
            self.assertTrue(html_path.exists())
            html_content = html_path.read_text(encoding="utf-8")
            self.assertIn("Weekly Task List", html_content)


class FetchProcessTasksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.progress_patcher = patch("extractor.Progress", DummyProgress)
        self.spinner_patcher = patch("extractor.SpinnerColumn", DummySpinnerColumn)
        self.text_patcher = patch("extractor.TextColumn", DummyTextColumn)
        self.bar_patcher = patch("extractor.BarColumn", DummyBarColumn)
        self.task_prog_patcher = patch("extractor.TaskProgressColumn", DummyTaskProgressColumn)
        self.console_patcher = patch("extractor.console")

        self.progress_patcher.start()
        self.spinner_patcher.start()
        self.text_patcher.start()
        self.bar_patcher.start()
        self.task_prog_patcher.start()
        self.console_mock = self.console_patcher.start()

    def tearDown(self) -> None:
        self.progress_patcher.stop()
        self.spinner_patcher.stop()
        self.text_patcher.stop()
        self.bar_patcher.stop()
        self.task_prog_patcher.stop()
        self.console_patcher.stop()

    def test_fetch_and_process_tasks_exports_records(self) -> None:
        timestamp_ms = int(datetime(2025, 10, 7, 12, 0, 0).timestamp() * 1000)

        workspace_name = "KMS"
        space_name = "Kikkoman"

        responses: dict[str, Any] = {
            "/team": {"teams": [{"id": "team1", "name": workspace_name}]},
            "/team/team1/space": {"spaces": [{"id": "space1", "name": space_name}]},
            "/space/space1/folder": {"folders": []},
            "/space/space1/list?archived=false": {"lists": [{"id": "list1", "name": "Support"}]},
            "/list/list1/task?archived=false": {
                "tasks": [
                    {
                        "id": "task1",
                        "name": "Incident 1",
                        "archived": False,
                        "status": {"status": "open"},
                        "date_created": str(timestamp_ms),
                    }
                ]
            },
            "/list/list1": {"custom_fields": []},
            "/task/task1": {
                "name": "Incident 1 Detailed",
                "priority": {"priority": 3},
                "status": {"status": "In Progress"},
                "description": "Printer outage details",
                "custom_fields": [
                    {
                        "name": "Branch",
                        "value": "hq",
                        "type_config": {"options": [{"id": "hq", "name": "Headquarters"}]},
                        "options": [{"id": "hq", "name": "Headquarters"}],
                    },
                    {"name": "Subject", "value": "Printer outage"},
                    {"name": "Description", "value": "Investigated issue"},
                    {"name": "Resolution", "value": "Replaced toner"},
                ],
            },
        }

        class RecordingExtractor(ClickUpTaskExtractor):
            def __init__(self, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self.export_calls: list[list[TaskRecord]] = []

            def export(self, tasks: list[TaskRecord]) -> None:  # type: ignore[override]
                self.export_calls.append(tasks)

        with tempfile.TemporaryDirectory() as tmpdir:
            config = ClickUpConfig(
                api_key="dummy",
                output_path=str(Path(tmpdir) / "out.csv"),
            )
            api_client = DummyAPIClient(responses)
            extractor = RecordingExtractor(config, api_client)

            extractor._fetch_and_process_tasks()

            self.assertEqual(len(extractor.export_calls), 1)
            exported_tasks = extractor.export_calls[0]
            self.assertEqual(len(exported_tasks), 1)
            task_record = exported_tasks[0]
            self.assertIsInstance(task_record, TaskRecord)
            self.assertEqual(task_record.Task, "Incident 1 Detailed")
            self.assertEqual(task_record.Company, "Support")
            self.assertEqual(task_record.Branch, "Headquarters")
            self.assertEqual(task_record.Priority, "High")
            self.assertEqual(task_record.Status, "In Progress")
            self.assertIn("Subject: Printer outage", task_record.Notes)


class TaskExportSortingTests(unittest.TestCase):
    """Test that tasks are properly sorted during export."""

    def test_export_sorts_tasks_by_priority_then_name(self):
        """Test that export method sorts tasks before rendering."""
        # Create unsorted tasks
        tasks = [
            TaskRecord(Task="Zebra", Company="A", Branch="", Priority="High", Status="Open"),
            TaskRecord(Task="Alpha", Company="B", Branch="", Priority="Urgent", Status="Open"),
            TaskRecord(Task="Beta", Company="C", Branch="", Priority="Low", Status="Open"),
            TaskRecord(Task="Charlie", Company="D", Branch="", Priority="Normal", Status="Open"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            config = ClickUpConfig(
                api_key="test",
                output_path=str(Path(tmpdir) / "test.csv"),
                output_format=OutputFormat.CSV,
            )
            api_client = DummyAPIClient({})
            extractor = ClickUpTaskExtractor(config, api_client)

            # Mock progress to avoid Rich output during test
            with patch("extractor.Progress", DummyProgress), \
                 patch("extractor.SpinnerColumn", DummySpinnerColumn), \
                 patch("extractor.TextColumn", DummyTextColumn):
                extractor.export(tasks)

            # Read the CSV and verify order
            with open(config.output_path, "r") as f:
                import csv
                reader = csv.DictReader(f)
                rows = list(reader)

            # Verify tasks are sorted
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[0]["Task"], "Alpha")
            self.assertEqual(rows[0]["Priority"], "Urgent")
            self.assertEqual(rows[1]["Task"], "Zebra")
            self.assertEqual(rows[1]["Priority"], "High")
            self.assertEqual(rows[2]["Task"], "Charlie")
            self.assertEqual(rows[2]["Priority"], "Normal")
            self.assertEqual(rows[3]["Task"], "Beta")
            self.assertEqual(rows[3]["Priority"], "Low")


if __name__ == "__main__":
    unittest.main()
