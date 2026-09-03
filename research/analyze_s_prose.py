#!/usr/bin/env python3
"""Analyze S grade prose for patterns."""
import json
import sys
from collections import Counter, defaultdict
import re

# Read the S notes we extracted
s_notes_list = []
with open('research/_extract_s_notes.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            obj = json.loads(line)
            if obj.get('notes'):
                s_notes_list.append(obj)
        except:
            pass

print(f"S notes with content: {len(s_notes_list)}")
print()

# Keywords/patterns to search for
patterns = {
    'BR+OCR confluence': r'break.*retest|retest|ocr|confluence',
    'displacement': r'displacement',
    'as candle forming': r'as candle.*forming|candle.*forming|as.*forming',
    'HOD/LOD': r'hod|lod|high.*day|low.*day',
    'chop/choppy': r'chop|choppy|chopping',
    'too many candles': r'too many|many candles|candles?.*too',
    'early trade/entry': r'early.*trade|early.*entry|entry.*early',
    'reclaim': r'reclaim',
    'entry timing': r'entry.*minute|entry.*time|minute.*entry|timing',
    'level/support/resistance': r'level|support|resistance|clean',
    'initial range': r'range|ir|open.*range',
    'trend/momentum': r'trend|momentum|uptrend|downtrend',
    'first setup of day': r'first.*day|day.*first|start.*day|early.*day',
    'runners/target': r'run|target|pt|price.*target|2r|3r',
    'stop placement': r'stop|wick|halt|floor',
    'no displacement': r'no displacement|without displacement',
    'tight entries': r'tight|close.*entry|small.*range',
    'HTF thesis': r'htf|higher.*frame|swing|daily',
}

# Count occurrences
keyword_counts = Counter()
notes_with_keyword = defaultdict(list)

for entry in s_notes_list:
    notes = entry['notes'].lower()
    key = entry['key']

    for pattern_name, pattern_regex in patterns.items():
        if re.search(pattern_regex, notes):
            keyword_counts[pattern_name] += 1
            notes_with_keyword[pattern_name].append(key)

print("Pattern occurrences in S notes (n_S_with_pattern / total_S_with_notes):")
print()
for pattern, count in sorted(keyword_counts.items(), key=lambda x: -x[1]):
    pct = 100.0 * count / len(s_notes_list)
    print(f"  {pattern:30s} {count:3d} / {len(s_notes_list):3d} ({pct:5.1f}%)")

print()
print(f"SUMMARY:")
print(f"  Total S entries (canonical): 347")
print(f"  S entries with notes: {len(s_notes_list)}")
print(f"  S entries without notes: {347 - len(s_notes_list)}")
print()

# Show examples for top patterns
print("Examples (first 5 keys per pattern, top 5 patterns):")
for pattern, count in sorted(keyword_counts.items(), key=lambda x: -x[1])[:5]:
    keys = notes_with_keyword[pattern][:5]
    print(f"\n{pattern}:")
    for key in keys:
        # Find and show the note
        for entry in s_notes_list:
            if entry['key'] == key:
                note_preview = entry['notes'][:100]
                print(f"    {key}: {note_preview}")
                break
