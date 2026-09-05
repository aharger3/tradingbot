#!/usr/bin/env python
"""
F1 (part 8 of 8): Extract comments from mark files assigned to this agent.

Agent F1 processes every 8th file in sorted order (index % 8 == 0).
Reads LEGACY_MARK_FILES + research/marks/*.jsonl.
Emits research/g150_marks_comments_part8.jsonl with one row per (symbol, day, source_file, card_id).
"""
import json
import os
import glob
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

# From build_deck.py
LEGACY_MARK_FILES = [
    "marks/deck_marks_h2_3lane_2026-08-28.jsonl",
    "marks/regrade_confirm_2026-09-03.jsonl",
    "austin_marks_v7.jsonl",
    "blind_marks_all.jsonl",
    "marks_clean.jsonl",
    "mark_batch_02_grades.jsonl",
    "mark_batch_03_regrades.jsonl",
    "mark_batch_04_grades.jsonl",
    "derived_marks_v1.jsonl",
    "derived_marks_v2.jsonl",
    "recovered_reviews.jsonl",
    "austin_verdicts.json",
]

MARKS_DIR = os.path.join(HERE, "marks")
OUTPUT_FILE = os.path.join(HERE, "g150_marks_comments_part8.jsonl")
REPORT_FILE = os.path.join(HERE, "g150_marks_comments_part8.md")

# Agent assignment: F1 gets index % 8 == 0
AGENT_INDEX = 0
AGENT_TOTAL = 8

def get_all_mark_files():
    """Get all mark files (LEGACY + marks/*.jsonl), return sorted list."""
    files = set()

    # Add LEGACY_MARK_FILES (make paths absolute)
    for f in LEGACY_MARK_FILES:
        if f.endswith('.json') and not f.endswith('.jsonl'):
            # austin_verdicts.json
            full_path = os.path.join(HERE, f)
        elif f.startswith('marks/'):
            # Already in marks/
            full_path = os.path.join(HERE, f)
        else:
            # Research root
            full_path = os.path.join(HERE, f)
        if os.path.exists(full_path):
            files.add(full_path)

    # Add all marks/*.jsonl
    for f in glob.glob(os.path.join(MARKS_DIR, "*.jsonl")):
        files.add(f)

    return sorted(list(files))

def read_jsonl(path):
    """Read a JSONL file, yield rows."""
    if path.endswith('.json') and not path.endswith('.jsonl'):
        # Handle austin_verdicts.json (list, not jsonl)
        try:
            with open(path) as f:
                data = json.load(f)
                if isinstance(data, list):
                    for row in data:
                        yield row
        except Exception as e:
            print(f"Warning: failed to read {path}: {e}", file=sys.stderr)
    else:
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
        except Exception as e:
            print(f"Warning: failed to read {path}: {e}", file=sys.stderr)

def extract_comment(row):
    """Extract concatenated comment from all prose fields."""
    parts = []

    # Possible prose field names
    prose_fields = ['note', 'notes', 'comment', 'review', 'why']
    for field in prose_fields:
        if field in row and row[field]:
            val = row[field]
            if isinstance(val, str):
                parts.append(val)

    # Answers array
    if 'answers' in row and row['answers']:
        if isinstance(row['answers'], list):
            for ans in row['answers']:
                if isinstance(ans, dict):
                    if 'text' in ans and ans['text']:
                        parts.append(ans['text'])
                elif isinstance(ans, str):
                    parts.append(ans)

    # Variant: answer (singular)
    if 'answer' in row and row['answer']:
        val = row['answer']
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, dict) and 'text' in val:
            parts.append(val['text'])

    return ' '.join(parts)

def extract_row(row, source_file):
    """
    Extract the required fields from a row.
    Returns (symbol, day, source_file, card_id, grade, comment, entry_t, stop, target)
    or None if required fields are missing.
    """
    # Try to get symbol/day/card_id from various schema variations
    symbol = row.get('symbol') or row.get('ticker')

    # day/date
    day = row.get('day') or row.get('date')

    # card_id
    card_id = row.get('card_id') or row.get('id')

    if not (symbol and day and card_id):
        return None

    # Grade
    grade = row.get('grade') or row.get('verdict') or ''

    # Comment
    comment = extract_comment(row)

    # Optional fields
    entry_t = row.get('entry_t')
    stop = row.get('stop')
    target = row.get('target')

    return {
        'symbol': symbol,
        'day': day,
        'source_file': os.path.basename(source_file),
        'card_id': card_id,
        'grade': grade,
        'comment': comment,
        'entry_t': entry_t,
        'stop': stop,
        'target': target,
    }

def main():
    all_files = get_all_mark_files()
    print(f"Total mark files found: {len(all_files)}")

    # Assign files to agents
    my_files = [f for i, f in enumerate(all_files) if i % AGENT_TOTAL == AGENT_INDEX]
    print(f"F1 assigned {len(my_files)} files:")
    for f in my_files:
        print(f"  {os.path.basename(f)}")

    # Process files
    rows = []
    seen = set()  # For deduplication
    grade_counts = defaultdict(int)
    comment_len_counts = defaultdict(int)
    file_counts = defaultdict(int)

    for source_file in my_files:
        for raw_row in read_jsonl(source_file):
            extracted = extract_row(raw_row, source_file)
            if extracted is None:
                continue

            # Dedupe exact duplicates
            row_tuple = (
                extracted['symbol'],
                extracted['day'],
                extracted['source_file'],
                extracted['card_id'],
            )
            if row_tuple in seen:
                continue
            seen.add(row_tuple)

            rows.append(extracted)

            # Stats
            grade = extracted['grade']
            grade_counts[grade] += 1

            comment_len = len(extracted['comment'])
            file_counts[os.path.basename(source_file)] += 1
            if comment_len > 3:
                comment_len_counts[os.path.basename(source_file)] += 1

    # Write output
    with open(OUTPUT_FILE, 'w') as f:
        for row in rows:
            f.write(json.dumps(row) + '\n')

    print(f"Wrote {len(rows)} rows to {OUTPUT_FILE}")

    # Write report
    with open(REPORT_FILE, 'w') as f:
        f.write("# F1 Mark Comments Extract (Part 8)\n\n")
        f.write(f"Extracted comments from {len(my_files)} mark files assigned to F1.\n\n")
        f.write(f"**Total rows: {len(rows)}**\n")
        f.write(f"**Rows with comment > 3 chars: {sum(1 for r in rows if len(r['comment']) > 3)}**\n\n")

        f.write("## By Grade\n\n")
        for grade in sorted(grade_counts.keys()):
            count = grade_counts[grade]
            f.write(f"- {grade}: {count}\n")

        f.write("\n## By Source File\n\n")
        for fname in sorted(file_counts.keys()):
            count = file_counts[fname]
            with_comment = comment_len_counts[fname]
            f.write(f"- {fname}: {count} rows, {with_comment} with comment > 3 chars\n")

    print(f"Wrote report to {REPORT_FILE}")

    # Return stats
    total_rows = len(rows)
    rows_with_comment = sum(1 for r in rows if len(r['comment']) > 3)
    print(f"\n=== Summary ===")
    print(f"Total rows: {total_rows}")
    print(f"Rows with comment > 3 chars: {rows_with_comment}")

if __name__ == '__main__':
    main()
