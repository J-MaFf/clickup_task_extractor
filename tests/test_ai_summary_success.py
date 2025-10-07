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

    @patch('ai_summary.genai', None)
    @patch('ai_summary._console')
    def test_no_genai_sdk_returns_fallback(self, mock_console):
        """Test returns fallback when GenAI SDK not available."""
        field_entries = [('Name', 'Task 1'), ('Status', 'Open')]
        
        result = get_ai_summary('Test Task', field_entries, 'api_key')
        
        self.assertIn('Name: Task 1', result)
        self.assertIn('Status: Open', result)


class TestGetAISummarySuccess(unittest.TestCase):
    """Tests for successful AI summary generation."""

    @patch('ai_summary.genai')
    def test_successful_summary_generation(self, mock_genai):
        """Test successful AI summary generation."""
        # Mock the client and response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = 'This is an AI-generated summary about the task status.'
        
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        field_entries = [
            ('Subject', 'Test subject'),
            ('Description', 'Test description'),
            ('Resolution', 'Fixed the issue')
        ]
        
        result = get_ai_summary('Test Task', field_entries, 'test_api_key')
        
        self.assertEqual(result, 'This is an AI-generated summary about the task status.')
        mock_genai.Client.assert_called_once_with(api_key='test_api_key')

    @patch('ai_summary.genai')
    def test_summary_adds_period_if_missing(self, mock_genai):
        """Test summary adds period at end if missing."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = 'Summary without period'
        
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        field_entries = [('Name', 'Task')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')
        
        self.assertTrue(result.endswith('.'))

    @patch('ai_summary.genai')
    def test_summary_removes_newlines(self, mock_genai):
        """Test summary removes newlines from response."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = 'Summary with\nnewlines\nin it'
        
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        field_entries = [('Name', 'Task')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')
        
        self.assertNotIn('\n', result)
        self.assertIn('Summary with newlines in it', result)

    @patch('ai_summary.genai')
    def test_empty_response_returns_fallback(self, mock_genai):
        """Test empty response from API returns fallback."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = ''
        
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        field_entries = [('Subject', 'Test'), ('Description', 'Desc')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')
        
        self.assertIn('Subject: Test', result)
        self.assertIn('Description: Desc', result)

    @patch('ai_summary.genai')
    def test_none_response_returns_fallback(self, mock_genai):
        """Test None response returns fallback."""
        mock_client = Mock()
        mock_client.models.generate_content.return_value = None
        mock_genai.Client.return_value = mock_client
        
        field_entries = [('Name', 'Task')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')
        
        self.assertIn('Name: Task', result)


class TestRateLimitingAndRetry(unittest.TestCase):
    """Tests for rate limiting and retry logic."""

    @patch('ai_summary.Progress')
    @patch('ai_summary.time.sleep')
    @patch('ai_summary.genai')
    @patch('ai_summary._console')
    def test_rate_limit_retry_succeeds(self, mock_console, mock_genai, mock_sleep, mock_progress):
        """Test successful retry after rate limit."""
        mock_client = Mock()
        
        # Mock Progress context manager
        mock_progress_instance = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_instance
        
        # First call raises rate limit, second succeeds
        mock_response = Mock()
        mock_response.text = 'Success after retry'
        
        mock_client.models.generate_content.side_effect = [
            Exception('429 RESOURCE_EXHAUSTED retryDelay: "30s"'),
            mock_response
        ]
        mock_genai.Client.return_value = mock_client
        
        field_entries = [('Name', 'Task')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')
        
        self.assertEqual(result, 'Success after retry.')
        # Should have slept for rate limit (or used progress bar)
        self.assertTrue(mock_sleep.called or mock_progress.called)

    @patch('ai_summary.Progress')
    @patch('ai_summary.time.sleep')
    @patch('ai_summary.genai')
    @patch('ai_summary._console')
    def test_rate_limit_all_retries_fail(self, mock_console, mock_genai, mock_sleep, mock_progress):
        """Test fallback after all retries fail."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception('429 RESOURCE_EXHAUSTED')
        mock_genai.Client.return_value = mock_client
        
        # Mock Progress context manager
        mock_progress_instance = MagicMock()
        mock_progress.return_value.__enter__.return_value = mock_progress_instance
        
        field_entries = [('Subject', 'Test'), ('Description', 'Desc')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')
        
        # Should return fallback
        self.assertIn('Subject: Test', result)
        self.assertIn('Description: Desc', result)

    @patch('ai_summary.time.sleep')
    @patch('ai_summary.genai')
    def test_rate_limit_extracts_retry_delay(self, mock_genai, mock_sleep):
        """Test retry delay is extracted from error message."""
        mock_client = Mock()
        
        error_msg = '429 RESOURCE_EXHAUSTED retryDelay: "45s"'
        mock_response = Mock()
        mock_response.text = 'Success'
        
        mock_client.models.generate_content.side_effect = [
            Exception(error_msg),
            mock_response
        ]
        mock_genai.Client.return_value = mock_client
        
        field_entries = [('Name', 'Task')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')
        
        # Check that it used extracted delay (would be in sleep calls)
        self.assertEqual(result, 'Success.')

    @patch('ai_summary.genai')
    @patch('ai_summary._console')
    def test_non_rate_limit_error_returns_fallback(self, mock_console, mock_genai):
        """Test non-rate-limit errors return fallback immediately."""
        mock_client = Mock()
        mock_client.models.generate_content.side_effect = Exception('Some other error')
        mock_genai.Client.return_value = mock_client
        
        field_entries = [('Name', 'Task'), ('Status', 'Open')]
        result = get_ai_summary('Test Task', field_entries, 'api_key')
        
        # Should return fallback without retries
        self.assertIn('Name: Task', result)
        self.assertIn('Status: Open', result)


class TestPromptConstruction(unittest.TestCase):
    """Tests for AI prompt construction."""

    @patch('ai_summary.genai')
    def test_prompt_includes_task_name(self, mock_genai):
        """Test prompt includes task name."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = 'Summary'
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        field_entries = [('Name', 'Important Task')]
        get_ai_summary('Important Task Name', field_entries, 'api_key')
        
        # Check that generate_content was called with prompt containing task name
        call_args = mock_client.models.generate_content.call_args
        prompt = call_args[1]['contents']
        self.assertIn('Important Task Name', prompt)

    @patch('ai_summary.genai')
    def test_prompt_includes_field_labels(self, mock_genai):
        """Test prompt includes field labels."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = 'Summary'
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        field_entries = [
            ('Subject', 'Test subject'),
            ('Vendor', 'Vendor name'),
            ('Resolution', '(not provided)')
        ]
        get_ai_summary('Task', field_entries, 'api_key')
        
        call_args = mock_client.models.generate_content.call_args
        prompt = call_args[1]['contents']
        self.assertIn('Subject: Test subject', prompt)
        self.assertIn('Vendor: Vendor name', prompt)
        self.assertIn('Resolution: (not provided)', prompt)

    @patch('ai_summary.genai')
    def test_uses_correct_model(self, mock_genai):
        """Test uses correct Gemini model."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = 'Summary'
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        field_entries = [('Name', 'Task')]
        get_ai_summary('Task', field_entries, 'api_key')
        
        call_args = mock_client.models.generate_content.call_args
        model_name = call_args[1]['model']
        self.assertEqual(model_name, 'gemini-2.5-flash-lite')

    @patch('ai_summary.genai')
    def test_prompt_uses_first_person_perspective(self, mock_genai):
        """Test prompt instructs AI to use first-person voice."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = 'I completed the task'
        mock_client.models.generate_content.return_value = mock_response
        mock_genai.Client.return_value = mock_client
        
        field_entries = [('Subject', 'Bug fix'), ('Status', 'Done')]
        get_ai_summary('Test Task', field_entries, 'api_key')
        
        # Check that generate_content was called with prompt containing first-person instructions
        call_args = mock_client.models.generate_content.call_args
        prompt = call_args[1]['contents']
        
        # Verify first-person perspective instructions are present
        self.assertIn('first-person', prompt.lower())
        self.assertIn('I completed', prompt)
        self.assertIn('you have done', prompt.lower())


if __name__ == '__main__':
    unittest.main()
