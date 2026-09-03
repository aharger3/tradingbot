"""ADVERSARIAL VERIFY of research/g71_losshalt.md S2c "days benched" table.

Independent re-implementation (does NOT import g71_losshalt_grid). Read-only over
research/bt2y_trades.json. Reports, per arm:
  A  days on which >=1 candidate was BLOCKED        (the report's likely definition)
  B  days on which the gate was ever TRIPPED
  C  days on which the arm took ZERO trades         (actually benched)
  plus trades removed, and trades already taken before the first block.
"""
from __future__ import annotations
import json, statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / "research" / "bt2y_trades.json").read_text(encoding="utf-8"))
rows = d["trades"]
print("meta:", {k: d["meta"][k] for k in ("first", "last", "sessions", "loss_halt", "halted", "traded")})
cand = [r for r in rows if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
all_sessions = sorted({r["day"] for r in rows})
cand_sessions = sorted({r["day"] for r in cand})
print("rows=%d candidates=%d  sessions_all=%d sessions_with_candidate=%d"
      % (len(rows), len(cand), len(all_sessions), len(cand_sessions)))
print("status histogram:", dict(sorted(
    ((s, sum(1 for r in rows if r["status"] == s)) for s in {x["status"] for x in rows}))))

ek = lambda r: (r["entry_i"], r["et"], r["sym"])
xk = lambda r: (r["entry_i"] + r["bars"], r["et"], r["sym"])


def walk(day_rows, halt_n, r_floor):
    order = sorted(day_rows, key=ek)
    pending, streak, realised = [], 0, 0.0
    taken, blocked = [], []
    tripped = False
    taken_before_first_block = None
    for row in order:
        at = ek(row)
        while pending and pending[0][0] <= at:
            _x, lost, rr = pending.pop(0)
            streak = streak + 1 if lost else 0
            realised += rr
        gate = (halt_n and streak >= halt_n) or (r_floor is not None and realised <= r_floor)
        if gate:
            tripped = True
        if gate:
            if taken_before_first_block is None:
                taken_before_first_block = len(taken)
            blocked.append(row)
            continue
        taken.append(row)
        pending.append((xk(row), row["out"] == "loss", row["r"]))
        pending.sort(key=lambda p: p[0])
    # B: gate state reached even after the last candidate (drain the queue)
    if not tripped:
        s, re_ = streak, realised
        for _x, lost, rr in pending:
            s = s + 1 if lost else 0
            re_ += rr
            if (halt_n and s >= halt_n) or (r_floor is not None and re_ <= r_floor):
                tripped = True
                break
    return taken, blocked, tripped, taken_before_first_block


by_day = defaultdict(list)
for r in cand:
    by_day[r["day"]].append(r)

ARMS = [("halt=1", 1, None), ("halt=2 (SHIPPED)", 2, None),
        ("halt=3 + -2R floor", 3, -2.0), ("-2R floor alone", None, -2.0),
        ("no governor", None, None)]

print("\n%-20s %7s %7s %8s %8s %8s %8s %9s" % (
    "arm", "n_take", "n_block", "A_blkday", "B_trip", "C_zero", "%A", "pre-block med"))
for name, hn, fl in ARMS:
    T = B = 0
    A = Btrip = C = 0
    pre = []
    for day in cand_sessions:
        t, b, trip, pb = walk(by_day[day], hn, fl)
        T += len(t); B += len(b)
        if b: A += 1
        if trip: Btrip += 1
        if not t: C += 1
        if pb is not None: pre.append(pb)
    print("%-20s %7d %7d %8d %8d %8d %7.0f%% %9s" % (
        name, T, B, A, Btrip, C, A / len(cand_sessions) * 100,
        statistics.median(pre) if pre else "-"))

print("\ndenominator check: len(cand_sessions)=%d" % len(cand_sessions))
print("min trades taken on a benched day, halt=2:",
      min(len(walk(by_day[dd], 2, None)[0]) for dd in cand_sessions
          if walk(by_day[dd], 2, None)[1]))
