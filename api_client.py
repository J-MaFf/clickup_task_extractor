#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ClickUp API Client Module

Contains:
- APIClient protocol for structural typing
- ClickUpAPIClient class for HTTP API interactions
- Error handling and debugging for API requests
"""

import requests
from typing import Any, Protocol


class APIError(Exception):
    """Base exception for API-related errors."""
    pass


class AuthenticationError(APIError):
    """Raised when API authentication fails."""
    pass


class APIClient(Protocol):
    """Protocol defining the interface for API clients."""

    def get(self, endpoint: str) -> Any:
        """Make a GET request to the API endpoint."""
        ...


class ClickUpAPIClient:
    """HTTP client for ClickUp API v2 with error handling and debugging."""

    BASE_URL = 'https://api.clickup.com/api/v2'

    def __init__(self, api_key: str) -> None:
        """
        Initialize the ClickUp API client.

        Args:
            api_key: ClickUp API key for authentication
        """
        self.headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json'
        }

    def get(self, endpoint: str) -> Any:
        """
        Make a GET request to the ClickUp API.

        Args:
            endpoint: API endpoint (without base URL)

        Returns:
            JSON response from the API

        Raises:
            AuthenticationError: If API key is invalid or expired
            APIError: If the request fails for other reasons
        """
        url = f"{self.BASE_URL}{endpoint}"

        try:
            resp = requests.get(url, headers=self.headers, timeout=30)
        except requests.exceptions.RequestException as e:
            raise APIError(f"Network error while accessing {url}: {e}") from e

        # Handle authentication errors specifically
        if resp.status_code == 401:
            raise AuthenticationError(
                "API authentication failed. Please check your ClickUp API key."
            )

        # Add debugging information for other failed requests
        if not resp.ok:
            error_msg = f"API Request failed:\n  URL: {url}\n  Status: {resp.status_code}"
            try:
                error_detail = resp.json().get('err', resp.text)
                error_msg += f"\n  Error: {error_detail}"
            except Exception:
                error_msg += f"\n  Response: {resp.text}"

            print(error_msg)
            raise APIError(f"HTTP {resp.status_code}: {resp.text}")

        try:
            return resp.json()
        except ValueError as e:
            raise APIError(f"Invalid JSON response from {url}: {e}") from e