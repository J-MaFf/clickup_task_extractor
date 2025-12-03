#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests for api_client.py module.

Tests cover:
- ClickUpAPIClient initialization
- Successful API requests
- Authentication errors (401)
- Shard routing errors (SHARD_* error codes)
- Network errors
- Invalid JSON responses
- Various HTTP error status codes
- Retry logic with exponential backoff
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import requests

from api_client import ClickUpAPIClient, APIError, AuthenticationError, ShardRoutingError


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

        self.assertIn('Network timeout', str(context.exception))
        self.assertIn('accessing', str(context.exception))

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

    @patch('api_client.requests.get')
    @patch('builtins.print')
    def test_shard_routing_error_shard_006(self, mock_print, mock_get):
        """Test 404 with SHARD_006 raises ShardRoutingError."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = '{"err":"Not found","ECODE":"SHARD_006"}'
        mock_response.json.return_value = {'err': 'Not found', 'ECODE': 'SHARD_006'}
        mock_get.return_value = mock_response

        with self.assertRaises(ShardRoutingError) as context:
            self.client.get('/team')

        error_message = str(context.exception).lower()
        self.assertIn('shard_006', error_message)
        self.assertIn('shard routing error', error_message)
        self.assertIn('workspace', error_message)
        self.assertIn('api key', error_message)

    @patch('api_client.requests.get')
    @patch('builtins.print')
    def test_shard_routing_error_generic_shard(self, mock_print, mock_get):
        """Test any SHARD_* error code raises ShardRoutingError."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = '{"err":"Service error","ECODE":"SHARD_999"}'
        mock_response.json.return_value = {'err': 'Service error', 'ECODE': 'SHARD_999'}
        mock_get.return_value = mock_response

        with self.assertRaises(ShardRoutingError) as context:
            self.client.get('/team/123')

        self.assertIn('SHARD_999', str(context.exception))

    @patch('api_client.requests.get')
    @patch('builtins.print')
    def test_non_shard_404_raises_api_error(self, mock_print, mock_get):
        """Test 404 without SHARD error code raises generic APIError."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = '{"err":"Not found","ECODE":"RESOURCE_NOT_FOUND"}'
        mock_response.json.return_value = {'err': 'Not found', 'ECODE': 'RESOURCE_NOT_FOUND'}
        mock_get.return_value = mock_response

        with self.assertRaises(APIError) as context:
            self.client.get('/task/invalid')

        # Should raise generic APIError, not ShardRoutingError
        self.assertNotIsInstance(context.exception, ShardRoutingError)
        self.assertIn('HTTP 404', str(context.exception))


class TestRetryLogic(unittest.TestCase):
    """Tests for exponential backoff retry logic."""

    def setUp(self):
        """Set up test client."""
        self.api_key = 'test_api_key_12345'
        self.client = ClickUpAPIClient(self.api_key)

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    def test_retry_on_502_then_success(self, mock_get, mock_sleep):
        """Test successful retry after 502 Bad Gateway error."""
        # First call returns 502, second call succeeds
        mock_response_502 = Mock()
        mock_response_502.ok = False
        mock_response_502.status_code = 502
        mock_response_502.text = 'Bad Gateway'

        mock_response_success = Mock()
        mock_response_success.ok = True
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'data': 'success'}

        mock_get.side_effect = [mock_response_502, mock_response_success]

        result = self.client.get('/test/endpoint')

        # Verify successful result
        self.assertEqual(result, {'data': 'success'})
        # Verify two requests were made
        self.assertEqual(mock_get.call_count, 2)
        # Verify sleep was called once (for retry)
        self.assertEqual(mock_sleep.call_count, 1)
        # Verify backoff time is reasonable (1s base + jitter)
        self.assertGreaterEqual(mock_sleep.call_args[0][0], 1.0)
        self.assertLessEqual(mock_sleep.call_args[0][0], 1.2)  # 1s + 10% jitter

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    def test_retry_on_503_then_success(self, mock_get, mock_sleep):
        """Test successful retry after 503 Service Unavailable error."""
        mock_response_503 = Mock()
        mock_response_503.ok = False
        mock_response_503.status_code = 503
        mock_response_503.text = 'Service Unavailable'

        mock_response_success = Mock()
        mock_response_success.ok = True
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'data': 'recovered'}

        mock_get.side_effect = [mock_response_503, mock_response_success]

        result = self.client.get('/test/endpoint')

        self.assertEqual(result, {'data': 'recovered'})
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    def test_retry_on_504_then_success(self, mock_get, mock_sleep):
        """Test successful retry after 504 Gateway Timeout error."""
        mock_response_504 = Mock()
        mock_response_504.ok = False
        mock_response_504.status_code = 504
        mock_response_504.text = 'Gateway Timeout'

        mock_response_success = Mock()
        mock_response_success.ok = True
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'data': 'recovered'}

        mock_get.side_effect = [mock_response_504, mock_response_success]

        result = self.client.get('/test/endpoint')

        self.assertEqual(result, {'data': 'recovered'})
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    def test_retry_on_429_then_success(self, mock_get, mock_sleep):
        """Test successful retry after 429 Rate Limit error."""
        mock_response_429 = Mock()
        mock_response_429.ok = False
        mock_response_429.status_code = 429
        mock_response_429.text = 'Rate Limit Exceeded'

        mock_response_success = Mock()
        mock_response_success.ok = True
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'data': 'success_after_rate_limit'}

        mock_get.side_effect = [mock_response_429, mock_response_success]

        result = self.client.get('/test/endpoint')

        self.assertEqual(result, {'data': 'success_after_rate_limit'})
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 1)

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    @patch('builtins.print')
    def test_max_retries_exhausted(self, mock_print, mock_get, mock_sleep):
        """Test that max retries are enforced (3 attempts total)."""
        # All three attempts return 502
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 502
        mock_response.text = 'Bad Gateway'
        mock_response.json.return_value = {'err': 'Bad Gateway'}

        mock_get.return_value = mock_response

        with self.assertRaises(APIError) as context:
            self.client.get('/test/endpoint')

        # Verify all 3 attempts were made
        self.assertEqual(mock_get.call_count, 3)
        # Verify sleep was called 2 times (before 2nd and 3rd attempts)
        self.assertEqual(mock_sleep.call_count, 2)
        self.assertIn('HTTP 502', str(context.exception))

    @patch('api_client.requests.get')
    def test_no_retry_on_401(self, mock_get):
        """Test that 401 errors are not retried."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'

        mock_get.return_value = mock_response

        with self.assertRaises(AuthenticationError):
            self.client.get('/test/endpoint')

        # Verify only 1 request was made (no retries)
        self.assertEqual(mock_get.call_count, 1)

    @patch('api_client.requests.get')
    @patch('builtins.print')
    def test_no_retry_on_404(self, mock_print, mock_get):
        """Test that 404 errors are not retried."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.text = 'Not Found'
        mock_response.json.return_value = {'err': 'Resource not found'}

        mock_get.return_value = mock_response

        with self.assertRaises(APIError):
            self.client.get('/test/endpoint')

        # Verify only 1 request was made (no retries)
        self.assertEqual(mock_get.call_count, 1)

    @patch('api_client.requests.get')
    @patch('builtins.print')
    def test_no_retry_on_400(self, mock_print, mock_get):
        """Test that 400 errors are not retried."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_response.text = 'Bad Request'
        mock_response.json.return_value = {'err': 'Invalid parameters'}

        mock_get.return_value = mock_response

        with self.assertRaises(APIError):
            self.client.get('/test/endpoint')

        # Verify only 1 request was made (no retries)
        self.assertEqual(mock_get.call_count, 1)

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    def test_exponential_backoff_timing(self, mock_get, mock_sleep):
        """Test exponential backoff calculations with jitter."""
        # Mock three 502 responses
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 502
        mock_response.text = 'Bad Gateway'
        mock_response.json.return_value = {'err': 'Bad Gateway'}

        mock_get.return_value = mock_response

        with self.assertRaises(APIError):
            self.client.get('/test/endpoint')

        # Verify sleep was called twice (before 2nd and 3rd attempts)
        self.assertEqual(mock_sleep.call_count, 2)

        # Check first backoff (attempt 0): base = 1s, with jitter
        first_backoff = mock_sleep.call_args_list[0][0][0]
        self.assertGreaterEqual(first_backoff, 1.0)
        self.assertLessEqual(first_backoff, 1.2)  # 1s + 10% jitter = 1.1s, with margin

        # Check second backoff (attempt 1): base = 2s, with jitter
        second_backoff = mock_sleep.call_args_list[1][0][0]
        self.assertGreaterEqual(second_backoff, 2.0)
        self.assertLessEqual(second_backoff, 2.3)  # 2s + 10% jitter = 2.2s, with margin

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    def test_max_backoff_limit(self, mock_get, mock_sleep):
        """Test that backoff is capped at MAX_BACKOFF."""
        # Simulate a scenario where backoff would exceed MAX_BACKOFF
        # MAX_BACKOFF = 30, so with attempt >= 5, backoff would be > 30s
        # We'll test by mocking the _exponential_backoff_with_jitter method
        
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 502
        mock_response.text = 'Bad Gateway'
        mock_response.json.return_value = {'err': 'Bad Gateway'}
        mock_get.return_value = mock_response

        # Test the backoff calculation directly
        backoff_5 = self.client._exponential_backoff_with_jitter(5)
        backoff_10 = self.client._exponential_backoff_with_jitter(10)
        
        # Both should be capped at MAX_BACKOFF (30s) + jitter (10% = 3s)
        self.assertLessEqual(backoff_5, 33)
        self.assertLessEqual(backoff_10, 33)

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    def test_timeout_retry_behavior(self, mock_get, mock_sleep):
        """Test that timeouts are retried with exponential backoff."""
        # First two calls timeout, third succeeds
        mock_response_success = Mock()
        mock_response_success.ok = True
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'data': 'success_after_timeout'}

        mock_get.side_effect = [
            requests.exceptions.Timeout('Request timed out'),
            requests.exceptions.Timeout('Request timed out'),
            mock_response_success
        ]

        result = self.client.get('/test/endpoint')

        self.assertEqual(result, {'data': 'success_after_timeout'})
        # Verify three requests were made
        self.assertEqual(mock_get.call_count, 3)
        # Verify sleep was called twice (before 2nd and 3rd attempts)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    def test_timeout_max_retries(self, mock_get, mock_sleep):
        """Test that timeouts are retried up to max attempts then raise."""
        mock_get.side_effect = requests.exceptions.Timeout('Request timed out')

        with self.assertRaises(APIError) as context:
            self.client.get('/test/endpoint')

        # Verify all 3 attempts were made
        self.assertEqual(mock_get.call_count, 3)
        # Verify sleep was called 2 times (before 2nd and 3rd attempts)
        self.assertEqual(mock_sleep.call_count, 2)
        self.assertIn('Network timeout', str(context.exception))

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    def test_connection_error_retry_behavior(self, mock_get, mock_sleep):
        """Test that connection errors are retried with exponential backoff."""
        # First call fails, second succeeds
        mock_response_success = Mock()
        mock_response_success.ok = True
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'data': 'success_after_connection_error'}

        mock_get.side_effect = [
            requests.exceptions.ConnectionError('Connection refused'),
            mock_response_success
        ]

        result = self.client.get('/test/endpoint')

        self.assertEqual(result, {'data': 'success_after_connection_error'})
        # Verify two requests were made
        self.assertEqual(mock_get.call_count, 2)
        # Verify sleep was called once (before 2nd attempt)
        self.assertEqual(mock_sleep.call_count, 1)

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    def test_connection_error_max_retries(self, mock_get, mock_sleep):
        """Test that connection errors are retried up to max attempts then raise."""
        mock_get.side_effect = requests.exceptions.ConnectionError('Connection refused')

        with self.assertRaises(APIError) as context:
            self.client.get('/test/endpoint')

        # Verify all 3 attempts were made
        self.assertEqual(mock_get.call_count, 3)
        # Verify sleep was called 2 times (before 2nd and 3rd attempts)
        self.assertEqual(mock_sleep.call_count, 2)
        self.assertIn('Network error', str(context.exception))
        self.assertIn('Connection refused', str(context.exception))

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    @patch('api_client.logger')
    def test_retry_logging(self, mock_logger, mock_get, mock_sleep):
        """Test that retry attempts are logged correctly."""
        # First call returns 502, second succeeds
        mock_response_502 = Mock()
        mock_response_502.ok = False
        mock_response_502.status_code = 502
        mock_response_502.text = 'Bad Gateway'

        mock_response_success = Mock()
        mock_response_success.ok = True
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'data': 'success'}

        mock_get.side_effect = [mock_response_502, mock_response_success]

        result = self.client.get('/test/endpoint')

        # Verify logger.warning was called for retry
        self.assertEqual(mock_logger.warning.call_count, 1)
        # Verify the log message contains retry information
        log_message = mock_logger.warning.call_args[0][0]
        self.assertIn('502', log_message)
        self.assertIn('Retrying', log_message)
        self.assertIn('attempt 1/3', log_message)

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    @patch('api_client.logger')
    def test_timeout_retry_logging(self, mock_logger, mock_get, mock_sleep):
        """Test that timeout retries are logged correctly."""
        mock_response_success = Mock()
        mock_response_success.ok = True
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'data': 'success'}

        mock_get.side_effect = [
            requests.exceptions.Timeout('Request timed out'),
            mock_response_success
        ]

        result = self.client.get('/test/endpoint')

        # Verify logger.warning was called for timeout retry
        self.assertEqual(mock_logger.warning.call_count, 1)
        log_message = mock_logger.warning.call_args[0][0]
        self.assertIn('timeout', log_message.lower())
        self.assertIn('Retrying', log_message)
        self.assertIn('attempt 1/3', log_message)

    @patch('api_client.time.sleep')
    @patch('api_client.requests.get')
    @patch('api_client.logger')
    def test_connection_error_retry_logging(self, mock_logger, mock_get, mock_sleep):
        """Test that connection error retries are logged correctly."""
        mock_response_success = Mock()
        mock_response_success.ok = True
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'data': 'success'}

        mock_get.side_effect = [
            requests.exceptions.ConnectionError('Connection refused'),
            mock_response_success
        ]

        result = self.client.get('/test/endpoint')

        # Verify logger.warning was called for connection error retry
        self.assertEqual(mock_logger.warning.call_count, 1)
        log_message = mock_logger.warning.call_args[0][0]
        self.assertIn('Connection error', log_message)
        self.assertIn('Retrying', log_message)
        self.assertIn('attempt 1/3', log_message)


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

    def test_shard_routing_error_inheritance(self):
        """Test ShardRoutingError inherits from APIError."""
        error = ShardRoutingError("Shard routing failed")
        self.assertIsInstance(error, APIError)
        self.assertIsInstance(error, Exception)

    def test_exception_messages(self):
        """Test exception messages are preserved."""
        api_error = APIError("API error message")
        self.assertEqual(str(api_error), "API error message")

        auth_error = AuthenticationError("Auth error message")
        self.assertEqual(str(auth_error), "Auth error message")

        shard_error = ShardRoutingError("Shard routing error message")
        self.assertEqual(str(shard_error), "Shard routing error message")


if __name__ == '__main__':
    unittest.main()
