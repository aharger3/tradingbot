#!/usr/bin/env python3
"""Extract marks comments from part 7 file group."""

import json
import sys
from pathlib import Path
from collections import defaultdict

def extract_comment(row):
    """Concatenate all prose fields into one comment."""
    parts = []

    # Direct fields
    for field in ['note', 'comment', 'review', 'why']:
        if field in row and row[field]:
            val = str(row[field]).strip()
            if val:
                parts.append(val)

    # notes dict fields
    if 'notes' in row and isinstance(row['notes'], dict):
        for key, val in row['notes'].items():
            if val:
                val_str = str(val).strip()
                if val_str:
                    parts.append(val_str)

    # answers fields
    if 'answers' in row and isinstance(row['answers'], dict):
        for key, val_list in row['answers'].items():
            if isinstance(val_list, list):
                for val in val_list:
                    if val:
                        val_str = str(val).strip()
                        if val_str:
                            parts.append(val_str)

    return ' '.join(parts)

def extract_row(row, source_file):
    """Extract row data from a mark record."""
    # Extract required fields
    symbol = row.get('symbol')
    day = row.get('date')
    card_id = row.get('card_id')
    grade = row.get('grade')

    # Convert None grade to 'none'
    if grade is None:
        grade = 'none'
    else:
        grade = str(grade).strip()

    # Extract comment
    comment = extract_comment(row)

    # Extract optional timing fields
    entry_t = row.get('entry_t')
    stop = row.get('stop')
    target = row.get('target')

    # Build output row
    out = {
        'symbol': symbol,
        'day': day,
        'source_file': source_file,
        'card_id': card_id,
        'grade': grade,
        'comment': comment,
    }

    # Add optional fields if present
    if entry_t is not None:
        out['entry_t'] = entry_t
    if stop is not None:
        out['stop'] = stop
    if target is not None:
        out['target'] = target

    return out

def process_files():
    """Process all files in the file group."""
    file_group = [
        'research/marks/probe_master_2026-08-29.jsonl',
        'research/marks/probe_master_homework_2026-08-26.jsonl',
        'research/marks/probe_s_sweep_2026-08-28.jsonl',
        'research/marks/probe_g71_homework_s3_2026-08-29.jsonl',
    ]

    # Also check for _complete variant
    for fname in list(Path('research/marks').glob('probe_g71_homework_s3_2026-08-29*.jsonl')):
        if fname.name not in file_group:
            file_group.append(str(fname))

    rows = []
    seen_exact = set()

    for fpath_str in file_group:
        fpath = Path(fpath_str)
        if not fpath.exists():
            print(f"Warning: {fpath} not found", file=sys.stderr)
            continue

        source_file = fpath.name

        with open(fpath) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    row_data = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"Error parsing {source_file} line {line_num}: {e}", file=sys.stderr)
                    continue

                # Extract the row
                row = extract_row(row_data, source_file)

                # Dedup exact duplicates only
                # Create a hashable key from the row
                row_key = (
                    row.get('symbol'),
                    row.get('day'),
                    row.get('source_file'),
                    row.get('card_id'),
                    row.get('grade'),
                    row.get('comment'),
                    row.get('entry_t'),
                    row.get('stop'),
                    row.get('target'),
                )

                if row_key not in seen_exact:
                    seen_exact.add(row_key)
                    rows.append(row)

    return rows

def main():
    rows = process_files()

    # Write output
    with open('research/g150_marks_comments_part7.jsonl', 'w') as f:
        for row in rows:
            f.write(json.dumps(row) + '\n')

    # Count statistics
    total = len(rows)
    with_comment_gt3 = sum(1 for r in rows if len(r.get('comment', '')) > 3)

    print(f"Rows written: {total}")
    print(f"Rows with comment > 3 chars: {with_comment_gt3}")

    # Count by grade
    grade_counts = defaultdict(int)
    for r in rows:
        grade_counts[r.get('grade', 'unknown')] += 1

    print("\nGrade distribution:")
    for grade in sorted(grade_counts.keys()):
        print(f"  {grade}: {grade_counts[grade]}")

    # Count by source file
    source_counts = defaultdict(int)
    for r in rows:
        source_counts[r.get('source_file')] += 1

    print("\nSource file distribution:")
    for source in sorted(source_counts.keys()):
        print(f"  {source}: {source_counts[source]}")

if __name__ == '__main__':
    main()
