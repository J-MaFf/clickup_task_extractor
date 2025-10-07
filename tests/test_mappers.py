#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests for mappers.py module.

Tests cover:
- get_date_range function with different filter options
- extract_images function with various image patterns
- LocationMapper.map_location with different matching strategies
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from io import StringIO

from config import DateFilter
from mappers import get_date_range, extract_images, LocationMapper, get_yes_no_input


class TestGetDateRange(unittest.TestCase):
    """Tests for the get_date_range function."""

    def test_this_week_with_enum(self):
        """Test ThisWeek filter returns correct date range using enum."""
        start, end = get_date_range(DateFilter.THIS_WEEK)
        
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        
        # Verify it's actually this week
        today = datetime.now()
        expected_start = today - timedelta(days=today.weekday())
        expected_end = expected_start + timedelta(days=6)
        
        # Compare dates only (ignore time)
        self.assertEqual(start.date(), expected_start.date())
        self.assertEqual(end.date(), expected_end.date())

    def test_this_week_with_string(self):
        """Test ThisWeek filter returns correct date range using string."""
        start, end = get_date_range('ThisWeek')
        
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        
        # Verify week span is 7 days
        delta = end - start
        self.assertEqual(delta.days, 6)

    def test_last_week_with_enum(self):
        """Test LastWeek filter returns correct date range using enum."""
        start, end = get_date_range(DateFilter.LAST_WEEK)
        
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        
        # Verify it's actually last week
        today = datetime.now()
        expected_start = today - timedelta(days=today.weekday() + 7)
        expected_end = expected_start + timedelta(days=6)
        
        # Compare dates only (ignore time)
        self.assertEqual(start.date(), expected_start.date())
        self.assertEqual(end.date(), expected_end.date())

    def test_last_week_with_string(self):
        """Test LastWeek filter returns correct date range using string."""
        start, end = get_date_range('LastWeek')
        
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        
        # Verify week span is 7 days
        delta = end - start
        self.assertEqual(delta.days, 6)

    def test_all_open_returns_none(self):
        """Test AllOpen filter returns (None, None)."""
        start, end = get_date_range(DateFilter.ALL_OPEN)
        
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_invalid_filter_returns_none(self):
        """Test invalid filter returns (None, None)."""
        start, end = get_date_range('InvalidFilter')
        
        self.assertIsNone(start)
        self.assertIsNone(end)


class TestExtractImages(unittest.TestCase):
    """Tests for the extract_images function."""

    def test_empty_text_returns_empty_string(self):
        """Test empty text returns empty string."""
        result = extract_images('')
        self.assertEqual(result, '')

    def test_none_text_returns_empty_string(self):
        """Test None text returns empty string."""
        result = extract_images(None)
        self.assertEqual(result, '')

    def test_markdown_image_syntax(self):
        """Test extraction of markdown image syntax."""
        text = 'Check this image: ![alt text](https://example.com/image.png)'
        result = extract_images(text)
        
        self.assertIn('![alt text](https://example.com/image.png)', result)

    def test_html_img_tag(self):
        """Test extraction of HTML img tags."""
        text = 'Here is an image: <img src="https://example.com/photo.jpg" alt="photo">'
        result = extract_images(text)
        
        self.assertIn('<img src="https://example.com/photo.jpg" alt="photo">', result)

    def test_direct_url_patterns(self):
        """Test extraction of direct image URLs (captures extension)."""
        test_cases = [
            ('https://example.com/image.jpg', 'jpg'),
            ('http://example.com/photo.jpeg', 'jpeg'),
            ('https://cdn.example.com/pic.png', 'png'),
            ('https://example.com/animated.gif', 'gif'),
            ('https://example.com/bitmap.bmp', 'bmp'),
            ('https://example.com/modern.webp', 'webp'),
        ]
        
        for url, expected_ext in test_cases:
            text = f'Look at this: {url} and more text'
            result = extract_images(text)
            # The regex captures just the extension, not the full URL
            self.assertIn(expected_ext, result, f"Failed to extract extension from {url}")

    def test_attachment_patterns(self):
        """Test extraction of attachment patterns."""
        # Note: The regex pattern for attachments looks for file extensions within the text
        # It requires the pattern attachment[s]?[:.]?[^\s]*\.(ext) which includes the extension
        test_cases = [
            ('attachment:screenshot.png', 'png'),  # No space after colon
            ('attachments.photo.jpg', 'jpg'),      # Using dot separator
        ]
        
        for pattern, expected_ext in test_cases:
            text = f'See {pattern} for details'
            result = extract_images(text)
            # Should find the extension
            self.assertIn(expected_ext, result, f"Failed to find extension in: {pattern}")

    def test_multiple_images(self):
        """Test extraction of multiple images."""
        text = '''
        Here are some images:
        ![First](https://example.com/first.jpg)
        <img src="https://example.com/second.png">
        https://example.com/third.gif
        '''
        result = extract_images(text)
        
        # Should contain all three images separated by semicolons
        self.assertIn('![First](https://example.com/first.jpg)', result)
        self.assertIn('; ', result)  # Multiple images should be separated

    def test_case_insensitive_extensions(self):
        """Test case-insensitive matching of file extensions."""
        text = 'Images: https://example.com/IMAGE.JPG and https://example.com/photo.PNG'
        result = extract_images(text)
        
        # The regex extracts extensions (case-insensitive), not full URLs
        self.assertIn('JPG', result)
        self.assertIn('PNG', result)

    def test_text_without_images(self):
        """Test text without any images returns empty string."""
        text = 'This is just regular text without any image references.'
        result = extract_images(text)
        
        self.assertEqual(result, '')


class TestLocationMapper(unittest.TestCase):
    """Tests for the LocationMapper class."""

    def test_map_location_by_id(self):
        """Test mapping location by ID match."""
        options = [
            {'id': '123', 'name': 'Location A', 'orderindex': 0},
            {'id': '456', 'name': 'Location B', 'orderindex': 1},
        ]
        
        result = LocationMapper.map_location('123', 'dropdown', options)
        self.assertEqual(result, 'Location A')

    def test_map_location_by_orderindex(self):
        """Test mapping location by orderindex when ID doesn't match."""
        options = [
            {'id': 'abc', 'name': 'First', 'orderindex': 0},
            {'id': 'def', 'name': 'Second', 'orderindex': 1},
        ]
        
        # Pass value as orderindex
        result = LocationMapper.map_location('1', 'dropdown', options)
        self.assertEqual(result, 'Second')

    def test_map_location_by_name(self):
        """Test mapping location by name when ID and orderindex don't match."""
        options = [
            {'id': 'x', 'name': 'Alpha', 'orderindex': 0},
            {'id': 'y', 'name': 'Beta', 'orderindex': 1},
        ]
        
        result = LocationMapper.map_location('Beta', 'dropdown', options)
        self.assertEqual(result, 'Beta')

    def test_map_location_no_options(self):
        """Test mapping returns string value when no options provided."""
        result = LocationMapper.map_location('some_value', 'dropdown', None)
        self.assertEqual(result, 'some_value')
        
        result = LocationMapper.map_location('another', 'dropdown', [])
        self.assertEqual(result, 'another')

    def test_map_location_no_match(self):
        """Test mapping returns string value when no match found."""
        options = [
            {'id': '1', 'name': 'One', 'orderindex': 0},
            {'id': '2', 'name': 'Two', 'orderindex': 1},
        ]
        
        result = LocationMapper.map_location('999', 'dropdown', options)
        self.assertEqual(result, '999')

    def test_map_location_id_match_ignores_orderindex(self):
        """Test that ID match takes precedence over orderindex."""
        options = [
            {'id': '100', 'name': 'ID Match', 'orderindex': 5},
            {'id': '200', 'name': 'Index Match', 'orderindex': 100},
        ]
        
        result = LocationMapper.map_location('100', 'dropdown', options)
        self.assertEqual(result, 'ID Match')

    def test_map_location_with_missing_name(self):
        """Test mapping when option doesn't have name field."""
        options = [
            {'id': '123', 'orderindex': 0},  # Missing 'name' field
        ]
        
        result = LocationMapper.map_location('123', 'dropdown', options)
        self.assertEqual(result, '123')  # Should return the original value

    def test_map_location_with_integer_value(self):
        """Test mapping with integer value."""
        options = [
            {'id': '1', 'name': 'One', 'orderindex': 1},
            {'id': '2', 'name': 'Two', 'orderindex': 2},
        ]
        
        result = LocationMapper.map_location(2, 'dropdown', options)
        self.assertEqual(result, 'Two')


class TestGetYesNoInput(unittest.TestCase):
    """Tests for the get_yes_no_input function."""

    @patch('builtins.input', return_value='yes')
    def test_yes_input(self, mock_input):
        """Test 'yes' input returns True."""
        result = get_yes_no_input('Test prompt: ')
        self.assertTrue(result)

    @patch('builtins.input', return_value='y')
    def test_y_input(self, mock_input):
        """Test 'y' input returns True."""
        result = get_yes_no_input('Test prompt: ')
        self.assertTrue(result)

    @patch('builtins.input', return_value='no')
    def test_no_input(self, mock_input):
        """Test 'no' input returns False."""
        result = get_yes_no_input('Test prompt: ')
        self.assertFalse(result)

    @patch('builtins.input', return_value='n')
    def test_n_input(self, mock_input):
        """Test 'n' input returns False."""
        result = get_yes_no_input('Test prompt: ')
        self.assertFalse(result)

    @patch('builtins.input', return_value='  YES  ')
    def test_case_insensitive_and_whitespace(self, mock_input):
        """Test case-insensitive input with whitespace."""
        result = get_yes_no_input('Test prompt: ')
        self.assertTrue(result)

    @patch('builtins.input', side_effect=EOFError)
    @patch('sys.stdout', new_callable=StringIO)
    def test_eof_default_false(self, mock_stdout, mock_input):
        """Test EOFError returns default (False)."""
        result = get_yes_no_input('Test prompt: ', default_on_interrupt=False)
        self.assertFalse(result)
        self.assertIn('Defaulting to no', mock_stdout.getvalue())

    @patch('builtins.input', side_effect=EOFError)
    @patch('sys.stdout', new_callable=StringIO)
    def test_eof_default_true(self, mock_stdout, mock_input):
        """Test EOFError returns default (True)."""
        result = get_yes_no_input('Test prompt: ', default_on_interrupt=True)
        self.assertTrue(result)
        self.assertIn('Defaulting to yes', mock_stdout.getvalue())

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    @patch('sys.stdout', new_callable=StringIO)
    def test_keyboard_interrupt(self, mock_stdout, mock_input):
        """Test KeyboardInterrupt returns default."""
        result = get_yes_no_input('Test prompt: ', default_on_interrupt=False)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
