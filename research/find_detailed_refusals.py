#!/usr/bin/env python3
"""Find refusal entries with detailed prose explanations."""
import sys
import json
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

# Find entries with any detailed explanation
detailed_refusals = []

for key, row in refusal_entries.items():
    text_parts = []

    # Check answers.why_not field for prose
    answers = row.get('answers', {})
    if isinstance(answers, dict):
        why_not_answer = answers.get('why_not')
        # Skip if it's just a single checkbox like 'chop'
        if isinstance(why_not_answer, str) and len(why_not_answer) > 20:
            text_parts.append(f"answers.why_not: {why_not_answer}")

    # Check top-level notes/why_not
    for field in ['notes', 'note', 'comment', 'description', 'why_not']:
        val = row.get(field)
        if isinstance(val, str) and val.strip() and len(val.strip()) > 10:
            text_parts.append(f"{field}: {val.strip()}")

    if text_parts:
        combined = ' | '.join(text_parts)
        detailed_refusals.append((key, combined))

print(f"Refusals with detailed prose: {len(detailed_refusals)}")
print()

# Show samples
print("Sample refusal explanations (first 25):\n")
for i, (key, text) in enumerate(detailed_refusals[:25], 1):
    preview = text[:200].replace('\n', ' ')
    print(f"{i:2d}. {key:25s}")
    print(f"    {preview}\n")

print()
print("Detailed refusal summary:")
print(f"  Total refusals: 405")
print(f"  With detailed prose: {len(detailed_refusals)}")
print(f"  Without explanation: {405 - len(detailed_refusals)}")
