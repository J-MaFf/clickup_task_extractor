#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ClickUp API Client Module

Contains:
- ClickUpAPIClient class for HTTP API interactions
- Error handling and debugging for API requests
"""

import requests
from typing import Any


class ClickUpAPIClient:
    """HTTP client for ClickUp API v2 with error handling and debugging."""
    
    BASE_URL = 'https://api.clickup.com/api/v2'

    def __init__(self, api_key: str):
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
            requests.HTTPError: If the request fails
        """
        url = f"{self.BASE_URL}{endpoint}"
        resp = requests.get(url, headers=self.headers)

        # Add debugging information for failed requests
        if not resp.ok:
            print(f"API Request failed:")
            print(f"  URL: {url}")
            print(f"  Status: {resp.status_code}")
            print(f"  Response: {resp.text}")

        resp.raise_for_status()
        return resp.json()