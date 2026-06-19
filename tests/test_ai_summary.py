import re
import unittest

import ai_summary
import eta_calculator
from ai_summary import _normalize_field_entries, get_ai_summary


# Published Google Gemini model ids follow this shape, e.g.
# "gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-2.0-flash".
# See https://ai.google.dev/gemini-api/docs/models
_VALID_GEMINI_MODEL_RE = re.compile(r"^gemini-\d+(?:\.\d+)?-[a-z0-9-]+$")

# Known-invalid id that previously shipped and returned an invalid-model error
# at runtime. Guarding against it explicitly prevents a regression.
_KNOWN_BAD_MODEL = "gemini-flash-lite-latest"


class GeminiModelSmokeTests(unittest.TestCase):
    """Catch model-name regressions without making a live API call (issue #109)."""

    def test_ai_summary_model_id_is_well_formed(self) -> None:
        self.assertNotEqual(ai_summary.GEMINI_MODEL, _KNOWN_BAD_MODEL)
        self.assertRegex(ai_summary.GEMINI_MODEL, _VALID_GEMINI_MODEL_RE)

    def test_eta_calculator_model_id_is_well_formed(self) -> None:
        self.assertNotEqual(eta_calculator.GEMINI_MODEL, _KNOWN_BAD_MODEL)
        self.assertRegex(eta_calculator.GEMINI_MODEL, _VALID_GEMINI_MODEL_RE)

    def test_model_ids_match_across_modules(self) -> None:
        # Both modules drive the same Gemini integration; their defaults must agree.
        self.assertEqual(ai_summary.GEMINI_MODEL, eta_calculator.GEMINI_MODEL)


class NormalizeFieldEntriesTests(unittest.TestCase):
    def test_normalize_sequence_of_tuples(self) -> None:
        entries = [("Subject", "Printer is jammed"), ("Resolution", "Clear paper path")]
        normalized = _normalize_field_entries(entries)
        self.assertEqual(normalized, entries)

    def test_normalize_mapping(self) -> None:
        entries = {"Subject": "Reset router", "Resolution": "Power cycle complete"}
        normalized = _normalize_field_entries(entries)
        # dict iteration preserves insertion order in Python 3.7+ (and inputs in literal order)
        self.assertEqual(normalized, [("Subject", "Reset router"), ("Resolution", "Power cycle complete")])


class GetAISummaryFallbackTests(unittest.TestCase):
    def test_empty_field_entries_returns_message(self) -> None:
        summary = get_ai_summary("Sample Task", [], gemini_api_key="")
        self.assertEqual(summary, "No content available for summary.")

    def test_returns_field_block_when_no_api_key(self) -> None:
        entries = [
            ("Subject", "Replace toner"),
            ("Resolution", "(not provided)"),
        ]
        summary = get_ai_summary("Printer Maintenance", entries, gemini_api_key="")
        expected = "Subject: Replace toner\nResolution: (not provided)"
        self.assertEqual(summary, expected)


if __name__ == "__main__":
    unittest.main()
