#!/usr/bin/env python3
"""
F1 Part 5: Extract comments from mark_batch_02/03/04, derived_marks_v*, rule_ballot_batch0*, austin_verdicts
"""

import json
import os
from pathlib import Path
from collections import defaultdict

def extract_comment_from_row(row):
    """Extract comment text from all prose fields"""
    comment_parts = []

    # Fields to search for comment text
    prose_fields = ['note', 'notes', 'comment', 'review', 'why']

    for field in prose_fields:
        if field in row and row[field]:
            comment_parts.append(str(row[field]))

    # Check for answers array
    if 'answers' in row and isinstance(row['answers'], list):
        for answer in row['answers']:
            if isinstance(answer, dict):
                for key, val in answer.items():
                    if val and key not in ['id', 'card_id', 'symbol', 'day']:
                        comment_parts.append(str(val))
            else:
                comment_parts.append(str(answer))

    # Also check for standalone answer field
    if 'answer' in row and row['answer']:
        comment_parts.append(str(row['answer']))

    return ' '.join(comment_parts).strip()

def get_grade_from_row(row):
    """Extract grade field (S/A/C/none)"""
    # Different files use different grade field names
    for field_name in ['austin_grade', 'tier', 'verdict', 'grade']:
        if field_name in row:
            grade = row[field_name]
            if grade:
                return str(grade).upper()
    return 'none'

def get_symbol_day(row):
    """Extract symbol and day"""
    symbol = row.get('symbol', '')
    day = row.get('day', '')
    return symbol, day

def process_mark_batch_02():
    """Process mark_batch_02_grades.jsonl"""
    rows = []
    filepath = Path('research/mark_batch_02_grades.jsonl')
    if not filepath.exists():
        return rows

    with open(filepath) as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                symbol, day = get_symbol_day(row)
                if not symbol or not day:
                    continue

                # Extract card_id or use line number
                card_id = row.get('card', f'mark_batch_02_line{line_no}')
                grade = row.get('austin_grade', 'none')
                comment = extract_comment_from_row(row)

                # Extract entry_t, stop, target if present
                entry_t = row.get('entry_t', row.get('tod'))
                stop = row.get('stop')
                target = row.get('target')

                rows.append({
                    'symbol': symbol,
                    'day': day,
                    'source_file': 'mark_batch_02_grades.jsonl',
                    'card_id': str(card_id),
                    'grade': grade,
                    'comment': comment,
                    'entry_t': entry_t,
                    'stop': stop,
                    'target': target
                })
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_no} in mark_batch_02_grades.jsonl: {e}")

    return rows

def process_mark_batch_03():
    """Process mark_batch_03_regrades.jsonl"""
    rows = []
    filepath = Path('research/mark_batch_03_regrades.jsonl')
    if not filepath.exists():
        return rows

    with open(filepath) as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                symbol, day = get_symbol_day(row)
                if not symbol or not day:
                    continue

                card_id = row.get('id', row.get('card', f'mark_batch_03_line{line_no}'))
                grade = row.get('tier', 'none')
                comment = extract_comment_from_row(row)

                entry_t = row.get('entry_t', row.get('tod'))
                stop = row.get('stop')
                target = row.get('target')

                rows.append({
                    'symbol': symbol,
                    'day': day,
                    'source_file': 'mark_batch_03_regrades.jsonl',
                    'card_id': str(card_id),
                    'grade': grade,
                    'comment': comment,
                    'entry_t': entry_t,
                    'stop': stop,
                    'target': target
                })
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_no} in mark_batch_03_regrades.jsonl: {e}")

    return rows

def process_mark_batch_04():
    """Process mark_batch_04_grades.jsonl"""
    rows = []
    filepath = Path('research/mark_batch_04_grades.jsonl')
    if not filepath.exists():
        return rows

    with open(filepath) as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)

                # These don't always have symbol/day in the same way
                if 'id' in row:
                    # Try to parse from id: "AMD_2026-05-14_17"
                    parts = row['id'].rsplit('_', 1)
                    if len(parts) >= 2:
                        symbol_day = parts[0]
                        symbol_day_parts = symbol_day.rsplit('_', 1)
                        if len(symbol_day_parts) == 2:
                            symbol, day = symbol_day_parts
                        else:
                            continue
                    else:
                        continue
                else:
                    symbol = row.get('symbol', '')
                    day = row.get('day', '')

                if not symbol or not day:
                    continue

                card_id = row.get('id', f'mark_batch_04_line{line_no}')
                grade = row.get('tier', 'none')
                comment = extract_comment_from_row(row)

                entry_t = row.get('entry_t')
                stop = row.get('stop')
                target = row.get('target')

                rows.append({
                    'symbol': symbol,
                    'day': day,
                    'source_file': 'mark_batch_04_grades.jsonl',
                    'card_id': str(card_id),
                    'grade': grade,
                    'comment': comment,
                    'entry_t': entry_t,
                    'stop': stop,
                    'target': target
                })
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing line {line_no} in mark_batch_04_grades.jsonl: {e}")

    return rows

def process_derived_marks_v1():
    """Process derived_marks_v1.jsonl"""
    rows = []
    filepath = Path('research/derived_marks_v1.jsonl')
    if not filepath.exists():
        return rows

    with open(filepath) as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                symbol, day = get_symbol_day(row)
                if not symbol or not day:
                    continue

                card_id = row.get('id', f'derived_marks_v1_line{line_no}')
                grade = row.get('tier', 'none')
                comment = extract_comment_from_row(row)

                entry_t = row.get('entry_t', row.get('tod'))
                stop = row.get('stop')
                target = row.get('target')

                rows.append({
                    'symbol': symbol,
                    'day': day,
                    'source_file': 'derived_marks_v1.jsonl',
                    'card_id': str(card_id),
                    'grade': grade,
                    'comment': comment,
                    'entry_t': entry_t,
                    'stop': stop,
                    'target': target
                })
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_no} in derived_marks_v1.jsonl: {e}")

    return rows

def process_derived_marks_v2():
    """Process derived_marks_v2.jsonl"""
    rows = []
    filepath = Path('research/derived_marks_v2.jsonl')
    if not filepath.exists():
        return rows

    with open(filepath) as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                symbol, day = get_symbol_day(row)
                if not symbol or not day:
                    continue

                card_id = row.get('id', f'derived_marks_v2_line{line_no}')
                grade = row.get('tier', 'none')
                comment = extract_comment_from_row(row)

                entry_t = row.get('entry_t', row.get('tod'))
                stop = row.get('stop')
                target = row.get('target')

                rows.append({
                    'symbol': symbol,
                    'day': day,
                    'source_file': 'derived_marks_v2.jsonl',
                    'card_id': str(card_id),
                    'grade': grade,
                    'comment': comment,
                    'entry_t': entry_t,
                    'stop': stop,
                    'target': target
                })
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_no} in derived_marks_v2.jsonl: {e}")

    return rows

def process_rule_ballot_batch01():
    """Process rule_ballot_batch01.jsonl"""
    rows = []
    filepath = Path('research/rule_ballot_batch01.jsonl')
    if not filepath.exists():
        return rows

    with open(filepath) as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)

                # These are rule ballots, not necessarily tied to specific symbol-days
                # Extract rule+ballot as pseudo symbol-day if available
                ballot = row.get('ballot', '')
                q = row.get('q', '')

                if not ballot or not q:
                    continue

                # Use ballot info as identifier
                symbol = f"{ballot}_q{q}"
                day = row.get('day', '2026-09-05')  # Use current date as placeholder

                card_id = f"rule_ballot_01_{q}"
                comment = extract_comment_from_row(row)

                # Rule ballots might have grade in answer
                grade = row.get('answer', 'none')
                if grade and grade.lower() in ['yes', 'no']:
                    grade = 'A' if grade.lower() == 'yes' else 'C'
                else:
                    grade = 'A'  # Default for rule ballots

                rows.append({
                    'symbol': symbol,
                    'day': day,
                    'source_file': 'rule_ballot_batch01.jsonl',
                    'card_id': str(card_id),
                    'grade': grade,
                    'comment': comment,
                    'entry_t': None,
                    'stop': None,
                    'target': None
                })
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_no} in rule_ballot_batch01.jsonl: {e}")

    return rows

def process_rule_ballot_batch02():
    """Process rule_ballot_batch02.jsonl"""
    rows = []
    filepath = Path('research/rule_ballot_batch02.jsonl')
    if not filepath.exists():
        return rows

    with open(filepath) as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)

                ballot = row.get('ballot', '')
                q = row.get('q', '')

                if not ballot or not q:
                    continue

                symbol = f"{ballot}_q{q}"
                day = row.get('day', '2026-09-05')

                card_id = f"rule_ballot_02_{q}"
                comment = extract_comment_from_row(row)

                grade = row.get('answer', 'none')
                if grade and grade.lower() in ['yes', 'no']:
                    grade = 'A' if grade.lower() == 'yes' else 'C'
                else:
                    grade = 'A'

                rows.append({
                    'symbol': symbol,
                    'day': day,
                    'source_file': 'rule_ballot_batch02.jsonl',
                    'card_id': str(card_id),
                    'grade': grade,
                    'comment': comment,
                    'entry_t': None,
                    'stop': None,
                    'target': None
                })
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_no} in rule_ballot_batch02.jsonl: {e}")

    return rows

def process_austin_verdicts():
    """Process austin_verdicts.json"""
    rows = []
    filepath = Path('research/austin_verdicts.json')
    if not filepath.exists():
        return rows

    try:
        with open(filepath) as f:
            verdicts = json.load(f)

        for idx, row in enumerate(verdicts):
            symbol = row.get('symbol', '')
            day = row.get('day', '')

            if not symbol or not day:
                continue

            entry_i = row.get('entry_i', '')
            card_id = f"{symbol}_{day}_{entry_i}"
            grade = row.get('verdict', 'none').upper()

            rows.append({
                'symbol': symbol,
                'day': day,
                'source_file': 'austin_verdicts.json',
                'card_id': card_id,
                'grade': grade,
                'comment': '',
                'entry_t': None,
                'stop': None,
                'target': None
            })
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing austin_verdicts.json: {e}")

    return rows

def main():
    os.chdir(Path(__file__).parent.parent)

    # Collect all rows from all files
    all_rows = []
    all_rows.extend(process_mark_batch_02())
    all_rows.extend(process_mark_batch_03())
    all_rows.extend(process_mark_batch_04())
    all_rows.extend(process_derived_marks_v1())
    all_rows.extend(process_derived_marks_v2())
    all_rows.extend(process_rule_ballot_batch01())
    all_rows.extend(process_rule_ballot_batch02())
    all_rows.extend(process_austin_verdicts())

    print(f"Total rows before dedup: {len(all_rows)}")

    # Dedupe exact duplicates only
    seen = {}
    deduped = []
    for row in all_rows:
        # Create a key from the unique fields (but not source_file for dedup)
        key = (row['symbol'], row['day'], row['card_id'], row['grade'],
               row['comment'], row['entry_t'], row['stop'], row['target'])

        if key not in seen:
            seen[key] = row
            deduped.append(row)

    print(f"Total rows after dedup: {len(deduped)}")

    # Count by source and grade
    source_counts = defaultdict(lambda: defaultdict(int))
    comment_over_40 = 0

    for row in deduped:
        source_counts[row['source_file']][row['grade']] += 1
        if len(row['comment']) > 40:
            comment_over_40 += 1

    print(f"\nRows with comment > 40 chars: {comment_over_40}")
    print("\nRows by source and grade:")
    for source in sorted(source_counts.keys()):
        print(f"  {source}:")
        for grade in sorted(source_counts[source].keys()):
            count = source_counts[source][grade]
            print(f"    {grade}: {count}")

    # Write output
    output_path = Path('research/g150_marks_comments_part5.jsonl')
    with open(output_path, 'w') as f:
        for row in deduped:
            # Only write non-null fields
            out_row = {
                'symbol': row['symbol'],
                'day': row['day'],
                'source_file': row['source_file'],
                'card_id': row['card_id'],
                'grade': row['grade'],
                'comment': row['comment']
            }
            if row['entry_t']:
                out_row['entry_t'] = row['entry_t']
            if row['stop']:
                out_row['stop'] = row['stop']
            if row['target']:
                out_row['target'] = row['target']

            f.write(json.dumps(out_row) + '\n')

    print(f"\nWrote {len(deduped)} rows to {output_path}")
    print(f"Rows with comment over 3 chars: {sum(1 for r in deduped if len(r['comment']) > 3)}")

if __name__ == '__main__':
    main()
