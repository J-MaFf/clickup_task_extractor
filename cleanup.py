import os
import glob

# Clean up temporary test files
temp_files = ["find_markdown.py", "test_markdown_fix.py", "verify_fix.py"]

for f in temp_files:
    if os.path.exists(f):
        os.remove(f)
        print(f"Deleted {f}")

print("Cleanup complete")
