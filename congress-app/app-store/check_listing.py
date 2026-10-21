"""Checks the fields in listing.md against App Store Connect's length limits.

    python app-store/check_listing.py

A field is a bold heading with its limit in brackets, e.g. **Subtitle** [30], followed by a
fenced block with the text.
"""
import re
import sys
from pathlib import Path

text = Path(__file__).with_name("listing.md").read_text(encoding="utf-8")
fields = re.findall(r"\*\*([^*\n]+)\*\* \[(\d+)\][^\n]*\n\n```\n(.*?)\n```", text, re.S)
failed = False
for name, limit, value in fields:
    length = len(value)
    ok = length <= int(limit)
    failed |= not ok
    print(f"{'ok ' if ok else 'TOO LONG'} {name}: {length} of {limit}")
keywords = next(v for n, _, v in fields if n == "Keywords")
if ", " in keywords:
    print("Keywords: remove the spaces after commas; they count toward the limit")
    failed = True
sys.exit(1 if failed or not fields else 0)
