"""sunday_summary.py -- weekly tape receipt line for the tape summary.

Reads the last 7 days of research/tape/nightly.md and current loop.json baseline_figures,
appends one row to Projects/omen-tape-summary.md in the vault under a Weekly receipts table.
Never rewrites earlier weeks -- append-only.

Then git -C <vault> pull --rebase --autostash, commit the summary file, and push.
Returns 0 always so the scheduled task never fails.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAPE = ROOT / "research" / "tape"
NIGHTLY = TAPE / "nightly.md"
LOOP_CONFIG = TAPE / "loop.json"
VAULT = Path(r"C:\Users\aharg\Austin's Vault")
SUMMARY = VAULT / "Projects" / "omen-tape-summary.md"


def read_nightly_lines(days: int = 7) -> list[str]:
    """Return the last N days of receipt lines (non-empty, non-header).

    Format of each line: | YYYY-MM-DD | flag | decision | ... |
    """
    if not NIGHTLY.exists():
        return []

    lines = NIGHTLY.read_text(encoding="utf-8").split("\n")
    # Skip header lines (comment and separator)
    receipt_lines = [l.strip() for l in lines if l.strip().startswith("|") and "date" not in l and "---|" not in l]
    return receipt_lines[-days:] if receipt_lines else []


def parse_receipt_line(line: str) -> dict:
    """Parse one receipt line into its fields.

    Format: | YYYY-MM-DD | flag | decision | $/day a->b | green a->b | off_book_id -> on_book_id |
    Returns {'date': str, 'decision': str, 'tried': bool}
    """
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 4:
        return None
    try:
        return {
            "date": parts[1],
            "decision": parts[3].lower(),  # "ship", "hold", "empty"
            "tried": parts[3].lower() != "empty",
        }
    except IndexError:
        return None


def load_baseline_figures() -> dict:
    """Read baseline_figures from loop.json."""
    if not LOOP_CONFIG.exists():
        return {}
    try:
        data = json.loads(LOOP_CONFIG.read_text(encoding="utf-8"))
        return data.get("baseline_figures", {})
    except json.JSONDecodeError:
        return {}


def make_summary_row(nightly_lines: list[str], baseline: dict) -> str:
    """Build one summary row from the last 7 days of nightly.md.

    Format: | week of YYYY-MM-DD | tried N | shipped N | held N | $X/day | G/25 green |

    where "week of YYYY-MM-DD" is the Monday of the week being summarized.
    """
    if not nightly_lines:
        return None

    # Parse each receipt line
    receipts = [parse_receipt_line(l) for l in nightly_lines]
    receipts = [r for r in receipts if r is not None]

    if not receipts:
        return None

    # Count outcomes
    tried = sum(1 for r in receipts if r["tried"])
    shipped = sum(1 for r in receipts if r["tried"] and r["decision"] == "ship")
    held = sum(1 for r in receipts if r["tried"] and r["decision"] == "hold")

    # Get the earliest date in this slice to label the week
    # Find the Monday of that week
    earliest_date_str = receipts[0]["date"]  # First line is oldest (read bottom-to-top)
    earliest = date.fromisoformat(earliest_date_str)
    week_monday = earliest - timedelta(days=earliest.weekday())

    # Get baseline figures
    whole = baseline.get("whole", {})
    per_day = whole.get("per_day", "-")
    months_green = whole.get("months_green", "-")
    months_total = whole.get("months", 25)

    green_str = f"{months_green}/{months_total}" if isinstance(months_green, int) else f"{months_green}/{months_total}"

    # Build the row
    row = f"| week of {week_monday.isoformat()} | tried {tried} | shipped {shipped} | held {held} | ${per_day}/day | {green_str} green |"
    return row


def append_to_summary(row: str) -> bool:
    """Append the row to omen-tape-summary.md, creating the table if needed.

    Returns True if successful, False otherwise.
    """
    if not SUMMARY.parent.exists():
        print(f"sunday_summary.py: vault path does not exist: {SUMMARY.parent}", file=sys.stderr)
        return False

    heading = "## Weekly receipts"
    header = "| week of YYYY-MM-DD | tried N | shipped N | held N | $/day | green months |"
    separator = "|---|---|---|---|---|---|"

    if not SUMMARY.exists():
        # Create the file with heading, header, separator, and first row
        content = f"---\ntype: receipt\n---\n\n{heading}\n\n{header}\n{separator}\n{row}\n"
        SUMMARY.write_text(content, encoding="utf-8")
        print(f"Created {SUMMARY} with first row", file=sys.stderr)
        return True

    # File exists -- check if the heading is present
    content = SUMMARY.read_text(encoding="utf-8")

    if heading not in content:
        # Append the heading and table
        if not content.endswith("\n"):
            content += "\n"
        content += f"\n{heading}\n\n{header}\n{separator}\n{row}\n"
    else:
        # Heading exists -- find it and append after the separator
        lines = content.split("\n")
        heading_idx = None
        sep_idx = None
        for i, line in enumerate(lines):
            if heading in line:
                heading_idx = i
            if heading_idx is not None and separator in line:
                sep_idx = i
                break

        if sep_idx is not None:
            # Insert the row after the separator
            lines.insert(sep_idx + 1, row)
            content = "\n".join(lines)
        else:
            # Separator not found, append to end
            if not content.endswith("\n"):
                content += "\n"
            content += row + "\n"

    SUMMARY.write_text(content, encoding="utf-8")
    return True


def git_commit_vault() -> bool:
    """Commit the summary file in the vault repo and push.

    Returns True if successful, False otherwise.
    """
    try:
        # Pull first with autostash
        proc = subprocess.run(
            ["git", "-C", str(VAULT), "pull", "--rebase", "--autostash"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            print(f"sunday_summary.py: git pull failed: {proc.stderr}", file=sys.stderr)
            # Continue anyway -- commit anyway

        # Stage the summary file
        proc = subprocess.run(
            ["git", "-C", str(VAULT), "add", str(SUMMARY)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            print(f"sunday_summary.py: git add failed: {proc.stderr}", file=sys.stderr)
            return False

        # Commit
        week_str = date.today().isoformat()
        proc = subprocess.run(
            ["git", "-C", str(VAULT), "commit", "-m", f"omen: weekly tape receipt {week_str}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            # Commit may fail if there's nothing to commit (no change)
            # This is OK -- the row was already written
            print(f"sunday_summary.py: git commit (may be OK): {proc.stderr}", file=sys.stderr)

        # Push
        proc = subprocess.run(
            ["git", "-C", str(VAULT), "push"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            print(f"sunday_summary.py: git push failed: {proc.stderr}", file=sys.stderr)
            return False

        return True
    except Exception as exc:
        print(f"sunday_summary.py: git operations failed: {exc}", file=sys.stderr)
        return False


def main() -> int:
    """Main entry point. Always returns 0 so the task never fails."""
    try:
        nightly_lines = read_nightly_lines(days=7)
        if not nightly_lines:
            print("No nightly receipts found", file=sys.stderr)
            return 0

        baseline = load_baseline_figures()
        row = make_summary_row(nightly_lines, baseline)

        if row is None:
            print("Could not build summary row from nightly receipts", file=sys.stderr)
            return 0

        if not append_to_summary(row):
            print("Failed to append row to summary", file=sys.stderr)
            return 0

        if not git_commit_vault():
            print("Failed to commit to vault (but row was written)", file=sys.stderr)
            # Don't fail the task -- the row exists locally
            return 0

        print(row.strip())
        return 0
    except Exception as exc:
        print(f"sunday_summary.py: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
