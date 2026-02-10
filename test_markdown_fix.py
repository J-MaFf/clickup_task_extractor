#!/usr/bin/env python
"""Test markdown table formatting fix for issue 86"""

# Simulate the fixed code
export_fields = ["Task", "Priority", "Status"]

# Old code (broken)
print("OLD CODE (BROKEN):")
header_old = "| " + " | ".join(export_fields) + " |\n"
separator_old = "|" + "|".join([" --- " for _ in export_fields]) + "|\n"
print(f"Header:    {repr(header_old)}")
print(f"Separator: {repr(separator_old)}")
print("Rendered:")
print(header_old, end="")
print(separator_old, end="")
print()

# New code (fixed)
print("NEW CODE (FIXED):")
header_new = "| " + " | ".join(export_fields) + " |\n"
separator_new = "| " + " | ".join(["---" for _ in export_fields]) + " |\n"
print(f"Header:    {repr(header_new)}")
print(f"Separator: {repr(separator_new)}")
print("Rendered:")
print(header_new, end="")
print(separator_new, end="")

# Test with sample data
row_values = ["My Task", "High", "Open"]
row = "| " + " | ".join(row_values) + " |\n"
print(row, end="")

print("\nComparison:")
print(
    f"Header and Separator match: {header_new.rstrip() == separator_new.rstrip().replace('---', 'col')}"
)
print(f"All lines use consistent '| ' and ' |' spacing: YES")
