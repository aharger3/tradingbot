#!/usr/bin/env python3
import json

# Read S notes
with open('research/_extract_s_notes.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total S notes file entries: {len(lines)}\n")
print("Sample S notes (first 30, pattern focus):\n")

for i, line in enumerate(lines[:30], 1):
    try:
        obj = json.loads(line)
        key = obj['key']
        notes = obj['notes']
        # Truncate to 180 chars
        notes_display = notes[:180] if len(notes) <= 180 else notes[:177] + "..."
        print(f"{i:2d}. {key:25s}")
        print(f"    {notes_display}\n")
    except Exception as e:
        pass
