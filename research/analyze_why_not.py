#!/usr/bin/env python3
"""Analyze why_not checkbox selections in refusal entries."""
import sys
from collections import Counter, defaultdict

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

# Collect all why_not values
why_not_counter = Counter()
why_not_examples = defaultdict(list)

for key, row in refusal_entries.items():
    why_not = row.get('why_not')
    if isinstance(why_not, list):
        for reason in why_not:
            reason = str(reason).strip().lower()
            if reason:
                why_not_counter[reason] += 1
                if len(why_not_examples[reason]) < 3:
                    why_not_examples[reason].append(key)
    elif isinstance(why_not, str) and why_not.strip():
        reason = why_not.strip().lower()
        why_not_counter[reason] += 1
        if len(why_not_examples[reason]) < 3:
            why_not_examples[reason].append(key)

print(f"Why_not checkbox selections found:")
print()

if why_not_counter:
    for reason, count in why_not_counter.most_common():
        pct = 100.0 * count / len(refusal_entries)
        print(f"  {reason:40s} {count:3d} / 405 ({pct:5.1f}%)")
        if why_not_examples[reason]:
            examples = ', '.join(why_not_examples[reason][:2])
            print(f"    Examples: {examples}")
else:
    print("  No why_not checkboxes found!")

print()

# Also check for answer-style why_not
print("Checking for answer-based why_not selections:")
print()

answer_why_not = Counter()
for key, row in refusal_entries.items():
    answers = row.get('answers', {})
    if isinstance(answers, dict):
        why_not_answer = answers.get('why_not')
        if why_not_answer:
            if isinstance(why_not_answer, list):
                for w in why_not_answer:
                    w = str(w).strip().lower()
                    if w:
                        answer_why_not[w] += 1
            elif isinstance(why_not_answer, str):
                w = why_not_answer.strip().lower()
                if w:
                    answer_why_not[w] += 1

if answer_why_not:
    for reason, count in answer_why_not.most_common():
        pct = 100.0 * count / len(refusal_entries)
        print(f"  {reason:40s} {count:3d} / 405 ({pct:5.1f}%)")
else:
    print("  No answer-based why_not found!")

print()

# Show some refusal notes with prose
print("Refusals with prose notes (from notes/note fields):")
print()

prose_count = 0
for key, row in sorted(refusal_entries.items()):
    # Check for notes
    notes = row.get('notes') or row.get('note') or ''
    if isinstance(notes, str) and notes.strip():
        print(f"  {key:25s}: {notes[:100]}")
        prose_count += 1
        if prose_count >= 20:
            break

if prose_count == 0:
    print("  No prose notes found in refusal entries!")
