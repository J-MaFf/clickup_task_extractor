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


def setup_logging(
    log_level: int = logging.INFO,
    log_file: str | Path | None = None,
    console_output: bool = True
) -> logging.Logger:
    """
    Set up logging configuration for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        console_output: Whether to output logs to console

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logging(logging.DEBUG, "app.log")
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

    # Console handler
    if console_output:
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
