#!/usr/bin/env python3
"""Exhaustive prose analysis of all S judgments."""
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

print(f"Canonical S days: {len(s_days)}")
print()

# Collect all S entries with full row data
s_full_entries = {}  # key -> row
refusal_entries = {}  # key -> row

for path in build_deck.mark_sources():
    for row in build_deck._rows(path):
        key = build_deck._judgement_key(row)
        if not key:
            continue
        grade = grade_read.read_grade(row)
        if grade is None:
            continue

        if key in s_days and grade == 'S':
            if key not in s_full_entries:
                s_full_entries[key] = row
        elif grade == 'none':
            if key not in refusal_entries:
                refusal_entries[key] = row

print(f"S full entries: {len(s_full_entries)}")
print(f"Refusal entries: {len(refusal_entries)}")
print()

# Extract all text/notes from each entry
def get_all_text(row):
    """Extract all text content from a row."""
    texts = []

    # Top-level string fields
    for field in ['notes', 'note', 'comment', 'description']:
        val = row.get(field)
        if val and isinstance(val, str):
            texts.append(val)

    # answers dict content
    answers = row.get('answers', {})
    if isinstance(answers, dict):
        for k, v in answers.items():
            if isinstance(v, str) and v.strip():
                texts.append(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and item.strip():
                        texts.append(item)

    # Combine
    combined = ' | '.join(texts)
    return combined.lower()

# For S entries, look at prose content
s_prose = {k: get_all_text(s_full_entries[k]) for k in s_full_entries.keys()}
refusal_prose = {k: get_all_text(refusal_entries[k]) for k in refusal_entries.keys()}

print(f"S entries with any text: {sum(1 for p in s_prose.values() if p.strip())}")
print(f"Refusal entries with any text: {sum(1 for p in refusal_prose.values() if p.strip())}")
print()

# ============================================================================
# DETAILED PATTERN ANALYSIS FOR S
# ============================================================================

print("=" * 70)
print("S GRADE PROSE ANALYSIS - DETAILED THEMES")
print("=" * 70)
print()

# Group by broad themes
themes = {
    "Entry Mechanics & Timing": {
        "patterns": [
            ("OCR / off-chart retest", r'ocr\b|off.?chart'),
            ("Break and retest", r'break.*retest|breakout.*retest|br\b|br\s'),
            ("As candle forming/closing", r'as.*candle\s+(forming|closing)|candle\s+(forming|closing)'),
            ("Early entry / first candle", r'early\s+(entry|candle|trade)|first\s+candle|candle.*early'),
            ("Candle count references", r'candle[s]?\s+(?:after|before|earlier)|^\d+\s+candles?'),
            ("Minute/time specific", r'\d{1,2}:\d{2}|9:3\d|10:\d{2}|specific.*time|minute.*entry'),
            ("Multiple entry possibilities", r'entry.*9:|entry.*10:|two\s+entries|three\s+entries'),
        ],
        "description": "Specific entry timing and mechanics"
    },

    "Price Level References": {
        "patterns": [
            ("HOD / High of Day", r'\bhod\b|high.*day'),
            ("LOD / Low of Day", r'\blod\b|low.*day'),
            ("Pivot / Support / Resistance", r'pivot|support|resistance|level'),
            ("Reclaim", r'reclaim'),
            ("Gap references", r'gap|gapped'),
        ],
        "description": "References to specific price levels"
    },

    "Price Action Quality": {
        "patterns": [
            ("Tight / Clean price action", r'tight|clean\s+(?:price|action|pa)'),
            ("Displacement", r'\bdisplacement\b|displaced'),
            ("Chop / Chopping / No direction", r'chop|choppy|no.*direction|rangy|range|back.*forth'),
            ("One candle rule", r'one\s+candle\s+rule|one.?candle'),
        ],
        "description": "Quality/style descriptors of the price action"
    },

    "Confluence & Structure": {
        "patterns": [
            ("Confluence / Confluence with", r'confluence|confluence\s+with|align'),
            ("Bullish/bearish bias", r'bullish\s+bias|bearish\s+bias|bias\s+(?:up|down)'),
            ("HTF thesis / higher timeframe", r'htf|higher.*timeframe|higher.*frame|swing'),
            ("Rejection at level", r'rejection|reject|rejected\s+at'),
        ],
        "description": "Multi-level confluence and structural alignment"
    },

    "Quality Assessment & Caveats": {
        "patterns": [
            ("Not greatest but acceptable", r'not.*greatest|mediocre|having trouble.*downgrade'),
            ("Barely missed / close call", r'barely.*missed|close.*call|almost'),
            ("Forgiven / acceptable despite", r'forgiven|acceptable|can.*pay.*attention'),
            ("Good for data", r'good.*for.*data'),
        ],
        "description": "Qualitative assessment of setup quality"
    },

    "Targets & Risk Management": {
        "patterns": [
            ("Stop placement / definition", r'stop(?:\s+|:)|floor|wick|risk'),
            ("Scale / Multiple targets", r'scale|pt\d|price.*target|2r|3r'),
            ("Runner / significant move", r'runner|run(?:\s+|$)|bigger'),
        ],
        "description": "Risk and scaling discussion"
    },
}

# Count theme occurrences
theme_counts = {}
theme_details = {}

for theme_name, theme_config in themes.items():
    theme_counts[theme_name] = Counter()
    theme_details[theme_name] = defaultdict(list)

    for pattern_label, pattern_regex in theme_config["patterns"]:
        for key, prose in s_prose.items():
            if prose.strip() and re.search(pattern_regex, prose):
                theme_counts[theme_name][pattern_label] += 1
                theme_details[theme_name][pattern_label].append(key)

# Print theme analysis
for theme_name, theme_config in themes.items():
    counts = theme_counts[theme_name]
    if not counts:
        continue

    print(f"{theme_name}")
    print(f"  ({theme_config['description']})")
    print()

    for pattern, count in counts.most_common():
        pct = 100.0 * count / len(s_prose) if s_prose else 0
        s_with_notes = sum(1 for p in s_prose.values() if p.strip())
        pct_of_noted = 100.0 * count / s_with_notes if s_with_notes > 0 else 0
        print(f"    {pattern:40s} {count:3d} / 347 S  ({pct:5.1f}% of all)")
        print(f"      {'':40s}      ({pct_of_noted:5.1f}% of S with notes)")

    print()

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total S entries: 347")
print(f"S entries with any prose: {sum(1 for p in s_prose.values() if p.strip())}")
print(f"S entries without prose: {sum(1 for p in s_prose.values() if not p.strip())}")
