import unittest

from ai_summary import _normalize_field_entries, get_ai_summary


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
