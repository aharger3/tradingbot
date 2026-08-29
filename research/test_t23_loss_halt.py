"""R31 — the two-consecutive-loss halt, asserted on hand-built rows.

Austin's verdict on R31 is `both`: the halt runs in the backtest AND in the live
path. T0 landed 27 of the 33 ratified answers and left this one; T23 lands it in
`loss_halt.py`, called from `backtest_2y.main()` and from
`live_scanner._tier()`.

Every fixture here is a hand-built row with a known answer, so a failure names
the rule that broke rather than a number that drifted.

    python research/test_t23_loss_halt.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loss_halt

FAILED = []


def check(label, cond, detail=""):
    print("  %-4s %s%s" % ("ok" if cond else "FAIL", label,
                           ("  -- " + detail) if detail else ""))
    if not cond:
        FAILED.append(label)


def row(sym, day, entry_i, bars, out, traded=True, status="fired"):
    return {"sym": sym, "day": day, "entry_i": entry_i, "bars": bars,
            "et": "09:%02d" % (30 + entry_i % 30), "out": out,
            "traded": traded, "status": status, "reason": "x"}


def blocked(rows, n=2):
    got = loss_halt.halt_day(
        rows,
        entry_key=lambda x: (x["entry_i"], x["et"], x["sym"]),
        exit_key=lambda x: (x["entry_i"] + x["bars"], x["et"], x["sym"]),
        loss_key=lambda x: x["out"] == "loss", n=n)
    return [r["sym"] for r in got]


print("1. the rule itself")
check("no losses, nothing is blocked",
      blocked([row("A", "d", 0, 5, "win"), row("B", "d", 6, 5, "win")]) == [])

check("one loss does not halt",
      blocked([row("A", "d", 0, 5, "loss"), row("B", "d", 6, 5, "win")]) == [])

check("two closed losses halt every later entry",
      blocked([row("A", "d", 0, 2, "loss"),
               row("B", "d", 3, 2, "loss"),
               row("C", "d", 6, 2, "win")]) == ["C"])

check("a win between two losses resets the streak",
      blocked([row("A", "d", 0, 1, "loss"),
               row("B", "d", 2, 1, "win"),
               row("C", "d", 4, 1, "loss"),
               row("D", "d", 6, 1, "win")]) == [])

check("a scratch also resets the streak (only `loss` counts)",
      blocked([row("A", "d", 0, 1, "loss"),
               row("B", "d", 2, 1, "scratch"),
               row("C", "d", 4, 1, "loss"),
               row("D", "d", 6, 1, "win")]) == [])

check("the halt persists for the rest of the day once tripped",
      blocked([row("A", "d", 0, 1, "loss"), row("B", "d", 2, 1, "loss"),
               row("C", "d", 4, 1, "win"), row("D", "d", 8, 1, "win"),
               row("E", "d", 20, 1, "win")]) == ["C", "D", "E"])

print("\n2. CAUSAL — the counter advances on the EXIT, not on the entry")
# Both losers are still OPEN when the third trade is placed: at bar 3 nothing
# has closed yet, so nothing can have halted. The post-process approximation in
# research/t20_loss_halt_postprocess.py sorts by entry time and would block C
# here using an outcome the trader could not yet know.
check("two losses still OPEN at the third entry do NOT halt it",
      blocked([row("A", "d", 0, 90, "loss"),
               row("B", "d", 1, 90, "loss"),
               row("C", "d", 3, 5, "win")]) == [])

check("the same three trades DO halt once both losers have closed",
      blocked([row("A", "d", 0, 2, "loss"),
               row("B", "d", 1, 3, "loss"),
               row("C", "d", 5, 5, "win")]) == ["C"])

print("\n3. a blocked trade never happened, so it never feeds the streak")
# C is blocked. It lost. If a blocked row still counted, D would stay blocked
# even after the win at E resets things -- and more importantly the streak must
# not deepen on trades the halt already refused.
seq = [row("A", "d", 0, 1, "loss"), row("B", "d", 2, 1, "loss"),
       row("C", "d", 4, 1, "loss")]
check("a blocked loser is not added to the streak", blocked(seq) == ["C"])

print("\n4. account-wide, not per symbol")
check("two losses on two DIFFERENT symbols halt a third symbol",
      blocked([row("NVDA", "d", 0, 1, "loss"), row("TSLA", "d", 2, 1, "loss"),
               row("QQQ", "d", 4, 1, "win")]) == ["QQQ"],
      "this is what live_scanner's per-runner counter could never see")

print("\n5. days do not leak into each other, and n is honoured")
book = [row("A", "d1", 0, 1, "loss"), row("B", "d1", 2, 1, "loss"),
        row("C", "d1", 4, 1, "win"),
        row("D", "d2", 0, 1, "win"), row("E", "d2", 2, 1, "win")]
n = loss_halt.apply_to_book([dict(r) for r in book])
check("apply_to_book blocks 1 of 5 across two days", n == 1, str(n))

marked = [dict(r) for r in book]
loss_halt.apply_to_book(marked)
c = [r for r in marked if r["sym"] == "C"][0]
check("a blocked row is flipped to traded=False", c["traded"] is False)
check("a blocked row is flipped to status='halted'", c["status"] == "halted")
check("a blocked row says why in its reason", "[halt:" in c["reason"])
d = [r for r in marked if r["sym"] == "D"][0]
check("an untouched row keeps traded=True and status='fired'",
      d["traded"] is True and d["status"] == "fired")

check("n=3 needs three in a row",
      blocked([row("A", "d", 0, 1, "loss"), row("B", "d", 2, 1, "loss"),
               row("C", "d", 4, 1, "win")], n=3) == [])
check("n=0 disables the halt entirely",
      blocked([row("A", "d", 0, 1, "loss"), row("B", "d", 2, 1, "loss"),
               row("C", "d", 4, 1, "win")], n=0) == [])

print("\n6. only TRADED, FIRED rows are eligible")
skipped = [row("A", "d", 0, 1, "loss"), row("B", "d", 2, 1, "loss"),
           row("C", "d", 4, 1, "win", traded=False, status="skipped")]
n = loss_halt.apply_to_book([dict(r) for r in skipped])
check("an already-skipped row is not counted as halted", n == 0, str(n))

print("\n7. it ships ON — R31 is ratified (method rule 4)")
check("LOSS_HALT defaults ON", loss_halt.LOSS_HALT is True)
check("HALT_AFTER_CONSECUTIVE_LOSSES is 2", loss_halt.HALT_AFTER_CONSECUTIVE_LOSSES == 2)

print("\n8. the LIVE path reads the same module and is account-wide")
src = (ROOT / "live_scanner.py").read_text(encoding="utf-8")
check("live_scanner imports loss_halt", "import loss_halt" in src)
check("live_scanner keeps an account-wide streak", "_account_streak" in src)
check("_tier consults it before promoting to TRADE",
      "_account_streak[\"n\"] >= loss_halt.HALT_AFTER_CONSECUTIVE_LOSSES" in src)
bt = (ROOT / "backtest_2y.py").read_text(encoding="utf-8")
check("backtest_2y applies it to the book", "loss_halt.apply_to_book(rows)" in bt)

print()
if FAILED:
    print("%d check(s) FAILED:" % len(FAILED))
    for f in FAILED:
        print("  -", f)
    raise SystemExit(1)
print("R31 loss-halt selftest ok")
