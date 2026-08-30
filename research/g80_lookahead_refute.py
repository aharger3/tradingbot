"""G80 -- an attempt to REFUTE the central look-ahead claim in
`research/g76_rebuild_verdict.md`.

THE CLAIM UNDER TEST
--------------------
    "3,841 of the 4,508 trades in the book -- 85% -- are filled at a price the
     minute had already traded BEFORE the signal existed. signal_runner.py line
     ~1330 returns min(max(level, candle.low), candle.high), and because the
     signal only exists once the minute CLOSES, any fill below the close is a
     price that printed earlier in that minute."

Everything here is recomputed from the archive and from the shipped engine. No
engine file is edited, no mark file is opened, nothing is committed.

WHAT THIS SCRIPT MEASURES

 1. the 85% figure, recomputed from `research/bt2y_trades.json` independently
    of `g76_rebuild_lookahead.py`;
 2. whether the booked fill IS the level (a price a resting limit order would
    have been filled at) or is the bar's own extreme after the clamp bit (a
    price no resting order at the level could have got);
 3. whether the level was KNOWABLE before the entry minute opened -- by level
    family, and then by replaying the actual break-and-retest state machine to
    find the bar on which the setup became armable;
 4. whether the first touch of the level after the setup armed happens IN the
    entry minute (order fills there) or EARLIER (order would have filled sooner,
    at the same price, on a trade the book does not contain);
 5. whether the +0.70R / -0.07R split is a fill effect or a population effect,
    by re-pricing the intrabar group at its own close and by comparing the two
    groups on covariates that have nothing to do with the fill.

Usage:  python research/g80_lookahead_refute.py
Writes: research/g80_lookahead_refute.json
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf            # noqa: E402
import signal_runner as sr           # noqa: E402
from omen_bot import detect_break_retest  # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"
OUT = ROOT / "research" / "g80_lookahead_refute.json"
EPS = 0.005                          # the book carries prices to the cent
BR_WINDOW = 12                       # detect_break_retest default window


# ---------------------------------------------------------------- bar access
_cache: dict = {}


def bars(sym, day):
    k = (sym, day)
    if k not in _cache:
        if len(_cache) > 40:
            _cache.clear()
        _cache[k] = pf.rth(pf.fetch_day(sym, day))
    return _cache[k]


# ------------------------------------------------- the B&R FSM, instrumented
def br_trace(candles, level, is_long, window=BR_WINDOW, rtol_mult=0.0):
    """A read-only replay of omen_bot.detect_break_retest that ALSO reports the
    bar on which each ordered step completed.

    The state machine below is transcribed from omen_bot.detect_break_retest
    (the shipped one). The transcription is checked against the shipped
    function on every row -- `fsm_agrees` in the output counts the rows where
    this replay and the real detector give the same yes/no. Nothing here feeds
    a book; it exists to answer ONE question -- on which bar did BREAK and
    LEAVE complete, i.e. from which bar could an order have been resting at
    the level.

    Indices returned are absolute (into `candles`), not window-relative.
    """
    if len(candles) < 4:
        return None
    w = candles[-window:]
    base = len(candles) - len(w)
    avg_rng = sum(c.high - c.low for c in w) / len(w)
    eps = 0.10 * avg_rng
    rtol = rtol_mult * avg_rng
    state, retest_idx, break_idx, leave_idx = "seek_break", None, None, None
    for i in range(1, len(w)):
        c, p = w[i], w[i - 1]
        if state == "seek_break":
            crossed = (p.close <= level and c.close > level + eps) if is_long \
                else (p.close >= level and c.close < level - eps)
            if crossed:
                state, break_idx = "seek_leave", i
        elif state == "seek_leave":
            left = (c.low > level + eps) if is_long else (c.high < level - eps)
            failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
            if left:
                state, leave_idx = "seek_retest", i
            elif failed:
                state, break_idx, leave_idx = "seek_break", None, None
        elif state == "seek_retest":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back:
                retest_idx, state = i, "hold"
        elif state == "hold":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back:
                retest_idx = i
    if retest_idx is None:
        return None
    return {"break_i": None if break_idx is None else base + break_idx,
            "leave_i": None if leave_idx is None else base + leave_idx,
            "retest_i": base + retest_idx,
            "avg_rng": avg_rng}


# --------------------------------------------------- when was the level known
PIVOT_RE = re.compile(r"pivot (high|low) @(\d\d:\d\d)")


def level_known_by(row, bs):
    """First bar index at which this level's PRICE was already fixed and
    visible. Returns (index, family). A `None` index means it could not be
    established from the trade record alone.

      1D                 prior-day high/low        -> known before the open
      1m premarket       premarket high/low        -> known before the open
      5m opening range   high/low of bars 0..4     -> fixed once bar 4 closed,
                                                      first usable on bar 5
      1m intraday swing  pivot high/low @HH:MM     -> pivot_levels()'s own
                                                      usable_from = i + k + 1
      1m single candle   order block candle        -> the block bar, located as
                                                      the latest earlier bar
                                                      whose high/low IS the level
      1m failed entry    the 84% rule's prior fill -> the earlier signal on the
                                                      same symbol-day
    """
    tf = row.get("level_tf")
    name = row.get("level_name") or ""
    lvl = row.get("level_px")
    ei = row["entry_i"]
    if tf in ("1D", "1m premarket"):
        return 0, tf
    if tf == "5m opening range":
        return 5, tf
    if tf == "1m intraday swing":
        m = PIVOT_RE.search(name)
        if not m:
            return None, tf
        want = m.group(2)
        for j, c in enumerate(bs):
            if sr.bar_time(c.timestamp)[:5] == want:
                return j + sr.PIVOT_STRENGTH + 1, tf
        return None, tf
    if tf in ("1m single candle", "1m failed entry"):
        # the level is a price some EARLIER bar printed; take the latest earlier
        # bar that carries it exactly, which is the tightest honest bound.
        best = None
        if lvl is not None:
            for j in range(min(ei, len(bs))):
                c = bs[j]
                if abs(c.high - lvl) <= EPS or abs(c.low - lvl) <= EPS:
                    best = j
        return best, tf
    return None, tf


# ------------------------------------------------------------------ measures
def summ(rows):
    if not rows:
        return {"n": 0}
    rs = [x["r"] for x in rows]
    return {"n": len(rows),
            "mean_r": round(statistics.fmean(rs), 4),
            "median_r": round(statistics.median(rs), 4),
            "win_pct": round(100 * sum(1 for x in rs if x > 0) / len(rs), 1),
            "total_dollars": round(sum(x["pnl"] for x in rows), 0)}


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    rows = [r for r in book["trades"] if r.get("traded")]
    print("traded rows: %d" % len(rows), flush=True)
    rows.sort(key=lambda r: (r["sym"], r["day"]))

    recs = []
    fsm_agrees = fsm_checked = 0
    for r in rows:
        bs = bars(r["sym"], r["day"])
        i = r["entry_i"]
        if i >= len(bs):
            continue
        c = bs[i]
        long = r["dir"] == "call"
        fill, lvl, stop = r["entry"], r.get("level_px"), r["stop"]
        risk = abs(fill - stop)
        head = (c.close - fill) if long else (fill - c.close)
        rec = {"sym": r["sym"], "day": r["day"], "et": r["et"], "long": long,
               "setup": r["setup"], "level_name": r.get("level_name"),
               "level_tf": r.get("level_tf"), "level_px": lvl,
               "entry_i": i, "fill": fill, "stop": stop, "exit": r["exit"],
               "o": c.open, "h": c.high, "l": c.low, "close": c.close,
               "risk": risk, "head": round(head, 6),
               "head_r": round(head / risk, 4) if risk else 0.0,
               "r": r["r"], "pnl": r["pnl"], "grade": r.get("grade"),
               "sgrade": r.get("sgrade"), "stop_pct": r.get("stop_pct"),
               "out": r.get("out")}
        rec["intrabar"] = head > EPS
        # --- INDEPENDENT CHECK that `level_px` really is the level fill_price
        # was handed: re-run the shipped fill_price on (level_px, this bar) and
        # see whether it reproduces the booked entry. Session extremes are
        # taken from the bars up to and including the entry bar, as the engine
        # does. If this reproduces the book, the fill classification below is
        # reading the same numbers the engine used.
        if lvl is not None:
            shi = max(b.high for b in bs[:i + 1])
            slo = min(b.low for b in bs[:i + 1])
            rec["fill_price_repro"] = abs(
                sr.fill_price(lvl, c, long, shi, slo) - fill) <= EPS
        else:
            rec["fill_price_repro"] = None
        # --- is the booked fill the LEVEL, or the bar extreme after the clamp?
        if lvl is None:
            rec["fillkind"] = "no_level"
        elif abs(fill - lvl) <= EPS:
            rec["fillkind"] = "at_level"
        elif long and abs(fill - c.low) <= EPS and lvl < c.low - EPS:
            rec["fillkind"] = "clamped_to_bar_low"
        elif (not long) and abs(fill - c.high) <= EPS and lvl > c.high + EPS:
            rec["fillkind"] = "clamped_to_bar_high"
        elif abs(fill - c.close) <= EPS:
            rec["fillkind"] = "at_close"
        else:
            rec["fillkind"] = "other"
        # --- did the level's price trade during the entry minute at all?
        rec["level_inside_bar"] = (lvl is not None
                                   and c.low - EPS <= lvl <= c.high + EPS)
        # --- was the level knowable before the entry minute opened?
        kb, fam = level_known_by(r, bs)
        rec["known_by"] = kb
        rec["level_family"] = fam
        rec["known_before_entry"] = (kb is not None and kb < i)
        # --- when did the setup ARM, i.e. break + leave complete?
        rec["armed_by"] = None
        rec["armed_before_entry"] = False
        rec["first_touch_after_arm"] = None
        if r["setup"] == "break_and_retest" and lvl is not None:
            sl = bs[:i + 1]
            tr = br_trace(sl, lvl, long, rtol_mult=sr._retest_tol())
            real = detect_break_retest(sl, lvl, is_long=long,
                                       retest_tol_mult=sr._retest_tol())
            fsm_checked += 1
            if (tr is not None) == (real is not None):
                fsm_agrees += 1
            if tr and tr["leave_i"] is not None:
                rec["armed_by"] = tr["leave_i"]
                rec["armed_before_entry"] = tr["leave_i"] < i
                rec["retest_i"] = tr["retest_i"]
                ft = None
                for j in range(tr["leave_i"] + 1, i + 1):
                    b = bs[j]
                    if (b.low <= lvl) if long else (b.high >= lvl):
                        ft = j
                        break
                rec["first_touch_after_arm"] = ft
        recs.append(rec)

    intra = [x for x in recs if x["intrabar"]]
    atcl = [x for x in recs if not x["intrabar"]]

    out = {"traded_rows": len(recs),
           "fsm_replay_checked": fsm_checked, "fsm_replay_agrees": fsm_agrees}

    # ---- 1. the headline, recomputed
    out["headline"] = {
        "intrabar_n": len(intra), "at_close_n": len(atcl),
        "intrabar_pct": round(100 * len(intra) / len(recs), 1),
        "intrabar": summ(intra), "at_close": summ(atcl),
        "g76_said": {"intrabar_n": 3841, "pct": 85.2,
                     "intrabar_mean_r": 0.6978, "at_close_mean_r": -0.0696}}

    # ---- 2. is the fill a price a resting order could have been filled at?
    out["fillkind"] = dict(Counter(x["fillkind"] for x in intra).most_common())
    out["fillkind_all"] = dict(Counter(x["fillkind"] for x in recs).most_common())
    out["fillkind_perf"] = {k: summ([x for x in intra if x["fillkind"] == k])
                            for k in out["fillkind"]}
    out["level_inside_bar"] = sum(1 for x in intra if x["level_inside_bar"])
    out["fill_price_repro"] = {
        "checked": sum(1 for x in recs if x["fill_price_repro"] is not None),
        "reproduced": sum(1 for x in recs if x["fill_price_repro"] is True)}

    # ---- 3. was the level knowable before the entry minute?
    fam = {}
    for f in sorted(set(x["level_family"] or "?" for x in intra)):
        g = [x for x in intra if (x["level_family"] or "?") == f]
        fam[f] = {"n": len(g),
                  "known_before_entry": sum(1 for x in g if x["known_before_entry"]),
                  "unresolved": sum(1 for x in g if x["known_by"] is None)}
    out["level_family"] = fam
    out["level_known_before_entry"] = sum(1 for x in intra if x["known_before_entry"])
    out["level_unresolved"] = sum(1 for x in intra if x["known_by"] is None)

    # ---- 4. arming and first touch (break-and-retest only)
    br = [x for x in intra if x["setup"] == "break_and_retest"]
    br_traced = [x for x in br if x["armed_by"] is not None]
    ft_entry = [x for x in br_traced if x["first_touch_after_arm"] == x["entry_i"]]
    ft_early = [x for x in br_traced if x["first_touch_after_arm"] is not None
                and x["first_touch_after_arm"] < x["entry_i"]]
    ft_none = [x for x in br_traced if x["first_touch_after_arm"] is None]
    out["arming"] = {
        "br_intrabar_n": len(br),
        "fsm_traced": len(br_traced),
        "fsm_untraceable": len(br) - len(br_traced),
        "armed_strictly_before_entry_bar": sum(1 for x in br_traced if x["armed_before_entry"]),
        "arm_to_entry_bars_median": statistics.median(
            [x["entry_i"] - x["armed_by"] for x in br_traced]) if br_traced else None,
        "first_touch_is_the_entry_bar": len(ft_entry),
        "first_touch_earlier_than_entry_bar": len(ft_early),
        "never_touched": len(ft_none),
        "perf_first_touch_is_entry_bar": summ(ft_entry),
        "perf_first_touch_earlier": summ(ft_early)}

    # ---- 5. fill effect vs population effect
    def reprice(x):
        """R if the same trade had been filled at its own bar close, exit price
        held fixed. Conservative: the target would in reality move out with the
        wider risk, so this OVERSTATES what the close-filled trade keeps."""
        rk = abs(x["close"] - x["stop"])
        if rk <= 0:
            return None
        d = (x["exit"] - x["close"]) if x["long"] else (x["close"] - x["exit"])
        return d / rk

    rp = [(x, reprice(x)) for x in intra]
    rp = [(x, v) for x, v in rp if v is not None]
    out["reprice_intrabar_at_close"] = {
        "n": len(rp),
        "mean_r_as_booked": round(statistics.fmean([x["r"] for x, _ in rp]), 4),
        "mean_r_if_filled_at_close": round(statistics.fmean([v for _, v in rp]), 4),
        "median_r_if_filled_at_close": round(statistics.median([v for _, v in rp]), 4),
        "at_close_group_mean_r": out["headline"]["at_close"].get("mean_r"),
        "note": "exit price held fixed; the real close-filled trade would carry a "
                "further-out target, so this is an upper bound on what survives"}

    out["reprice_by_fillkind"] = {}
    for k in out["fillkind"]:
        g = [(x, reprice(x)) for x in intra if x["fillkind"] == k]
        g = [(x, v) for x, v in g if v is not None]
        if g:
            out["reprice_by_fillkind"][k] = {
                "n": len(g),
                "as_booked": round(statistics.fmean([x["r"] for x, _ in g]), 4),
                "if_filled_at_close": round(statistics.fmean([v for _, v in g]), 4)}

    # the ONE subset where the g76 claim is simply wrong: the fill is the level,
    # the level was fixed by an earlier bar, the setup had already armed, and
    # the first touch of the level after arming is the entry bar itself -- so a
    # limit order resting since the arm bar fills exactly there, in that minute,
    # on that trade.
    attainable = [x for x in intra
                  if x["fillkind"] == "at_level"
                  and x["known_before_entry"]
                  and x["armed_before_entry"]
                  and x["first_touch_after_arm"] == x["entry_i"]]
    # arming is only traced for break-and-retest, so for the order block and the
    # 84% re-entry the first-touch test cannot be run. Carry the upper bound:
    # every at-the-level fill on a known-early level from those two setups is
    # counted as if it passed, which it almost certainly does not.
    ub = [x for x in intra
          if x["fillkind"] == "at_level" and x["known_before_entry"]
          and x["setup"] != "break_and_retest"]
    out["attainable_upper_bound_untraced_setups"] = {"n": len(ub), **summ(ub)}
    out["genuinely_attainable_on_this_trade"] = {
        "n": len(attainable),
        "pct_of_intrabar": round(100 * len(attainable) / len(intra), 2),
        "pct_of_book": round(100 * len(attainable) / len(recs), 2),
        **summ(attainable)}

    out["head_start"] = {
        "intrabar_mean_head_r": round(statistics.fmean([x["head_r"] for x in intra]), 4),
        "intrabar_median_head_r": round(statistics.median([x["head_r"] for x in intra]), 4),
        "all_mean_head_r": round(statistics.fmean([x["head_r"] for x in recs]), 4),
        "book_mean_r": round(statistics.fmean([x["r"] for x in recs]), 4),
        "pct_up_half_r": round(100 * sum(1 for x in recs if x["head_r"] >= 0.5) / len(recs), 1),
        "pct_up_one_r": round(100 * sum(1 for x in recs if x["head_r"] >= 1.0) / len(recs), 1)}

    # head-start quartiles inside the intrabar group -- does R scale with it?
    hs = sorted(intra, key=lambda x: x["head_r"])
    q = len(hs) // 4
    out["head_start_quartiles"] = [
        {"band": i + 1,
         "head_r_range": [round(g[0]["head_r"], 3), round(g[-1]["head_r"], 3)],
         **summ(g)}
        for i, g in enumerate([hs[:q], hs[q:2 * q], hs[2 * q:3 * q], hs[3 * q:]]) if g]

    # population covariates -- things the fill rule does not touch
    def cov(g):
        return {"n": len(g),
                "pct_long": round(100 * sum(1 for x in g if x["long"]) / len(g), 1),
                "median_bar_range_pct": round(statistics.median(
                    [100 * (x["h"] - x["l"]) / x["close"] for x in g]), 4),
                "median_stop_pct": round(statistics.median(
                    [x["stop_pct"] for x in g if x["stop_pct"] is not None]), 4),
                "setup_mix": dict(Counter(x["setup"] for x in g).most_common()),
                "sgrade_mix": dict(Counter(x["sgrade"] for x in g).most_common()),
                "median_body_frac": round(statistics.median(
                    [abs(x["close"] - x["o"]) / (x["h"] - x["l"])
                     for x in g if x["h"] > x["l"]]), 4)}
    out["population"] = {"intrabar": cov(intra), "at_close": cov(atcl)}

    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2)

    # ------------------------------------------------------------- console
    p = print
    p("")
    p("FSM replay agrees with the shipped detector on %d of %d rows"
      % (fsm_agrees, fsm_checked))
    p("")
    p("1. HEADLINE  intrabar fills %d of %d = %.1f%%   (g76 said 3841 / 85.2%%)"
      % (len(intra), len(recs), out["headline"]["intrabar_pct"]))
    p("   intrabar mean R %+.4f   at-close mean R %+.4f"
      % (out["headline"]["intrabar"]["mean_r"], out["headline"]["at_close"]["mean_r"]))
    p("")
    p("2. WHAT THE FILL ACTUALLY IS, inside the intrabar group")
    for k, v in out["fillkind"].items():
        p("   %-22s %5d  (%.1f%%)   mean R %+.3f"
          % (k, v, 100 * v / len(intra), out["fillkind_perf"][k]["mean_r"]))
    p("   level price traded inside the entry minute: %d of %d"
      % (out["level_inside_bar"], len(intra)))
    p("")
    p("3. WAS THE LEVEL KNOWN BEFORE THE ENTRY MINUTE OPENED?")
    p("   %d of %d intrabar fills sit on a level fixed by an EARLIER bar"
      % (out["level_known_before_entry"], len(intra)))
    for f, v in fam.items():
        p("   %-20s %5d   known-before %5d   unresolved %4d"
          % (f, v["n"], v["known_before_entry"], v["unresolved"]))
    p("")
    p("4. WAS THE ORDER PLACEABLE BEFORE THE ENTRY MINUTE? (break-and-retest)")
    a = out["arming"]
    p("   traced %d of %d;  break+leave complete before the entry bar: %d"
      % (a["fsm_traced"], a["br_intrabar_n"], a["armed_strictly_before_entry_bar"]))
    p("   median bars from arm to entry: %s" % a["arm_to_entry_bars_median"])
    p("   first touch of the level after arming lands ON the entry bar: %d  (mean R %+.3f)"
      % (a["first_touch_is_the_entry_bar"], a["perf_first_touch_is_entry_bar"]["mean_r"]))
    p("   ... lands EARLIER (a resting order fills sooner, same price): %d  (mean R %+.3f)"
      % (a["first_touch_earlier_than_entry_bar"], a["perf_first_touch_earlier"]["mean_r"]))
    p("")
    p("5. FILL EFFECT OR POPULATION EFFECT?")
    rr = out["reprice_intrabar_at_close"]
    p("   intrabar group as booked            mean R %+.4f" % rr["mean_r_as_booked"])
    p("   same trades re-priced at the close  mean R %+.4f  (upper bound)"
      % rr["mean_r_if_filled_at_close"])
    p("   the group that DID fill at the close mean R %+.4f" % rr["at_close_group_mean_r"])
    p("   head start: intrabar mean %+.3fR, whole book mean %+.3fR, book mean R %+.3f"
      % (out["head_start"]["intrabar_mean_head_r"],
         out["head_start"]["all_mean_head_r"], out["head_start"]["book_mean_r"]))
    for b in out["head_start_quartiles"]:
        p("   head-start band %d  %s  n=%d  mean R %+.3f  win %.1f%%"
          % (b["band"], b["head_r_range"], b["n"], b["mean_r"], b["win_pct"]))
    p("   re-price by fill kind:")
    for k, v in out["reprice_by_fillkind"].items():
        p("     %-22s n=%5d  booked %+.3f -> at close %+.3f"
          % (k, v["n"], v["as_booked"], v["if_filled_at_close"]))
    ga = out["genuinely_attainable_on_this_trade"]
    p("")
    p("6. FILLS THAT A RESTING ORDER REALLY WOULD HAVE GOT, ON THIS TRADE, IN THIS MINUTE")
    p("   %d  (%.2f%% of the intrabar group, %.2f%% of the book)  mean R %+.3f"
      % (ga["n"], ga["pct_of_intrabar"], ga["pct_of_book"], ga["mean_r"]))
    ub2 = out["attainable_upper_bound_untraced_setups"]
    p("   + at most %d more from the order block / 84%% rule, where arming is not traced"
      % ub2["n"])
    p("")
    p("   fill_price() reproduced from level_px on %d of %d rows"
      % (out["fill_price_repro"]["reproduced"], out["fill_price_repro"]["checked"]))
    p("")
    p("   population  intrabar vs at-close:")
    for k in ("median_bar_range_pct", "median_stop_pct", "median_body_frac", "pct_long"):
        p("     %-22s %8s  vs %8s"
          % (k, out["population"]["intrabar"][k], out["population"]["at_close"][k]))
    p("     setup mix   %s  vs  %s"
      % (out["population"]["intrabar"]["setup_mix"],
         out["population"]["at_close"]["setup_mix"]))
    p("")
    p("wrote %s" % OUT)


if __name__ == "__main__":
    main()
