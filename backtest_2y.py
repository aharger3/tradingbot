"""24-month archive replay -> one flat per-trade JSON for the interactive report.

Same engine as backtest_12mo.py (backtest_week.simulate_day, cache-first
polygon_feed = data_archive on disk), only the window is 2 years and the output
is a row per signal with every slicing dimension attached, so the HTML report
can filter without re-running anything.

Usage:  python backtest_2y.py [--days 730] [--out research/bt2y_trades.json]
"""
import argparse, json, re, statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import loss_halt
import polygon_feed as pf
from research import downgrade as dg
import backtest_week as bw
from backtest_week import simulate_day, htf_bias_for, RISK_DOLLARS
# The ONE entry fill. Nothing is priced here -- this book records WHICH
# fill it was run on, because a dollar figure in this repo is only live if
# it names its fill as well as its book (DIRECTION.md, 2026-08-30).
from entry_fill import ENTRY_FILL
from backtest_12mo import hourly_from_1m, qqq_level_breaks
from universe import (ALL_SYMS, INDEX_POOL, CORE_SYMBOLS, EXPERIMENTAL_SYMBOLS,
                      pool_for, has_archive)

ROOT = Path(__file__).parent
ETFS = set(INDEX_POOL)                       # the only ETFs in the archive
TAG_RE = re.compile(r"\[([a-z0-9]+)\]")
S_RE = re.compile(r" S(\d+)")
LEVEL_RE = re.compile(r"(?:above|below) (PDH|PDL|PMH|PML|OR high|OR low|pivot high|pivot low)")

# G7.1/labels. Austin, 2026-08-29: "so in homework also tell me what setup you
# think it is", "remember BR and OCR is also a setup when both of them are
# together." Both fields already exist on every signal (signal_runner.py
# SignalRunner._label_confluence stamps setup_type; every emit site stamps
# stop_level_name) and were being thrown away when SimTrade was built --
# nothing here is computed, it is read off backtest_week.SimTrade now that it
# carries the two fields through (research/g71_labeller.md). See
# research/g72_labels_report.py for the distribution/sample this produces.
SETUP_LABEL = {"break_and_retest": "break-and-retest",
               "one_candle_rule": "one-candle-rule",
               "br_ocr_confluence": "BR+OCR",
               "reentry_84_rule": "other (84% re-entry)",
               "fair_value_gap": "other (FVG)", "flag": "other (flag)"}

# His six, named directly by Austin on 2026-08-29 (Projects/omen-rulebook.md,
# "The six levels, named at last"): PDH, PDL, PMH, PML, HOD, LOD. NOTE this
# corrects research/g71_labeller.md, which was written earlier the same day
# and still guessed the opening range belonged in the six -- it does not.
# "you know the 6 levels i watch thats it." The engine's stop_level_name
# already spells these four ("PDH"/"PDL"/"PMH"/"PML") plus "HOD"/"LOD" when
# HODLOD_PAIR is on (dormant today; F3 2026-07-11) -- no remapping needed,
# only OR high/OR low have to be named honestly as NOT one of the six.
HIS_SIX = {"PDH", "PDL", "PMH", "PML", "HOD", "LOD"}
# The timeframe each level is DRAWN on. The ENTRY timeframe is 1m for every
# row in this engine (polygon_feed.rth); the HTF bias is 1h
# (backtest_12mo.hourly_from_1m). There is no other timeframe.
LEVEL_TF = {"PDH": "1D", "PDL": "1D",
            "PMH": "1m premarket", "PML": "1m premarket",
            "HOD": "1m session extreme", "LOD": "1m session extreme"}


def level_label(t):
    """(level name -- his six spelled plainly, or 'not-his: <what it really
    was>' -- and the timeframe it was drawn on), read off SimTrade.stop_level_
    name. A label only: nothing here routes, grades or vetoes a trade."""
    n = (t.stop_level_name or "").strip()
    if n in HIS_SIX:
        return n, LEVEL_TF[n]
    if n in ("OR high", "OR low"):
        return "not-his: " + n, "5m opening range"
    if n.startswith("pivot"):
        return "not-his: " + n, "1m intraday swing"
    if n.startswith("Order block"):
        return "not-his: order block", "1m single candle"
    if n.startswith(("FVG", "Flag")):
        return "not-his: " + n, "1m intraday"
    if n:
        # The 84% re-entry's stop_level_name spells the STOP ("Original
        # stop" / "Reclaim candle low" / ...), never a level -- Austin's own
        # rules confirm this is the one setup where "which level" is
        # genuinely unrecoverable: the level is the prior failed entry, not
        # a level the detector named. Reported honestly, not guessed at.
        return "not-his: prior entry (84%)", "1m failed entry"
    return "not-his: unnamed", "1m intraday"


def archive_days(sym):
    d = ROOT / "data_archive" / sym
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []


def daily_ohlc(sym):
    """day -> (open, close, high, low) from the archived RTH bars."""
    out = {}
    for d in archive_days(sym):
        try:
            rth = pf.rth(pf.fetch_day(sym, d))
        except Exception:
            continue
        if len(rth) < 30:
            continue
        out[d] = (rth[0].open, rth[-1].close,
                  max(c.high for c in rth), min(c.low for c in rth))
    return out


def spy_context():
    """day -> {spy_trend, spy_ret, vol_regime} from SPY's own archive."""
    spy = daily_ohlc("SPY")
    keys = sorted(spy)
    closes = [spy[k][1] for k in keys]
    ctx, rets = {}, []
    for i, k in enumerate(keys):
        prev = closes[i - 1] if i else closes[i]
        rets.append((closes[i] - prev) / prev * 100 if prev else 0.0)
        sma = statistics.fmean(closes[max(0, i - 19):i + 1])
        vol = statistics.pstdev(rets[max(0, i - 19):i + 1]) if i >= 5 else 0.0
        ctx[k] = {"spy_trend": "bull" if closes[i] >= sma else "bear",
                  "spy_ret": round(rets[i], 2), "_vol": vol}
    vols = sorted(v["_vol"] for v in ctx.values() if v["_vol"])
    lo = vols[len(vols) // 3] if vols else 0
    hi = vols[2 * len(vols) // 3] if vols else 0
    for v in ctx.values():
        v["vol_regime"] = ("calm" if v["_vol"] <= lo else
                           "normal" if v["_vol"] <= hi else "wild")
        v.pop("_vol")
    return ctx


def dg_bars(rth):
    """downgrade.py reads plain dicts, not Candle objects (same shape t66 feeds it)."""
    return [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
            for c in rth]


def bucket(x, edges, names):
    for e, n in zip(edges, names):
        if x <= e:
            return n
    return names[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--out", default="research/bt2y_trades.json")
    args = ap.parse_args()

    syms = [s for s in ALL_SYMS if has_archive(s, 100)]
    last = max((archive_days(s) or ["1970-01-01"])[-1] for s in syms)
    start = (date.fromisoformat(last) - timedelta(days=args.days)).isoformat()
    window = sorted({d for s in syms for d in archive_days(s) if d >= start})
    print("%d symbols, %d sessions %s..%s" % (len(syms), len(window), window[0], window[-1]))

    ctx = spy_context()
    qqq_brk = qqq_level_breaks(window)
    print("QQQ key-level breaks on %d days" % len(qqq_brk))

    rows, sessions = [], set()
    for sym in syms:
        days = [d for d in archive_days(sym) if d >= start]
        day_bars, hourly = {}, []
        for d in days:
            try:
                bars = pf.fetch_day(sym, d)
            except Exception:
                continue
            if not bars:
                continue
            r = pf.rth(bars)
            if len(r) < 30:
                continue
            day_bars[d] = (bars, r)
            hourly += hourly_from_1m(d, r)

        n0, prev = len(rows), None
        for d in sorted(day_bars):
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = pf.premarket_hi_lo(bars)
            bias = htf_bias_for(hourly, d)
            trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc,
                                  qqq=qqq_brk.get(d))
            sessions.add(d)

            dopen, dclose = rth[0].open, rth[-1].close
            dhi, dlo = max(c.high for c in rth), min(c.low for c in rth)
            gap = (dopen - pdc) / pdc * 100 if pdc else 0.0
            drange = (dhi - dlo) / dopen * 100 if dopen else 0.0
            dret = (dclose - dopen) / dopen * 100 if dopen else 0.0
            cx = ctx.get(d, {})
            dow = datetime.fromisoformat(d).strftime("%a")
            seq = defaultdict(int)
            dbars = dg_bars(rth) if trades else None

            for t in trades:
                # Austin's own S/A/C ladder, computed alongside the engine's
                # legacy A+/A/B/C/X. downgrade.py is still NOT wired into
                # detection -- this only ATTACHES his grade to each signal so
                # the report can filter on it. Level proxy is the stop, the same
                # input research/t66_downgrade_measure.py graded on, so the two
                # measurements stay comparable.
                rec = dg.score(dbars, t.entry_idx, t.stop, t.direction == "call", bias)
                risk = abs(t.entry - t.stop)
                lv = LEVEL_RE.search(t.reason)
                lvl_name, lvl_tf = level_label(t)
                sm = S_RE.search(t.reason)
                stop_pct = risk / t.entry * 100 if t.entry else 0.0
                key = "fired" if t.status == "fired" else "skip"
                seq[key] += 1
                rows.append({
                    "sym": sym,
                    "cls": "etf" if sym in ETFS else "stock",
                    "pool": pool_for(sym),
                    "tier": ("core" if sym in CORE_SYMBOLS else
                             "experimental" if sym in EXPERIMENTAL_SYMBOLS else "other"),
                    "day": d, "ym": d[:7], "yr": d[:4], "dow": dow,
                    "setup": t.signal_type, "dir": t.direction,
                    # G7.1/labels: the labeller's answers, surfaced not derived.
                    # `setup` above stays the BASE detector so nothing that
                    # already groups on it moves; setup_label is the class
                    # Austin names, BR+OCR as its own third class per his rule.
                    "setup_label": SETUP_LABEL.get(t.setup_type or t.signal_type,
                                                   t.setup_type or t.signal_type),
                    "entry_tf": "1m", "bias_tf": "1h",
                    "grade": t.grade, "status": t.status,
                    "traded": bool(t.counted), "alert": bool(t.is_alert),
                    "et": t.entry_time[:5],
                    "slot": t.entry_time[:2] + (":00" if t.entry_time[3:5] < "30" else ":30"),
                    "entry": round(t.entry, 2), "stop": round(t.stop, 2),
                    "target": round(t.target, 2), "exit": round(t.exit_price, 2),
                    "out": t.outcome, "pnl": t.pnl, "r": round(t.pnl / RISK_DOLLARS, 3),
                    "bars": max(0, t.exit_idx - t.entry_idx),
                    "entry_i": t.entry_idx,          # index into pf.rth(day) — exit sweeps need it
                    "side": "L" if t.direction == "call" else "S",
                    "stop_pct": round(stop_pct, 3),
                    "stopb": bucket(stop_pct, [0.15, 0.35, 0.7],
                                    ["tight", "mid", "wide", "very wide"]),
                    "bias": bias or "none",
                    "aligned": ("n/a" if not bias else
                                # htf_bias_for returns "bullish"/"bearish"/"neutral",
                                # never "bull" -- comparing to "bull" collapsed this
                                # whole facet into "is this a put" (found by G4).
                                "n/a" if bias == "neutral" else
                                "with" if (bias == "bullish") == (t.direction == "call")
                                else "against"),
                    "level": lv.group(1) if lv else "other",
                    "level_name": lvl_name, "level_tf": lvl_tf,
                    "level_px": round(t.level_price or t.stop, 2),
                    "s": int(sm.group(1)) if sm else -1,
                    "tags": TAG_RE.findall(t.reason),
                    "seq": seq[key],
                    "gap": round(gap, 2),
                    "gapb": bucket(abs(gap), [0.25, 1.0], ["flat", "small gap", "big gap"]),
                    "drange": round(drange, 2),
                    "rangeb": bucket(drange, [1.5, 3.0], ["quiet", "normal", "big range"]),
                    "dret": round(dret, 2),
                    "sgrade": (rec or {}).get("grade", "n/a"),
                    "tripped": str((rec or {}).get("n_tripped", "n/a")),
                    "confluence": "yes" if (rec or {}).get("confluence") else "no",
                    "downgrades": (rec or {}).get("tripped", []),
                    "scaled": bool(t.scaled),
                    "spy_trend": cx.get("spy_trend", "n/a"),
                    "vol_regime": cx.get("vol_regime", "n/a"),
                    "reason": t.reason,
                })
            prev = d
        print("[%s] %d sessions, %d signals" % (sym, len(day_bars), len(rows) - n0))

    # R31 — the two-consecutive-loss halt, account-wide, causal on the exit.
    # It has to run here and not inside simulate_day: the halt is a statement
    # about the DAY across every symbol, and the loop above walks one symbol at
    # a time. See loss_halt.py for why the counter advances on the close and not
    # on the entry. LOSS_HALT=0 restores the unhalted book.
    halted = loss_halt.apply_to_book(rows)
    print("R31 loss halt: %d trades blocked (%s)"
          % (halted, "ON" if loss_halt.LOSS_HALT else "OFF"))

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    # The book NAMES ITS FILL. `entry_fill: "published"` marks a book priced at
    # the pre-2026-08-30 clamp, which only 105 of 4,508 trades could actually
    # have been filled at (research/g80_lookahead_refute.md) -- any reader of
    # this JSON can now tell which of the two it is holding instead of guessing.
    # `entry_misses` is days the entry order never filled: 0 on the shipped
    # `close` default, non-zero only on the resting-limit arms, and it must be
    # reported alongside the dollars rather than dropped.
    misses = bw.ENTRY_FILL_MISSES
    print("entry fill: %s — %d setups never filled%s"
          % (ENTRY_FILL, len(misses),
             " (NOT TRADES — count them against the days traded)" if misses else ""))
    meta = {"generated": datetime.now().isoformat(timespec="seconds"),
            "first": min(sessions), "last": max(sessions),
            "sessions": len(sessions), "symbols": syms,
            "risk_dollars": RISK_DOLLARS, "signals": len(rows),
            "entry_fill": ENTRY_FILL, "entry_misses": len(misses),
            "loss_halt": bool(loss_halt.LOSS_HALT), "halted": halted,
            "traded": sum(1 for r in rows if r["traded"])}
    out.write_text(json.dumps({"meta": meta, "trades": rows}, separators=(",", ":")),
                   encoding="utf-8")
    print("wrote %s (%.1f MB) — %d signals, %d traded, %d sessions"
          % (out, out.stat().st_size / 1e6, len(rows), meta["traded"], meta["sessions"]))


if __name__ == "__main__":
    main()
