#!/usr/bin/env python3
"""Extract all statements about specific rungs/targets."""
import json
import os
import re

HERE = "research"

# Files to search
MARK_FILES = [
    "austin_marks_v7.jsonl", "blind_marks_all.jsonl", "recovered_reviews.jsonl",
]

marks_dir = os.path.join(HERE, "marks")
if os.path.exists(marks_dir):
    for f in os.listdir(marks_dir):
        if f.endswith(".jsonl"):
            MARK_FILES.append(os.path.join("marks", f))

# Find PT1 statements
pt1_stmts = []
pt2_stmts = []
pt3_stmts = []
scale_stmts = []
runner_stmts = []

def read_jsonl(path):
    if not os.path.exists(path):
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except:
                    continue

                card_id = row.get('card_id') or row.get('id') or row.get('card') or ''
                date = row.get('date') or row.get('day') or ''
                symbol = row.get('symbol', '')

                # Get all text fields
                texts = []
                note = row.get('note') or row.get('notes', '')
                if isinstance(note, dict):
                    for val in note.values():
                        if isinstance(val, str):
                            texts.append((val, 'notes'))
                elif isinstance(note, str):
                    texts.append((note, 'note'))

                answers = row.get('answers', {})
                if isinstance(answers, dict):
                    for key, val in answers.items():
                        if isinstance(val, str):
                            texts.append((val, f'answers.{key}'))
                        elif isinstance(val, list):
                            for item in val:
                                if isinstance(item, str):
                                    texts.append((item, f'answers.{key}'))

                for text, field in texts:
                    if not text:
                        continue

                    if re.search(r'\bpt1\b|hod|lod|high of day|low of day', text, re.I):
                        pt1_stmts.append((symbol, card_id, date, field, text[:200]))

                    if re.search(r'\bpt2\b', text, re.I):
                        pt2_stmts.append((symbol, card_id, date, field, text[:200]))

                    if re.search(r'\bpt3\b|\bpt4\b|\bpt5\b', text, re.I):
                        pt3_stmts.append((symbol, card_id, date, field, text[:200]))

                    if re.search(r'scale.*hod|hod.*scale|scale.*lod|lod.*scale', text, re.I):
                        scale_stmts.append((symbol, card_id, date, field, text[:200]))

                    if re.search(r'runner', text, re.I):
                        runner_stmts.append((symbol, card_id, date, field, text[:200]))

    except Exception as e:
        print(f"Error: {e}")

for f in MARK_FILES:
    full_path = os.path.join(HERE, f)
    read_jsonl(full_path)

print("PT1 (HOD/LOD) STATEMENTS:", len(pt1_stmts))
for sym, cid, d, field, txt in pt1_stmts[:5]:
    print(f"  {sym}/{cid}/{d} [{field}]")
    print(f"    {txt}")

print("\nPT2 STATEMENTS:", len(pt2_stmts))
for sym, cid, d, field, txt in pt2_stmts[:5]:
    print(f"  {sym}/{cid}/{d} [{field}]")
    print(f"    {txt}")

print("\nPT3/PT4/PT5 STATEMENTS:", len(pt3_stmts))
for sym, cid, d, field, txt in pt3_stmts[:5]:
    print(f"  {sym}/{cid}/{d} [{field}]")
    print(f"    {txt}")

print("\nSCALE AT HOD/LOD STATEMENTS:", len(scale_stmts))
for sym, cid, d, field, txt in scale_stmts[:8]:
    print(f"  {sym}/{cid}/{d} [{field}]")
    print(f"    {txt}")

print("\nRUNNER STATEMENTS:", len(runner_stmts))
for sym, cid, d, field, txt in runner_stmts[:8]:
    print(f"  {sym}/{cid}/{d} [{field}]")
    print(f"    {txt}")
