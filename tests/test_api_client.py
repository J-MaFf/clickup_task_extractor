#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests for api_client.py module.

Tests cover:
- ClickUpAPIClient initialization
- Successful API requests
- Authentication errors (401)
- Network errors
- Invalid JSON responses
- Various HTTP error status codes
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import requests

from api_client import ClickUpAPIClient, APIError, AuthenticationError


class TestClickUpAPIClient(unittest.TestCase):
    """Tests for the ClickUpAPIClient class."""

    def setUp(self):
        """Set up test client."""
        self.api_key = 'test_api_key_12345'
        self.client = ClickUpAPIClient(self.api_key)

    def test_initialization(self):
        """Test client initializes with correct headers."""
        self.assertEqual(self.client.headers['Authorization'], self.api_key)
        self.assertEqual(self.client.headers['Content-Type'], 'application/json')

    @patch('api_client.requests.get')
    def test_successful_get_request(self, mock_get):
        """Test successful GET request returns JSON data."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': 'test_value', 'success': True}
        mock_get.return_value = mock_response

        result = self.client.get('/test/endpoint')

        self.assertEqual(result, {'data': 'test_value', 'success': True})
        mock_get.assert_called_once_with(
            'https://api.clickup.com/api/v2/test/endpoint',
            headers=self.client.headers,
            timeout=30
        )

    @patch('api_client.requests.get')
    def test_authentication_error_401(self, mock_get):
        """Test 401 status raises AuthenticationError."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        mock_get.return_value = mock_response

        with self.assertRaises(AuthenticationError) as context:
            self.client.get('/test/endpoint')

        self.assertIn('API authentication failed', str(context.exception))

    @patch('api_client.requests.get')
    def test_network_error(self, mock_get):
        """Test network errors raise APIError."""
        mock_get.side_effect = requests.exceptions.ConnectionError('Connection refused')

        with self.assertRaises(APIError) as context:
            self.client.get('/test/endpoint')

        self.assertIn('Network error', str(context.exception))
        self.assertIn('Connection refused', str(context.exception))

    @patch('api_client.requests.get')
    def test_timeout_error(self, mock_get):
        """Test timeout raises APIError."""
        mock_get.side_effect = requests.exceptions.Timeout('Request timed out')

        with self.assertRaises(APIError) as context:
            self.client.get('/test/endpoint')

        self.assertIn('Network error', str(context.exception))
        self.assertIn('timed out', str(context.exception))

    @patch('api_client.requests.get')
    def test_invalid_json_response(self, mock_get):
        """Test invalid JSON response raises APIError."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError('Invalid JSON')
        mock_get.return_value = mock_response

        with self.assertRaises(APIError) as context:
            self.client.get('/test/endpoint')

        self.assertIn('Invalid JSON response', str(context.exception))

    @patch('api_client.requests.get')
    @patch('builtins.print')
    def test_http_400_error(self, mock_print, mock_get):
        """Test 400 Bad Request raises APIError."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = 'Bad Request'
        mock_response.json.return_value = {'err': 'Invalid parameters'}
        mock_get.return_value = mock_response

        with self.assertRaises(APIError) as context:
            self.client.get('/test/endpoint')

        self.assertIn('HTTP 400', str(context.exception))

    @patch('api_client.requests.get')
    @patch('builtins.print')
    def test_http_404_error(self, mock_print, mock_get):
        """Test 404 Not Found raises APIError."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = 'Not Found'
        mock_response.json.return_value = {'err': 'Resource not found'}
        mock_get.return_value = mock_response

        with self.assertRaises(APIError) as context:
            self.client.get('/test/endpoint')

        self.assertIn('HTTP 404', str(context.exception))

    @patch('api_client.requests.get')
    @patch('builtins.print')
    def test_http_429_rate_limit(self, mock_print, mock_get):
        """Test 429 Rate Limit raises APIError."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 429
        mock_response.text = 'Rate limit exceeded'
        mock_response.json.return_value = {'err': 'Too many requests'}
        mock_get.return_value = mock_response

        with self.assertRaises(APIError) as context:
            self.client.get('/test/endpoint')

        self.assertIn('HTTP 429', str(context.exception))

    @patch('api_client.requests.get')
    @patch('builtins.print')
    def test_http_500_server_error(self, mock_print, mock_get):
        """Test 500 Internal Server Error raises APIError."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_response.json.side_effect = Exception('Cannot parse JSON')
        mock_get.return_value = mock_response

        with self.assertRaises(APIError) as context:
            self.client.get('/test/endpoint')

        self.assertIn('HTTP 500', str(context.exception))

    @patch('api_client.requests.get')
    @patch('builtins.print')
    def test_error_message_includes_url_and_status(self, mock_print, mock_get):
        """Test error messages include URL and status code."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 403
        mock_response.text = 'Forbidden'
        mock_response.json.return_value = {'err': 'Access denied'}
        mock_get.return_value = mock_response

        with self.assertRaises(APIError):
            self.client.get('/secure/endpoint')

        # Verify print was called with error details
        mock_print.assert_called_once()
        printed_message = mock_print.call_args[0][0]
        self.assertIn('API Request failed', printed_message)
        self.assertIn('403', printed_message)
        self.assertIn('/secure/endpoint', printed_message)

    @patch('api_client.requests.get')
    def test_request_exception_handling(self, mock_get):
        """Test various request exceptions are handled properly."""
        exceptions = [
            requests.exceptions.ConnectTimeout('Connection timeout'),
            requests.exceptions.ReadTimeout('Read timeout'),
            requests.exceptions.TooManyRedirects('Too many redirects'),
        ]

        for exc in exceptions:
            with self.subTest(exception=exc):
                mock_get.side_effect = exc
                with self.assertRaises(APIError):
                    self.client.get('/test/endpoint')

    @patch('api_client.requests.get')
    def test_base_url_construction(self, mock_get):
        """Test that base URL is correctly constructed."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        self.client.get('/workspaces')

        expected_url = 'https://api.clickup.com/api/v2/workspaces'
        actual_url = mock_get.call_args[0][0]
        self.assertEqual(actual_url, expected_url)

    @patch('api_client.requests.get')
    def test_timeout_is_set(self, mock_get):
        """Test that timeout is set on requests."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        self.client.get('/test')

        # Verify timeout parameter was passed
        self.assertEqual(mock_get.call_args[1]['timeout'], 30)


class TestAPIErrorExceptions(unittest.TestCase):
    """Tests for custom exception classes."""

    def test_api_error_inheritance(self):
        """Test APIError inherits from Exception."""
        error = APIError("Test error")
        self.assertIsInstance(error, Exception)

    def test_authentication_error_inheritance(self):
        """Test AuthenticationError inherits from APIError."""
        error = AuthenticationError("Auth failed")
        self.assertIsInstance(error, APIError)
        self.assertIsInstance(error, Exception)

    def test_exception_messages(self):
        """Test exception messages are preserved."""
        api_error = APIError("API error message")
        self.assertEqual(str(api_error), "API error message")

        auth_error = AuthenticationError("Auth error message")
        self.assertEqual(str(auth_error), "Auth error message")


if __name__ == '__main__':
    unittest.main()
