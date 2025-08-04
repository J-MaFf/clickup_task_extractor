#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Authentication and Security Module for ClickUp Task Extractor

Contains:
- 1Password SDK/CLI integration functions
- API key retrieval with fallback methods
- Secure credential management
"""

import os
import asyncio
import subprocess
from typing import TypeAlias

# Import logging infrastructure
from logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

# Type aliases for clarity
SecretValue: TypeAlias = str | None

# 1Password SDK imports with PyInstaller compatibility
OnePasswordClient = None
try:
    # Only import if not running as PyInstaller executable
    import sys
    if not getattr(sys, 'frozen', False):
        from onepassword.client import Client as OnePasswordClient
    else:
        logger.info("Running as executable - 1Password SDK disabled, using CLI fallback only")
except ImportError:
    pass  # Will use CLI fallback


def _load_secret_with_fallback(secret_reference: str, secret_name: str) -> SecretValue:
    """
    Generic function to load a secret from 1Password using SDK with CLI fallback.

    Args:
        secret_reference: The 1Password secret reference
        secret_name: Human-readable name for the secret (for error messages)

    Returns:
        The secret string if successful, None if failed
    """
    # Try 1Password SDK first
    try:
        secret = get_secret_from_1password(secret_reference, secret_name)
        logger.info(f"✅ {secret_name} loaded from 1Password SDK.")
        return secret
    except ImportError as e:
        logger.warning(f"1Password SDK not available for {secret_name}: {e}")
        logger.info(f"Falling back to 1Password CLI for {secret_name}...")
        # Fallback to 1Password CLI
        try:
            secret = subprocess.check_output([
                'op', 'read', secret_reference
            ], encoding='utf-8').strip()
            logger.info(f"✅ {secret_name} loaded from 1Password CLI.")
            return secret
        except Exception as cli_error:
            logger.error(f"Could not read {secret_name} from 1Password CLI: {cli_error}")
            return None
    except Exception as e:
        logger.error(f"Could not read {secret_name} from 1Password SDK: {e}")
        return None


def get_secret_from_1password(secret_reference: str, secret_type: str = "API key") -> SecretValue:
    """
    Retrieve a secret from 1Password using the SDK.

    Args:
        secret_reference: The 1Password secret reference (e.g., "op://Home Server/ClickUp personal API token/credential")
        secret_type: Description of the secret type for error messages (default: "API key")

    Returns:
        The secret string if successful, None if failed

    Raises:
        Various exceptions for different failure modes (network, auth, not found, etc.)
    """
    if OnePasswordClient is None:
        raise ImportError("1Password SDK not available. Install with: pip install onepassword-sdk")

    # Get service account token from environment
    service_token = os.environ.get('OP_SERVICE_ACCOUNT_TOKEN')
    if not service_token:
        raise ValueError("OP_SERVICE_ACCOUNT_TOKEN environment variable not set. Required for 1Password SDK authentication.")

    try:
        async def _get_secret():
            # Ensure OnePasswordClient is not None before using it
            if OnePasswordClient is None:
                raise ImportError("1Password SDK not available. Install with: pip install onepassword-sdk")
            # Authenticate with 1Password using service account token
            client = await OnePasswordClient.authenticate(
                auth=service_token,
                integration_name="ClickUp Task Extractor",
                integration_version="1.0.0"
            )

            # Resolve the secret reference to get the secret
            secret = await client.secrets.resolve(secret_reference)

            if not secret:
                raise ValueError(f"Secret reference '{secret_reference}' resolved to empty value")

            return secret.strip()

        # Run the async function
        return asyncio.run(_get_secret())

    except Exception as e:
        # Re-raise with more context
        error_msg = f"Failed to retrieve {secret_type} from 1Password: {type(e).__name__}: {e}"
        raise RuntimeError(error_msg) from e


def get_api_key_from_1password(secret_reference: str) -> SecretValue:
    """
    Retrieve ClickUp API key from 1Password using the SDK.

    Args:
        secret_reference: The 1Password secret reference (e.g., "op://Home Server/ClickUp personal API token/credential")

    Returns:
        The API key string if successful, None if failed

    Raises:
        Various exceptions for different failure modes (network, auth, not found, etc.)
    """
    return get_secret_from_1password(secret_reference, "ClickUp API key")


def get_gemini_api_key_from_1password(secret_reference: str) -> SecretValue:
    """
    Retrieve Gemini API key from 1Password using the SDK.

    Args:
        secret_reference: The 1Password secret reference (e.g., "op://Home Server/nftoo3gsi3wpx7z5bdmcsvr7p4/credential")

    Returns:
        The Gemini API key string if successful, None if failed

    Raises:
        Various exceptions for different failure modes (network, auth, not found, etc.)
    """
    return get_secret_from_1password(secret_reference, "Gemini API key")