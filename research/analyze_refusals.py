#!/usr/bin/env python3
"""Analyze refusal prose for patterns."""
import sys
import json
from collections import Counter, defaultdict
import re

sys.path.insert(0, '.')
import marks_pool
import grade_read
import build_deck

# Get canonical pool
pool = marks_pool.canonical_pool()
s_days = marks_pool.s_days(pool)

print(f"Total S symbol-days: {len(s_days)}")
print()

# Collect all refusal (none) notes from source files
refusal_entries = {}  # key -> (notes_text, why_not_checkboxes)

for path in build_deck.mark_sources():
    for row in build_deck._rows(path):
        key = build_deck._judgement_key(row)
        if not key:
            continue

        grade = grade_read.read_grade(row)
        if grade != 'none':
            continue

        # Extract note
        notes = ''
        if 'notes' in row:
            notes = row.get('notes', '')
        elif 'note' in row:
            notes = row.get('note', '')

        if isinstance(notes, list):
            notes = ' '.join(str(n) for n in notes if n)
        notes = str(notes).strip() if notes else ''

        # Also check answers.note
        if isinstance(row.get('answers'), dict):
            ans = row['answers']
            if 'note' in ans:
                ans_note = ans['note']
                if isinstance(ans_note, list):
                    ans_note = ans_note[0] if ans_note else ''
                if ans_note:
                    notes = (notes + ' | ' + str(ans_note)).strip() if notes else str(ans_note)

        # Extract why_not checkboxes
        why_not = row.get('why_not', []) if isinstance(row.get('why_not'), list) else []

        if key not in refusal_entries:
            refusal_entries[key] = (notes, why_not)

print(f"Refusal entries collected: {len(refusal_entries)}")
refusal_with_notes = sum(1 for k, (n, w) in refusal_entries.items() if n)
refusal_with_why_not = sum(1 for k, (n, w) in refusal_entries.items() if w)
print(f"Refusal entries with notes: {refusal_with_notes}")
print(f"Refusal entries with why_not checkboxes: {refusal_with_why_not}")
print()

# Analyze why_not checkboxes
why_not_counter = Counter()
for key, (notes, why_not) in refusal_entries.items():
    for reason in why_not:
        why_not_counter[reason] += 1

print("Why_not refusal reasons (checkbox selections):")
for reason, count in why_not_counter.most_common():
    pct = 100.0 * count / refusal_with_why_not if refusal_with_why_not > 0 else 0
    print(f"  {reason:40s} {count:3d} ({pct:5.1f}%)")

print()

# Now analyze text patterns in refusal notes
refusal_notes_list = [(k, n) for k, (n, w) in refusal_entries.items() if n]

print(f"Analyzing {len(refusal_notes_list)} refusal notes:")
print()

patterns = {
    'too many candles': r'too many|many candles|candles?.*too',
    'no displacement': r'no displacement|without displacement|no break',
    'entry too late': r'too late|late.*entry|already.*fill|already.*happened',
    'chop/no direction': r'chop|choppy|no.*direction|back and forth',
    'stop placement issue': r'stop|ambiguous|wick|unclear',
    'entry quality': r'entry.*bad|poor.*entry|ugly|cheap',
    'levels not clean': r'level.*clean|not.*clean|clean.*level',
    'displacement present': r'displacement|too much|already.*moved',
    'already filled': r'already.*filled|already.*at|price already',
    'low probability': r'low.*prob|unlikely|slim',
}

keyword_counts = Counter()
for key, notes in refusal_notes_list:
    notes_lower = notes.lower()
    for pattern_name, pattern_regex in patterns.items():
        if re.search(pattern_regex, notes_lower):
            keyword_counts[pattern_name] += 1

print("Refusal pattern occurrences in prose:")
for pattern, count in sorted(keyword_counts.items(), key=lambda x: -x[1]):
    pct = 100.0 * count / len(refusal_notes_list)
    print(f"  {pattern:30s} {count:3d} / {len(refusal_notes_list):3d} ({pct:5.1f}%)")

print()
print(f"REFUSAL SUMMARY:")
print(f"  Total refusal (none) entries: {len(refusal_entries)}")
print(f"  Refusal entries with notes text: {refusal_with_notes}")
print(f"  Refusal entries with why_not checkboxes: {refusal_with_why_not}")

# Show examples
print()
print("Examples of refusal notes (first 10):")
for i, (key, notes) in enumerate(refusal_notes_list[:10]):
    preview = notes[:100].replace('\n', ' ')
    print(f"  {key}: {preview}")
