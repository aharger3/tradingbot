#!/usr/bin/env python3
"""Extract mentions of Scarface, JDub, or flag/FVG in recovered_reviews."""

import json
from pathlib import Path

repo_root = Path(__file__).parent.parent
file_path = repo_root / "research" / "recovered_reviews.jsonl"

print("Searching recovered_reviews for mentor references and FVG/flag...")
print("=" * 80)

with open(file_path, 'r') as f:
    for line in f:
        try:
            record = json.loads(line.strip())
        except:
            continue

        note = record.get('note', '').lower()

        # Look for setup mentions
        if 'fvg' in note or 'fair value gap' in note:
            print(f"\nFVG mention in {record.get('id', 'N/A')}:")
            print(f"  Setup: {record.get('setup')}, Tier: {record.get('austin_tier')}")
            print(f"  Note: {record.get('note')[:200]}")

        if 'flag' in note:
            print(f"\nFLAG mention in {record.get('id', 'N/A')}:")
            print(f"  Setup: {record.get('setup')}, Tier: {record.get('austin_tier')}")
            print(f"  Note: {record.get('note')[:200]}")

        # Look for explicit teaching mentions
        if 'scarface' in note and ('fvg' in note or 'flag' in note or 'fair value gap' in note):
            print(f"\nSCARFACE + setup mention in {record.get('id', 'N/A')}:")
            print(f"  Setup: {record.get('setup')}, Tier: {record.get('austin_tier')}")
            print(f"  Note: {record.get('note')}")

print("\n" + "=" * 80)
print("Note: 'bull flag' patterns mentioned in notes are descriptions of break-and-retest,")
print("not references to a 'flag' setup in the system.")
