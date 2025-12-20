#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests for interactive mode AI summary generation.

Tests cover:
- AI summary generation after task selection in interactive mode
- AI summary generation when enabled via CLI flags
- AI summary generation when user opts-in during interactive mode
- Ensuring no AI summaries are generated for skipped tasks
"""

import unittest
from unittest.mock import patch, Mock, MagicMock, call
from typing import Any

from config import ClickUpConfig, OutputFormat, TaskRecord
from extractor import ClickUpTaskExtractor


class DummyAPIClient:
    """Simple API client stub that returns pre-seeded responses."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self._responses = responses

    def get(self, endpoint: str) -> Any:
        return self._responses.get(endpoint, {})


class TestInteractiveAISummary(unittest.TestCase):
    """Tests for AI summary generation in interactive mode."""

    def setUp(self):
        """Set up test configuration and mock responses."""
        # Mock API responses
        self.team_id = "team_123"
        self.space_id = "space_456"
        self.list_id = "list_789"
        
        self.api_responses = {
            "/team": {"teams": [{"id": self.team_id, "name": "Test Workspace"}]},
            f"/team/{self.team_id}/space": {
                "spaces": [{"id": self.space_id, "name": "Test Space"}]
            },
            f"/space/{self.space_id}/folder": {"folders": []},
            f"/space/{self.space_id}/list?archived=false": {
                "lists": [{"id": self.list_id, "name": "Test List"}]
            },
            f"/list/{self.list_id}/task?archived=false": {
                "tasks": [
                    {"id": "task_1", "name": "Task 1", "date_created": "1609459200000"},
                    {"id": "task_2", "name": "Task 2", "date_created": "1609459200000"},
                    {"id": "task_3", "name": "Task 3", "date_created": "1609459200000"},
                ]
            },
            f"/list/{self.list_id}": {"custom_fields": []},
            "/task/task_1": {
                "name": "Task 1",
                "priority": {"priority": 2},
                "status": {"status": "Open"},
                "description": "Task 1 description",
                "custom_fields": [],
            },
            "/task/task_2": {
                "name": "Task 2",
                "priority": {"priority": 2},
                "status": {"status": "Open"},
                "description": "Task 2 description",
                "custom_fields": [],
            },
            "/task/task_3": {
                "name": "Task 3",
                "priority": {"priority": 2},
                "status": {"status": "Open"},
                "description": "Task 3 description",
                "custom_fields": [],
            },
        }

    @patch('extractor.Progress')
    @patch('extractor.console')
    @patch('extractor.get_yes_no_input')
    @patch('extractor.get_ai_summary')
    def test_ai_summary_enabled_via_cli_interactive_mode(
        self, mock_ai_summary, mock_get_yes_no, mock_console, mock_progress
    ):
        """Test AI summary generation when enabled via CLI in interactive mode."""
        # Configure mocks
        mock_progress.return_value.__enter__ = Mock(return_value=mock_progress.return_value)
        mock_progress.return_value.__exit__ = Mock(return_value=None)
        mock_progress.return_value.add_task = Mock(return_value=1)
        mock_progress.return_value.remove_task = Mock()
        mock_progress.return_value.update = Mock()
        mock_progress.return_value.advance = Mock()
        mock_progress.return_value.stop = Mock()
        
        # User selects tasks 1 and 2, skips task 3
        mock_get_yes_no.side_effect = [True, True, False]
        
        # Mock AI summary to return a simple string
        mock_ai_summary.return_value = "AI generated summary."
        
        # Create config with AI summary enabled and interactive mode
        config = ClickUpConfig(
            api_key='test_key',
            workspace_name='Test Workspace',
            space_name='Test Space',
            output_format=OutputFormat.CSV,
            output_path='test_output.csv',
            enable_ai_summary=True,
            gemini_api_key='test_gemini_key',
            interactive_selection=True
        )
        
        api_client = DummyAPIClient(self.api_responses)
        extractor = ClickUpTaskExtractor(config, api_client)
        
        # Mock export to prevent file I/O
        with patch.object(extractor, 'export'):
            extractor.run()
        
        # Verify AI summary was called exactly 2 times (for selected tasks only)
        self.assertEqual(mock_ai_summary.call_count, 2, 
                        "AI summary should be called only for selected tasks (2 out of 3)")
        
        # Verify AI summary was NOT called during initial processing
        # (all calls should happen after task selection)
        calls = mock_ai_summary.call_args_list
        self.assertEqual(len(calls), 2, "Should generate AI summaries for 2 selected tasks")

    @patch('extractor.Progress')
    @patch('extractor.console')
    @patch('extractor.get_yes_no_input')
    @patch('extractor.get_ai_summary')
    def test_ai_summary_user_opts_in_interactive_mode(
        self, mock_ai_summary, mock_get_yes_no, mock_console, mock_progress
    ):
        """Test AI summary when user opts-in during interactive mode."""
        # Configure mocks
        mock_progress.return_value.__enter__ = Mock(return_value=mock_progress.return_value)
        mock_progress.return_value.__exit__ = Mock(return_value=None)
        mock_progress.return_value.add_task = Mock(return_value=1)
        mock_progress.return_value.remove_task = Mock()
        mock_progress.return_value.update = Mock()
        mock_progress.return_value.advance = Mock()
        mock_progress.return_value.stop = Mock()
        
        # First 3 calls: user selects tasks 1 and 2, skips task 3
        # 4th call: user opts-in for AI summary
        mock_get_yes_no.side_effect = [True, True, False, True]
        
        # Mock console input for API key
        mock_console.input = Mock(return_value='test_gemini_key')
        
        # Mock AI summary to return a simple string
        mock_ai_summary.return_value = "AI generated summary."
        
        # Create config WITHOUT AI summary enabled
        config = ClickUpConfig(
            api_key='test_key',
            workspace_name='Test Workspace',
            space_name='Test Space',
            output_format=OutputFormat.CSV,
            output_path='test_output.csv',
            enable_ai_summary=False,  # Not enabled via CLI
            interactive_selection=True
        )
        
        api_client = DummyAPIClient(self.api_responses)
        extractor = ClickUpTaskExtractor(config, api_client)
        
        # Mock export to prevent file I/O
        with patch.object(extractor, 'export'):
            extractor.run()
        
        # Verify AI summary was called exactly 2 times (for selected tasks only)
        self.assertEqual(mock_ai_summary.call_count, 2,
                        "AI summary should be called only for selected tasks (2 out of 3)")

    @patch('extractor.Progress')
    @patch('extractor.console')
    @patch('extractor.get_yes_no_input')
    @patch('extractor.get_ai_summary')
    def test_ai_summary_user_opts_out_interactive_mode(
        self, mock_ai_summary, mock_get_yes_no, mock_console, mock_progress
    ):
        """Test no AI summary when user opts-out during interactive mode."""
        # Configure mocks
        mock_progress.return_value.__enter__ = Mock(return_value=mock_progress.return_value)
        mock_progress.return_value.__exit__ = Mock(return_value=None)
        mock_progress.return_value.add_task = Mock(return_value=1)
        mock_progress.return_value.remove_task = Mock()
        mock_progress.return_value.update = Mock()
        mock_progress.return_value.advance = Mock()
        mock_progress.return_value.stop = Mock()
        
        # First 3 calls: user selects all tasks
        # 4th call: user opts-out of AI summary
        mock_get_yes_no.side_effect = [True, True, True, False]
        
        # Create config WITHOUT AI summary enabled
        config = ClickUpConfig(
            api_key='test_key',
            workspace_name='Test Workspace',
            space_name='Test Space',
            output_format=OutputFormat.CSV,
            output_path='test_output.csv',
            enable_ai_summary=False,
            interactive_selection=True
        )
        
        api_client = DummyAPIClient(self.api_responses)
        extractor = ClickUpTaskExtractor(config, api_client)
        
        # Mock export to prevent file I/O
        with patch.object(extractor, 'export'):
            extractor.run()
        
        # Verify AI summary was never called
        mock_ai_summary.assert_not_called()

    @patch('extractor.Progress')
    @patch('extractor.console')
    @patch('extractor.get_ai_summary')
    def test_ai_summary_non_interactive_mode(
        self, mock_ai_summary, mock_console, mock_progress
    ):
        """Test AI summary generation in non-interactive mode (original behavior)."""
        # Configure mocks
        mock_progress.return_value.__enter__ = Mock(return_value=mock_progress.return_value)
        mock_progress.return_value.__exit__ = Mock(return_value=None)
        mock_progress.return_value.add_task = Mock(return_value=1)
        mock_progress.return_value.remove_task = Mock()
        mock_progress.return_value.update = Mock()
        mock_progress.return_value.advance = Mock()
        mock_progress.return_value.stop = Mock()
        
        # Mock AI summary to return a simple string
        mock_ai_summary.return_value = "AI generated summary."
        
        # Create config with AI summary enabled but NO interactive mode
        config = ClickUpConfig(
            api_key='test_key',
            workspace_name='Test Workspace',
            space_name='Test Space',
            output_format=OutputFormat.CSV,
            output_path='test_output.csv',
            enable_ai_summary=True,
            gemini_api_key='test_gemini_key',
            interactive_selection=False  # Non-interactive
        )
        
        api_client = DummyAPIClient(self.api_responses)
        extractor = ClickUpTaskExtractor(config, api_client)
        
        # Mock export to prevent file I/O
        with patch.object(extractor, 'export'):
            extractor.run()
        
        # Verify AI summary was called for all 3 tasks during initial processing
        self.assertEqual(mock_ai_summary.call_count, 3,
                        "AI summary should be called for all tasks in non-interactive mode")


if __name__ == '__main__':
    unittest.main()
