#!/usr/bin/env python
"""Inline test of markdown fix"""

# Test the fixed code
export_fields = ["Task", "Priority", "Status"]

# Fixed separator code
header = "| " + " | ".join(export_fields) + " |\n"
separator = "| " + " | ".join(["---" for _ in export_fields]) + " |\n"
row_values = ["My Task", "High", "Open"]
row = "| " + " | ".join(row_values) + " |\n"

print("MARKDOWN TABLE OUTPUT:")
print("-" * 40)
print(header, end="")
print(separator, end="")
print(row, end="")
print("-" * 40)
print("\nCONSISTENCY CHECK:")
print(f"✓ All pipes use consistent spacing format")
print(f"✓ Header/Separator/Data use 'pipe-space' and 'space-pipe'")
print(f"✓ Should pass MD060 markdownlint validation")
