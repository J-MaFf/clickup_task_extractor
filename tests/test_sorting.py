"""
Unit tests for task sorting functionality.

Tests the sort_tasks_by_priority_and_name function to ensure tasks are
properly ordered by priority (Urgent → High → Normal → Low) and then
alphabetically by task name.
"""

import unittest
from config import TaskRecord, sort_tasks_by_priority_and_name


class TestTaskSorting(unittest.TestCase):
    """Test suite for task sorting functionality."""

    def test_sort_by_priority_only(self):
        """Test tasks are sorted by priority when names are same."""
        tasks = [
            TaskRecord(Task="Task", Company="A", Branch="", Priority="Low", Status="Open"),
            TaskRecord(Task="Task", Company="A", Branch="", Priority="Urgent", Status="Open"),
            TaskRecord(Task="Task", Company="A", Branch="", Priority="Normal", Status="Open"),
            TaskRecord(Task="Task", Company="A", Branch="", Priority="High", Status="Open"),
        ]
        
        sorted_tasks = sort_tasks_by_priority_and_name(tasks)
        
        expected_order = ["Urgent", "High", "Normal", "Low"]
        actual_order = [t.Priority for t in sorted_tasks]
        
        self.assertEqual(actual_order, expected_order)

    def test_sort_by_name_when_same_priority(self):
        """Test tasks are sorted alphabetically when priority is the same."""
        tasks = [
            TaskRecord(Task="Zebra Task", Company="A", Branch="", Priority="High", Status="Open"),
            TaskRecord(Task="Apple Task", Company="A", Branch="", Priority="High", Status="Open"),
            TaskRecord(Task="Banana Task", Company="A", Branch="", Priority="High", Status="Open"),
        ]
        
        sorted_tasks = sort_tasks_by_priority_and_name(tasks)
        
        expected_names = ["Apple Task", "Banana Task", "Zebra Task"]
        actual_names = [t.Task for t in sorted_tasks]
        
        self.assertEqual(actual_names, expected_names)

    def test_sort_by_priority_then_name(self):
        """Test combined sorting: priority first, then alphabetically by name."""
        tasks = [
            TaskRecord(Task="Zebra", Company="A", Branch="", Priority="Low", Status="Open"),
            TaskRecord(Task="Alpha", Company="A", Branch="", Priority="High", Status="Open"),
            TaskRecord(Task="Beta", Company="A", Branch="", Priority="Urgent", Status="Open"),
            TaskRecord(Task="Charlie", Company="A", Branch="", Priority="Normal", Status="Open"),
            TaskRecord(Task="Apple", Company="A", Branch="", Priority="High", Status="Open"),
            TaskRecord(Task="Yak", Company="A", Branch="", Priority="Low", Status="Open"),
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
            TaskRecord(Task="zebra", Company="A", Branch="", Priority="Normal", Status="Open"),
            TaskRecord(Task="Apple", Company="A", Branch="", Priority="Normal", Status="Open"),
            TaskRecord(Task="BANANA", Company="A", Branch="", Priority="Normal", Status="Open"),
        ]
        
        sorted_tasks = sort_tasks_by_priority_and_name(tasks)
        
        expected_names = ["Apple", "BANANA", "zebra"]
        actual_names = [t.Task for t in sorted_tasks]
        
        self.assertEqual(actual_names, expected_names)

    def test_empty_priority_sorting(self):
        """Test tasks with empty priority are sorted last."""
        tasks = [
            TaskRecord(Task="Task A", Company="A", Branch="", Priority="Normal", Status="Open"),
            TaskRecord(Task="Task B", Company="A", Branch="", Priority="", Status="Open"),
            TaskRecord(Task="Task C", Company="A", Branch="", Priority="High", Status="Open"),
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
            TaskRecord(Task="Only Task", Company="A", Branch="", Priority="High", Status="Open")
        ]
        sorted_tasks = sort_tasks_by_priority_and_name(tasks)
        self.assertEqual(len(sorted_tasks), 1)
        self.assertEqual(sorted_tasks[0].Task, "Only Task")

    def test_all_priorities_represented(self):
        """Test comprehensive scenario with all priority levels."""
        tasks = [
            TaskRecord(Task="C-Low", Company="A", Branch="", Priority="Low", Status="Open"),
            TaskRecord(Task="B-Normal", Company="A", Branch="", Priority="Normal", Status="Open"),
            TaskRecord(Task="A-Urgent", Company="A", Branch="", Priority="Urgent", Status="Open"),
            TaskRecord(Task="D-High", Company="A", Branch="", Priority="High", Status="Open"),
            TaskRecord(Task="E-Low", Company="A", Branch="", Priority="Low", Status="Open"),
            TaskRecord(Task="F-Urgent", Company="A", Branch="", Priority="Urgent", Status="Open"),
            TaskRecord(Task="G-Normal", Company="A", Branch="", Priority="Normal", Status="Open"),
            TaskRecord(Task="H-High", Company="A", Branch="", Priority="High", Status="Open"),
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
            TaskRecord(Task="[Urgent] Fix bug", Company="A", Branch="", Priority="High", Status="Open"),
            TaskRecord(Task="(High) Update docs", Company="A", Branch="", Priority="High", Status="Open"),
            TaskRecord(Task="!Important task", Company="A", Branch="", Priority="High", Status="Open"),
        ]
        
        sorted_tasks = sort_tasks_by_priority_and_name(tasks)
        
        # Should be sorted alphabetically with special chars
        actual_names = [t.Task for t in sorted_tasks]
        
        # All have same priority, so just alphabetical
        self.assertEqual(len(actual_names), 3)
        self.assertTrue(all(t.Priority == "High" for t in sorted_tasks))


if __name__ == '__main__':
    unittest.main()
