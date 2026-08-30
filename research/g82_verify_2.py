"""Adversarial recompute of the OMEN 7.1 verdict sheet's After column.

Reads research/bt2y_trades.json (the shipped stack book) directly, with no
help from research/t23_stack.json, and reprints every number the page's
Before/After table claims in its After column. Then it reads the numbers
back out of research/omen-71-verdict.html and diffs them.

Also hunts duplicate rows in the book and duplicate lines on the page,
because the complaint that started this was "random repeats".

  python research/g82_verify_2.py
"""
from __future__ import annotations

import json, math, os, re, statistics as st
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.join(HERE, "bt2y_trades.json")
PAGE = os.path.join(HERE, "omen-71-verdict.html")
STACK = os.path.join(HERE, "t23_stack.json")

rows = json.load(open(BOOK, encoding="utf-8"))["trades"]
tr = [r for r in rows if r.get("traded")]
rs = [r["r"] for r in tr]

wins = sum(1 for r in tr if r["out"] == "win")
losses = sum(1 for r in tr if r["out"] == "loss")
decided = wins + losses
by_month = defaultdict(float)
for r in tr:
    by_month[r["ym"]] += r["r"]

mine = {
    "signals":     len(rows),
    "traded":      len(tr),
    "mean_r":      round(st.fmean(rs), 4),
    "win_rate":    round(wins / decided * 100, 2),
    "total_r":     round(sum(rs), 2),
    "months_green": "%d/%d" % (sum(1 for v in by_month.values() if v > 0), len(by_month)),
    "index_trades": sum(1 for r in tr if r["cls"] == "etf"),
    "worst_r":     round(min(rs), 4),
    "past_1r":     sum(1 for r in rs if r < -1.0 - 1e-9),
}

print("== recomputed straight off bt2y_trades.json ==")
for k, v in mine.items():
    print("  %-14s %s" % (k, v))

# --- compare to t23_stack.json, which the generator reads -------------------
stack = json.load(open(STACK, encoding="utf-8"))["arms"]["stack"]
print("\n== vs research/t23_stack.json arms.stack ==")
bad = 0
for k in ("signals", "traded", "mean_r", "win_rate", "total_r", "months_green", "index_trades"):
    theirs = stack.get(k)
    ok = str(theirs) == str(mine[k])
    bad += 0 if ok else 1
    print("  %-14s mine=%-12s theirs=%-12s %s" % (k, mine[k], theirs, "OK" if ok else "MISMATCH"))

# --- pull the After column out of the page ----------------------------------
html = open(PAGE, encoding="utf-8").read()
cells = {}
for m in re.finditer(r"<tr><td>([^<]+)</td><td class=\"n\">([^<]*)</td><td class=\"n\">([^<]*)</td>", html):
    cells[m.group(1).strip()] = (m.group(2).strip(), m.group(3).strip())

def num(s):
    s = s.replace("&minus;", "-").replace("&times;", "").replace(",", "").replace("%", "").replace("R", "").replace("+", "").strip()
    try:
        return float(s)
    except ValueError:
        return s

print("\n== page After column vs recompute ==")
checks = [
    ("Traded signals",  mine["traded"]),
    ("Signals detected", mine["signals"]),
    ("Mean R",          mine["mean_r"]),
    ("Win rate",        round(mine["win_rate"], 1)),
    ("Total R",         round(mine["total_r"])),
    ("Index trades",    mine["index_trades"]),
    ("Worst single trade", mine["worst_r"]),
    ("Losses past 1R",  mine["past_1r"]),
]
for label, expect in checks:
    if label not in cells:
        print("  %-20s NOT FOUND ON PAGE" % label); bad += 1; continue
    got = num(cells[label][1])
    ok = isinstance(got, float) and abs(got - float(expect)) < 0.51
    bad += 0 if ok else 1
    print("  %-20s page=%-10s recomputed=%-10s %s" % (label, cells[label][1], expect, "OK" if ok else "MISMATCH"))

# --- the two derived move cells --------------------------------------------
print("\n== derived moves ==")
print("  win rate move   53.1 -> %.1f  = %+.1f" % (mine["win_rate"], mine["win_rate"] - 53.1))
print("  index multiple  %d / 18       = %.2fx" % (mine["index_trades"], mine["index_trades"] / 18))

# --- duplicate hunt: book ---------------------------------------------------
key = lambda r: (r["sym"], r["day"], r["et"], r["setup"], r["dir"], r["entry"])
dupes = [k for k, c in Counter(key(r) for r in tr).items() if c > 1]
print("\n== duplicate traded rows in the book ==")
print("  exact repeats of (sym, day, time, setup, dir, entry): %d" % len(dupes))
for k in dupes[:10]:
    print("   ", k)

# --- duplicate hunt: page ---------------------------------------------------
lines = [l.strip() for l in html.splitlines() if l.strip()]
content = [l for l in lines if l.startswith("<tr>") or l.startswith("<p") or l.startswith("<li")]
pdupes = [(l, c) for l, c in Counter(content).items() if c > 1]
print("\n== duplicate content lines on the page ==")
print("  repeated <tr>/<p>/<li> lines: %d" % len(pdupes))
for l, c in pdupes[:10]:
    print("   x%d  %s" % (c, l[:120]))

# --- external network resources --------------------------------------------
ext = re.findall(r'(?:src|href)\s*=\s*["\'](https?:|//)', html)
print("\n== external resources on the page: %d ==" % len(ext))

print("\nVERDICT: %d mismatch(es)" % bad)
