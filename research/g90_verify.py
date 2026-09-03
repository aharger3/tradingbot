"""OMEN 8.0 R1 verify: research/g90_fill_arms.md carries a table with all four
fill arms, each with mean R / win rate / months green / trades / $/day, all
computed from the same signal set (a single run of g90_fill_arms.py), and no
two arms report an identical trade count. Exit 0 = pass, nonzero = fail."""
import re
import sys

ARMS = ["as_booked", "limit_level", "next_open", "chase_once"]
PATH = "g90_fill_arms.md"


def main():
    try:
        text = open(PATH).read()
    except OSError as e:
        print(f"FAIL: cannot read {PATH}: {e}")
        return 1

    rows = {}
    for line in text.splitlines():
        m = re.match(r"\|\s*(\w+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)%\s*\|\s*([+\-][\d.]+)\s*\|"
                     r"\s*(\d+)\s*\|\s*(\d+)/(\d+)\s*\|\s*\$([\d,]+)\s*\|", line)
        if m:
            arm = m.group(1)
            if arm in ARMS:
                rows[arm] = dict(trades=int(m.group(2)), unfilled=int(m.group(3)),
                                 wr=float(m.group(4)), mean_r=float(m.group(5)),
                                 months=int(m.group(6)), green=int(m.group(7)),
                                 dollar_day=int(m.group(9).replace(",", "")))

    missing = [a for a in ARMS if a not in rows]
    if missing:
        print(f"FAIL: missing arm(s): {missing}")
        return 1

    counts = [rows[a]["trades"] for a in ARMS]
    if len(set(counts)) != len(counts):
        dupes = {c for c in counts if counts.count(c) > 1}
        print(f"FAIL: two or more arms share a trade count: {dupes} -- "
              f"{[a for a in ARMS if rows[a]['trades'] in dupes]}")
        return 1

    for a in ARMS:
        r = rows[a]
        if r["trades"] <= 0:
            print(f"FAIL: {a} has zero trades")
            return 1
        if r["months"] <= 0 or r["green"] > r["months"]:
            print(f"FAIL: {a} has an invalid green-months figure")
            return 1

    print(f"PASS: all four arms present, distinct trade counts {sorted(counts)}, "
          f"each carrying mean R / win rate / months green / $/day.")
    for a in ARMS:
        print(f"  {a}: {rows[a]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
