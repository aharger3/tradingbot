#!/usr/bin/env python3
"""
Search corpus for FVG (fair-value-gap) and flag setup references.
Scans all mark files for explicit mentions in setup/note fields and prose.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

repo_root = Path(__file__).parent.parent
research_dir = repo_root / "research"

# Files to search
mark_files = [
    "austin_marks_v2.jsonl",
    "austin_marks_v3.jsonl",
    "austin_marks_v4.jsonl",
    "austin_marks_v5.jsonl",
    "austin_marks_v6.jsonl",
    "austin_marks_v7.jsonl",
    "blind_marks_all.jsonl",
    "recovered_reviews.jsonl",
    "marks_clean.jsonl",
    "derived_marks_v1.jsonl",
    "derived_marks_v2.jsonl",
]

probe_files = [
    "marks/probe_autopsy_2026-08-23.jsonl",
    "marks/probe_head2head_2026-08-24.jsonl",
]

all_files = mark_files + probe_files

# Case-insensitive patterns for FVG and flag
fvg_pattern = re.compile(r'\b(fvg|fair.value.gap|fair value gap)\b', re.IGNORECASE)
flag_pattern = re.compile(r'\b(flag|flagpole)\b', re.IGNORECASE)

results = defaultdict(list)

print("Searching corpus for FVG and flag references...")
print("=" * 80)

for file_name in all_files:
    file_path = research_dir / file_name
    if not file_path.exists():
        print(f"SKIP (not found): {file_name}")
        continue

    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    record = json.loads(line.strip())
                except json.JSONDecodeError:
                    continue

                # Search all string fields
                found_fvg = False
                found_flag = False
                match_text = []

                for key, value in record.items():
                    if isinstance(value, str):
                        if fvg_pattern.search(value):
                            found_fvg = True
                            match_text.append(f"{key}: {value[:100]}")
                        if flag_pattern.search(value):
                            # Filter out false positives like "flagged" in technical context
                            if 'flag' in value.lower() and not 'flagged' in value.lower():
                                found_flag = True
                                match_text.append(f"{key}: {value[:100]}")

                if found_fvg:
                    results['fvg'].append({
                        'file': file_name,
                        'line': line_num,
                        'record': record,
                        'matches': match_text
                    })

                if found_flag:
                    results['flag'].append({
                        'file': file_name,
                        'line': line_num,
                        'record': record,
                        'matches': match_text
                    })
    except Exception as e:
        print(f"ERROR in {file_name}: {e}")

print(f"\nFVG RESULTS: {len(results['fvg'])} matches")
print("-" * 80)
if results['fvg']:
    for item in results['fvg']:
        print(f"File: {item['file']}, Line {item['line']}")
        print(f"  Record ID: {item['record'].get('id', 'N/A')}")
        print(f"  Setup: {item['record'].get('setup', 'N/A')}")
        print(f"  Tier: {item['record'].get('austin_tier', 'N/A')}")
        for match in item['matches']:
            print(f"  -> {match}")
        print()
else:
    print("  NO MATCHES FOUND")

print(f"\nFLAG RESULTS: {len(results['flag'])} matches")
print("-" * 80)
if results['flag']:
    for item in results['flag']:
        print(f"File: {item['file']}, Line {item['line']}")
        print(f"  Record ID: {item['record'].get('id', 'N/A')}")
        print(f"  Setup: {item['record'].get('setup', 'N/A')}")
        print(f"  Tier: {item['record'].get('austin_tier', 'N/A')}")
        for match in item['matches']:
            print(f"  -> {match}")
        print()
else:
    print("  NO MATCHES FOUND")

# Also check for setup types that might be FVG or flag related
print("\nSETUP TYPES IN CORPUS:")
print("-" * 80)
setup_types = defaultdict(int)
for file_name in all_files:
    file_path = research_dir / file_name
    if not file_path.exists():
        continue
    with open(file_path, 'r') as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                setup = record.get('setup', 'N/A')
                setup_types[setup] += 1
            except:
                continue

for setup, count in sorted(setup_types.items(), key=lambda x: x[1], reverse=True):
    print(f"  {setup}: {count}")

print("\n" + "=" * 80)
print(f"Summary: FVG={len(results['fvg'])}, FLAG={len(results['flag'])}")
