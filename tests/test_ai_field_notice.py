#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests for the ClickUp AI Summary field notice (_emit_ai_field_notice).

The missing/empty-field notice should only appear for AI sources that actually
consume the ClickUp Summary field as primary content (ClickUp, Both) — not for
Claude/Gemini runs, where "ensure automation populates it" is misleading noise
(issue #161).
"""

import unittest
from unittest.mock import patch

from config import AISource, ClickUpConfig, OutputFormat
from extractor import ClickUpTaskExtractor


class _DummyAPIClient:
    def get(self, endpoint):  # pragma: no cover - not used by these tests
        return {}


def _extractor(source: AISource) -> ClickUpTaskExtractor:
    config = ClickUpConfig(
        api_key="k",
        workspace_name="W",
        space_name="S",
        output_format=OutputFormat.MARKDOWN,
        output_path="out.md",
        enable_ai_summary=True,
        ai_source=source,
    )
    return ClickUpTaskExtractor(config, _DummyAPIClient())


class AIFieldNoticeTests(unittest.TestCase):
    def test_notice_emitted_for_clickup_source(self) -> None:
        extractor = _extractor(AISource.CLICKUP)
        with patch("extractor.console") as mock_console:
            extractor._emit_ai_field_notice("field is empty")
        mock_console.print.assert_called_once()
        self.assertTrue(extractor._ai_field_notice_emitted)

    def test_notice_emitted_for_both_source(self) -> None:
        extractor = _extractor(AISource.BOTH)
        with patch("extractor.console") as mock_console:
            extractor._emit_ai_field_notice("field is empty")
        mock_console.print.assert_called_once()

    def test_notice_suppressed_for_claude_source(self) -> None:
        extractor = _extractor(AISource.CLAUDE)
        with patch("extractor.console") as mock_console:
            extractor._emit_ai_field_notice("field is empty")
        mock_console.print.assert_not_called()
        self.assertFalse(extractor._ai_field_notice_emitted)

    def test_notice_suppressed_for_gemini_source(self) -> None:
        extractor = _extractor(AISource.GEMINI)
        with patch("extractor.console") as mock_console:
            extractor._emit_ai_field_notice("field is empty")
        mock_console.print.assert_not_called()

    def test_notice_emitted_only_once(self) -> None:
        extractor = _extractor(AISource.CLICKUP)
        with patch("extractor.console") as mock_console:
            extractor._emit_ai_field_notice("field is empty")
            extractor._emit_ai_field_notice("field is empty")
        mock_console.print.assert_called_once()


if __name__ == "__main__":
    unittest.main()
