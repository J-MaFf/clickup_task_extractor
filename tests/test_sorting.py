"""
Unit tests for task sorting functionality.

Tests the sort_tasks_by_priority_and_name and sort_tasks_by_priority_and_eta functions
to ensure tasks are properly ordered by priority (Urgent → High → Normal → Low) and
then by ETA (earliest first) or alphabetically by task name.
"""

import unittest
from config import (
    TaskRecord,
    sort_tasks_by_priority_and_name,
    sort_tasks_by_priority_and_eta,
)


class TestTaskSorting(unittest.TestCase):
    """Test suite for task sorting functionality."""

    def test_sort_by_priority_only(self):
        """Test tasks are sorted by priority when names are same."""
        tasks = [
            TaskRecord(
                Task="Task", Company="A", Branch="", Priority="Low", Status="Open"
            ),
            TaskRecord(
                Task="Task", Company="A", Branch="", Priority="Urgent", Status="Open"
            ),
            TaskRecord(
                Task="Task", Company="A", Branch="", Priority="Normal", Status="Open"
            ),
            TaskRecord(
                Task="Task", Company="A", Branch="", Priority="High", Status="Open"
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_name(tasks)

        expected_order = ["Urgent", "High", "Normal", "Low"]
        actual_order = [t.Priority for t in sorted_tasks]

        self.assertEqual(actual_order, expected_order)

    def test_sort_by_name_when_same_priority(self):
        """Test tasks are sorted alphabetically when priority is the same."""
        tasks = [
            TaskRecord(
                Task="Zebra Task",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
            ),
            TaskRecord(
                Task="Apple Task",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
            ),
            TaskRecord(
                Task="Banana Task",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_name(tasks)

        expected_names = ["Apple Task", "Banana Task", "Zebra Task"]
        actual_names = [t.Task for t in sorted_tasks]

        self.assertEqual(actual_names, expected_names)

    def test_sort_by_priority_then_name(self):
        """Test combined sorting: priority first, then alphabetically by name."""
        tasks = [
            TaskRecord(
                Task="Zebra", Company="A", Branch="", Priority="Low", Status="Open"
            ),
            TaskRecord(
                Task="Alpha", Company="A", Branch="", Priority="High", Status="Open"
            ),
            TaskRecord(
                Task="Beta", Company="A", Branch="", Priority="Urgent", Status="Open"
            ),
            TaskRecord(
                Task="Charlie", Company="A", Branch="", Priority="Normal", Status="Open"
            ),
            TaskRecord(
                Task="Apple", Company="A", Branch="", Priority="High", Status="Open"
            ),
            TaskRecord(
                Task="Yak", Company="A", Branch="", Priority="Low", Status="Open"
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_name(tasks)

        # Expected order: Urgent tasks first, then High (alphabetically), then Normal, then Low (alphabetically)
        expected = [
            ("Beta", "Urgent"),
            ("Alpha", "High"),
            ("Apple", "High"),
            ("Charlie", "Normal"),
            ("Yak", "Low"),
            ("Zebra", "Low"),
        ]

        actual = [(t.Task, t.Priority) for t in sorted_tasks]

        self.assertEqual(actual, expected)

    def test_case_insensitive_name_sorting(self):
        """Test that name sorting is case-insensitive."""
        tasks = [
            TaskRecord(
                Task="zebra", Company="A", Branch="", Priority="Normal", Status="Open"
            ),
            TaskRecord(
                Task="Apple", Company="A", Branch="", Priority="Normal", Status="Open"
            ),
            TaskRecord(
                Task="BANANA", Company="A", Branch="", Priority="Normal", Status="Open"
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_name(tasks)

        expected_names = ["Apple", "BANANA", "zebra"]
        actual_names = [t.Task for t in sorted_tasks]

        self.assertEqual(actual_names, expected_names)

    def test_empty_priority_sorting(self):
        """Test tasks with empty priority are sorted last."""
        tasks = [
            TaskRecord(
                Task="Task A", Company="A", Branch="", Priority="Normal", Status="Open"
            ),
            TaskRecord(
                Task="Task B", Company="A", Branch="", Priority="", Status="Open"
            ),
            TaskRecord(
                Task="Task C", Company="A", Branch="", Priority="High", Status="Open"
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_name(tasks)

        # Empty priority should be last
        expected = [
            ("Task C", "High"),
            ("Task A", "Normal"),
            ("Task B", ""),
        ]

        actual = [(t.Task, t.Priority) for t in sorted_tasks]

        self.assertEqual(actual, expected)

    def test_empty_list(self):
        """Test sorting empty list returns empty list."""
        tasks = []
        sorted_tasks = sort_tasks_by_priority_and_name(tasks)
        self.assertEqual(sorted_tasks, [])

    def test_single_task(self):
        """Test sorting single task returns same task."""
        tasks = [
            TaskRecord(
                Task="Only Task", Company="A", Branch="", Priority="High", Status="Open"
            )
        ]
        sorted_tasks = sort_tasks_by_priority_and_name(tasks)
        self.assertEqual(len(sorted_tasks), 1)
        self.assertEqual(sorted_tasks[0].Task, "Only Task")

    def test_all_priorities_represented(self):
        """Test comprehensive scenario with all priority levels."""
        tasks = [
            TaskRecord(
                Task="C-Low", Company="A", Branch="", Priority="Low", Status="Open"
            ),
            TaskRecord(
                Task="B-Normal",
                Company="A",
                Branch="",
                Priority="Normal",
                Status="Open",
            ),
            TaskRecord(
                Task="A-Urgent",
                Company="A",
                Branch="",
                Priority="Urgent",
                Status="Open",
            ),
            TaskRecord(
                Task="D-High", Company="A", Branch="", Priority="High", Status="Open"
            ),
            TaskRecord(
                Task="E-Low", Company="A", Branch="", Priority="Low", Status="Open"
            ),
            TaskRecord(
                Task="F-Urgent",
                Company="A",
                Branch="",
                Priority="Urgent",
                Status="Open",
            ),
            TaskRecord(
                Task="G-Normal",
                Company="A",
                Branch="",
                Priority="Normal",
                Status="Open",
            ),
            TaskRecord(
                Task="H-High", Company="A", Branch="", Priority="High", Status="Open"
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_name(tasks)

        # Urgent first (alphabetically), then High (alphabetically), then Normal, then Low
        expected = [
            ("A-Urgent", "Urgent"),
            ("F-Urgent", "Urgent"),
            ("D-High", "High"),
            ("H-High", "High"),
            ("B-Normal", "Normal"),
            ("G-Normal", "Normal"),
            ("C-Low", "Low"),
            ("E-Low", "Low"),
        ]

        actual = [(t.Task, t.Priority) for t in sorted_tasks]

        self.assertEqual(actual, expected)

    def test_special_characters_in_names(self):
        """Test sorting with special characters in task names."""
        tasks = [
            TaskRecord(
                Task="[Urgent] Fix bug",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
            ),
            TaskRecord(
                Task="(High) Update docs",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
            ),
            TaskRecord(
                Task="!Important task",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_name(tasks)

        # Should be sorted alphabetically with special chars
        actual_names = [t.Task for t in sorted_tasks]

        # All have same priority, so just alphabetical
        self.assertEqual(len(actual_names), 3)
        self.assertTrue(all(t.Priority == "High" for t in sorted_tasks))


class TestTaskSortingByETA(unittest.TestCase):
    """Test suite for task sorting by priority and ETA."""

    def test_sort_by_eta_when_same_priority(self):
        """Test tasks are sorted by ETA (earliest first) when priority is the same."""
        tasks = [
            TaskRecord(
                Task="Task C",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2/20/2026 at 3:45 PM",
            ),
            TaskRecord(
                Task="Task A",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2/10/2026 at 3:45 PM",
            ),
            TaskRecord(
                Task="Task B",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2/15/2026 at 3:45 PM",
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_eta(tasks)

        # Should be sorted by ETA (earliest first)
        expected = ["Task A", "Task B", "Task C"]
        actual = [t.Task for t in sorted_tasks]

        self.assertEqual(actual, expected)

    def test_sort_by_priority_then_eta(self):
        """Test combined sorting: priority first, then ETA within same priority."""
        tasks = [
            TaskRecord(
                Task="Alpha",
                Company="A",
                Branch="",
                Priority="Urgent",
                Status="Open",
                ETA="2/20/2026 at 3:45 PM",
            ),
            TaskRecord(
                Task="Zebra",
                Company="A",
                Branch="",
                Priority="Urgent",
                Status="Open",
                ETA="2/15/2026 at 3:45 PM",
            ),
            TaskRecord(
                Task="Beta",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2/10/2026 at 3:45 PM",
            ),
            TaskRecord(
                Task="Yak",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2/25/2026 at 3:45 PM",
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_eta(tasks)

        # Expected: Urgent (by ETA), then High (by ETA)
        expected = [
            ("Zebra", "Urgent", "2/15/2026 at 3:45 PM"),
            ("Alpha", "Urgent", "2/20/2026 at 3:45 PM"),
            ("Beta", "High", "2/10/2026 at 3:45 PM"),
            ("Yak", "High", "2/25/2026 at 3:45 PM"),
        ]

        actual = [(t.Task, t.Priority, t.ETA) for t in sorted_tasks]

        self.assertEqual(actual, expected)

    def test_empty_eta_appears_last_in_priority(self):
        """Test tasks with missing ETA appear last within their priority level."""
        tasks = [
            TaskRecord(
                Task="Task A",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2/10/2026 at 3:45 PM",
            ),
            TaskRecord(
                Task="Task B",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="",
            ),
            TaskRecord(
                Task="Task C",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2/15/2026 at 3:45 PM",
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_eta(tasks)

        # Tasks with ETA first (sorted by ETA), then tasks with no ETA
        expected = [
            ("Task A", "High", "2/10/2026 at 3:45 PM"),
            ("Task C", "High", "2/15/2026 at 3:45 PM"),
            ("Task B", "High", ""),
        ]

        actual = [(t.Task, t.Priority, t.ETA) for t in sorted_tasks]

        self.assertEqual(actual, expected)

    def test_missing_eta_across_priorities(self):
        """Test missing ETAs appear last within each priority tier."""
        tasks = [
            TaskRecord(
                Task="Urgent-NoETA",
                Company="A",
                Branch="",
                Priority="Urgent",
                Status="Open",
                ETA="",
            ),
            TaskRecord(
                Task="Urgent-ETA",
                Company="A",
                Branch="",
                Priority="Urgent",
                Status="Open",
                ETA="2/15/2026 at 3:45 PM",
            ),
            TaskRecord(
                Task="High-NoETA",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="",
            ),
            TaskRecord(
                Task="High-ETA",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2/10/2026 at 3:45 PM",
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_eta(tasks)

        # Urgent (with ETA), then Urgent (no ETA), then High (with ETA), then High (no ETA)
        expected = [
            ("Urgent-ETA", "Urgent"),
            ("Urgent-NoETA", "Urgent"),
            ("High-ETA", "High"),
            ("High-NoETA", "High"),
        ]

        actual = [(t.Task, t.Priority) for t in sorted_tasks]

        self.assertEqual(actual, expected)

    def test_iso_format_eta(self):
        """Test parsing ISO format ETAs (YYYY-MM-DD)."""
        tasks = [
            TaskRecord(
                Task="Task C",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2026-02-20",
            ),
            TaskRecord(
                Task="Task A",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2026-02-10",
            ),
            TaskRecord(
                Task="Task B",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2026-02-15",
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_eta(tasks)

        # Should be sorted by ETA chronologically
        expected = ["Task A", "Task B", "Task C"]
        actual = [t.Task for t in sorted_tasks]

        self.assertEqual(actual, expected)

    def test_complex_scenario_all_levels(self):
        """Test comprehensive scenario with all priority levels and mixed ETAs."""
        tasks = [
            # Urgent
            TaskRecord(
                Task="U-Late",
                Company="A",
                Branch="",
                Priority="Urgent",
                Status="Open",
                ETA="2/28/2026 at 3:45 PM",
            ),
            TaskRecord(
                Task="U-Early",
                Company="A",
                Branch="",
                Priority="Urgent",
                Status="Open",
                ETA="2/10/2026 at 3:45 PM",
            ),
            # High
            TaskRecord(
                Task="H-NoETA",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="",
            ),
            TaskRecord(
                Task="H-Mid",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2/15/2026 at 3:45 PM",
            ),
            # Normal
            TaskRecord(
                Task="N-Early",
                Company="A",
                Branch="",
                Priority="Normal",
                Status="Open",
                ETA="2/12/2026 at 3:45 PM",
            ),
            # Low
            TaskRecord(
                Task="L-NoETA",
                Company="A",
                Branch="",
                Priority="Low",
                Status="Open",
                ETA="",
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_eta(tasks)

        # Expected order: Urgent (by ETA), then High (by ETA), then Normal, then Low
        expected = [
            ("U-Early", "Urgent", "2/10/2026 at 3:45 PM"),
            ("U-Late", "Urgent", "2/28/2026 at 3:45 PM"),
            ("H-Mid", "High", "2/15/2026 at 3:45 PM"),
            ("H-NoETA", "High", ""),
            ("N-Early", "Normal", "2/12/2026 at 3:45 PM"),
            ("L-NoETA", "Low", ""),
        ]

        actual = [(t.Task, t.Priority, t.ETA) for t in sorted_tasks]

        self.assertEqual(actual, expected)

    def test_empty_list_eta_sort(self):
        """Test sorting empty list returns empty list."""
        tasks = []
        sorted_tasks = sort_tasks_by_priority_and_eta(tasks)
        self.assertEqual(sorted_tasks, [])

    def test_single_task_eta_sort(self):
        """Test sorting single task returns same task."""
        tasks = [
            TaskRecord(
                Task="Only Task",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2/15/2026 at 3:45 PM",
            )
        ]
        sorted_tasks = sort_tasks_by_priority_and_eta(tasks)
        self.assertEqual(len(sorted_tasks), 1)
        self.assertEqual(sorted_tasks[0].Task, "Only Task")

    def test_whitespace_only_eta(self):
        """Test tasks with whitespace-only ETA are treated as missing."""
        tasks = [
            TaskRecord(
                Task="Task A",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="   ",
            ),
            TaskRecord(
                Task="Task B",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2/15/2026 at 3:45 PM",
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_eta(tasks)

        # Task with valid ETA should come first
        expected = ["Task B", "Task A"]
        actual = [t.Task for t in sorted_tasks]

        self.assertEqual(actual, expected)

    def test_same_eta_different_priorities(self):
        """Test tasks with same ETA are sorted by priority."""
        tasks = [
            TaskRecord(
                Task="Low Task",
                Company="A",
                Branch="",
                Priority="Low",
                Status="Open",
                ETA="2/15/2026 at 3:45 PM",
            ),
            TaskRecord(
                Task="Urgent Task",
                Company="A",
                Branch="",
                Priority="Urgent",
                Status="Open",
                ETA="2/15/2026 at 3:45 PM",
            ),
            TaskRecord(
                Task="High Task",
                Company="A",
                Branch="",
                Priority="High",
                Status="Open",
                ETA="2/15/2026 at 3:45 PM",
            ),
        ]

        sorted_tasks = sort_tasks_by_priority_and_eta(tasks)

        # Should be sorted by priority (Urgent → High → Low) despite same ETA
        expected = ["Urgent Task", "High Task", "Low Task"]
        actual = [t.Task for t in sorted_tasks]

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
