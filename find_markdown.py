#!/usr/bin/env python
"""Find markdown generation code in extractor.py"""

with open("extractor.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'table = "| "' in line or 'table += "| "' in line:
        # Print surrounding context
        start = max(0, i - 5)
        end = min(len(lines), i + 20)
        for j in range(start, end):
            print(f"{j + 1:4d}: {lines[j]}", end="")
        break
