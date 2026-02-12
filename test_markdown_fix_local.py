#!/usr/bin/env python3
"""Quick test to verify markdown line break fix."""

import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ClickUpConfig, TaskRecord, OutputFormat
from extractor import ClickUpTaskExtractor


class DummyAPIClient:
    """Minimal API client for testing."""

    def get(self, endpoint):
        return {}


def test_markdown_render():
    """Test that markdown rendering works correctly with new line break strategy."""
    config = ClickUpConfig(
        api_key="test_key",
        output_path="output/test.md",
        output_format=OutputFormat.MARKDOWN,
        workspace_name="TestWorkspace",
        space_name="TestSpace",
    )
    api_client = DummyAPIClient()
    extractor = ClickUpTaskExtractor(config, api_client)

    # Test 1: Multi-line notes
    task1 = TaskRecord(
        Task="Multi-line Task",
        Company="Test Company",
        Branch="Main",
        Priority="High",
        Status="Open",
        ETA="12/25/2024",
        Notes="Line one\nLine two\nLine three",
        Extra="",
    )

    markdown = extractor.render_markdown([task1])

    # Check results
    assert "<br>" not in markdown, "Should not contain HTML <br> tags"
    assert "Line one Line two Line three" in markdown, (
        f"Expected 'Line one Line two Line three' in output"
    )
    assert "  \n" not in markdown, (
        "Should not contain trailing spaces followed by newline (MD009 violation)"
    )
    print("✅ Test 1 PASSED: Multi-line notes are properly normalized")

    # Test 2: Pipe escaping with line breaks
    task2 = TaskRecord(
        Task="Complex Task",
        Company="Test",
        Branch="Main",
        Priority="High",
        Status="Open",
        ETA="",
        Notes="First | line\nSecond | line\nThird line",
        Extra="",
    )

    markdown = extractor.render_markdown([task2])

    assert "First \\| line Second \\| line Third line" in markdown, (
        f"Expected pipes to be escaped and newlines to be spaces. Got: {markdown}"
    )
    print("✅ Test 2 PASSED: Pipe escaping with line breaks work together")

    # Test 3: Table structure integrity
    task3 = TaskRecord(
        Task="Test Task",
        Company="Company",
        Branch="Main",
        Priority="Normal",
        Status="Open",
        ETA="",
        Notes="Multi\nLine\nNotes",
        Extra="Extra\nContent",
    )

    markdown = extractor.render_markdown([task3])

    # Count pipes in a row - should be consistent
    lines = markdown.split("\n")
    table_lines = [line for line in lines if line.strip() and not line.startswith("#")]

    if len(table_lines) >= 3:  # Header, separator, and at least one data row
        header_pipes = table_lines[0].count("|")
        data_row_pipes = (
            table_lines[2].count("|") if len(table_lines) > 2 else header_pipes
        )
        assert header_pipes == data_row_pipes, (
            f"Table structure broken: header has {header_pipes} pipes, data row has {data_row_pipes}"
        )
        print("✅ Test 3 PASSED: Table structure integrity maintained")

    print("\n✅ ALL TESTS PASSED!")
    print("\nGenerated markdown sample:")
    print(markdown[:500] + "..." if len(markdown) > 500 else markdown)
    return True


if __name__ == "__main__":
    try:
        test_markdown_render()
        sys.exit(0)
    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
