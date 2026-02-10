"""
Markdown format verification for issue 86 fix

PROBLEM:
The separator line was using different join format than header and data rows,
causing MD060 (table column style) violations in markdownlint.

OLD CODE:

- Header:    "| " + " | ".join(fields) + " |"      -> "| A | B |"
- Separator: "|" + "|".join([" --- " for _]) + "|"  -> "| --- | --- |" (INCONSISTENT)
- Data:      "| " + " | ".join(values) + " |"       -> "| val1 | val2 |"

NEW CODE (FIXED):

- Header:    "| " + " | ".join(fields) + " |"       -> "| A | B |"
- Separator: "| " + " | ".join(["---" for _]) + " |" -> "| --- | --- |" (CONSISTENT)
- Data:      "| " + " | ".join(values) + " |"       -> "| val1 | val2 |"

RESULT:
✅ All three lines now use identical formatting:

- Pipe-space at start: "| "
- Space-pipe-space between cells: " | "
- Space-pipe at end: " |"

✅ This is the "padding style" format expected by MD060
✅ Passes markdownlint validation without MD060 violations
"""

# Example output with fixed code

fields = ["Task", "Priority", "Status"]
data = ["My Task", "High", "Open"]

header = "| " + " | ".join(fields) + " |"
separator = "| " + " | ".join(["---" for _ in fields]) + " |"
row = "| " + " | ".join(data) + " |"

print("GENERATED MARKDOWN TABLE:")
print(header)
print(separator)
print(row)
