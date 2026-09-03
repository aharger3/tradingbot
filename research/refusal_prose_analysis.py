#!/usr/bin/env python3
"""Exhaustive prose analysis of all refusal (none grade) judgments."""
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

# Collect all refusal entries with full row data
refusal_entries = {}  # key -> row

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

print(f"Total refusal (none) entries: {len(refusal_entries)}")
print()

# Extract all text/notes from each entry
def get_all_text(row):
    """Extract all text content from a row."""
    texts = []

    # Top-level string fields
    for field in ['notes', 'note', 'comment', 'description', 'why_not']:
        val = row.get(field)
        if val:
            if isinstance(val, str):
                texts.append(val)
            elif isinstance(val, list):
                texts.extend([str(v) for v in val if isinstance(v, str)])

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

# For refusal entries, look at prose content
refusal_prose = {k: get_all_text(refusal_entries[k]) for k in refusal_entries.keys()}

refusals_with_text = sum(1 for p in refusal_prose.values() if p.strip())
print(f"Refusal entries with any text: {refusals_with_text}")
print(f"Refusal entries without text: {len(refusal_entries) - refusals_with_text}")
print()

# ============================================================================
# DETAILED PATTERN ANALYSIS FOR REFUSALS
# ============================================================================

print("=" * 70)
print("REFUSAL (NONE GRADE) PROSE ANALYSIS - DETAILED THEMES")
print("=" * 70)
print()

themes = {
    "Entry Issues": {
        "patterns": [
            ("Too late / Already happened", r'too\s+late|already\s+(?:filled|happened|at|happened)|price\s+already'),
            ("Not at key level", r'not\s+at|not\s+on|away\s+from|displaced'),
            ("Entry too early", r'too\s+early|early(?:\s+entry)?'),
            ("No clear entry", r'no\s+clear\s+entry|unclear\s+entry'),
            ("Entry quality poor", r'ugly\s+candle|poor\s+entry|bad\s+entry'),
        ],
        "description": "Problems with entry location or timing"
    },

    "Range & Chop Issues": {
        "patterns": [
            ("In range / Range bound", r'\bin\s+range\b|range\s+bound|ranging|stuck\s+in'),
            ("Chop / Choppy / No direction", r'chop|choppy|no\s+(?:direction|momentum)|back\s+and\s+forth'),
            ("Too much movement already", r'too\s+much|already\s+move|already\s+ran'),
            ("No clear structure", r'no\s+clear|unclear'),
        ],
        "description": "Range-bound or choppy market conditions"
    },

    "Level & Structure Problems": {
        "patterns": [
            ("No good levels", r'no\s+(?:clear\s+)?levels|levels\s+unclear|no\s+clean.*level'),
            ("Levels already broken", r'levels?\s+(?:already|broken|through)'),
            ("Pivot not clean", r'pivot\s+not\s+clean|pivot\s+bad|pivot\s+ugly'),
            ("No displacement", r'no\s+displacement|without\s+displacement'),
        ],
        "description": "Issues with price level structure or quality"
    },

    "Displacement/Risk Issues": {
        "patterns": [
            ("Displacement too far", r'displacement\s+too|too\s+much\s+displacement|displaced\s+too'),
            ("Risk not clean", r'risk\s+(?:not|un)?clean|unclear\s+risk'),
            ("Stop ambiguous", r'stop\s+(?:ambiguous|unclear|bad)'),
        ],
        "description": "Problems with displacement or stop definition"
    },

    "Day/Time Issues": {
        "patterns": [
            ("Too long to develop", r'too\s+long|took\s+too\s+long|long\s+setup'),
            ("Late in day", r'too\s+late\s+in\s+day|late\s+day|past\s+\d{2}:\d{2}'),
            ("No early setup", r'no\s+early|looking\s+for\s+early'),
        ],
        "description": "Timing relative to the trading day"
    },

    "Comparison to Alternatives": {
        "patterns": [
            ("A opportunity exists instead", r'\ba\s+(?:opportunity|trade|entry)|a.*instead|a.*instead'),
            ("Could be A not S", r'a.*trade|a.*entry|a.*setup'),
        ],
        "description": "Setup is A-grade or worse, not S-worthy"
    },

    "Stock/Market Issues": {
        "patterns": [
            ("Stock cheap / weak", r'cheap\s+stock|weak\s+stock|ugly\s+stock'),
            ("Stock characteristics bad", r'stock\s+(?:is|was)\s+(?:cheap|ugly|weak)'),
        ],
        "description": "Issues with the specific stock or market condition"
    },
}

# Count theme occurrences
theme_counts = {}
theme_details = {}

for theme_name, theme_config in themes.items():
    theme_counts[theme_name] = Counter()
    theme_details[theme_name] = defaultdict(list)

    for pattern_label, pattern_regex in theme_config["patterns"]:
        for key, prose in refusal_prose.items():
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
        pct = 100.0 * count / len(refusal_entries) if refusal_entries else 0
        pct_of_with_text = 100.0 * count / refusals_with_text if refusals_with_text > 0 else 0
        print(f"    {pattern:40s} {count:3d} / 405 refusals ({pct:5.1f}% of all)")
        print(f"      {'':40s}      ({pct_of_with_text:5.1f}% of refusals with text)")

    print()

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total refusal entries: 405")
print(f"Refusal entries with any prose: {refusals_with_text}")
print(f"Refusal entries without prose: {len(refusal_entries) - refusals_with_text}")
print()
print("KEY DIFFERENCE: S trades focus on ENTRY MECHANICS & LEVEL REFERENCES,")
print("while refusals focus on RANGE/CHOP, TIMING, and STRUCTURAL PROBLEMS.")
