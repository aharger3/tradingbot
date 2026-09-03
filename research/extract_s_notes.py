#!/usr/bin/env python3
"""Extract all S grade notes and cluster them."""
import sys
import json
from collections import Counter, defaultdict

sys.path.insert(0, '.')
import marks_pool
import grade_read
import build_deck

# Get canonical pool
pool = marks_pool.canonical_pool()
s_days = marks_pool.s_days(pool)

print(f"Total S symbol-days in pool: {len(s_days)}")
print()

# Collect all S notes from source files
s_entries = {}  # key -> (grade, notes_text, row)
refusal_entries = {}  # key -> (grade, notes_text, why_not_checkboxes)

for path in build_deck.mark_sources():
    for row in build_deck._rows(path):
        key = build_deck._judgement_key(row)
        if not key:
            continue

        grade = grade_read.read_grade(row)
        if grade is None:
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

        if key in s_days and grade == 'S':
            if key not in s_entries:
                s_entries[key] = (grade, notes, row)
        elif grade == 'none':
            if key not in refusal_entries:
                why_not = row.get('why_not', []) if isinstance(row.get('why_not'), list) else []
                refusal_entries[key] = (grade, notes, why_not)

print(f"S entries collected: {len(s_entries)}")
print(f"S entries with notes text: {sum(1 for k, (g, n, r) in s_entries.items() if n)}")
print(f"Refusal entries collected: {len(refusal_entries)}")
print()

# Write S entries to file for detailed analysis
with open('research/_extract_s_notes.jsonl', 'w', encoding='utf-8') as f:
    for key in sorted(s_entries.keys()):
        grade, notes, row = s_entries[key]
        f.write(json.dumps({'key': key, 'grade': 'S', 'notes': notes}, ensure_ascii=False) + '\n')

print(f"Wrote {len(s_entries)} S entries to research/_extract_s_notes.jsonl")

# Show sample
print("\nSample S notes (first 15 with content):")
count = 0
for key in sorted(s_entries.keys()):
    grade, notes, row = s_entries[key]
    if notes and count < 15:
        print(f"  {key}: {notes[:120]}")
        count += 1
