#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests for ETA Calculator module.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from eta_calculator import calculate_eta, _get_fallback_eta, PRIORITY_ETA_DAYS


class ETACalculatorFallbackTests(unittest.TestCase):
    """Tests for fallback ETA calculation based on priority and status."""

    def test_urgent_priority_calculates_1_day(self) -> None:
        """Urgent tasks should have 1-day ETA."""
        eta = _get_fallback_eta("Urgent", "to do")
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        expected_date = datetime.now() + timedelta(days=1)
        self.assertEqual(eta_date.date(), expected_date.date())

    def test_high_priority_calculates_3_days(self) -> None:
        """High priority tasks should have 3-day ETA."""
        eta = _get_fallback_eta("High", "to do")
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        expected_date = datetime.now() + timedelta(days=3)
        self.assertEqual(eta_date.date(), expected_date.date())

    def test_normal_priority_calculates_7_days(self) -> None:
        """Normal priority tasks should have 7-day ETA."""
        eta = _get_fallback_eta("Normal", "to do")
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        expected_date = datetime.now() + timedelta(days=7)
        self.assertEqual(eta_date.date(), expected_date.date())

    def test_low_priority_calculates_14_days(self) -> None:
        """Low priority tasks should have 14-day ETA."""
        eta = _get_fallback_eta("Low", "to do")
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        expected_date = datetime.now() + timedelta(days=14)
        self.assertEqual(eta_date.date(), expected_date.date())

    def test_in_progress_status_reduces_eta(self) -> None:
        """Tasks in progress should have reduced ETA (50% of base)."""
        eta = _get_fallback_eta("Normal", "in progress")
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        # Normal is 7 days, in progress multiplier is 0.5, so 3-4 days
        expected_date = datetime.now() + timedelta(days=3)
        self.assertEqual(eta_date.date(), expected_date.date())

    def test_investigating_status_slightly_reduces_eta(self) -> None:
        """Tasks being investigated should have slightly reduced ETA (75% of base)."""
        eta = _get_fallback_eta("Normal", "investigating")
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        # Normal is 7 days, investigating multiplier is 0.75, so 5 days
        expected_date = datetime.now() + timedelta(days=5)
        self.assertEqual(eta_date.date(), expected_date.date())

    def test_empty_priority_defaults_to_7_days(self) -> None:
        """Empty priority should default to 7 days."""
        eta = _get_fallback_eta("", "to do")
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        expected_date = datetime.now() + timedelta(days=7)
        self.assertEqual(eta_date.date(), expected_date.date())

    def test_unknown_status_uses_default_multiplier(self) -> None:
        """Unknown status should use default multiplier of 1.0."""
        eta = _get_fallback_eta("Normal", "unknown status")
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        expected_date = datetime.now() + timedelta(days=7)
        self.assertEqual(eta_date.date(), expected_date.date())

    def test_eta_date_format(self) -> None:
        """ETA should be in MM/DD/YYYY format."""
        eta = _get_fallback_eta("Normal", "to do")
        # Should be parseable as MM/DD/YYYY
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        self.assertIsInstance(eta_date, datetime)


class ETACalculatorIntegrationTests(unittest.TestCase):
    """Integration tests for calculate_eta function."""

    def test_calculate_eta_without_ai(self) -> None:
        """Test ETA calculation without AI (fallback only)."""
        eta = calculate_eta(
            task_name="Test Task",
            priority="High",
            status="to do",
            enable_ai=False,
        )
        # Should get fallback ETA
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        expected_date = datetime.now() + timedelta(days=3)  # High priority = 3 days
        self.assertEqual(eta_date.date(), expected_date.date())

    def test_calculate_eta_with_ai_disabled(self) -> None:
        """Test that AI calculation is skipped when enable_ai=False."""
        eta = calculate_eta(
            task_name="Test Task",
            priority="Normal",
            status="to do",
            description="Test description",
            subject="Test subject",
            gemini_api_key="fake_key",
            enable_ai=False,  # AI disabled
        )
        # Should use fallback even with API key
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        expected_date = datetime.now() + timedelta(days=7)
        self.assertEqual(eta_date.date(), expected_date.date())

    def test_calculate_eta_without_gemini_key(self) -> None:
        """Test fallback when no Gemini API key is provided."""
        eta = calculate_eta(
            task_name="Test Task",
            priority="Urgent",
            status="in progress",
            enable_ai=True,
            gemini_api_key=None,  # No API key
        )
        # Should use fallback
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        # Urgent = 1 day, in progress = 0.5x, so 0 -> minimum 1 day
        expected_date = datetime.now() + timedelta(days=1)
        self.assertEqual(eta_date.date(), expected_date.date())

    @patch("eta_calculator.types")
    @patch("eta_calculator.GenerativeModel")
    @patch("eta_calculator.configure")
    def test_calculate_eta_with_ai_success(
        self, mock_configure: MagicMock, mock_model_class: MagicMock, mock_types: MagicMock
    ) -> None:
        """Test successful AI-based ETA calculation."""
        # Mock AI response
        mock_response = MagicMock()
        mock_response.text = "12/25/2025"
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        # Mock types.GenerationConfig
        mock_types.GenerationConfig = MagicMock()

        eta = calculate_eta(
            task_name="Test Task",
            priority="High",
            status="to do",
            description="Complex issue requiring investigation",
            subject="Server outage",
            resolution="Need to replace hardware",
            gemini_api_key="valid_key",
            enable_ai=True,
        )

        # Should return AI-generated ETA
        self.assertEqual(eta, "12/25/2025")
        mock_configure.assert_called_once_with(api_key="valid_key")
        mock_model.generate_content.assert_called_once()

    @patch("eta_calculator.types")
    @patch("eta_calculator.GenerativeModel")
    @patch("eta_calculator.configure")
    def test_calculate_eta_with_ai_failure_falls_back(
        self, mock_configure: MagicMock, mock_model_class: MagicMock, mock_types: MagicMock
    ) -> None:
        """Test that fallback is used when AI fails."""
        # Mock AI failure
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API Error")
        mock_model_class.return_value = mock_model
        mock_types.GenerationConfig = MagicMock()

        eta = calculate_eta(
            task_name="Test Task",
            priority="Normal",
            status="to do",
            description="Test description",
            gemini_api_key="valid_key",
            enable_ai=True,
        )

        # Should fall back to priority-based calculation
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        expected_date = datetime.now() + timedelta(days=7)
        self.assertEqual(eta_date.date(), expected_date.date())

    @patch("eta_calculator.types")
    @patch("eta_calculator.GenerativeModel")
    @patch("eta_calculator.configure")
    def test_calculate_eta_with_invalid_ai_response(
        self, mock_configure: MagicMock, mock_model_class: MagicMock, mock_types: MagicMock
    ) -> None:
        """Test fallback when AI returns invalid date format."""
        # Mock AI response with invalid format
        mock_response = MagicMock()
        mock_response.text = "invalid response text"
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        mock_types.GenerationConfig = MagicMock()

        eta = calculate_eta(
            task_name="Test Task",
            priority="High",
            status="to do",
            gemini_api_key="valid_key",
            enable_ai=True,
        )

        # Should fall back to priority-based calculation
        eta_date = datetime.strptime(eta, "%m/%d/%Y")
        expected_date = datetime.now() + timedelta(days=3)
        self.assertEqual(eta_date.date(), expected_date.date())


if __name__ == "__main__":
    unittest.main()
