import os
import unittest
from datetime import datetime

from config import DISPLAY_FORMAT, default_output_path, format_datetime


class FormatDateTimeTests(unittest.TestCase):
    def test_removes_leading_zeros(self) -> None:
        sample_dt = datetime(2025, 1, 8, 9, 5, 0)
        formatted = format_datetime(sample_dt, DISPLAY_FORMAT)
        self.assertEqual(formatted, "8/1/2025 at 9:05 AM")


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
