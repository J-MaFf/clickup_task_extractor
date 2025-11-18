#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests for logger_config.py module.

Tests cover:
- setup_logging with Rich enabled
- setup_logging without Rich
- File handler creation
- Console handler configuration
- Logger retrieval
"""

import unittest
from unittest.mock import patch, Mock, MagicMock
import logging
import tempfile
import os
from pathlib import Path

from logger_config import setup_logging, get_logger


class TestSetupLogging(unittest.TestCase):
    """Tests for the setup_logging function."""

    def tearDown(self):
        """Clean up logger handlers after each test."""
        logger = logging.getLogger("clickup_extractor")
        for handler in list(logger.handlers):
            try:
                handler.flush()
            except Exception:
                pass
            handler.close()
            logger.removeHandler(handler)

    def test_setup_logging_returns_logger(self):
        """Test setup_logging returns a Logger instance."""
        logger = setup_logging()

        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "clickup_extractor")

    def test_setup_logging_sets_log_level(self):
        """Test setup_logging sets the correct log level."""
        logger = setup_logging(log_level=logging.DEBUG)

        self.assertEqual(logger.level, logging.DEBUG)

    def test_setup_logging_clears_existing_handlers(self):
        """Test setup_logging clears existing handlers."""
        logger = logging.getLogger("clickup_extractor")

        # Add some handlers
        logger.addHandler(logging.StreamHandler())
        logger.addHandler(logging.StreamHandler())
        initial_count = len(logger.handlers)
        self.assertEqual(initial_count, 2)

        # Setup logging should clear them
        setup_logging()

        # Should have new handler(s) but not the old ones
        self.assertNotEqual(len(logger.handlers), initial_count)

    @patch('logger_config.RICH_AVAILABLE', True)
    @patch('logger_config.RichHandler')
    @patch('logger_config.Console')
    def test_setup_logging_with_rich_enabled(self, mock_console_class, mock_rich_handler_class):
        """Test setup_logging uses Rich handler when available."""
        mock_console = Mock()
        mock_console_class.return_value = mock_console
        mock_handler = Mock()
        mock_rich_handler_class.return_value = mock_handler

        logger = setup_logging(use_rich=True)

        # Should create Console and RichHandler
        mock_console_class.assert_called_once_with(stderr=False)
        mock_rich_handler_class.assert_called_once()

        # Check handler was configured
        mock_handler.setLevel.assert_called_once()

    @patch('logger_config.RICH_AVAILABLE', False)
    def test_setup_logging_without_rich(self):
        """Test setup_logging uses standard handler when Rich unavailable."""
        logger = setup_logging(use_rich=True)  # Even if requested, can't use it

        # Should have at least one handler (standard StreamHandler)
        self.assertGreater(len(logger.handlers), 0)

        # Handler should be StreamHandler, not RichHandler
        handler = logger.handlers[0]
        self.assertIsInstance(handler, logging.StreamHandler)

    def test_setup_logging_with_rich_disabled(self):
        """Test setup_logging with use_rich=False uses standard handler."""
        logger = setup_logging(use_rich=False)

        # Should have standard handler
        self.assertGreater(len(logger.handlers), 0)
        handler = logger.handlers[0]
        self.assertIsInstance(handler, logging.StreamHandler)

    def test_setup_logging_creates_file_handler(self):
        """Test setup_logging creates file handler when log_file specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            logger = setup_logging(log_file=log_file)

            # Should have file handler
            file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
            self.assertEqual(len(file_handlers), 1)

            # File should be created
            self.assertTrue(os.path.exists(log_file))

            for handler in file_handlers:
                handler.flush()
                handler.close()

    def test_setup_logging_creates_parent_directories(self):
        """Test setup_logging creates parent directories for log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'nested', 'subdir', 'test.log')

            logger = setup_logging(log_file=log_file)

            # Parent directories should be created
            self.assertTrue(os.path.exists(os.path.dirname(log_file)))
            self.assertTrue(os.path.exists(log_file))

            for handler in logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    handler.flush()
                    handler.close()

    def test_setup_logging_no_console_output(self):
        """Test setup_logging with console_output=False."""
        logger = setup_logging(console_output=False)

        # Should not have any StreamHandler or RichHandler
        console_handlers = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        self.assertEqual(len(console_handlers), 0)

    def test_setup_logging_file_handler_formatting(self):
        """Test file handler has correct formatter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            logger = setup_logging(log_file=log_file)

            file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
            handler = file_handlers[0]

            # Should have a formatter
            self.assertIsNotNone(handler.formatter)

            # Test formatter format
            formatter = handler.formatter
            self.assertIsInstance(formatter, logging.Formatter)

            handler.flush()
            handler.close()

    def test_setup_logging_file_handler_level(self):
        """Test file handler respects log level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            logger = setup_logging(log_level=logging.WARNING, log_file=log_file)

            file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
            handler = file_handlers[0]

            self.assertEqual(handler.level, logging.WARNING)

            handler.flush()
            handler.close()

    def test_setup_logging_writes_to_file(self):
        """Test logging actually writes to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, 'test.log')

            logger = setup_logging(log_file=log_file, console_output=False)
            logger.info("Test message")

            # Flush handlers
            for handler in logger.handlers:
                handler.flush()

            # Check file contains message
            with open(log_file, 'r') as f:
                content = f.read()
                self.assertIn("Test message", content)

            for handler in logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    handler.flush()
                    handler.close()


class TestGetLogger(unittest.TestCase):
    """Tests for the get_logger function."""

    def test_get_logger_default_name(self):
        """Test get_logger returns default logger."""
        logger = get_logger()

        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "clickup_extractor")

    def test_get_logger_custom_name(self):
        """Test get_logger returns logger with custom name."""
        logger = get_logger("custom_module")

        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.name, "custom_module")

    def test_get_logger_none_returns_default(self):
        """Test get_logger with None returns default logger."""
        logger = get_logger(None)

        self.assertEqual(logger.name, "clickup_extractor")

    def test_get_logger_returns_same_instance(self):
        """Test get_logger returns same instance for same name."""
        logger1 = get_logger("test_module")
        logger2 = get_logger("test_module")

        self.assertIs(logger1, logger2)


class TestRichHandlerConfiguration(unittest.TestCase):
    """Tests for Rich handler configuration."""

    def tearDown(self):
        """Clean up logger handlers after each test."""
        logger = logging.getLogger("clickup_extractor")
        for handler in list(logger.handlers):
            try:
                handler.flush()
            except Exception:
                pass
            handler.close()
            logger.removeHandler(handler)

    @patch('logger_config.RICH_AVAILABLE', True)
    @patch('logger_config.RichHandler')
    @patch('logger_config.Console')
    def test_rich_handler_configuration_parameters(self, mock_console_class, mock_rich_handler_class):
        """Test Rich handler is configured with correct parameters."""
        mock_console = Mock()
        mock_console_class.return_value = mock_console
        mock_handler = Mock()
        mock_rich_handler_class.return_value = mock_handler

        setup_logging(use_rich=True)

        # Check RichHandler was created with correct parameters
        call_kwargs = mock_rich_handler_class.call_args[1]
        self.assertEqual(call_kwargs['console'], mock_console)
        self.assertEqual(call_kwargs['show_time'], False)
        self.assertEqual(call_kwargs['show_path'], False)
        self.assertEqual(call_kwargs['rich_tracebacks'], True)
        self.assertEqual(call_kwargs['markup'], True)
        self.assertEqual(call_kwargs['show_level'], True)

    @patch('logger_config.RICH_AVAILABLE', True)
    @patch('logger_config.RichHandler')
    @patch('logger_config.Console')
    def test_console_uses_stdout(self, mock_console_class, mock_rich_handler_class):
        """Test Rich console uses stdout instead of stderr."""
        mock_console = Mock()
        mock_console_class.return_value = mock_console

        setup_logging(use_rich=True)

        # Console should be created with stderr=False
        mock_console_class.assert_called_once_with(stderr=False)


class TestLogLevels(unittest.TestCase):
    """Tests for different log levels."""

    def tearDown(self):
        """Clean up logger handlers after each test."""
        logger = logging.getLogger("clickup_extractor")
        for handler in list(logger.handlers):
            try:
                handler.flush()
            except Exception:
                pass
            handler.close()
            logger.removeHandler(handler)

    def test_debug_level(self):
        """Test setup with DEBUG level."""
        logger = setup_logging(log_level=logging.DEBUG)
        self.assertEqual(logger.level, logging.DEBUG)

    def test_info_level(self):
        """Test setup with INFO level."""
        logger = setup_logging(log_level=logging.INFO)
        self.assertEqual(logger.level, logging.INFO)

    def test_warning_level(self):
        """Test setup with WARNING level."""
        logger = setup_logging(log_level=logging.WARNING)
        self.assertEqual(logger.level, logging.WARNING)

    def test_error_level(self):
        """Test setup with ERROR level."""
        logger = setup_logging(log_level=logging.ERROR)
        self.assertEqual(logger.level, logging.ERROR)

    def test_critical_level(self):
        """Test setup with CRITICAL level."""
        logger = setup_logging(log_level=logging.CRITICAL)
        self.assertEqual(logger.level, logging.CRITICAL)


if __name__ == '__main__':
    unittest.main()
