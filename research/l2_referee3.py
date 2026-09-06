"""l2_referee3.py -- THIRD-PASS independent re-derivation of row L2 (RULE84_DECIDED).

Referee pass 3 for row L2 of OMEN 10.0. Builder commits: 7fb977f7 (flag lands
OFF), d317ff43 (repair), refereed upheld at 3d168491 (pass 2). This pass takes
nothing from research/loop_cycle.py, research/g72_suppress_price.py or either
earlier referee script -- every figure below is recomputed from the two stamped
books with arithmetic written here, from the definitions in the spec and
SWARM.md, so a shared bug in the shipped helpers cannot hide inside an
"independent" check.

WHAT IS RE-DERIVED
  1. stamps      -- OFF book's book_id vs research/tape/loop.json's baseline id;
                    OFF vs ON stamp flag dicts must differ in exactly one key.
  2. gate        -- $/day, mean R, green months, trades on the config's unit
                    (up_to_3_stop_win_or_2loss) over the core-11 slice
                    (tier == "core"), whole window and both halves split at
                    2025-09-01, then the no-regression verdict per half.
  3. cycles.md   -- the committed ledger row must equal what (2) prints.
  4. funnel      -- 84%-rule rows at any status / fired / traded, both arms,
                    all-28 pool and core-11 slice.
  5. isolation   -- non-84% row counts must be identical across arms (a flag
                    that moved a break-and-retest row is not "one change").
  6. semantics   -- the reclaim tolerance is 25% of the PREVIOUS candle's range
                    (not R, not the current candle) and the arm gate is
                    S-or-A on Austin's ladder: checked against the shipped
                    source with a property test over synthetic candles, and
                    against raw archived bars for every ON-arm 84% fired row
                    whose reclaim bar can be located in data_archive.

Fill = close (both books' entry_fill stamp). Exit = shipped engine, 1R hard
stop on the intrabar touch, SCALE_PLAN=hod_then_runner_be, LOSS_HALT on.
1R = $1,000. Unit named on every line. Script = this file.

    python research/l2_referee3.py
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TAPE = ROOT / "research" / "tape"
RISK = 1000.0
BOUNDARY = "2025-09-01"
MIN_TRADES = 30
MIN_MONTHS = 12
MAX_DROP_PCT = 5.0

FAILS: list[str] = []
NOTES: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    print("  %-5s %s%s" % ("OK" if ok else "FAIL", label, ("  -- " + detail) if detail else ""))
    if not ok:
        FAILS.append(label + ((" -- " + detail) if detail else ""))
    return ok


def load(path) -> tuple[dict, list]:
    p = str(path)
    if p.endswith(".gz"):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            b = json.load(f)
    else:
        b = json.loads(Path(p).read_text(encoding="utf-8"))
    return b["meta"], b["trades"]


# ------------------------------------------------------------------ arithmetic
# Written here rather than imported: g72_suppress_price.stats and
# loop_cycle.up_to_3_rows are the code under review.

def day_policy_rows(rows):
    """His day policy, from the spec sentence: up to 3 fired-and-traded
    signals a day in arrival order, stop after the first win or the second
    loss. Halted rows join the candidate stream (the account-wide two-loss
    halt may have blocked a signal this unit's own counter had not yet
    reached)."""
    byday: dict[str, list] = {}
    for r in rows:
        st = r.get("status")
        if (st == "fired" and r.get("traded")) or st == "halted":
            byday.setdefault(r["day"], []).append(r)
    picked = []
    for day in sorted(byday):
        seq = sorted(byday[day], key=lambda r: (r.get("et") or "", r.get("sym") or ""))
        losses = 0
        for i, r in enumerate(seq):
            if i >= 3:
                break
            picked.append(r)
            p = r.get("pnl", 0.0)
            if p > 0:
                break
            if p < 0:
                losses += 1
                if losses >= 2:
                    break
    return picked


def money(rows, n_days):
    """$/day, mean R, green months, trades -- written from the definitions,
    not imported. A month is green when its summed pnl is strictly > 0."""
    if not rows or not n_days:
        return {"trades": 0, "total": 0.0, "per_day": 0.0, "mean_r": 0.0,
                "months_green": 0, "months": 0, "avg_win": 0.0, "avg_loss": 0.0,
                "win_pct": 0.0}
    total = sum(r.get("pnl", 0.0) for r in rows)
    by_m: dict[str, float] = {}
    for r in rows:
        by_m[r["day"][:7]] = by_m.get(r["day"][:7], 0.0) + r.get("pnl", 0.0)
    wins = [r["pnl"] for r in rows if r.get("pnl", 0.0) > 0]
    losses = [r["pnl"] for r in rows if r.get("pnl", 0.0) < 0]
    return {
        "trades": len(rows),
        "total": round(total, 0),
        "per_day": round(total / n_days, 0),
        "mean_r": round(total / len(rows) / RISK, 4),
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "avg_win": round(sum(wins) / len(wins), 0) if wins else 0.0,
        "avg_loss": round(abs(sum(losses) / len(losses)), 0) if losses else 0.0,
        "win_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 1) if (wins or losses) else 0.0,
    }


def verdict(before, after, max_drop_pct=MAX_DROP_PCT):
    """SWARM.md law 2 on one half, law 3 layered on top. A negative baseline
    may not get more than max_drop_pct WORSE."""
    if before["trades"] < MIN_TRADES or before["months"] < MIN_MONTHS:
        return {"enough": False, "pass": None}
    green_ok = after["months_green"] >= before["months_green"]
    b, a = before["per_day"], after["per_day"]
    if b > 0:
        dollar_ok = a >= b * (1 - max_drop_pct / 100.0)
    elif b < 0:
        dollar_ok = a >= b * (1 + max_drop_pct / 100.0)
    else:
        dollar_ok = a >= 0
    return {"enough": True, "pass": bool(green_ok and dollar_ok),
            "green_ok": green_ok, "dollar_ok": dollar_ok}


def slice_book(rows, tier="core"):
    return [r for r in rows if r.get("tier") == tier]


def halves(rows):
    return ([r for r in rows if r.get("day", "") < BOUNDARY],
            [r for r in rows if r.get("day", "") >= BOUNDARY])


def n_days_of(rows):
    return len({r["day"] for r in rows if r.get("day")})


# ------------------------------------------------------------------------ main

def main() -> int:
    off_p = TAPE / "book_RULE84_DECIDED_off.json.gz"
    on_p = TAPE / "book_RULE84_DECIDED_on.json.gz"
    cfg = json.loads((TAPE / "loop.json").read_text(encoding="utf-8"))

    print("\n[1] stamps")
    off_meta, off_rows = load(off_p)
    on_meta, on_rows = load(on_p)
    off_stamp, on_stamp = off_meta.get("stamp", {}), on_meta.get("stamp", {})
    for nm, st in (("off", off_stamp), ("on", on_stamp)):
        g = st.get("git", {})
        print("    %s: commit %s  dirty_py=%s dirty_engine=%s built_at=%s"
              % (nm, (g.get("commit") or "")[:8], g.get("dirty_py_count"),
                 g.get("dirty_engine_py"), st.get("built_at")))
    check(off_stamp.get("git", {}).get("commit", "")[:8] == "7fb977f7"
          and on_stamp.get("git", {}).get("commit", "")[:8] == "7fb977f7",
          "both books stamped at 7fb977f7")
    check(off_stamp.get("git", {}).get("dirty_py_count") == 0
          and on_stamp.get("git", {}).get("dirty_py_count") == 0,
          "neither book was built on a dirty tree")

    import research.book_stamp as bs  # noqa: E402  (identity function only)
    off_id = off_stamp.get("book_id") or bs.book_id(off_rows)
    on_id = on_stamp.get("book_id") or bs.book_id(on_rows)
    base_id = cfg["baseline_book_id"]
    print("    off book_id %s | baseline %s | on book_id %s" % (off_id, base_id, on_id))
    check(off_id == base_id, "OFF book_id == loop.json baseline_book_id",
          "%s vs %s" % (off_id, base_id))
    check(on_id != off_id, "ON book_id differs from OFF")

    fo, fn = off_stamp.get("flags", {}), on_stamp.get("flags", {})
    diff = sorted(k for k in set(fo) | set(fn) if fo.get(k) != fn.get(k))
    print("    flag keys differing between the two stamps: %s" % diff)
    check(diff == ["signal_runner.RULE84_DECIDED"],
          "exactly one flag differs, and it is RULE84_DECIDED", str(diff))
    check(fo.get("signal_runner.RULE84_DECIDED") in (False, "false", 0, "0")
          and fn.get("signal_runner.RULE84_DECIDED") in (True, "true", 1, "1"),
          "the differing flag reads OFF in the off book and ON in the on book",
          "%r -> %r" % (fo.get("signal_runner.RULE84_DECIDED"),
                        fn.get("signal_runner.RULE84_DECIDED")))
    check("RULE84_DECIDED" in Path(ROOT / "research" / "book_stamp.py").read_text(encoding="utf-8"),
          "RULE84_DECIDED is in research/book_stamp.py FLAG_SOURCES")

    src = (ROOT / "signal_runner.py").read_text(encoding="utf-8")
    m = re.search(r'RULE84_DECIDED\s*=\s*os\.getenv\("RULE84_DECIDED",\s*"([^"]*)"\)', src)
    print("    code default for RULE84_DECIDED: %r" % (m.group(1) if m else None))
    check(bool(m) and m.group(1) == "0",
          "code default is OFF, matching the HOLD decision")

    print("\n[2] the gate, re-derived (unit up_to_3_stop_win_or_2loss, core-11, "
          "fill=close, exit=shipped 1R stop + hod_then_runner_be)")
    off_core, on_core = slice_book(off_rows), slice_book(on_rows)
    print("    core-11 rows: off %d  on %d  (all rows: %d / %d)"
          % (len(off_core), len(on_core), len(off_rows), len(on_rows)))

    n_whole = off_meta.get("sessions")
    o1, o2 = halves(off_core)
    a1, a2 = halves(on_core)
    n1_off, n2_off = n_days_of(o1), n_days_of(o2)
    n1_on, n2_on = n_days_of(a1), n_days_of(a2)
    print("    session counts: whole %s (book meta) | H1 %d/%d  H2 %d/%d "
          "(distinct core-11 days, off/on)" % (n_whole, n1_off, n1_on, n2_off, n2_on))

    res = {}
    res["whole_off"] = money(day_policy_rows(off_core), n_whole)
    res["whole_on"] = money(day_policy_rows(on_core), n_whole)
    res["h1_off"] = money(day_policy_rows(o1), n1_off)
    res["h1_on"] = money(day_policy_rows(a1), n1_on)
    res["h2_off"] = money(day_policy_rows(o2), n2_off)
    res["h2_on"] = money(day_policy_rows(a2), n2_on)

    hdr = "%-9s %7s %9s %9s %8s %8s" % ("slice", "trades", "$/day", "mean R", "green", "months")
    print("    " + hdr)
    for k in ("whole_off", "whole_on", "h1_off", "h1_on", "h2_off", "h2_on"):
        v = res[k]
        print("    %-9s %7d %9.0f %9.4f %8d %8d"
              % (k, v["trades"], v["per_day"], v["mean_r"], v["months_green"], v["months"]))

    h1v = verdict(res["h1_off"], res["h1_on"])
    h2v = verdict(res["h2_off"], res["h2_on"])
    dec = "ship" if (h1v["enough"] and h1v["pass"] and h2v["enough"] and h2v["pass"]) else "hold"
    print("    H1 verdict %s | H2 verdict %s | decision %s" % (h1v, h2v, dec))

    rep = {"whole_trades": 769, "whole_off_pd": -52, "whole_on_pd": -57,
           "whole_off_mr": -0.0335, "whole_on_mr": -0.0371,
           "green_off": 11, "green_on": 11,
           "h1_trades": 382, "h1_off_pd": 9, "h1_on_pd": -8,
           "h2_trades": 387, "h2_off_pd": -111, "h2_on_pd": -106}
    check(res["whole_off"]["trades"] == rep["whole_trades"],
          "whole OFF trades == 769", str(res["whole_off"]["trades"]))
    check(res["whole_off"]["per_day"] == rep["whole_off_pd"],
          "whole OFF $/day == -52", str(res["whole_off"]["per_day"]))
    check(res["whole_on"]["per_day"] == rep["whole_on_pd"],
          "whole ON $/day == -57", str(res["whole_on"]["per_day"]))
    check(res["whole_off"]["mean_r"] == rep["whole_off_mr"]
          and res["whole_on"]["mean_r"] == rep["whole_on_mr"],
          "whole mean R -0.0335 -> -0.0371",
          "%s -> %s" % (res["whole_off"]["mean_r"], res["whole_on"]["mean_r"]))
    check(res["whole_off"]["months_green"] == 11 and res["whole_on"]["months_green"] == 11,
          "whole green months 11 -> 11",
          "%d -> %d" % (res["whole_off"]["months_green"], res["whole_on"]["months_green"]))
    check(res["h1_off"]["trades"] == rep["h1_trades"] and res["h2_off"]["trades"] == rep["h2_trades"],
          "half trade counts 382 / 387",
          "%d / %d" % (res["h1_off"]["trades"], res["h2_off"]["trades"]))
    check(res["h1_off"]["per_day"] == rep["h1_off_pd"] and res["h1_on"]["per_day"] == rep["h1_on_pd"],
          "H1 $/day 9 -> -8",
          "%.0f -> %.0f" % (res["h1_off"]["per_day"], res["h1_on"]["per_day"]))
    check(res["h2_off"]["per_day"] == rep["h2_off_pd"] and res["h2_on"]["per_day"] == rep["h2_on_pd"],
          "H2 $/day -111 -> -106",
          "%.0f -> %.0f" % (res["h2_off"]["per_day"], res["h2_on"]["per_day"]))
    check(h1v["enough"] and h1v["pass"] is False, "H1 FAILS the no-regression gate")
    check(h2v["enough"] and h2v["pass"] is True, "H2 passes the no-regression gate")
    check(dec == "hold", "decision is HOLD", dec)

    # the baseline row in loop.json must agree with the OFF arm we just priced
    bf = cfg["baseline_figures"]
    check(bf["whole"]["trades"] == res["whole_off"]["trades"]
          and bf["whole"]["per_day"] == res["whole_off"]["per_day"]
          and bf["whole"]["months_green"] == res["whole_off"]["months_green"],
          "OFF arm reproduces loop.json's baseline_figures.whole")
    check(bf["h1"]["per_day"] == res["h1_off"]["per_day"]
          and bf["h2"]["per_day"] == res["h2_off"]["per_day"],
          "OFF arm reproduces loop.json's baseline_figures halves")

    print("\n[2b] sensitivity: whole-window $/day if the day count were the "
          "distinct core-11 days instead of the book's 499 sessions")
    nd_core = n_days_of(off_core)
    print("    distinct core-11 days %d vs meta sessions %s -> OFF $/day %.0f "
          "(vs %.0f), ON $/day %.0f (vs %.0f)"
          % (nd_core, n_whole,
             res["whole_off"]["total"] / nd_core, res["whole_off"]["per_day"],
             res["whole_on"]["total"] / nd_core, res["whole_on"]["per_day"]))

    print("\n[3] cycles.md ledger row")
    cyc = (TAPE / "cycles.md").read_text(encoding="utf-8")
    lines = [l for l in cyc.splitlines()
             if l.startswith("|") and "RULE84_DECIDED" in l and "---" not in l]
    print("    rows mentioning the flag: %d" % len(lines))
    for l in lines:
        print("      " + l.strip())
    check(len(lines) == 1, "exactly one RULE84_DECIDED row in cycles.md", str(len(lines)))
    if lines:
        cells = [c.strip() for c in lines[0].strip().strip("|").split("|")]
        # date, label, flag, decision, $/day a->b, green a->b, H1, H2, trades, off, on, script
        want = {"decision": "hold", "dollars": "-52.0 -> -57.0", "green": "11 -> 11",
                "h1": "fail", "h2": "pass", "trades": "769"}
        got = {"decision": cells[3], "dollars": cells[4], "green": cells[5],
               "h1": cells[6], "h2": cells[7], "trades": cells[8]}
        check(got == want, "cycles.md row matches the re-derived gate",
              "got %s" % got)
        check(not re.search(r"[A-Z_]{4,}", cells[1]),
              "the ledger's label column is plain English (no flag names)", cells[1])

    print("\n[4] the 84% funnel, re-counted")
    def funnel(rows, tier=None):
        rs = [r for r in rows if r.get("setup") == "reentry_84_rule"]
        if tier:
            rs = [r for r in rs if r.get("tier") == tier]
        fired = [r for r in rs if r.get("status") == "fired"]
        traded = [r for r in fired if r.get("traded")]
        mr = (sum(r.get("pnl", 0.0) for r in traded) / len(traded) / RISK) if traded else 0.0
        return len(rs), len(fired), len(traded), round(mr, 4)
    fo_all, fn_all = funnel(off_rows), funnel(on_rows)
    fo_core, fn_core = funnel(off_rows, "core"), funnel(on_rows, "core")
    print("    all-28  OFF rows/fired/traded/meanR %s | ON %s" % (fo_all, fn_all))
    print("    core-11 OFF rows/fired/traded/meanR %s | ON %s" % (fo_core, fn_core))
    check(fo_all[0] == 542 and fn_all[0] == 200, "84% rows at any status 542 -> 200",
          "%d -> %d" % (fo_all[0], fn_all[0]))
    check(fo_all[1] == 124 and fn_all[1] == 39, "84% FIRED 124 -> 39",
          "%d -> %d" % (fo_all[1], fn_all[1]))
    check(fo_all[2] == 56 and fn_all[2] == 20, "84% traded 56 -> 20",
          "%d -> %d" % (fo_all[2], fn_all[2]))
    check(fo_core[1] == 53 and fn_core[1] == 20, "core-11 84% fired 53 -> 20",
          "%d -> %d" % (fo_core[1], fn_core[1]))
    check(fo_core[2] == 18 and fn_core[2] == 9, "core-11 84% traded 18 -> 9",
          "%d -> %d" % (fo_core[2], fn_core[2]))
    # The report (research/l2_rule84_decided.md) asserts "neither traded column
    # clears 30 trades ... 56 (OFF) and 20 (ON) are both under the 30-trade
    # floor". 56 is not under 30. The CONCLUSION ("not enough") survives -- the
    # ON cell is 20 -- but the sentence carrying it is arithmetically false.
    check(fo_all[2] < MIN_TRADES,
          "report's claim: the OFF traded cell (56) is under the 30-trade floor",
          "56 >= 30, so this claim in research/l2_rule84_decided.md is false")
    check(fn_all[2] < MIN_TRADES,
          "the ON traded cell (20) is under the 30-trade floor -> 'not enough' is "
          "still the right verdict on the re-entries' own mean R")
    print("    re-entry mean R (traded, all-28): OFF %+.4fR (n=%d) | ON %+.4fR (n=%d)"
          % (fo_all[3], fo_all[2], fn_all[3], fn_all[2]))
    check(abs(fo_all[3] - 0.061) < 0.001 and abs(fn_all[3] - 0.036) < 0.001,
          "reported re-entry mean R +0.061R -> +0.036R",
          "%+.4f -> %+.4f" % (fo_all[3], fn_all[3]))

    print("\n[5] isolation -- did the flag move anything but the 84% path?")
    def by_setup(rows):
        d = {}
        for r in rows:
            d[r.get("setup")] = d.get(r.get("setup"), 0) + 1
        return d
    bo, bn = by_setup(off_rows), by_setup(on_rows)
    print("    off %s\n    on  %s" % (bo, bn))
    non84_same = all(bo.get(k) == bn.get(k) for k in set(bo) | set(bn)
                     if k != "reentry_84_rule")
    check(non84_same, "every non-84% setup has an identical row count in both arms")
    # and the non-84% rows must be byte-identical, not merely equal in count
    def key(r):
        return (r["day"], r.get("et"), r.get("sym"), r.get("setup"), r.get("status"),
                round(r.get("pnl", 0.0), 6), round(r.get("entry", 0.0) or 0.0, 6))
    ko = sorted(key(r) for r in off_rows if r.get("setup") != "reentry_84_rule")
    kn = sorted(key(r) for r in on_rows if r.get("setup") != "reentry_84_rule")
    identical = ko == kn
    check(identical, "the non-84% rows are identical row-for-row across the two arms",
          "%d vs %d keys, %d differing" % (len(ko), len(kn), sum(1 for a, b in zip(ko, kn) if a != b)))
    if not identical:
        # Name the mechanism rather than leaving "30 rows moved" hanging: an
        # 84% re-entry that is (or is not) taken changes the account-wide
        # two-loss halt's state and the dedupe suppression window, so LATER
        # non-84% rows on the same day can change status. That is a downstream
        # consequence of the one change, not a second change -- but it must be
        # shown, not assumed.
        idx_o = {(r["day"], r.get("et"), r.get("sym"), r.get("setup")): r
                 for r in off_rows if r.get("setup") != "reentry_84_rule"}
        idx_n = {(r["day"], r.get("et"), r.get("sym"), r.get("setup")): r
                 for r in on_rows if r.get("setup") != "reentry_84_rule"}
        moved = [k for k in idx_o if k in idx_n
                 and (idx_o[k].get("status") != idx_n[k].get("status")
                      or round(idx_o[k].get("pnl", 0.0), 6) != round(idx_n[k].get("pnl", 0.0), 6)
                      or idx_o[k].get("traded") != idx_n[k].get("traded"))]
        print("    non-84%% rows whose status/traded/pnl moved: %d" % len(moved))
        fields = {}
        for k in moved:
            a, b = idx_o[k], idx_n[k]
            for f in ("status", "traded", "pnl", "out", "exit"):
                if a.get(f) != b.get(f):
                    fields[f] = fields.get(f, 0) + 1
        print("    fields that moved: %s" % fields)
        for k in sorted(moved)[:8]:
            a, b = idx_o[k], idx_n[k]
            print("      %s %s %s %-16s  %s/%s/%s  ->  %s/%s/%s"
                  % (k[0], k[1], k[2], k[3], a.get("status"), a.get("traded"),
                     a.get("pnl"), b.get("status"), b.get("traded"), b.get("pnl")))
        same_day_84 = sum(1 for k in moved
                          if any(q["day"] == k[0] and q["sym"] == k[2]
                                 and q.get("setup") == "reentry_84_rule"
                                 for q in off_rows))
        print("    of those, %d sit on a symbol-day that also carried an 84%% row "
              "in the OFF arm (the halt/dedupe cascade)" % same_day_84)
        NOTES.append("the flag moves %d non-84%% rows as a downstream cascade "
                     "(fields: %s); row COUNTS per setup are unchanged, so this is "
                     "the loss-halt / dedupe state following the one change, not a "
                     "second change -- but neither the report nor either earlier "
                     "referee pass discloses it" % (len(moved), fields))

    print("\n[6] semantics of the flag")
    print("    spec sentence (omen-10-0-spec.md, What the call settled):")
    spec = Path("C:/Users/aharg/Austin's Vault/Projects/omen-10-0-spec.md").read_text(encoding="utf-8")
    for l in spec.splitlines():
        if l.strip().startswith("| 84% rule"):
            print("      " + l.strip())
    # 6a. property test of the reclaim tolerance, run in a fresh interpreter is
    # unnecessary -- read the two env states by re-importing with the env set.
    os.environ["RULE84_DECIDED"] = "1"
    for mod in [m for m in list(sys.modules) if m.startswith("signal_runner")]:
        del sys.modules[mod]
    import signal_runner as sr_on  # noqa: E402
    C = sr_on.Candle
    prev = C(timestamp="2025-01-02T09:40:00", open=100.0, high=101.0, low=99.0,
             close=100.5, volume=1000)          # range 2.00 -> tolerance 0.50
    entry = 100.0
    cases = [(100.49, True), (100.50, True), (100.51, False),
             (99.51, True), (99.49, False)]
    ok = True
    for close, want in cases:
        got = sr_on._reclaim_gate_ok(close, entry, 99.0, prev)
        ok = ok and (got == want)
        print("      close %.2f vs entry %.2f, prev range 2.00 -> %s (want %s)"
              % (close, entry, got, want))
    check(ok, "reclaim tolerance is exactly 25% of the PREVIOUS candle's high-low range")
    check(sr_on.BAR_EXTREME_FRAC == 0.25, "BAR_EXTREME_FRAC is 0.25",
          str(sr_on.BAR_EXTREME_FRAC))
    # It must NOT be the R unit. RULE84_RECLAIM_TOL's shipped default is None
    # (unbounded), so with the flag OFF the gate admits every reclaim close;
    # with it ON the same close is refused. That is the whole difference.
    print("      RULE84_RECLAIM_TOL (the R-unit flag, untouched by this row): %r"
          % sr_on.RULE84_RECLAIM_TOL)
    check(sr_on.RULE84_RECLAIM_TOL is None,
          "the pre-existing R-unit tolerance is still at its unbounded default "
          "(this row did not reuse or repurpose it)", repr(sr_on.RULE84_RECLAIM_TOL))
    check(sr_on._reclaim_tol_ok(101.0, entry, 99.0) is True
          and sr_on._reclaim_gate_ok(101.0, entry, 99.0, prev) is False,
          "a close the shipped R-unit gate admits is refused by the candle-range "
          "unit (the two units are genuinely different)")
    check(sr_on._reclaim_gate_ok(100.60, entry, 99.0, None) is True,
          "no previous candle -> unbounded (documented fallback, not an invented denominator)")
    check(sr_on.RULE84_MAX_ATTEMPTS == 2, "two attempts is the shipped default",
          str(sr_on.RULE84_MAX_ATTEMPTS))
    check(str(sr_on.SESSION_END).startswith("11:00"), "session ends 11:00",
          str(sr_on.SESSION_END))
    check(sr_on.RULE84_DECIDED is True, "the env var arms the flag")

    # 6b. the arm gate reads Austin's S/A ladder, not the legacy A+/A one
    bw = (ROOT / "backtest_week.py").read_text(encoding="utf-8")
    arm = bw[bw.index("def _arm_84"): bw.index("def _entry_scratch")]
    check('if RULE84_DECIDED:\n        grade_ok = _sgrade_84(t, runner) in ("S", "A")' in arm,
          "arm gate under the flag is _sgrade_84(...) in (S, A)")
    check(arm.index("if RULE84_DECIDED:") < arm.index("elif RULE84_ARM_NOGATE:"),
          "the flag takes priority over the superseded RULE84_* readings")
    sg = bw[bw.index("def _sgrade_84"): bw.index("def _arm_84")]
    check("dg.score(" in sg, "_sgrade_84 grades on downgrade.score (Austin's ladder)")

    # 6c. against raw archived bars: every ON-arm 84% FIRED row must satisfy the
    # candle-range tolerance at its own reclaim bar.
    print("\n[6c] raw-bar check of the reclaim tolerance on the ON arm's own fires")
    arch = ROOT / "data_archive"
    on84 = [r for r in on_rows if r.get("setup") == "reentry_84_rule"
            and r.get("status") == "fired"]
    off84 = [r for r in off_rows if r.get("setup") == "reentry_84_rule"
             and r.get("status") == "fired"]
    on_keys = {(r["day"], r.get("et"), r.get("sym")) for r in on84}
    off_keys = {(r["day"], r.get("et"), r.get("sym")) for r in off84}
    # Not a defect -- a mechanism. Refusing an early reclaim leaves the two-attempt
    # budget intact, so the NEXT qualifying bar can fire instead: the tightening is
    # not purely subtractive. Verified on raw bars in research/l2_referee3_probe.py
    # (ORCL 2025-01-02: 10:58 refused, gap 0.035 vs tol 0.030; 10:59 fires).
    added = sorted(on_keys - off_keys)
    print("    ON fires absent from the OFF arm: %d -> %s" % (len(added), added))
    if added:
        NOTES.append("the flag is NOT purely subtractive: %d of %d ON-arm 84%% fires "
                     "do not exist in the OFF arm (%s). In the core-11 day-policy "
                     "candidate pool it removes 84 rows and ADDS 3, all three -$1,000. "
                     "Undisclosed in research/l2_rule84_decided.md." % (len(added), len(on84), added))

    # The row itself carries both sides of the tolerance test:
    #   entry     = the reclaim bar's close (ENTRY_FILL=close)
    #   level_px  = "prior entry (84%)" -- the ORIGINAL entry price the reclaim
    #               must come back to (level_name says so verbatim)
    # so |entry - level_px| <= 0.25 * (previous archived candle's high - low)
    # is the settled sentence, testable against the tape with no replay.
    import csv as _csv

    def bars_for(sym, day):
        p = arch / sym / ("%s.csv" % day)
        if not p.exists():
            return None
        out = []
        with open(p, newline="", encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                out.append(row)
        return out

    def prev_range(rows_b, et):
        """(previous candle's high-low, the reclaim bar's own close) at HH:MM."""
        idx = None
        for i, b in enumerate(rows_b):
            ts = b["Datetime"]
            if ts[11:16] == et:
                idx = i
                break
        if idx is None or idx == 0:
            return None, None
        pb = rows_b[idx - 1]
        return float(pb["High"]) - float(pb["Low"]), float(rows_b[idx]["Close"])

    def tol_audit(rows84, label):
        inside = outside = unresolved = 0
        worst = []
        for r in rows84:
            rows_b = bars_for(r["sym"], r["day"])
            if not rows_b:
                unresolved += 1
                continue
            rng, close = prev_range(rows_b, r.get("et") or "")
            if rng is None:
                unresolved += 1
                continue
            if abs(close - float(r.get("entry") or 0)) > 0.05:
                unresolved += 1          # fill is not this bar's close -- skip
                continue
            lvl = r.get("level_px")
            if lvl is None:
                unresolved += 1
                continue
            gap, tol = abs(close - float(lvl)), 0.25 * rng
            if rng <= 0 or gap <= tol + 1e-9:
                inside += 1
            else:
                outside += 1
                worst.append((r["sym"], r["day"], r.get("et"), round(gap, 4), round(tol, 4)))
        print("    %-8s inside tol %3d | outside tol %3d | unresolved %3d (of %d)"
              % (label, inside, outside, unresolved, len(rows84)))
        return inside, outside, unresolved, worst

    on_in, on_out, on_un, on_worst = tol_audit(on84, "ON")
    off_in, off_out, off_un, off_worst = tol_audit(off84, "OFF")
    # level_px is stored rounded to 2dp, so a violation smaller than the rounding
    # band (0.005) is an artefact of the book's own column, not a gate breach.
    # ORCL 2025-01-02 is the one such case: the original entry's true value is the
    # 10:35 bar's close, 166.895, not the stored 166.90 -- see
    # research/l2_referee3_probe.py, which reads it off data_archive.
    hard = [w for w in on_worst if w[3] - w[4] > 0.005]
    if on_in + on_out >= 5:
        check(not hard,
              "every resolvable ON-arm 84%% fire satisfies |reclaim close - original "
              "entry| <= 25%% of the previous archived candle's range, allowing the "
              "2dp rounding of the stored level_px",
              "violations beyond the rounding band: %s" % (hard[:5],))
        if on_worst and not hard:
            print("    (%d borderline case(s) inside the 2dp rounding band, resolved "
                  "by hand against data_archive: %s)" % (len(on_worst), on_worst))
    else:
        NOTES.append("only %d of %d ON fires resolved against data_archive -- the "
                     "raw-tape arm of the tolerance check is not enough on its own"
                     % (on_in + on_out, len(on84)))
    check(off_out > 0,
          "the OFF arm does contain fires the new tolerance would refuse "
          "(the gate is not a no-op)", "%d of %d resolved OFF fires outside tol"
          % (off_out, off_in + off_out))
    on_only_keys = on_keys
    off_only = [r for r in off84 if (r["day"], r.get("et"), r.get("sym")) not in on_only_keys]
    print("    OFF-only fires (dropped by the flag): %d" % len(off_only))
    oo_in, oo_out, oo_un, _ = tol_audit(off_only, "OFF-only")
    print("    of the dropped fires, %d were outside the new tolerance and %d were "
          "inside it (the latter must be the S/A arm gate's doing)" % (oo_out, oo_in))

    print("\n[7] one change per row / mark files")
    print("    (checked in the shell alongside this script; see research/l2_referee.md)")

    print("\n=== %d checks failed ===" % len(FAILS))
    for f in FAILS:
        print("  FAIL " + f)
    for n in NOTES:
        print("  NOTE " + n)
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
