#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Integration Module for ClickUp Task Extractor

Contains:
- AI summary generation using Google Gemini API
- Rate limiting and retry logic
- Progress bar functionality for wait times
"""

import re
import time
from typing import TypeAlias

# Type aliases for clarity
SummaryResult: TypeAlias = str

# Google GenAI SDK imports
try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None


def get_ai_summary(task_name: str, subject: str, description: str, resolution: str, gemini_api_key: str) -> SummaryResult:
    """
    Generate a concise 1-2 sentence summary about the current status of the task using Google Gemini AI.
    Automatically handles rate limiting with intelligent retry logic.

    Args:
        task_name: Name of the task
        subject: Subject field content
        description: Description field content
        resolution: Resolution field content
        gemini_api_key: Google Gemini API key for authentication

    Returns:
        AI-generated summary or original content if AI fails
    """
    if not gemini_api_key:
        return f"Subject: {subject}\nDescription: {description}\nResolution: {resolution}".strip()

    # Check if Google GenAI SDK is available
    if genai is None:
        print("Warning: Google GenAI SDK not available - install with: pip install google-genai")
        return f"Subject: {subject}\nDescription: {description}\nResolution: {resolution}".strip()

    max_retries = 3
    base_delay = 30  # Increased base delay to 30 seconds for rate limiting

    for attempt in range(max_retries + 1):
        try:
            # Initialize the Google GenAI client
            client = genai.Client(api_key=gemini_api_key)

            # Prepare the content for AI analysis
            content_parts = []
            if subject:
                content_parts.append(f"Subject: {subject}")
            if description:
                content_parts.append(f"Description: {description}")
            if resolution:
                content_parts.append(f"Resolution: {resolution}")

            if not content_parts:
                return "No content available for summary."

            full_content = "\n".join(content_parts)

            # Create the prompt for AI summary
            prompt = f"""Please provide a concise 1-2 sentence summary of the current status of this task using the Subject, Description, and Resolution fields:

Task: {task_name}

{full_content}

Focus on the current state and what has been done or needs to be done. Be specific and actionable."""

            # Use the official Google GenAI SDK with proper configuration
            if genai_types:
                config = genai_types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=150,
                    response_mime_type="text/plain"
                )
            else:
                config = None

            response = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt,
                config=config
            )

            if response and hasattr(response, 'text') and response.text:
                summary = response.text.strip()

                # Clean up the summary
                summary = summary.replace('\n', ' ').strip()
                if not summary.endswith('.'):
                    summary += '.'

                return summary
            else:
                print(f"Warning: No text response from Gemini API for task: {task_name}")
                return f"Subject: {subject}\nDescription: {description}\nResolution: {resolution}".strip()

        except Exception as e:
            error_str = str(e)

            # Check if this is a rate limit error
            if "429" in error_str and "RESOURCE_EXHAUSTED" in error_str:
                # Extract retry delay from error message if available
                retry_delay = base_delay
                try:
                    # Try to parse the retry delay from the error message
                    if "retryDelay" in error_str:
                        # Look for patterns like '"retryDelay": "20s"'
                        delay_match = re.search(r'"retryDelay":\s*"(\d+)s"', error_str)
                        if delay_match:
                            retry_delay = int(delay_match.group(1))
                        else:
                            # Fallback: extract quota value and calculate delay
                            quota_match = re.search(r'"quotaValue":\s*"(\d+)"', error_str)
                            if quota_match:
                                quota_value = int(quota_match.group(1))
                                # Calculate delay based on quota (60 seconds / quota = delay per request)
                                retry_delay = max(60 // quota_value, base_delay)
                except (ValueError, AttributeError, TypeError) as e:
                    # If parsing fails, use exponential backoff
                    retry_delay = base_delay * (2 ** attempt)

                if attempt < max_retries:
                    print(f"⏳ Rate limit hit for task '{task_name}'. Waiting {retry_delay} seconds before retry (attempt {attempt + 1}/{max_retries})...")

                    # Progress bar for wait time
                    def show_progress_bar(total_seconds):
                        """Display a progress bar showing remaining wait time."""
                        bar_length = 50
                        for i in range(total_seconds):
                            remaining = total_seconds - i
                            elapsed = i
                            progress = elapsed / total_seconds
                            filled_length = int(bar_length * progress)

                            # Create progress bar
                            bar = '█' * filled_length + '░' * (bar_length - filled_length)

                            # Format time display
                            mins, secs = divmod(remaining, 60)
                            time_str = f"{mins:02d}:{secs:02d}" if mins > 0 else f"{secs:02d}s"

                            # Print progress (carriage return to overwrite)
                            print(f"\r  ⏱️  [{bar}] {elapsed}/{total_seconds}s - {time_str} remaining", end='', flush=True)
                            time.sleep(1)

                        # Clear the progress line and show completion
                        print(f"\r  ✅  Wait complete - retrying API call...{' ' * 20}")

                    show_progress_bar(retry_delay)
                    continue
                else:
                    print(f"❌ Rate limit retry failed for task '{task_name}' after {max_retries} attempts.")

            else:
                # Non-rate-limit error
                print(f"AI Summary error for task '{task_name}': {e}")

            # Final attempt failed or non-retryable error - return fallback
            return f"Subject: {subject}\nDescription: {description}\nResolution: {resolution}".strip()

    # Should never reach here, but just in case
    return f"Subject: {subject}\nDescription: {description}\nResolution: {resolution}".strip()