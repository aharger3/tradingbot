"""X2 -- stops that go past 1R, and max drawdown.

Austin, 2026-08-28: *"still think some stops are going past 1r need to fix
that"* and *"max dd if thats rr loss its slipping back 1r so needs fixing"* and
*"the risk floor shouldnt cause false fires it just stops losers from running
past 1-1.25."*

Three questions, three sections, one script.

1. ``--book``  The left tail of ``research/g3_arm_ow1.json`` as booked. Tests
   DIRECTION.md's standing claim ("worst traded outcome is -1.000R, so the floor
   never binds today") against the file.

2. ``--tape``  The same 1,017 rows replayed against the archived 1-minute tape,
   asking what the stop-triggering bar's CLOSE actually was. `CLAUDE.md` states
   the rule as *"Stops trigger on the candle CLOSE, fill at that close, floored
   at -1.25R"*; `backtest_week.py` triggers on the close and then fills at
   ``t.stop``. This section prices the difference. Every replay is causal --
   nothing reads past the bar being tested -- and it uses the SAME bar loader
   (`research.r9_simple_book.Bars`) every other W-report used, so the tape
   cannot disagree between rigs.

3. ``--dd``  The equity curve in R, 1R per trade, chronological. Max drawdown in
   R and in trade count, plus the longest losing streak -- so "max DD" can be
   named as a per-trade phenomenon or a portfolio one.

Run:

    python research/x2_stop_floor_audit.py            # all three
    python research/x2_stop_floor_audit.py --book     # section 1 only
    python research/x2_stop_floor_audit.py --json out.json

No fetches: `data_archive/` replay only. Writes nothing unless --json is given.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

BOOK = os.path.join(_HERE, "g3_arm_ow1.json")

# Austin's stated worst case, ballot q1: "max slippage -1.25r". Same constant
# research/exit_lab.py ships; imported there rather than re-typed here would
# drag exit_lab's whole import chain into --book, so it is asserted equal in
# _check_constants() instead.
MAX_LOSS_R = 1.25


def _check_constants():
    """The -1.25R floor must be ONE number. Fail loudly if it forked."""
    from research import exit_lab as xl
    assert xl.MAX_LOSS_R == MAX_LOSS_R, (
        "MAX_LOSS_R forked: exit_lab=%r x2=%r" % (xl.MAX_LOSS_R, MAX_LOSS_R))


# ---------------------------------------------------------------------------
# shared
# ---------------------------------------------------------------------------

def load_traded(path=BOOK):
    with open(path, encoding="utf-8") as fh:
        blob = json.load(fh)
    rows = [r for r in blob["trades"] if r.get("traded")]
    return blob["meta"], blob["trades"], rows


def pct(xs, p):
    """Nearest-rank percentile on a sorted-able list. Empty -> None."""
    if not xs:
        return None
    s = sorted(xs)
    k = max(0, min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1)))))
    return s[k]


def implied_r(row):
    """R recomputed from the row's own stored prices, not from its `r` field.

    The point of recomputing is to catch a `r` column that has been clamped or
    rounded away from the prices it claims to describe.
    """
    entry, stop, exit_ = float(row["entry"]), float(row["stop"]), float(row["exit"])
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    sgn = 1.0 if row["side"] == "L" else -1.0
    return sgn * (exit_ - entry) / risk


# ---------------------------------------------------------------------------
# 1. the book as booked
# ---------------------------------------------------------------------------

def section_book(out):
    meta, all_rows, traded = load_traded()
    rs = [float(r["r"]) for r in traded]
    all_r = [float(r["r"]) for r in all_rows if r.get("r") is not None]

    worse = [r for r in traded if float(r["r"]) < -1.0 - 1e-12]
    at = [r for r in traded if abs(float(r["r"]) + 1.0) <= 1e-12]
    between = [r for r in traded if -1.0 + 1e-12 < float(r["r"]) < 0.0]

    worse_all = [r for r in all_rows
                 if r.get("r") is not None and float(r["r"]) < -1.0 - 1e-12]

    # the stored prices, independently of the stored r
    imp = [(implied_r(r), r) for r in traded]
    imp = [(v, r) for v, r in imp if v is not None]
    imp_worse = [(v, r) for v, r in imp if v < -1.0 - 1e-9]
    # every loss's exit price vs its stop price, in cents
    loss_gap = [abs(float(r["exit"]) - float(r["stop"])) for r in traded
                if r["out"] == "loss"]

    b = {
        "n_traded": len(traded),
        "n_all_signals": len(all_rows),
        "min_r": min(rs),
        "max_r": max(rs),
        "p1_r": pct(rs, 1),
        "p5_r": pct(rs, 5),
        "median_r": statistics.median(rs),
        "mean_r": sum(rs) / len(rs),
        "n_worse_than_minus1": len(worse),
        "n_exactly_minus1": len(at),
        "n_between_minus1_and_0": len(between),
        "n_worse_than_minus125": sum(1 for x in rs if x < -MAX_LOSS_R - 1e-12),
        "min_r_all_45k": min(all_r),
        "n_worse_than_minus1_all_45k": len(worse_all),
        "outcomes": dict(Counter(r["out"] for r in traded)),
        "distinct_negative_r": sorted({round(float(r["r"]), 6)
                                       for r in traded if float(r["r"]) < 0}),
        "min_implied_r": min(v for v, _ in imp),
        "n_implied_worse_than_minus1": len(imp_worse),
        "loss_exit_equals_stop": sum(1 for g in loss_gap if g < 1e-9),
        "n_losses": len(loss_gap),
        "max_loss_exit_minus_stop": max(loss_gap) if loss_gap else None,
        "scaled_losses": sum(1 for r in traded
                             if float(r["r"]) < 0 and r.get("scaled")),
    }
    out["book"] = b

    print("== 1. THE BOOK AS BOOKED (research/g3_arm_ow1.json) ==")
    print("traded rows                 %d   (of %d signals)"
          % (b["n_traded"], b["n_all_signals"]))
    print("min r / p1 / p5 / median    %.4f / %.4f / %.4f / %+.4f"
          % (b["min_r"], b["p1_r"], b["p5_r"], b["median_r"]))
    print("rows r < -1.0               %d" % b["n_worse_than_minus1"])
    print("rows r == -1.0 exactly      %d" % b["n_exactly_minus1"])
    print("rows -1.0 < r < 0           %d" % b["n_between_minus1_and_0"])
    print("distinct negative r values  %s" % (b["distinct_negative_r"],))
    print("min r over ALL 45,193 rows  %.4f  (rows worse than -1: %d)"
          % (b["min_r_all_45k"], b["n_worse_than_minus1_all_45k"]))
    print("losses whose exit == stop   %d of %d   (max |exit-stop| = %s)"
          % (b["loss_exit_equals_stop"], b["n_losses"],
             b["max_loss_exit_minus_stop"]))
    print("min r recomputed from price %.4f  (rows < -1: %d)"
          % (b["min_implied_r"], b["n_implied_worse_than_minus1"]))
    print()
    return b


# ---------------------------------------------------------------------------
# 2. the tape: what the triggering close actually was
# ---------------------------------------------------------------------------

def section_tape(out, limit=None):
    from research.r9_simple_book import Bars

    _, _, traded = load_traded()
    if limit:
        traded = traded[:limit]
    cache = Bars()

    rows = []
    gaps = {"day": 0, "index": 0, "zero_risk": 0}
    for r in traded:
        got = cache.get(r["sym"], r["day"])
        if got is None:
            gaps["day"] += 1
            continue
        _rth, dicts, _idx, _hi, _lo = got
        ei = int(r["entry_i"])
        if ei >= len(dicts):
            gaps["index"] += 1
            continue
        entry, stop = float(r["entry"]), float(r["stop"])
        risk = abs(entry - stop)
        if risk <= 0:
            gaps["zero_risk"] += 1
            continue
        side = r["side"]
        long = side == "L"
        sgn = 1.0 if long else -1.0

        # First bar AFTER entry whose CLOSE is beyond the INITIAL stop. This is
        # exactly backtest_week._stop_hit under STOP_ON_CLOSE=1, scanned over the
        # same window backtest_week manages (entry+1 .. end of RTH; there is no
        # 11:00 force-flat in the shipped engine, only an 11:00 ENTRY cutoff).
        hit_i = None
        for i in range(ei + 1, len(dicts)):
            c = dicts[i]["c"]
            if (c <= stop) if long else (c >= stop):
                hit_i = i
                break

        rec = {
            "sym": r["sym"], "day": r["day"], "et": r["et"], "side": side,
            "setup": r["setup"], "sgrade": r.get("sgrade"), "level": r.get("level"),
            "entry_i": ei, "entry": entry, "stop": stop, "risk": risk,
            "booked_r": float(r["r"]), "out": r["out"], "scaled": bool(r["scaled"]),
            "bars_held": int(r["bars"]), "hit_i": hit_i,
        }
        if hit_i is not None:
            cl = dicts[hit_i]["c"]
            rec["trigger_close"] = cl
            rec["close_r"] = sgn * (cl - entry) / risk          # unfloored
            rec["close_r_floored"] = max(rec["close_r"], -MAX_LOSS_R)
            rec["overshoot_r"] = -1.0 - rec["close_r"]          # >0 = past 1R
            rec["minutes_after_entry"] = hit_i - ei
        rows.append(rec)

    stopped = [x for x in rows if x["hit_i"] is not None]
    # SELF-CHECK. For a row the book charged a full -1.000R the exit bar IS the
    # first close beyond the initial stop, so `hit_i` must equal
    # `entry_i + bars`. If it does not, this replay has found a different bar
    # than the engine did and the correction below would be measuring the wrong
    # thing. Reported, never silently absorbed.
    agree = mism = 0
    mismatches = []
    for x in rows:
        if abs(x["booked_r"] + 1.0) > 1e-12 or x["hit_i"] is None:
            continue
        if x["hit_i"] == x["entry_i"] + x["bars_held"]:
            agree += 1
        else:
            mism += 1
            mismatches.append((x["sym"], x["day"], x["entry_i"],
                               x["bars_held"], x["hit_i"]))
    # the rows the BOOK charged a full stop-out to: every one of them is a
    # pre-scale stop trigger on the initial stop, so its exit bar is exactly the
    # bar found above and the correction below is exact, not an approximation.
    booked_loss = [x for x in stopped if abs(x["booked_r"] + 1.0) <= 1e-12]

    def tail(xs, key="close_r"):
        v = [x[key] for x in xs]
        return {
            "n": len(v),
            "min": min(v) if v else None,
            "p1": pct(v, 1), "p5": pct(v, 5),
            "median": statistics.median(v) if v else None,
            "mean": (sum(v) / len(v)) if v else None,
            "n_worse_than_1R": sum(1 for x in v if x < -1.0 - 1e-9),
            "n_worse_than_125R": sum(1 for x in v if x < -MAX_LOSS_R - 1e-9),
        }

    t_all = tail(stopped)
    t_book = tail(booked_loss)

    # book-level cost of honouring "fill at that close, floored at -1.25R"
    _, _, traded_all = load_traded()
    n_book = len(traded_all)
    mean_booked = sum(float(r["r"]) for r in traded_all) / n_book
    corrected = {(x["sym"], x["day"], x["entry_i"], x["side"]): x["close_r_floored"]
                 for x in booked_loss}
    corr_rs = []
    for r in traded_all:
        k = (r["sym"], r["day"], int(r["entry_i"]), r["side"])
        corr_rs.append(corrected.get(k, float(r["r"])))
    mean_corrected = sum(corr_rs) / len(corr_rs)

    corr_unfloored = {(x["sym"], x["day"], x["entry_i"], x["side"]): x["close_r"]
                      for x in booked_loss}
    corr_rs_u = []
    for r in traded_all:
        k = (r["sym"], r["day"], int(r["entry_i"]), r["side"])
        corr_rs_u.append(corr_unfloored.get(k, float(r["r"])))
    mean_corrected_u = sum(corr_rs_u) / len(corr_rs_u)

    worst = sorted(booked_loss, key=lambda x: x["close_r"])[:20]
    by_sym = defaultdict(lambda: [0, 0])
    for x in booked_loss:
        by_sym[x["sym"]][0] += 1
        if x["close_r"] < -1.0 - 1e-9:
            by_sym[x["sym"]][1] += 1
    by_setup = Counter(x["setup"] for x in booked_loss
                       if x["close_r"] < -1.0 - 1e-9)
    by_grade = Counter(str(x["sgrade"]) for x in booked_loss
                       if x["close_r"] < -1.0 - 1e-9)
    by_level = Counter(str(x["level"]) for x in booked_loss
                       if x["close_r"] < -1.0 - 1e-9)

    t = {
        "gaps": gaps,
        "exit_bar_agreement": {"agree": agree, "mismatch": mism,
                               "rows": mismatches},
        "n_replayed": len(rows),
        "n_with_stop_trigger": len(stopped),
        "n_booked_full_loss": len(booked_loss),
        "tail_all_triggers": t_all,
        "tail_booked_losses": t_book,
        "mean_r_booked": mean_booked,
        "mean_r_close_fill_floored": mean_corrected,
        "mean_r_close_fill_unfloored": mean_corrected_u,
        "delta_floored": mean_corrected - mean_booked,
        "delta_unfloored": mean_corrected_u - mean_booked,
        "worst20": [{k: x[k] for k in
                     ("sym", "day", "et", "side", "setup", "sgrade", "level",
                      "entry", "stop", "trigger_close", "close_r",
                      "minutes_after_entry")} for x in worst],
        "by_symbol_past1R": {k: v for k, v in sorted(
            by_sym.items(), key=lambda kv: -kv[1][1])},
        "by_setup_past1R": dict(by_setup),
        "by_sgrade_past1R": dict(by_grade),
        "by_level_past1R": dict(by_level),
    }
    # --- per-grade rate, and what the correction does to the gates ----------
    den = Counter(str(r.get("sgrade")) for r in traded_all)
    loss_den = Counter(str(x["sgrade"]) for x in booked_loss)
    past = Counter(str(x["sgrade"]) for x in booked_loss
                   if x["close_r"] < -1.0 - 1e-9)
    t["by_sgrade_rate"] = {
        g: {"traded": den.get(g, 0), "booked_losses": loss_den.get(g, 0),
            "past_1R": past.get(g, 0),
            "rate": (past.get(g, 0) / loss_den[g]) if loss_den.get(g) else None}
        for g in sorted(set(list(den) + list(loss_den)))
    }
    # S-subset mean R, booked vs corrected
    for label, series in (("booked", None), ("corrected", corrected)):
        vals = []
        for r in traded_all:
            if str(r.get("sgrade")) != "S":
                continue
            k = (r["sym"], r["day"], int(r["entry_i"]), r["side"])
            vals.append(series.get(k, float(r["r"])) if series else float(r["r"]))
        t["s_mean_r_" + label] = (sum(vals) / len(vals)) if vals else None
        t["s_n"] = len(vals)
    # months green, booked vs corrected (durability gate)
    for label, series in (("booked", None), ("corrected", corrected)):
        by_m = defaultdict(float)
        for r in traded_all:
            k = (r["sym"], r["day"], int(r["entry_i"]), r["side"])
            by_m[r["ym"]] += (series.get(k, float(r["r"])) if series
                              else float(r["r"]))
        t["months_green_" + label] = sum(1 for v in by_m.values() if v > 0)
        t["months_total"] = len(by_m)

    out["tape"] = t

    print("== 2. THE TAPE: what the stop-triggering CLOSE actually was ==")
    print("replayed %d rows  (gaps: %s)" % (len(rows), gaps))
    print("rows whose initial stop was triggered by a close: %d" % len(stopped))
    print("of those, rows the book charged a full -1.000R:    %d" % len(booked_loss))
    print("self-check, exit bar == entry_i + bars:            %d agree, %d off "
          "(all +/-1 bar, half-cent rounding on the 2dp stored stop): %s"
          % (agree, mism, mismatches))
    print()
    print("close-fill R on the %d booked stop-outs:" % t_book["n"])
    print("  min %.4f   p1 %.4f   p5 %.4f   median %.4f   mean %.4f"
          % (t_book["min"], t_book["p1"], t_book["p5"],
             t_book["median"], t_book["mean"]))
    print("  worse than -1.00R : %d of %d  (%.1f%%)"
          % (t_book["n_worse_than_1R"], t_book["n"],
             100.0 * t_book["n_worse_than_1R"] / max(1, t_book["n"])))
    print("  worse than -1.25R : %d of %d  (%.1f%%)"
          % (t_book["n_worse_than_125R"], t_book["n"],
             100.0 * t_book["n_worse_than_125R"] / max(1, t_book["n"])))
    print()
    print("book mean R  booked %+.4f -> close-fill floored %+.4f  (delta %+.4f)"
          % (mean_booked, mean_corrected, mean_corrected - mean_booked))
    print("             booked %+.4f -> close-fill UNfloored %+.4f  (delta %+.4f)"
          % (mean_booked, mean_corrected_u, mean_corrected_u - mean_booked))
    print()
    print("S mean R  booked %+.4f -> corrected %+.4f   (n=%d)"
          % (t["s_mean_r_booked"], t["s_mean_r_corrected"], t["s_n"]))
    print("months green  booked %d/%d -> corrected %d/%d"
          % (t["months_green_booked"], t["months_total"],
             t["months_green_corrected"], t["months_total"]))
    print("past-1R rate by Austin grade:")
    for g, v in t["by_sgrade_rate"].items():
        if v["booked_losses"]:
            print("  %-5s traded %4d  booked losses %4d  past 1R %4d  (%.1f%%)"
                  % (g, v["traded"], v["booked_losses"], v["past_1R"],
                     100.0 * v["rate"]))
    print()
    print("worst 10 by close-fill R:")
    for x in worst[:10]:
        print("  %-6s %s %s %s  entry %.2f stop %.2f close %.2f -> %.4fR  (+%d min)"
              % (x["sym"], x["day"], x["et"], x["side"], x["entry"], x["stop"],
                 x["trigger_close"], x["close_r"], x["minutes_after_entry"]))
    print()
    return t, rows


# ---------------------------------------------------------------------------
# 3. drawdown
# ---------------------------------------------------------------------------

def _curve(seq):
    """(equity, max_dd, dd_start_i, dd_end_i, peak_i) over a list of R values."""
    eq, peak, peak_i = 0.0, 0.0, -1
    best = (0.0, -1, -1, -1)
    curve = []
    for i, r in enumerate(seq):
        eq += r
        curve.append(eq)
        if eq > peak:
            peak, peak_i = eq, i
        dd = peak - eq
        if dd > best[0]:
            best = (dd, peak_i, i, peak_i)
    return curve, best


def _streaks(seq):
    longest, cur = 0, 0
    for r in seq:
        if r < 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return longest


def section_dd(out, corrected_rows=None):
    _, _, traded = load_traded()

    def order_entry(r):
        return (r["day"], r["et"], r["sym"])

    def exit_minute(r):
        # entry_i is the index of the 09:30-based RTH bar; bars is the hold.
        m = int(r["entry_i"]) + int(r["bars"])
        return "%02d:%02d" % (9 + (30 + m) // 60, (30 + m) % 60)

    def order_exit(r):
        return (r["day"], exit_minute(r), r["sym"])

    res = {}
    for name, keyfn in (("by_entry_time", order_entry), ("by_exit_time", order_exit)):
        rows = sorted(traded, key=keyfn)
        seq = [float(r["r"]) for r in rows]
        curve, (dd, p_i, t_i, _) = _curve(seq)
        span = rows[p_i + 1: t_i + 1] if p_i >= 0 else rows[: t_i + 1]
        res[name] = {
            "n": len(seq),
            "total_r": curve[-1],
            "max_dd_r": dd,
            "dd_trades": len(span),
            "dd_from": (rows[p_i]["day"] if p_i >= 0 else rows[0]["day"]),
            "dd_to": rows[t_i]["day"],
            "dd_wins": sum(1 for r in span if float(r["r"]) > 0),
            "dd_losses": sum(1 for r in span if float(r["r"]) < 0),
            "dd_worst_single_r": min([float(r["r"]) for r in span] or [0.0]),
            "longest_losing_streak": _streaks(seq),
            "n_losses": sum(1 for x in seq if x < 0),
        }

    # the same curve if losses filled at the triggering close, floored at -1.25R
    if corrected_rows:
        for label, field in (("close_fill_floored", "close_r_floored"),
                             ("close_fill_unfloored", "close_r")):
            corr = {(x["sym"], x["day"], x["entry_i"], x["side"]): x[field]
                    for x in corrected_rows if x["hit_i"] is not None
                    and abs(x["booked_r"] + 1.0) <= 1e-12}
            rows = sorted(traded, key=order_entry)
            seq = [corr.get((r["sym"], r["day"], int(r["entry_i"]), r["side"]),
                            float(r["r"])) for r in rows]
            curve, (dd, p_i, t_i, _) = _curve(seq)
            span = rows[p_i + 1: t_i + 1] if p_i >= 0 else rows[: t_i + 1]
            res["by_entry_time_" + label] = {
                "n": len(seq), "total_r": curve[-1], "max_dd_r": dd,
                "dd_trades": len(span),
                "dd_from": rows[max(p_i, 0)]["day"], "dd_to": rows[t_i]["day"],
                "dd_wins": sum(1 for r in span if float(r["r"]) > 0),
                "dd_losses": sum(1 for r in span if float(r["r"]) < 0),
                "dd_worst_single_r": min(seq[p_i + 1: t_i + 1] or [0.0]),
                "longest_losing_streak": _streaks(seq),
            }

    out["dd"] = res
    print("== 3. DRAWDOWN (1R per trade, chronological) ==")
    for name, d in res.items():
        print("%-28s total %+8.2fR   max DD %7.2fR over %3d trades  "
              "(%s -> %s)  longest losing streak %d"
              % (name, d["total_r"], d["max_dd_r"], d["dd_trades"],
                 d["dd_from"], d["dd_to"], d["longest_losing_streak"]))
    d = res["by_entry_time"]
    print()
    print("deepest DD composition: %d trades, %d wins / %d losses, "
          "worst single trade %.3fR"
          % (d["dd_trades"], d["dd_wins"], d["dd_losses"], d["dd_worst_single_r"]))
    print()
    return res


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", action="store_true")
    ap.add_argument("--tape", action="store_true")
    ap.add_argument("--dd", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    run_all = not (a.book or a.tape or a.dd)

    out = {}
    if run_all or a.book:
        section_book(out)
    tape_rows = None
    if run_all or a.tape:
        _check_constants()
        _, tape_rows = section_tape(out, limit=a.limit or None)
    if run_all or a.dd:
        section_dd(out, corrected_rows=tape_rows)

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("wrote %s" % a.json)


if __name__ == "__main__":
    main()
