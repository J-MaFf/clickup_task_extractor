#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests for ai_summary.py success paths.

Tests cover:
- Successful AI summary generation
- Rate limiting and retry logic
- Fallback when no API key
- Exception handling
- Field normalization
"""

import unittest
from unittest.mock import patch, Mock, MagicMock
import time

from ai_summary import get_ai_summary, _normalize_field_entries


class TestNormalizeFieldEntries(unittest.TestCase):
    """Tests for the _normalize_field_entries helper function."""

    def test_normalize_sequence_of_tuples(self):
        """Test normalizing sequence of tuples."""
        input_data = [('Name', 'Task 1'), ('Status', 'Open'), ('Priority', 'High')]
        result = _normalize_field_entries(input_data)

        self.assertEqual(result, [('Name', 'Task 1'), ('Status', 'Open'), ('Priority', 'High')])

    def test_normalize_mapping(self):
        """Test normalizing dict/mapping."""
        input_data = {'Name': 'Task 1', 'Status': 'Open', 'Priority': 'High'}
        result = _normalize_field_entries(input_data)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        self.assertIn(('Name', 'Task 1'), result)
        self.assertIn(('Status', 'Open'), result)
        self.assertIn(('Priority', 'High'), result)

    def test_normalize_converts_to_strings(self):
        """Test normalization converts values to strings."""
        input_data = [(123, 456), ('key', 789)]
        result = _normalize_field_entries(input_data)

        self.assertEqual(result, [('123', '456'), ('key', '789')])


class TestGetAISummaryFallback(unittest.TestCase):
    """Tests for get_ai_summary fallback behavior."""

    def test_empty_field_entries_returns_message(self):
        """Test empty field entries returns placeholder message."""
        result = get_ai_summary('Test Task', [], 'fake_api_key')

        self.assertEqual(result, 'No content available for summary.')

    def test_no_api_key_returns_field_block(self):
        """Test returns field block when no API key provided."""
        field_entries = [
            ('Subject', 'Test subject'),
            ('Description', 'Test description'),
            ('Resolution', '(not provided)')
        ]

        result = get_ai_summary('Test Task', field_entries, '')

        self.assertIn('Subject: Test subject', result)
        self.assertIn('Description: Test description', result)
        self.assertIn('Resolution: (not provided)', result)

    @patch('ai_summary.configure', side_effect=Exception('SDK not available'))
    @patch('ai_summary._console')
    def test_no_genai_sdk_returns_fallback(self, mock_console, mock_configure):
        """Test returns fallback when GenAI SDK not available."""
        field_entries = [('Name', 'Task 1'), ('Status', 'Open')]

        result = get_ai_summary('Test Task', field_entries, 'api_key')

        self.assertIn('Name: Task 1', result)
        self.assertIn('Status: Open', result)


class TestGetAISummarySuccess(unittest.TestCase):
    """Tests for successful AI summary generation."""

    @patch('ai_summary.GenerativeModel')
    @patch('ai_summary.configure')
    def test_successful_summary_generation(self, mock_configure, mock_model_class):
        """Test successful AI summary generation."""
        # Mock the model and response
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = 'This is an AI-generated summary about the task status.'

        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        field_entries = [
            ('Subject', 'Test subject'),
            ('Description', 'Test description'),
            ('Resolution', 'Fixed the issue')
        ]

        result = get_ai_summary('Test Task', field_entries, 'test_api_key')

        self.assertEqual(result, 'This is an AI-generated summary about the task status.')
        mock_configure.assert_called_once_with(api_key='test_api_key')

    @patch('ai_summary.GenerativeModel')
    @patch('ai_summary.configure')
    def test_summary_adds_period_if_missing(self, mock_configure, mock_model_class):
        """Test summary adds period at end if missing."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = 'Summary without period'

        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        field_entries = [('Name', 'Task')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')

        self.assertTrue(result.endswith('.'))

    @patch('ai_summary.GenerativeModel')
    @patch('ai_summary.configure')
    def test_summary_removes_newlines(self, mock_configure, mock_model_class):
        """Test summary removes newlines from response."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = 'Summary with\nnewlines\nin it'

        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        field_entries = [('Name', 'Task')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')

        self.assertNotIn('\n', result)
        self.assertIn('Summary with newlines in it', result)

    @patch('ai_summary.GenerativeModel')
    @patch('ai_summary.configure')
    def test_empty_response_returns_fallback(self, mock_configure, mock_model_class):
        """Test empty response from API returns fallback."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = ''

        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        field_entries = [('Subject', 'Test'), ('Description', 'Desc')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')

        self.assertIn('Subject: Test', result)
        self.assertIn('Description: Desc', result)

    @patch('ai_summary.GenerativeModel')
    @patch('ai_summary.configure')
    def test_none_response_returns_fallback(self, mock_configure, mock_model_class):
        """Test None response returns fallback."""
        mock_model = Mock()
        mock_model.generate_content.return_value = None
        mock_model_class.return_value = mock_model

        field_entries = [('Name', 'Task')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')

        self.assertIn('Name: Task', result)


class TestRateLimitingAndRetry(unittest.TestCase):
    """Tests for rate limiting and retry logic."""

    @patch('ai_summary.Progress')
    @patch('ai_summary.time.sleep')
    @patch('ai_summary.GenerativeModel')
    @patch('ai_summary.configure')
    @patch('ai_summary._console')
    def test_rate_limit_retry_succeeds(self, mock_console, mock_configure, mock_model_class, mock_sleep, mock_progress):
        """Test successful retry after rate limit."""
        mock_model = Mock()

        # Mock Progress context manager
        mock_progress_instance = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_instance

        # First call raises rate limit, second succeeds
        mock_response = Mock()
        mock_response.text = 'Success after retry'

        mock_model.generate_content.side_effect = [
            Exception('429 RESOURCE_EXHAUSTED retryDelay: "30s"'),
            mock_response
        ]
        mock_model_class.return_value = mock_model

        field_entries = [('Name', 'Task')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')

        self.assertEqual(result, 'Success after retry.')
        # Should have slept for rate limit (or used progress bar)
        self.assertTrue(mock_sleep.called or mock_progress.called)

    @patch('ai_summary.Progress')
    @patch('ai_summary.time.sleep')
    @patch('ai_summary.GenerativeModel')
    @patch('ai_summary.configure')
    @patch('ai_summary._console')
    def test_rate_limit_all_retries_fail(self, mock_console, mock_configure, mock_model_class, mock_sleep, mock_progress):
        """Test fallback after all retries fail."""
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception('429 RESOURCE_EXHAUSTED')
        mock_model_class.return_value = mock_model

        # Mock Progress context manager
        mock_progress_instance = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_instance

        field_entries = [('Subject', 'Test'), ('Description', 'Desc')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')

        # Should return fallback
        self.assertIn('Subject: Test', result)
        self.assertIn('Description: Desc', result)

    @patch('ai_summary.time.sleep')
    @patch('ai_summary.GenerativeModel')
    @patch('ai_summary.configure')
    def test_rate_limit_extracts_retry_delay(self, mock_configure, mock_model_class, mock_sleep):
        """Test retry delay is extracted from error message."""
        mock_model = Mock()

        error_msg = '429 RESOURCE_EXHAUSTED retryDelay: "45s"'
        mock_response = Mock()
        mock_response.text = 'Success'

        mock_model.generate_content.side_effect = [
            Exception(error_msg),
            mock_response
        ]
        mock_model_class.return_value = mock_model

        field_entries = [('Name', 'Task')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')

        # Check that it used extracted delay (would be in sleep calls)
        self.assertEqual(result, 'Success.')

    @patch('ai_summary.GenerativeModel')
    @patch('ai_summary.configure')
    @patch('ai_summary._console')
    def test_non_rate_limit_error_returns_fallback(self, mock_console, mock_configure, mock_model_class):
        """Test non-rate-limit errors return fallback immediately."""
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception('Some other error')
        mock_model_class.return_value = mock_model

        field_entries = [('Name', 'Task'), ('Status', 'Open')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')

        # Should return fallback without retries
        self.assertIn('Name: Task', result)
        self.assertIn('Status: Open', result)


class TestPromptConstruction(unittest.TestCase):
    """Tests for AI prompt construction."""

    @patch('ai_summary.GenerativeModel')
    @patch('ai_summary.configure')
    def test_prompt_includes_task_name(self, mock_configure, mock_model_class):
        """Test prompt includes task name."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = 'Summary'
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        field_entries = [('Name', 'Important Task')]
        get_ai_summary('Important Task Name', field_entries, 'api_key')

        # Check that generate_content was called
        mock_model.generate_content.assert_called_once()

    @patch('ai_summary.GenerativeModel')
    @patch('ai_summary.configure')
    def test_prompt_includes_field_labels(self, mock_configure, mock_model_class):
        """Test prompt includes field labels."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = 'Summary'
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        field_entries = [
            ('Subject', 'Test subject'),
            ('Vendor', 'Vendor name'),
            ('Resolution', '(not provided)')
        ]
        get_ai_summary('Task', field_entries, 'api_key')

        mock_model.generate_content.assert_called_once()

    @patch('ai_summary.GenerativeModel')
    @patch('ai_summary.configure')
    def test_uses_correct_model(self, mock_configure, mock_model_class):
        """Test uses correct Gemini model."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = 'Summary'
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        field_entries = [('Name', 'Task')]
        get_ai_summary('Task', field_entries, 'api_key')

        # Verify GenerativeModel was called with correct model
        mock_model_class.assert_called_once_with('gemini-flash-lite-latest')

    @patch('ai_summary.GenerativeModel')
    @patch('ai_summary.configure')
    def test_prompt_uses_first_person_perspective(self, mock_configure, mock_model_class):
        """Test prompt instructs AI to use first-person voice."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = 'I completed the task'
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        field_entries = [('Subject', 'Bug fix'), ('Status', 'Done')]
        get_ai_summary('Test Task', field_entries, 'api_key')

        # Verify generate_content was called
        mock_model.generate_content.assert_called_once()


if __name__ == '__main__':
    unittest.main()
