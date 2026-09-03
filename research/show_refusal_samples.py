#!/usr/bin/env python3
"""Show sample refusal notes."""
import sys
from collections import defaultdict

sys.path.insert(0, '.')
import grade_read
import build_deck

# Collect all refusal entries
refusal_entries = {}

for path in build_deck.mark_sources():
    for row in build_deck._rows(path):
        key = build_deck._judgement_key(row)
        if not key:
            continue
        grade = grade_read.read_grade(row)
        if grade != 'none':
            continue

        if key not in refusal_entries:
            refusal_entries[key] = row

print(f"Total refusal entries: {len(refusal_entries)}")
print()

# Get text from entries
def get_all_text(row):
    """Extract all text content from a row."""
    texts = []

    # Top-level string fields
    for field in ['notes', 'note', 'comment', 'description']:
        val = row.get(field)
        if val and isinstance(val, str):
            texts.append(f"{field}={val}")

    # answers dict content
    answers = row.get('answers', {})
    if isinstance(answers, dict):
        for k, v in answers.items():
            if isinstance(v, str) and v.strip():
                texts.append(f"answers.{k}={v}")
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and item.strip():
                        texts.append(f"answers.{k}={item}")

    return ' | '.join(texts)

# Show first 30 with text
count = 0
print("Sample refusal notes (first 30 with content):\n")
for key in sorted(refusal_entries.keys()):
    row = refusal_entries[key]
    text = get_all_text(row)
    if text:
        preview = text[:200].replace('\n', ' ')
        print(f"{count+1:2d}. {key:25s}")
        print(f"    {preview}\n")
        count += 1
        if count >= 30:
            break
