#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Logging Configuration Module for ClickUp Task Extractor

Contains:
- Logger setup and configuration
- Console and file logging handlers
- Log formatting utilities
"""

import logging
import sys
from pathlib import Path
from typing import TextIO

# Rich imports for enhanced logging
try:
    from rich.logging import RichHandler
    from rich.console import Console
    from rich.traceback import install
    RICH_AVAILABLE = True

    # Install rich tracebacks for beautiful error displays
    install(show_locals=True, suppress=["logging"])
except ImportError:
    RICH_AVAILABLE = False
    RichHandler = None
    Console = None


def setup_logging(
    log_level: int = logging.INFO,
    log_file: str | Path | None = None,
    console_output: bool = True,
    use_rich: bool = True
) -> logging.Logger:
    """
    Set up logging configuration for the application with Rich integration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        console_output: Whether to output logs to console
        use_rich: Whether to use Rich handler for beautiful console output

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logging(logging.DEBUG, "app.log", use_rich=True)
        >>> logger.info("Application started")
    """
    # Create logger
    logger = logging.getLogger("clickup_extractor")
    logger.setLevel(log_level)

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler with Rich integration
    if console_output:
        if use_rich and RICH_AVAILABLE and RichHandler and Console:
            # Use Rich handler for beautiful console output with proper encoding for cross-platform compatibility
            rich_console = Console(
                stderr=False,  # Use stdout instead of stderr
                force_terminal=None,
                legacy_windows=False  # Ensure proper Unicode support on Windows
            )
            console_handler = RichHandler(
                console=rich_console,
                show_time=False,  # Rich handles time formatting
                show_path=False,  # Don't show file paths in console
                rich_tracebacks=True,
                markup=True,  # Allow Rich markup in log messages
                show_level=True
            )
            # Rich handler doesn't need our custom formatter
            console_handler.setLevel(log_level)
        else:
            # Fallback to standard handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (defaults to "clickup_extractor")

    Returns:
        Logger instance
    """
    return logging.getLogger(name or "clickup_extractor")
