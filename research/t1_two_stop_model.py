"""T1 - the two-stop model: four stop-regime arms over the two-year archive.

Austin's number one complaint, and the mechanism T0 already shipped
(`68e276ca`, `stop_rule.py::disaster_stop_price/disaster_stop_hit`,
`backtest_week.py::_disaster_hit`): a level stop that still fires on the
CLOSE (`stop_rule.stop_hit_on_close`, settled five times) with a DISASTER
STOP resting underneath it that fires INTRABAR on touch. His words,
`research/marks/probe_master_2026-08-29.jsonl`, `fact_stop_floor_is_fiction`:

    "-1r is what we want max slippage -1.25"

T1 does not change that mechanism -- it MEASURES it, across the four arms the
spec names, and answers the one question nobody had measured: how often the
disaster stop kills a trade that would have come back.

Arms:
  clamp     DISASTER_STOP=0                 -- "today's clamp": no resting
            order, a close-triggered stop floored at -1.25R (stop_rule's
            pre-two-stop-model book).
  r100      DISASTER_STOP=1 DISASTER_STOP_R=1.0  -- the shipped default
            (R1's ratified number).
  r125      DISASTER_STOP=1 DISASTER_STOP_R=1.25 -- the disaster order moved
            out to the -1.25R outer bound itself, so it only catches bars
            that gap straight through where the level stop already sits.
  nofloor   DISASTER_STOP=0, and the -1.25R clamp on `stop_fill_price`
            REMOVED (floor_r=inf) -- no risk cap of any kind. The
            counterfactual `research/x2_stop_floor_audit.md` measured before
            the floor became reachable: this is what a close-fill costs with
            nothing under it.

All four arms are run together in ONE pass over the archive: each day's bars
are fetched and RTH-parsed once (the expensive part), and `simulate_day` is
replayed four times per day/symbol with `backtest_week`'s stop-globals
swapped between arms. r100 is NOT loaded from `research/bt2y_trades.json`
(T0's committed AFTER book) even though its config matches the shipped
default: this working tree's `data_archive` tops out at 2026-08-10 for most
symbols (git-tracked, `git ls-files` confirmed), while that book's meta says
`last: 2026-08-21` -- eleven extra days T0's agent had cached locally and
never committed. Loading it would compare three fresh arms against a fourth
run over a DIFFERENT day window, which is not an A/B. Re-running r100 here
costs one more pass and buys back apples-to-apples; the small mean-R gap
against T0's published 0.5481R is archive-window drift, not a disagreement
about the engine.

Held-out recall is NOT re-scored per arm. `signal_runner.SignalRunner
.detect_signals` -- the ONLY thing `research/t4_engine_recall.run_day` and
the regression gate replay -- never reads `DISASTER_STOP` or any stop-fill
function (grep confirms it). The disaster stop is an EXIT rule; it cannot
change which bar the engine enters on, so held-out recall is mechanically
identical across all four arms. This script still runs it once, against the
shipped state, so the report carries a number it actually executed rather
than one merely asserted.

Recovery cost: for every trade in r100 and r125 whose exit price matches its
own disaster-stop price to the cent (`out == "loss"` and
`exit == disaster_stop_price(...)`), the identical trade (matched on
symbol/day/entry-time/setup/direction/entry price) is looked up in the clamp
arm, where no disaster stop exists and the trade rides to its close-triggered
stop or its target on the ORIGINAL numbers. If the clamp arm's outcome is a
win, the disaster stop killed a trade that recovered. This is symmetric: it
is exactly what a resting order underneath a close-only stop is FOR (cutting
losses before they run), so the finding is a cost/benefit pair, not a verdict.

Usage:
  python research/t1_two_stop_model.py [--days 730] [--out research/t1_two_stop_model.json]

Nothing here touches `research/marks/` or any mark file. `research/bt2y_trades.json`
is read, never written.
"""
from __future__ import annotations
import argparse, json, math, os, statistics as st, sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf
import backtest_week as bw
from backtest_week import simulate_day, htf_bias_for
from backtest_12mo import hourly_from_1m, qqq_level_breaks
from universe import ALL_SYMS, has_archive
from stop_rule import stop_fill_price as _orig_fill, disaster_stop_price

def archive_days(sym):
    d = ROOT / "data_archive" / sym
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []


def daily_ohlc_close(sym):
    out = {}
    for d in archive_days(sym):
        try:
            rth = pf.rth(pf.fetch_day(sym, d))
        except Exception:
            continue
        if len(rth) < 30:
            continue
        out[d] = rth[-1].close
    return out


def spy_trend_ctx():
    """day -> 'bull'/'bear', the only piece of ctx t1 needs (dret slicing)."""
    closes = daily_ohlc_close("SPY")
    keys = sorted(closes)
    vals = [closes[k] for k in keys]
    ctx = {}
    for i, k in enumerate(keys):
        sma = st.fmean(vals[max(0, i - 19):i + 1])
        ctx[k] = "bull" if vals[i] >= sma else "bear"
    return ctx


# ---------------------------------------------------------------------------
# Arm configuration: what to set on `bw` before calling simulate_day, and how
# to reset it after. `stop_fill_price` is monkeypatched only for `nofloor`
# (its default `floor_r` is bound at def time, so a module-global reassignment
# on `stop_rule.MAX_LOSS_R` would not reach it -- `bw.stop_fill_price` is the
# name `_stop_fill_px` actually looks up at call time).
# ---------------------------------------------------------------------------
def _nofloor_fill(close, entry, risk, long):
    return _orig_fill(close, entry, risk, long, floor_r=float("inf"))


ARMS = {
    "clamp":   dict(disaster=False, r=1.0,  fill=_orig_fill),
    "r100":    dict(disaster=True,  r=1.0,  fill=_orig_fill),
    "r125":    dict(disaster=True,  r=1.25, fill=_orig_fill),
    "nofloor": dict(disaster=False, r=1.0,  fill=_nofloor_fill),
}


def _set_arm(name):
    cfg = ARMS[name]
    bw.DISASTER_STOP = cfg["disaster"]
    bw.DISASTER_R = cfg["r"]
    bw.stop_fill_price = cfg["fill"]


def _row(sym, cls, d, ym, dow, t, dret_bucket):
    key = (sym, d, t.entry_time[:5], t.signal_type, t.direction,
          round(t.entry, 4))
    exit_via = "n/a"
    if t.outcome == "loss":
        risk = abs(t.entry - t.stop)
        if risk > 0:
            dpx = disaster_stop_price(t.entry, risk, t.direction == "call",
                                      bw.DISASTER_R)
            if bw.DISASTER_STOP and abs(t.exit_price - dpx) < 5e-3:
                exit_via = "disaster"
            else:
                exit_via = "level"
    elif t.outcome == "win":
        exit_via = "target"
    elif t.outcome == "scratch":
        exit_via = "scratch"
    return {
        "key": key, "sym": sym, "cls": cls, "day": d, "ym": ym, "dow": dow,
        "et": t.entry_time[:5], "setup": t.signal_type, "dir": t.direction,
        "grade": t.grade, "traded": bool(t.counted), "out": t.outcome,
        "r": round(t.pnl / bw.RISK_DOLLARS, 4), "exit_via": exit_via,
        "level": ("PMH" if "PMH" in t.reason else "PML" if "PML" in t.reason
                  else "PDH" if "PDH" in t.reason else "PDL" if "PDL" in t.reason
                  else "other"),
        "dret": dret_bucket,
    }


def run(days):
    from universe import INDEX_POOL
    ETFS = set(INDEX_POOL)
    syms = [s for s in ALL_SYMS if has_archive(s, 100)]
    last = max((archive_days(s) or ["1970-01-01"])[-1] for s in syms)
    start = (date.fromisoformat(last) - timedelta(days=days)).isoformat()
    window = sorted({d for s in syms for d in archive_days(s) if d >= start})
    print("%d symbols, %d sessions %s..%s" % (len(syms), len(window),
                                              window[0], window[-1]))

    spy_ctx = spy_trend_ctx()
    qqq_brk = qqq_level_breaks(window)

    rows = {name: [] for name in ARMS}
    sessions = set()

    for sym in syms:
        days_list = [d for d in archive_days(sym) if d >= start]
        day_bars = {}
        hourly = []
        for d in days_list:
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

        prev = None
        n0 = {name: len(rows[name]) for name in ARMS}
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
            sessions.add(d)
            cls = "etf" if sym in ETFS else "stock"
            ym, dow = d[:7], date.fromisoformat(d).strftime("%a")
            dret_bucket = spy_ctx.get(d, "n/a")

            for name in ARMS:
                _set_arm(name)
                trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml,
                                      pdo, pdc, qqq=qqq_brk.get(d))
                for t in trades:
                    if not t.counted:
                        continue
                    rows[name].append(_row(sym, cls, d, ym, dow, t, dret_bucket))
            prev = d
        print("[%s] %d sessions -> " % (sym, len(day_bars))
              + ", ".join("%s=%d" % (n, len(rows[n]) - n0[n]) for n in ARMS))

    _set_arm("clamp")  # leave bw in a known state
    return rows, sorted(sessions)


def stats(tr):
    if not tr:
        return None
    rs = [r["r"] for r in tr]
    wins = [r for r in tr if r["out"] == "win"]
    losses = [r for r in tr if r["out"] == "loss"]
    decided = len(wins) + len(losses)
    by_month = defaultdict(float)
    for r in tr:
        by_month[r["ym"]] += r["r"]
    green = sum(1 for v in by_month.values() if v > 0)
    gross_w = sum(r["r"] for r in tr if r["r"] > 0)
    gross_l = -sum(r["r"] for r in tr if r["r"] < 0)
    order = sorted(tr, key=lambda r: (r["day"], r["et"]))
    peak = cum = dd = 0.0
    for r in order:
        cum += r["r"]
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    sd = st.pstdev(rs) if len(rs) > 1 else 0.0
    return {
        "traded": len(tr), "mean_r": st.fmean(rs), "sd_r": sd,
        "se_r": sd / math.sqrt(len(rs)) if rs else 0.0,
        "total_r": sum(rs), "win_rate": (len(wins) / decided * 100) if decided else 0.0,
        "wins": len(wins), "losses": len(losses),
        "scratches": len(tr) - decided,
        "months": len(by_month), "months_green": green,
        "pf": (gross_w / gross_l) if gross_l else 0.0,
        "max_dd_r": dd, "worst_r": min(rs), "best_r": max(rs),
        "exit_via": {k: sum(1 for r in tr if r["exit_via"] == k)
                    for k in ("disaster", "level", "target", "scratch")},
    }


def recovery_cost(disaster_arm_rows, clamp_rows, label):
    """Of the trades this arm's disaster stop killed, how many would have
    recovered to a win under the clamp-only book (same trade, no disaster
    order)?"""
    clamp_by_key = {}
    dupe_keys = set()
    for r in clamp_rows:
        if r["key"] in clamp_by_key:
            dupe_keys.add(r["key"])
        clamp_by_key[r["key"]] = r

    killed = [r for r in disaster_arm_rows if r["exit_via"] == "disaster"]
    matched, would_have_won, would_have_lost, would_have_scratched, unmatched = (
        0, 0, 0, 0, 0)
    recovered_r_gain = []
    for r in killed:
        k = r["key"]
        if k in dupe_keys or k not in clamp_by_key:
            unmatched += 1
            continue
        c = clamp_by_key[k]
        matched += 1
        if c["out"] == "win":
            would_have_won += 1
            recovered_r_gain.append(c["r"] - r["r"])
        elif c["out"] == "loss":
            would_have_lost += 1
        else:
            would_have_scratched += 1

    return {
        "arm": label,
        "disaster_exits": len(killed),
        "matched_to_clamp": matched,
        "unmatched_or_duplicate_key": unmatched,
        "would_have_won_under_clamp": would_have_won,
        "would_have_lost_under_clamp": would_have_lost,
        "would_have_scratched_under_clamp": would_have_scratched,
        "recovery_rate_pct": (round(would_have_won / matched * 100, 1)
                              if matched else 0.0),
        "mean_r_given_up_on_recovered_trades": (
            round(st.fmean(recovered_r_gain), 4) if recovered_r_gain else 0.0),
        "total_r_given_up": round(sum(recovered_r_gain), 2),
    }


def heldout_recall():
    sys.path.insert(0, str(ROOT / "research"))
    from research.t4_engine_recall import run_day  # noqa: E402
    import json as _json

    def rows(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield _json.loads(line)

    SWEEP = ROOT / "research" / "marks" / "probe_s_sweep_2026-08-28.jsonl"
    cards = [r for r in rows(SWEEP) if r["answers"].get("s")]
    his_s = [r for r in cards if r["answers"]["s"] == ["s"]]
    his_no = [r for r in cards if r["answers"]["s"] != ["s"]]

    def fired(sym, day):
        try:
            entries, _sigs, _raw = run_day(sym, day)
        except Exception:
            return False
        return bool(entries)

    tp = sum(1 for r in his_s if fired(r["symbol"], r["date"]))
    fp = sum(1 for r in his_no if fired(r["symbol"], r["date"]))
    return {
        "n_S": len(his_s), "fired_on_S": tp,
        "recall_pct": round(tp / len(his_s) * 100, 1) if his_s else 0.0,
        "n_no": len(his_no), "fired_on_no": fp,
        "precision_pct": round(tp / (tp + fp) * 100, 1) if (tp + fp) else 0.0,
        "note": "detect_signals() never reads DISASTER_STOP/stop_fill_price "
                "(grep-confirmed) -- identical across all four T1 arms by "
                "construction; scored once against the shipped state.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--out", default=str(ROOT / "research" / "t1_two_stop_model.json"))
    ap.add_argument("--skip-recall", action="store_true",
                    help="dev flag: skip the (slow, but invariant) held-out replay")
    a = ap.parse_args()

    rows, sessions = run(a.days)

    arm_stats = {name: stats(rows[name]) for name in ARMS}

    recov = [
        recovery_cost(rows["r100"], rows["clamp"], "r100 (-1R, shipped default)"),
        recovery_cost(rows["r125"], rows["clamp"], "r125 (-1.25R)"),
    ]

    recall = {} if a.skip_recall else heldout_recall()

    out = {
        "meta": {
            "sessions": len(sessions), "days_arg": a.days,
            "first": sessions[0] if sessions else None,
            "last": sessions[-1] if sessions else None,
        },
        "arms": arm_stats,
        "recovery_cost": recov,
        "heldout_recall": recall,
    }
    print(json.dumps({k: v for k, v in out.items() if k != "arms"} |
                     {"arms": {k: (v and {kk: vv for kk, vv in v.items()
                                          if kk != "exit_via"} | {"exit_via": v["exit_via"]})
                              for k, v in arm_stats.items()}}, indent=2))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("wrote " + a.out)


if __name__ == "__main__":
    main()
