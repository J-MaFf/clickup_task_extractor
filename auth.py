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
import re
from typing import TypeAlias

# Import logging infrastructure
from logger_config import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

# Type aliases for clarity
SecretValue: TypeAlias = str | None

# 1Password SDK imports with PyInstaller compatibility
OnePasswordClient = None
OnePasswordDesktopAuth = None
try:
    # Only import if not running as PyInstaller executable
    import sys

    if not getattr(sys, "frozen", False):
        from onepassword import (
            Client as OnePasswordClient,
            DesktopAuth as OnePasswordDesktopAuth,
        )
    else:
        logger.info(
            "Running as executable - 1Password SDK disabled, using CLI fallback only"
        )
except ImportError:
    pass  # Will use CLI fallback


def get_secret_from_environment(
    environment_id: str, var_name: str, secret_name: str
) -> SecretValue:
    """
    Retrieve a secret from a 1Password Environment variable.

    Attempts to read from 1Password Environment using SDK first, then
    falls back to 1Password CLI using `op environment read`.

    Args:
        environment_id: The 1Password Environment ID (e.g., 'blgexucrwfr2dtsxe2q4uu7dp4')
        var_name: The environment variable name within the Environment (e.g., 'CLICKUP_API_KEY')
        secret_name: Human-readable name for the secret (for error messages)

    Returns:
        The secret string if successful, None if failed
    """
    # Try 1Password SDK first. Prefer DesktopAuth for local development, then
    # fall back to a service account token for automation.
    if OnePasswordClient is not None:
        try:
            explicit_account_name = os.environ.get("OP_ACCOUNT_NAME")
            service_token = os.environ.get("OP_SERVICE_ACCOUNT_TOKEN")

            account_candidates: list[str | None] = []
            if explicit_account_name:
                account_candidates.append(explicit_account_name)
            else:
                # Local desktop integration often maps to the account currently signed in
                # to the 1Password app. Try the common account URLs first.
                account_candidates.extend(
                    ["my.1password.com", "kmsservice.1password.com"]
                )

            if OnePasswordDesktopAuth is not None:
                for account_name in account_candidates:
                    try:
                        logger.debug(
                            f"Attempting to load {secret_name} from 1Password Environment (SDK/DesktopAuth: {account_name or 'default'}) - ID: {environment_id}"
                        )

                        async def _get_env_var_desktop():
                            client = await OnePasswordClient.authenticate(
                                auth=OnePasswordDesktopAuth(account_name),
                                integration_name="ClickUp Task Extractor",
                                integration_version="1.0.0",
                            )
                            response = await client.environments.get_variables(
                                environment_id
                            )
                            for var in response.variables:
                                if var.name == var_name:
                                    return var.value.strip() if var.value else None
                            return None

                        secret = asyncio.run(_get_env_var_desktop())
                        if secret:
                            logger.info(
                                f"✅ {secret_name} loaded from 1Password Environment (SDK/DesktopAuth: {account_name or 'default'})."
                            )
                            return secret
                    except Exception as auth_error:
                        logger.debug(
                            f"DesktopAuth failed for account '{account_name or 'default'}' while reading {secret_name}: {auth_error}"
                        )

            if service_token:
                logger.debug(
                    f"Attempting to load {secret_name} from 1Password Environment (SDK/service account token) - ID: {environment_id}"
                )

                async def _get_env_var_service_account():
                    client = await OnePasswordClient.authenticate(
                        auth=service_token,
                        integration_name="ClickUp Task Extractor",
                        integration_version="1.0.0",
                    )
                    response = await client.environments.get_variables(environment_id)
                    for var in response.variables:
                        if var.name == var_name:
                            return var.value.strip() if var.value else None
                    return None

                secret = asyncio.run(_get_env_var_service_account())
                if secret:
                    logger.info(
                        f"✅ {secret_name} loaded from 1Password Environment (SDK/service account token)."
                    )
                    return secret
                logger.debug(
                    f"Variable '{var_name}' not found in 1Password Environment {environment_id}"
                )
        except Exception as e:
            logger.debug(f"Could not read from 1Password Environment via SDK: {e}")

    # CLI fallback for environments (critical for executable builds where SDK is
    # disabled, and for SDK failures in Python mode).
    try:
        logger.debug(
            f"Attempting to load {secret_name} from 1Password Environment via CLI - ID: {environment_id}"
        )
        result = subprocess.run(
            ["op", "environment", "read", environment_id],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            output = result.stdout
            # Support common output styles:
            # KEY=value
            # export KEY=value
            # KEY="value with spaces"
            pattern = re.compile(
                rf"^\s*(?:export\s+)?{re.escape(var_name)}\s*=\s*(.*)\s*$",
                re.MULTILINE,
            )
            match = pattern.search(output)
            if match:
                raw_value = match.group(1).strip()
                if (
                    len(raw_value) >= 2
                    and raw_value[0] == raw_value[-1]
                    and raw_value[0] in {'"', "'"}
                ):
                    raw_value = raw_value[1:-1]

                secret = raw_value.strip()
                if secret:
                    logger.info(
                        f"✅ {secret_name} loaded from 1Password Environment (CLI)."
                    )
                    return secret

            logger.debug(
                f"Variable '{var_name}' not found in 1Password Environment CLI output for {environment_id}"
            )
        else:
            logger.debug(
                f"1Password Environment CLI read failed for {secret_name}: {result.stderr.strip()}"
            )
    except FileNotFoundError:
        logger.debug(
            "1Password CLI ('op' command) not found while reading Environment variable"
        )
    except subprocess.TimeoutExpired:
        logger.debug(f"1Password Environment CLI timed out while reading {secret_name}")
    except Exception as cli_error:
        logger.debug(f"Could not read from 1Password Environment via CLI: {cli_error}")

    return None


def load_secret_with_fallback(secret_reference: str, secret_name: str) -> SecretValue:
    """
    Generic function to load a secret from 1Password using multiple fallback methods.

    Fallback chain (in order):
    1. 1Password Environment (if OP_ENVIRONMENT_ID is set) - SDK then CLI
    2. 1Password SDK secret references (if OP_SERVICE_ACCOUNT_TOKEN is set)
    3. 1Password CLI secret references (requires 'op' command)
    4. None if all methods fail

    Args:
        secret_reference: The 1Password secret reference for vault-based lookups
                         (e.g., 'op://Home Server/ClickUp personal API token/credential')
        secret_name: Human-readable name for the secret (for error messages)

    Returns:
        The secret string if successful, None if failed
    """
    import sys

    is_frozen = getattr(sys, "frozen", False)

    # **NEW**: Try 1Password Environment first (if OP_ENVIRONMENT_ID is set)
    environment_id = os.environ.get("OP_ENVIRONMENT_ID")
    if environment_id:
        # Determine the variable name based on secret_name
        # Map common secret names to environment variable names
        env_var_map = {
            "ClickUp API key": "CLICKUP_API_KEY",
            "Gemini API key": "GEMINI_API_KEY",
        }
        var_name = env_var_map.get(secret_name, secret_name.replace(" ", "_").upper())

        logger.debug(
            f"OP_ENVIRONMENT_ID detected, attempting to load {secret_name} from Environment..."
        )
        secret = get_secret_from_environment(environment_id, var_name, secret_name)
        if secret:
            return secret
        # If Environment method fails, do not fall through to the old vault-based
        # secret references. That path is intentionally avoided when an Environment
        # ID is configured because it points at the legacy broken setup.
        logger.debug(
            f"Could not load {secret_name} from 1Password Environment. Skipping vault-based fallback because OP_ENVIRONMENT_ID is set."
        )
        return None

    # Try 1Password SDK first (only available for Python, not EXE)
    try:
        secret = get_secret_from_1password(secret_reference, secret_name)
        logger.info(f"✅ {secret_name} loaded from 1Password SDK.")
        return secret
    except (ImportError, ValueError) as e:
        # SDK not available or not configured - this is expected for most users
        if is_frozen:
            logger.info(
                f"1Password SDK not available in executable - trying 1Password CLI for {secret_name}..."
            )
        else:
            logger.debug(
                f"1Password SDK not available for {secret_name} (will try CLI): {e}"
            )
            logger.info(f"Falling back to 1Password CLI for {secret_name}...")

        # Fallback to 1Password CLI
        try:
            # First, try without specifying account
            result = subprocess.run(
                ["op", "read", secret_reference],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                secret = result.stdout.strip()
                logger.info(f"✅ {secret_name} loaded from 1Password CLI.")
                return secret
            elif "multiple accounts" in result.stderr.lower():
                # Multiple accounts error - try with personal account
                logger.debug(
                    "Multiple 1Password accounts detected, trying personal account (my.1password.com)..."
                )
                result = subprocess.run(
                    ["op", "read", secret_reference, "--account", "my.1password.com"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    secret = result.stdout.strip()
                    logger.info(
                        f"✅ {secret_name} loaded from 1Password CLI (personal account)."
                    )
                    return secret
                else:
                    logger.error(
                        f"❌ 1Password CLI failed with personal account for {secret_name}: {result.stderr.strip()}"
                    )
                    return None
            else:
                # Different error
                logger.error(
                    f"❌ 1Password CLI failed for {secret_name}: {result.stderr.strip()}"
                )
                return None
        except FileNotFoundError:
            # CLI not installed
            if is_frozen:
                logger.error(
                    "❌ 1Password CLI not found. When using the executable, you have two options:\n"
                    "   1. Install 1Password CLI from: https://developer.1password.com/docs/cli/get-started/\n"
                    "   2. Use environment variables (e.g., CLICKUP_API_KEY) or --api-key argument"
                )
            else:
                logger.error(
                    "❌ 1Password CLI ('op' command) not found.\n"
                    "   Install from: https://developer.1password.com/docs/cli/get-started/\n"
                    "   Or use environment variables/command line arguments instead."
                )
            return None
        except subprocess.TimeoutExpired:
            logger.error(
                f"❌ 1Password CLI timed out while reading {secret_name}. Check your 1Password setup."
            )
            return None
        except Exception as cli_error:
            logger.error(
                f"❌ Could not read {secret_name} from 1Password CLI: {cli_error}"
            )
            if is_frozen:
                logger.info(
                    "💡 Tip: For executables, use environment variables (e.g., CLICKUP_API_KEY) "
                    "or the --api-key argument instead."
                )
            return None
    except Exception as e:
        logger.error(f"Could not read {secret_name} from 1Password SDK: {e}")
        return None


def get_secret_from_1password(
    secret_reference: str, secret_type: str = "API key"
) -> SecretValue:
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
        raise ImportError(
            "1Password SDK not available. Install with: pip install onepassword-sdk"
        )

    # Get service account token from environment
    service_token = os.environ.get("OP_SERVICE_ACCOUNT_TOKEN")
    if not service_token:
        raise ValueError(
            "OP_SERVICE_ACCOUNT_TOKEN environment variable not set. Required for 1Password SDK authentication."
        )

    try:

        async def _get_secret():
            # Ensure OnePasswordClient is not None before using it
            if OnePasswordClient is None:
                raise ImportError(
                    "1Password SDK not available. Install with: pip install onepassword-sdk"
                )
            # Authenticate with 1Password using service account token
            client = await OnePasswordClient.authenticate(
                auth=service_token,
                integration_name="ClickUp Task Extractor",
                integration_version="1.0.0",
            )

            # Resolve the secret reference to get the secret
            secret = await client.secrets.resolve(secret_reference)

            if not secret:
                raise ValueError(
                    f"Secret reference '{secret_reference}' resolved to empty value"
                )

            return secret.strip()

        # Run the async function
        return asyncio.run(_get_secret())

    except Exception as e:
        # Re-raise with more context
        error_msg = (
            f"Failed to retrieve {secret_type} from 1Password: {type(e).__name__}: {e}"
        )
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


# Backward compatibility aliases for old naming
def load_gemini_api_key_from_environment():
    """
    Helper to load Gemini API key from 1Password Environment.
    Uses load_secret_with_fallback which checks OP_ENVIRONMENT_ID automatically.
    """
    gemini_secret_reference = "op://Home Server/nftoo3gsi3wpx7z5bdmcsvr7p4/credential"
    return load_secret_with_fallback(gemini_secret_reference, "Gemini API key")
