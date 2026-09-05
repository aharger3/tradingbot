#!/usr/bin/env python3
"""
F1 Part 4: Extract comments from marks_clean.jsonl and related deck/probe files.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict


def extract_comment_from_row(row):
    """Concatenate all prose fields into one comment."""
    parts = []

    # Direct prose fields (but skip 'notes' if it's a dict, handled separately below)
    for field in ['note', 'comment', 'review', 'why', 'management', 'align_reason']:
        if field in row and row[field]:
            val = str(row[field]).strip()
            if val:
                parts.append(val)

    # notes dict fields (if notes is a dict)
    if 'notes' in row and isinstance(row['notes'], dict):
        for key, val in row['notes'].items():
            if val:
                val_str = str(val).strip()
                if val_str:
                    parts.append(val_str)
    # notes as a direct string
    elif 'notes' in row and row['notes'] and not isinstance(row['notes'], dict):
        val = str(row['notes']).strip()
        if val:
            parts.append(val)

    # answers fields
    if 'answers' in row and isinstance(row['answers'], dict):
        for key, val_list in row['answers'].items():
            if isinstance(val_list, list):
                for val in val_list:
                    if val:
                        val_str = str(val).strip()
                        if val_str:
                            parts.append(val_str)
    elif 'answers' in row and isinstance(row['answers'], list):
        for val in row['answers']:
            if val:
                if isinstance(val, dict):
                    for k, v in val.items():
                        if v:
                            parts.append(str(v).strip())
                else:
                    parts.append(str(val).strip())

    return ' '.join(parts)


def get_grade(row):
    """Extract grade field (S/A/C/none)."""
    # Try multiple field names
    for field in ['austin_tier', 'tier', 'grade', 'verdict']:
        if field in row and row[field]:
            val = str(row[field]).strip()
            if val and val != '':
                return val
    return 'none'


def extract_row(row, source_file):
    """Extract a row from a mark record."""
    symbol = row.get('symbol')
    day = row.get('day') or row.get('date')
    grade = get_grade(row)
    comment = extract_comment_from_row(row)

    # Try to construct card_id
    entry_i = row.get('entry_i')
    if entry_i is not None and symbol and day:
        card_id = f"{symbol}_{day}_{entry_i}"
    else:
        card_id = row.get('id') or row.get('card_id') or f"{symbol}_{day}"

    out = {
        'symbol': symbol,
        'day': day,
        'source_file': source_file,
        'card_id': card_id,
        'grade': grade,
        'comment': comment,
    }

    # Add optional fields if present
    entry_t = row.get('entry_t')
    stop = row.get('stop')
    target = row.get('target')

    if entry_t is not None:
        out['entry_t'] = entry_t
    if stop is not None:
        out['stop'] = stop
    if target is not None:
        out['target'] = target

    return out


def process_marks_clean():
    """Process marks_clean.jsonl"""
    rows = []
    fpath = Path('research/marks_clean.jsonl')

    if fpath.exists():
        with open(fpath) as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    extracted = extract_row(row, 'marks_clean')
                    rows.append(extracted)

    return rows


def process_deck_marks_index():
    """Process deck_marks_index_2026-08-19.jsonl"""
    rows = []
    fpath = Path('research/marks/deck_marks_index_2026-08-19.jsonl')

    if fpath.exists():
        with open(fpath) as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    extracted = extract_row(row, 'deck_marks_index_2026-08-19')
                    rows.append(extracted)

    return rows


def process_deck_marks_tsla():
    """Process deck_marks_tsla_2026-08-20.jsonl"""
    rows = []
    fpath = Path('research/marks/deck_marks_tsla_2026-08-20.jsonl')

    if fpath.exists():
        with open(fpath) as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    extracted = extract_row(row, 'deck_marks_tsla_2026-08-20')
                    rows.append(extracted)

    return rows


def process_probe_autopsy():
    """Process probe_autopsy_2026-08-23.jsonl"""
    rows = []
    fpath = Path('research/marks/probe_autopsy_2026-08-23.jsonl')

    if fpath.exists():
        with open(fpath) as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    extracted = extract_row(row, 'probe_autopsy_2026-08-23')
                    rows.append(extracted)

    return rows


def process_probe_head2head():
    """Process probe_head2head_2026-08-24.jsonl"""
    rows = []
    fpath = Path('research/marks/probe_head2head_2026-08-24.jsonl')

    if fpath.exists():
        with open(fpath) as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    extracted = extract_row(row, 'probe_head2head_2026-08-24')
                    rows.append(extracted)

    return rows


def process_probe_trade_anatomy():
    """Process probe_trade_anatomy_2026-09-01.jsonl"""
    rows = []
    fpath = Path('research/marks/probe_trade_anatomy_2026-09-01.jsonl')

    if fpath.exists():
        with open(fpath) as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    extracted = extract_row(row, 'probe_trade_anatomy_2026-09-01')
                    rows.append(extracted)

    return rows


def main():
    # Collect all rows from all files
    all_rows = []
    all_rows.extend(process_marks_clean())
    all_rows.extend(process_deck_marks_index())
    all_rows.extend(process_deck_marks_tsla())
    all_rows.extend(process_probe_autopsy())
    all_rows.extend(process_probe_head2head())
    all_rows.extend(process_probe_trade_anatomy())

    print(f"Total rows before dedup: {len(all_rows)}")

    # Dedupe exact duplicates only
    seen = {}
    deduped = []
    for row in all_rows:
        key = (row['symbol'], row['day'], row['card_id'], row['grade'], row['comment'])
        if key not in seen:
            seen[key] = row
            deduped.append(row)

    print(f"Total rows after dedup: {len(deduped)}")

    # Write output
    with open('research/g150_marks_comments_part4.jsonl', 'w') as f:
        for row in deduped:
            f.write(json.dumps(row) + '\n')

    # Count statistics
    total = len(deduped)
    with_comment_gt3 = sum(1 for r in deduped if len(r.get('comment', '')) > 3)
    with_comment_gt40 = sum(1 for r in deduped if len(r.get('comment', '')) > 40)

    print(f"Rows written: {total}")
    print(f"Rows with comment > 3 chars: {with_comment_gt3}")
    print(f"Rows with comment > 40 chars: {with_comment_gt40}")

    # Count by grade
    grade_counts = defaultdict(int)
    for r in deduped:
        grade_counts[r.get('grade', 'unknown')] += 1

    print("\nGrade distribution:")
    for grade in sorted(grade_counts.keys()):
        print(f"  {grade}: {grade_counts[grade]}")

    # Count by source file
    source_counts = defaultdict(int)
    for r in deduped:
        source_counts[r.get('source_file')] += 1

    print("\nSource file distribution:")
    for source in sorted(source_counts.keys()):
        print(f"  {source}: {source_counts[source]}")


if __name__ == '__main__':
    main()
