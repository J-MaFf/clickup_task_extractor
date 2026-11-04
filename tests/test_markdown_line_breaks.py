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
            space_name="TestSpace",
        )
        self.api_client = DummyAPIClient()
        self.extractor = ClickUpTaskExtractor(self.config, self.api_client)

    def test_markdown_line_breaks_use_spaces(self):
        """Test that markdown export normalizes newlines to spaces for table integrity."""
        # Create a task with multi-line notes
        task = TaskRecord(
            Task="Multi-line Task",
            Company="Test Company",
            Branch="Main",
            Priority="High",
            Status="Open",
            ETA="12/25/2024",
            Notes="Line one\nLine two\nLine three",
            Extra="",
        )

        # Generate markdown
        markdown = self.extractor.render_markdown([task])

        # Verify that <br> tags are NOT used
        self.assertNotIn("<br>", markdown, "Markdown should not contain HTML <br> tags")

        # Verify that newlines are converted to spaces to maintain table structure
        self.assertIn(
            "Line one Line two Line three",
            markdown,
            "Newlines should be replaced with spaces to keep content in single table cell",
        )
        # Verify no trailing spaces (which cause MD009 violations)
        self.assertNotIn(
            "  \n", markdown, "Should not contain trailing spaces followed by newline"
        )

    def test_markdown_pipe_escaping(self):
        """Test that pipe characters are preserved safely in markdown list output."""
        task = TaskRecord(
            Task="Test | Task",
            Company="Company | Name",
            Branch="Main",
            Priority="Normal",
            Status="Open",
            ETA="",
            Notes="Notes with | pipes",
            Extra="",
        )

        markdown = self.extractor.render_markdown([task])

        # Verify values are present and bullets render as expected
        self.assertIn(
            "- **Task:** Test | Task",
            markdown,
            "Task line should render in bullet format",
        )
        self.assertIn(
            "- **Company:** Company | Name",
            markdown,
            "Company line should render in bullet format",
        )
        self.assertIn(
            "- **Notes:** Notes with | pipes",
            markdown,
            "Notes line should render in bullet format",
        )

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
            Extra="",
        )

        markdown = self.extractor.render_markdown([task])

        # Verify multiline text is normalized and rendered in bullet output
        self.assertIn(
            "- **Notes:** First | line Second | line Third line",
            markdown,
            "Should normalize newlines and preserve visible pipe characters",
        )

    def test_markdown_header_metadata_is_a_list(self):
        """Header metadata renders as list items, so each stays on its own line
        whether or not the renderer turns soft line breaks into <br> (#203)."""
        markdown = self.extractor.render_markdown([])
        lines = markdown.splitlines()

        generated = next(i for i, line in enumerate(lines) if "**Generated:**" in line)
        self.assertTrue(lines[generated].startswith("- **Generated:** "))
        self.assertEqual(lines[generated + 1], "- **Total Tasks:** 0")
        self.assertEqual(
            lines[generated + 2], "- **Workspace:** TestWorkspace / TestSpace"
        )

    def test_markdown_long_notes_are_not_wrapped(self):
        """A long field value stays on one line: a renderer with GFM line breaks
        on would turn every wrap into a hard break (#203)."""
        long_note = " ".join(["word"] * 80)  # ~400 characters
        task = TaskRecord(
            Task="Long Task",
            Company="Test",
            Branch="Main",
            Priority="Normal",
            Status="Open",
            ETA="",
            Notes=long_note,
            Extra="",
        )

        markdown = self.extractor.render_markdown([task])

        self.assertIn(f"- **Notes:** {long_note}\n", markdown)
        # No continuation lines (the old wrapping indented them two spaces)
        self.assertFalse(
            any(line.startswith("  ") for line in markdown.splitlines()),
            "Field values should not wrap onto indented continuation lines",
        )

    def test_markdown_disables_line_length_rule_after_title(self):
        """Unwrapped lines are long, so MD013 is disabled; the comment comes
        after the h1 so the file still starts with a heading (MD041)."""
        markdown = self.extractor.render_markdown([])
        lines = markdown.splitlines()

        self.assertEqual(lines[0], "# Weekly Task List")
        disable = lines.index("<!-- markdownlint-disable MD013 -->")
        generated = next(i for i, line in enumerate(lines) if "**Generated:**" in line)
        self.assertLess(disable, generated)

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
            Extra="",
        )

        markdown = self.extractor.render_markdown([task])

        # Should contain the notes as-is
        self.assertIn("Single line note without newlines", markdown)
        # Should not have unnecessary trailing spaces in the middle of content
        self.assertNotIn("Single  \n", markdown)

    def test_markdown_trims_field_values(self):
        """Ensure field values are stripped in bullet output."""
        task = TaskRecord(
            Task="  Task with spaces  ",
            Company="  Company  ",
            Branch=" Branch ",
            Priority=" Normal ",
            Status=" Open ",
            ETA=" 2/19/2026 ",
            Notes=" Note with trailing space ",
            Extra=" Extra ",
        )

        markdown = self.extractor.render_markdown([task])

        # Each field value should be trimmed
        self.assertIn(
            "- **Task:** Task with spaces",
            markdown,
        )
        self.assertIn(
            "- **Company:** Company",
            markdown,
        )
        self.assertIn(
            "- **Branch:** Branch",
            markdown,
        )
        self.assertIn(
            "- **Priority:** Normal",
            markdown,
        )
        self.assertIn(
            "- **Status:** Open",
            markdown,
        )
        self.assertIn(
            "- **ETA:** 2/19/2026",
            markdown,
        )
        self.assertIn(
            "- **Notes:** Note with trailing space",
            markdown,
        )
        self.assertIn(
            "- **Extra:** Extra",
            markdown,
        )


if __name__ == "__main__":
    unittest.main()
