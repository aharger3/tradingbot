#!/usr/bin/env python3
"""
Verify g150_marks_comments_part3.jsonl output.

Checks:
- Output file exists
- Row count is within 5% of input (176 rows)
- No corpus files modified
"""
import json
import subprocess
from pathlib import Path

def check_output():
    output_file = Path('research/g150_marks_comments_part3.jsonl')
    input_file = Path('research/recovered_reviews.jsonl')

    # Check output exists
    if not output_file.exists():
        print(f"ERROR: {output_file} does not exist")
        return False

    # Count input rows
    with open(input_file) as f:
        input_count = sum(1 for _ in f)

    # Count output rows
    with open(output_file) as f:
        output_count = sum(1 for _ in f)

    # Check within 5%
    tolerance = input_count * 0.05
    if abs(output_count - input_count) > tolerance:
        print(f"ERROR: Output count {output_count} not within 5% of input count {input_count}")
        print(f"       Tolerance: {tolerance}, difference: {abs(output_count - input_count)}")
        return False

    print(f"OK: Input {input_count} rows, output {output_count} rows (within 5%)")

    # Check corpus files not modified
    result = subprocess.run(
        ['git', 'status', '--porcelain', 'research/marks'],
        capture_output=True,
        text=True
    )

    if result.stdout.strip():
        print(f"ERROR: Corpus files were modified:")
        print(result.stdout)
        return False

    print(f"OK: No corpus files modified")

    # Validate JSON structure
    try:
        with open(output_file) as f:
            for i, line in enumerate(f):
                row = json.loads(line)
                required_fields = ['symbol', 'day', 'source_file', 'card_id', 'grade', 'comment']
                for field in required_fields:
                    if field not in row:
                        print(f"ERROR: Row {i} missing field '{field}'")
                        return False
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON at line {i}: {e}")
        return False

    print(f"OK: JSON structure valid ({output_count} rows)")

    return True

if __name__ == '__main__':
    success = check_output()
    exit(0 if success else 1)
