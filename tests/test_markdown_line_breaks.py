#!/usr/bin/env python3
"""
Unit tests for markdown line break handling in extractor.py
"""

import unittest
from config import ClickUpConfig, TaskRecord, OutputFormat
from extractor import ClickUpTaskExtractor


class DummyAPIClient:
    """Minimal API client for testing."""
    def get(self, endpoint):
        return {}


class TestMarkdownLineBreaks(unittest.TestCase):
    """Test that markdown export handles line breaks correctly."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = ClickUpConfig(
            api_key="test_key",
            output_path="output/test.md",
            output_format=OutputFormat.MARKDOWN,
            workspace_name="TestWorkspace",
            space_name="TestSpace"
        )
        self.api_client = DummyAPIClient()
        self.extractor = ClickUpTaskExtractor(self.config, self.api_client)

    def test_markdown_line_breaks_use_trailing_spaces(self):
        """Test that markdown export uses two trailing spaces for line breaks, not <br> tags."""
        # Create a task with multi-line notes
        task = TaskRecord(
            Task="Multi-line Task",
            Company="Test Company",
            Branch="Main",
            Priority="High",
            Status="Open",
            ETA="12/25/2024",
            Notes="Line one\nLine two\nLine three",
            Extra=""
        )

        # Generate markdown
        markdown = self.extractor.render_markdown([task])

        # Verify that <br> tags are NOT used
        self.assertNotIn("<br>", markdown, 
                        "Markdown should not contain HTML <br> tags")

        # Verify that trailing spaces ARE used for line breaks
        self.assertIn("Line one  \n", markdown,
                     "Line breaks should use two trailing spaces followed by newline")
        self.assertIn("Line two  \n", markdown,
                     "Line breaks should use two trailing spaces followed by newline")

    def test_markdown_pipe_escaping(self):
        """Test that pipe characters are properly escaped in markdown tables."""
        task = TaskRecord(
            Task="Test | Task",
            Company="Company | Name",
            Branch="Main",
            Priority="Normal",
            Status="Open",
            ETA="",
            Notes="Notes with | pipes",
            Extra=""
        )

        markdown = self.extractor.render_markdown([task])

        # Verify pipes are escaped with backslash
        self.assertIn("Test \\| Task", markdown,
                     "Pipe characters should be escaped with backslash")
        self.assertIn("Company \\| Name", markdown,
                     "Pipe characters should be escaped with backslash")
        self.assertIn("Notes with \\| pipes", markdown,
                     "Pipe characters should be escaped with backslash")

    def test_markdown_combined_escaping_and_line_breaks(self):
        """Test that both pipe escaping and line breaks work together."""
        task = TaskRecord(
            Task="Complex Task",
            Company="Test",
            Branch="Main",
            Priority="High",
            Status="Open",
            ETA="",
            Notes="First | line\nSecond | line\nThird line",
            Extra=""
        )

        markdown = self.extractor.render_markdown([task])

        # Verify both escaping and line breaks are applied
        self.assertIn("First \\| line  \n", markdown,
                     "Should escape pipes AND add trailing spaces for line breaks")
        self.assertIn("Second \\| line  \n", markdown,
                     "Should escape pipes AND add trailing spaces for line breaks")

    def test_markdown_empty_task_list(self):
        """Test markdown generation with no tasks."""
        markdown = self.extractor.render_markdown([])

        self.assertIn("# Weekly Task List", markdown)
        self.assertIn("*No tasks found.*", markdown)
        self.assertNotIn("<br>", markdown)

    def test_markdown_single_line_notes(self):
        """Test that single-line notes work correctly without extra processing."""
        task = TaskRecord(
            Task="Simple Task",
            Company="Test",
            Branch="Main",
            Priority="Normal",
            Status="Open",
            ETA="",
            Notes="Single line note without newlines",
            Extra=""
        )

        markdown = self.extractor.render_markdown([task])

        # Should contain the notes as-is
        self.assertIn("Single line note without newlines", markdown)
        # Should not have unnecessary trailing spaces in the middle of content
        self.assertNotIn("Single  \n", markdown)


if __name__ == "__main__":
    unittest.main()
