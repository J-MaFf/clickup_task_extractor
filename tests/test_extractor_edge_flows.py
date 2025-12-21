#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests for extractor.py edge cases and flows.

Tests cover:
- Interactive selection with user prompts
- Multi-format exports (CSV, HTML, Markdown, PDF, Both)
- Error handling for missing workspaces/spaces
- Export with temp directories
"""

import unittest
from unittest.mock import patch, Mock, MagicMock, mock_open
import tempfile
import os
from pathlib import Path
from dataclasses import dataclass

from config import ClickUpConfig, OutputFormat, TaskRecord
from extractor import ClickUpTaskExtractor, export_file, get_export_fields
from api_client import APIError, AuthenticationError


class TestExportFile(unittest.TestCase):
    """Tests for the export_file context manager."""

    def test_export_file_creates_directory(self):
        """Test export_file creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, 'nested', 'subdir', 'test.csv')

            with export_file(test_path, 'w') as f:
                f.write('test content')

            self.assertTrue(os.path.exists(test_path))
            with open(test_path, 'r') as f:
                self.assertEqual(f.read(), 'test content')

    def test_export_file_handles_existing_directory(self):
        """Test export_file works with existing directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, 'test.txt')

            with export_file(test_path, 'w') as f:
                f.write('content')

            self.assertTrue(os.path.exists(test_path))

    def test_export_file_custom_encoding(self):
        """Test export_file respects encoding parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, 'utf8.txt')

            with export_file(test_path, 'w', encoding='utf-8') as f:
                f.write('Test with émojis 🎉')

            with open(test_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn('émojis', content)
                self.assertIn('🎉', content)


class TestGetExportFields(unittest.TestCase):
    """Tests for the get_export_fields function."""

    def test_get_export_fields_excludes_private(self):
        """Test get_export_fields excludes fields starting with underscore."""
        fields = get_export_fields()

        # Should not include _metadata
        self.assertNotIn('_metadata', fields)

        # Should include normal fields
        self.assertIn('Task', fields)
        self.assertIn('Company', fields)
        self.assertIn('Status', fields)

    def test_get_export_fields_returns_list(self):
        """Test get_export_fields returns a list."""
        fields = get_export_fields()
        self.assertIsInstance(fields, list)
        self.assertGreater(len(fields), 0)


class TestInteractiveInclude(unittest.TestCase):
    """Tests for interactive task selection."""

    def setUp(self):
        """Set up test configuration and extractor."""
        self.config = ClickUpConfig(
            api_key='test_key',
            workspace_name='Test Workspace',
            space_name='Test Space',
            output_format=OutputFormat.CSV,
            output_path='test_output.csv'
        )
        self.client = Mock()
        self.extractor = ClickUpTaskExtractor(self.config, self.client)

    def test_interactive_include_with_all_yes(self):
        """Test interactive selection when user selects all tasks."""
        tasks = [
            TaskRecord(
                Task='Task 1',
                Company='Company A',
                Branch='Branch 1',
                Status='In Progress',
                Priority='High',
                Notes='Note 1',
                Extra='Extra 1'
            ),
            TaskRecord(
                Task='Task 2',
                Company='Company B',
                Branch='Branch 2',
                Status='Open',
                Priority='Low',
                Notes='Note 2',
                Extra='Extra 2'
            )
        ]

        with patch('extractor.get_yes_no_input', side_effect=[True, True]):
            result = self.extractor.interactive_include(tasks)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].Task, 'Task 1')
        self.assertEqual(result[1].Task, 'Task 2')

    def test_interactive_include_with_selective_yes(self):
        """Test interactive selection with selective task inclusion."""
        tasks = [
            TaskRecord(
                Task='Task 1',
                Company='Company A',
                Branch='Branch 1',
                Status='In Progress',
                Priority='High',
                Notes='Note 1',
                Extra='Extra 1'
            ),
            TaskRecord(
                Task='Task 2',
                Company='Company B',
                Branch='Branch 2',
                Status='Open',
                Priority='Low',
                Notes='Note 2',
                Extra='Extra 2'
            )
        ]

        # Select only first task
        with patch('extractor.get_yes_no_input', side_effect=[True, False]):
            result = self.extractor.interactive_include(tasks)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].Task, 'Task 1')

    def test_interactive_include_with_all_no(self):
        """Test interactive selection when user rejects all tasks."""
        tasks = [
            TaskRecord(
                Task='Task 1',
                Company='Company A',
                Branch='Branch 1',
                Status='In Progress',
                Priority='High',
                Notes='Note 1',
                Extra='Extra 1'
            )
        ]

        with patch('extractor.get_yes_no_input', return_value=False):
            result = self.extractor.interactive_include(tasks)

        self.assertEqual(len(result), 0)


class TestMultiFormatExport(unittest.TestCase):
    """Tests for multi-format export functionality."""

    def setUp(self):
        """Set up test configuration and extractor."""
        self.client = Mock()
        # Clean up any test output files before each test
        output_dir = Path("output")
        for filename in ["test.csv", "test.html"]:
            file_path = output_dir / filename
            if file_path.exists():
                file_path.unlink()

    def tearDown(self):
        """Clean up test output files after each test."""
        output_dir = Path("output")
        for filename in ["test.csv", "test.html"]:
            file_path = output_dir / filename
            if file_path.exists():
                file_path.unlink()

    @patch('extractor.console')
    def test_csv_export(self, mock_console):
        """Test CSV export creates file with correct format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # The extractor writes to output/ directory, not the temp directory
            config = ClickUpConfig(
                api_key='test_key',
                workspace_name='Test Workspace',
                space_name='Test Space',
                output_format=OutputFormat.CSV,
                output_path=os.path.join(tmpdir, 'test.csv')  # base filename is extracted
            )
            extractor = ClickUpTaskExtractor(config, self.client)

            tasks = [
                TaskRecord(
                    Task='Test Task',
                    Company='Test Company',
                    Branch='Test Branch',
                    Status='Open',
                    Priority='High',
                    Notes='Test Notes',
                    Extra='Extra'
                )
            ]

            extractor.export(tasks)

            # File should be in output/ directory
            actual_path = Path("output") / "test.csv"
            self.assertTrue(actual_path.exists())
            with open(actual_path, 'r') as f:
                content = f.read()
                self.assertIn('Test Task', content)
                self.assertIn('Test Company', content)

    @patch('extractor.console')
    def test_html_export(self, mock_console):
        """Test HTML export creates file with correct format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ClickUpConfig(
                api_key='test_key',
                workspace_name='Test Workspace',
                space_name='Test Space',
                output_format=OutputFormat.HTML,
                output_path=os.path.join(tmpdir, 'test.html')  # base filename is extracted
            )
            extractor = ClickUpTaskExtractor(config, self.client)

            tasks = [
                TaskRecord(
                    Task='HTML Test',
                    Company='HTML Company',
                    Branch='Branch',
                    Status='In Progress',
                    Priority='Normal',
                    Notes='HTML Notes',
                    Extra='Extra'
                )
            ]

            extractor.export(tasks)

            # File should be in output/ directory
            actual_path = Path("output") / "test.html"
            self.assertTrue(actual_path.exists())
            with open(actual_path, 'r') as f:
                content = f.read()
                self.assertIn('HTML Test', content)
                self.assertIn('HTML Company', content)

    @patch('extractor.console')
    def test_both_format_export(self, mock_console):
        """Test Both format creates both CSV and HTML files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ClickUpConfig(
                api_key='test_key',
                workspace_name='Test Workspace',
                space_name='Test Space',
                output_format=OutputFormat.BOTH,
                output_path=os.path.join(tmpdir, 'test.csv')  # base filename is extracted
            )
            extractor = ClickUpTaskExtractor(config, self.client)

            tasks = [
                TaskRecord(
                    Task='Both Format Test',
                    Company='Company',
                    Branch='Branch',
                    Status='Open',
                    Priority='High',
                    Notes='Notes',
                    Extra='Extra'
                )
            ]

            extractor.export(tasks)

            # Check both files exist in output/ directory
            csv_path = Path("output") / "test.csv"
            html_path = Path("output") / "test.html"
            self.assertTrue(csv_path.exists())
            self.assertTrue(html_path.exists())

    @patch('extractor.console')
    def test_export_with_no_tasks(self, mock_console):
        """Test export with empty task list prints warning."""
        config = ClickUpConfig(
            api_key='test_key',
            workspace_name='Test Workspace',
            space_name='Test Space',
            output_format=OutputFormat.CSV,
            output_path='test.csv'
        )
        extractor = ClickUpTaskExtractor(config, self.client)

        extractor.export([])

        # Should print warning message
        mock_console.print.assert_called()
        warning_call = str(mock_console.print.call_args)
        self.assertIn('No tasks', warning_call)


class TestErrorHandling(unittest.TestCase):
    """Tests for error handling in extractor."""

    def setUp(self):
        """Set up test configuration."""
        self.config = ClickUpConfig(
            api_key='test_key',
            workspace_name='Nonexistent Workspace',
            space_name='Nonexistent Space',
            output_format=OutputFormat.CSV,
            output_path='test.csv'
        )

    @patch('extractor.console')
    def test_workspace_not_found_error(self, mock_console):
        """Test error handling when workspace is not found."""
        client = Mock()
        # Mock the API responses - return empty teams, then empty spaces
        client.get.side_effect = [
            {'teams': []},  # /team endpoint
            {'spaces': []},  # /space endpoint
        ]

        extractor = ClickUpTaskExtractor(self.config, client)

        # Run should handle missing workspace gracefully without raising SystemExit
        # (it will just print a panel and return)
        extractor._fetch_and_process_tasks()

        # Verify that console.print was called (with the error panel)
        self.assertTrue(mock_console.print.called)

    @patch('extractor.sys.exit')
    @patch('extractor.console')
    def test_authentication_error_handling(self, mock_console, mock_exit):
        """Test handling of authentication errors."""
        client = Mock()
        client.get.side_effect = AuthenticationError('Invalid API key')

        extractor = ClickUpTaskExtractor(self.config, client)
        extractor.run()

        # Should call sys.exit(1) on auth error
        mock_exit.assert_called_once_with(1)

    @patch('extractor.sys.exit')
    @patch('extractor.console')
    def test_api_error_handling(self, mock_console, mock_exit):
        """Test handling of general API errors."""
        client = Mock()
        client.get.side_effect = APIError('Network error')

        extractor = ClickUpTaskExtractor(self.config, client)
        extractor.run()

        # Should call sys.exit(1) on API error
        mock_exit.assert_called_once_with(1)


if __name__ == '__main__':
    unittest.main()
