import os
import unittest
from datetime import datetime

from config import DISPLAY_FORMAT, TIMESTAMP_FORMAT, default_output_path, format_datetime


class FormatDateTimeTests(unittest.TestCase):
    def test_removes_leading_zeros(self) -> None:
        sample_dt = datetime(2025, 1, 8, 9, 5, 0)
        formatted = format_datetime(sample_dt, DISPLAY_FORMAT)
        self.assertEqual(formatted, "1/8/2025 at 9:05 AM")

    def test_filename_uses_mm_dd_yyyy_format(self) -> None:
        """Test that the filename format is MM-DD-YYYY as per issue requirements."""
        # Test case from the issue: October 7, 2025 at 3:45 PM
        sample_dt = datetime(2025, 10, 7, 15, 45, 0)
        formatted = format_datetime(sample_dt, TIMESTAMP_FORMAT)
        # Should be 10-7-2025_3-45PM (MM-DD-YYYY format)
        self.assertEqual(formatted, "10-7-2025_3-45PM")

    def test_display_format_uses_mm_dd_yyyy(self) -> None:
        """Test that display format is MM/DD/YYYY for consistency."""
        sample_dt = datetime(2025, 10, 7, 9, 30, 0)
        formatted = format_datetime(sample_dt, DISPLAY_FORMAT)
        # Should be 10/7/2025 at 9:30 AM (MM/DD/YYYY format)
        self.assertEqual(formatted, "10/7/2025 at 9:30 AM")


class DefaultOutputPathTests(unittest.TestCase):
    def test_default_output_path_uses_output_directory(self) -> None:
        path = default_output_path()
        self.assertTrue(path.startswith("output/WeeklyTaskList_"))
        self.assertTrue(path.endswith(".csv"))
        # Ensure directory component is "output" regardless of OS separators
        directory = os.path.dirname(path)
        self.assertIn("output", directory)


if __name__ == "__main__":
    unittest.main()
