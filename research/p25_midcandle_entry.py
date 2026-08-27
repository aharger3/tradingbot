"""P25 — how many of Austin's own entries are mid-candle, and what does waiting
for the close cost?

Austin, 2026-08-27: "im concerned with a lot of my entries all target HOD/LOD and
getting entries on the middle of candles not at candle close. im sure the
percentage on that is high."

This measures it instead of guessing. For every human-marked entry that carries a
bar index and a price, it asks three questions of the entry bar:

  1. Did he enter AT the close, or inside the bar?  (`entry_p` vs `bar.close`)
  2. Where inside the bar?                          (position in the bar's range)
  3. What does waiting for the close cost, in R?    (close-vs-entry over his stop)

Question 3 is the one that matters. The backtest fills at the close of the entry
bar. If Austin's real fills are systematically better than that close, every R
number in the book is understated -- or, if worse, overstated. Either way the
backtest is not modelling the thing he does.

Run:
    python research/p25_midcandle_entry.py            # table to stdout
    python research/p25_midcandle_entry.py --json OUT # machine-readable

Reads every mark corpus in MARK_FILES. Rows without entry_i/entry_p are counted
as "no entry recorded" and otherwise ignored -- an X-grade day has no entry by
definition, that is not missing data.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from research.t4_engine_recall import rth_candles

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every corpus that could hold a human entry mark. Same spirit as
# build_deck.LEGACY_MARK_FILES: if you add a corpus, add it here too.
MARK_FILES = [
    "research/marks/probe_omen_test1_2026-08-27.jsonl",
    "research/marks/probe_master_homework_2026-08-26.jsonl",
    "research/marks/probe_autopsy_2026-08-23.jsonl",
    "research/marks/probe_head2head_2026-08-24.jsonl",
    "research/marks/deck_marks_index_2026-08-19.jsonl",
    "research/marks/deck_marks_tsla_2026-08-20.jsonl",
    "research/austin_marks_v7.jsonl",
    "research/blind_marks_all.jsonl",
]

# A price typed into the stop box that is really a timestamp or a note. Austin
# typed "931" meaning the 9:31 wick, "957" meaning 9:57, "20" meaning 20 cents.
# These are notes, not stops -- they poison R math and must not be repaired by
# guessing. Rule: a stop more than 50% away from entry is not a stop.
STOP_SANITY_FRAC = 0.5


def iter_marks():
    """Yield every mark row that carries a usable human entry."""
    for rel in MARK_FILES:
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                row["_src"] = rel
                yield row


def usable(row):
    """Does this row carry a human entry we can locate on a bar?"""
    return (
        row.get("symbol")
        and row.get("date")
        and isinstance(row.get("entry_i"), int)
        and isinstance(row.get("entry_p"), (int, float))
        and row.get("entry_p") > 0
    )


def clean_stop(row):
    """His stop, or None if the field holds a note rather than a price."""
    stop = row.get("stop_p")
    entry = row.get("entry_p")
    if not isinstance(stop, (int, float)) or stop <= 0:
        return None
    if abs(stop - entry) > STOP_SANITY_FRAC * entry:
        return None
    return float(stop)


def measure(row, bars):
    """One entry, measured against its own bar. Returns None if unlocatable."""
    i = row["entry_i"]
    if i < 0 or i >= len(bars):
        return None
    bar = bars[i]
    entry = float(row["entry_p"])
    rng = bar.high - bar.low
    if rng <= 0:
        return None
    # Entry must actually be inside the bar it claims. If it is not, the index
    # and the price disagree and the row is not measurable -- do not clamp it.
    if not (bar.low - 1e-9 <= entry <= bar.high + 1e-9):
        return None

    side = (row.get("side") or "L").upper()
    long_side = side.startswith("L")

    # Position in the bar, oriented so 0.0 = the favourable extreme for his
    # direction (a long wants the low) and 1.0 = the adverse extreme.
    pos = (entry - bar.low) / rng if long_side else (bar.high - entry) / rng

    # What waiting for the close would have done to the fill. Positive = the
    # close is WORSE than what he got, i.e. entering mid-candle paid.
    slip = (bar.close - entry) if long_side else (entry - bar.close)

    stop = clean_stop(row)
    risk = abs(entry - stop) if stop is not None else None
    slip_r = (slip / risk) if risk else None

    # Is the entry bar's close sitting at the session extreme so far? That is
    # the "RR is shot by the close" complaint, stated as a measurement.
    hi = max(b.high for b in bars[: i + 1])
    lo = min(b.low for b in bars[: i + 1])
    day_rng = hi - lo
    if long_side:
        close_to_ext = (hi - bar.close) / day_rng if day_rng > 0 else None
    else:
        close_to_ext = (bar.close - lo) / day_rng if day_rng > 0 else None

    at_close = abs(entry - bar.close) < 0.005  # half a cent

    return {
        "symbol": row["symbol"],
        "date": row["date"],
        "src": row["_src"],
        "grade": row.get("grade_std") or row.get("grade"),
        "setup": row.get("setup"),
        "side": "L" if long_side else "S",
        "entry_i": i,
        "entry_t": row.get("entry_t"),
        "entry_p": entry,
        "bar_o": bar.open, "bar_h": bar.high,
        "bar_l": bar.low, "bar_c": bar.close,
        "bar_range": rng,
        "pos_in_bar": pos,
        "at_close": at_close,
        "slip_px": slip,
        "risk_px": risk,
        "slip_r": slip_r,
        "close_to_extreme_frac": close_to_ext,
    }


def pct(n, d):
    return (100.0 * n / d) if d else 0.0


def summarise(rows, label):
    if not rows:
        return {"label": label, "n": 0}
    at_close = [r for r in rows if r["at_close"]]
    mid = [r for r in rows if not r["at_close"]]
    slips = [r["slip_r"] for r in rows if r["slip_r"] is not None]
    positive = [s for s in slips if s > 0]
    return {
        "label": label,
        "n": len(rows),
        "at_close_n": len(at_close),
        "at_close_pct": pct(len(at_close), len(rows)),
        "mid_candle_n": len(mid),
        "mid_candle_pct": pct(len(mid), len(rows)),
        "pos_in_bar_median": statistics.median(r["pos_in_bar"] for r in rows),
        "slip_r_n": len(slips),
        "slip_r_mean": statistics.mean(slips) if slips else None,
        "slip_r_median": statistics.median(slips) if slips else None,
        "slip_r_positive_pct": pct(len(positive), len(slips)) if slips else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the full per-entry table here")
    args = ap.parse_args()

    seen = set()
    rows, no_entry, unlocatable, no_bars = [], 0, 0, 0
    bar_cache = {}

    for row in iter_marks():
        if not usable(row):
            no_entry += 1
            continue
        key = (row["symbol"], row["date"], row["entry_i"], round(float(row["entry_p"]), 4))
        if key in seen:
            continue
        seen.add(key)

        ck = (row["symbol"], row["date"])
        if ck not in bar_cache:
            try:
                bar_cache[ck] = rth_candles(row["symbol"], row["date"])
            except Exception:
                bar_cache[ck] = None
        bars = bar_cache[ck]
        if not bars:
            no_bars += 1
            continue

        m = measure(row, bars)
        if m is None:
            unlocatable += 1
            continue
        rows.append(m)

    print(f"marks with no human entry recorded : {no_entry}")
    print(f"entries with no bars in archive    : {no_bars}")
    print(f"entries the bar could not hold     : {unlocatable}")
    print(f"entries measured                   : {len(rows)}")
    print()

    if not rows:
        print("nothing measurable")
        return

    groups = [("ALL", rows)]
    for g in ("S", "A", "C"):
        groups.append((f"grade {g}", [r for r in rows if r["grade"] == g]))
    for s in ("BR", "OCR", "BR+OCR"):
        groups.append((f"setup {s}", [r for r in rows if r["setup"] == s]))

    hdr = (f"{'group':<12} {'n':>4} {'at close':>9} {'mid-bar':>9} "
           f"{'pos med':>8} {'slip R mean':>12} {'slip R med':>11} {'slip>0':>8}")
    print(hdr)
    print("-" * len(hdr))
    out_summary = []
    for label, sub in groups:
        s = summarise(sub, label)
        out_summary.append(s)
        if not s["n"]:
            print(f"{label:<12} {0:>4}")
            continue
        sm = "  n/a" if s["slip_r_mean"] is None else f"{s['slip_r_mean']:+.3f}"
        sd = "  n/a" if s["slip_r_median"] is None else f"{s['slip_r_median']:+.3f}"
        sp = "  n/a" if s["slip_r_positive_pct"] is None else f"{s['slip_r_positive_pct']:.0f}%"
        print(f"{label:<12} {s['n']:>4} "
              f"{s['at_close_n']:>3} {s['at_close_pct']:>4.0f}% "
              f"{s['mid_candle_n']:>3} {s['mid_candle_pct']:>4.0f}% "
              f"{s['pos_in_bar_median']:>8.2f} {sm:>12} {sd:>11} {sp:>8}")

    print()
    # How near the session extreme the entry bar CLOSES. 0.0 = the close is
    # exactly at the extreme -- his stated complaint.
    ext = [r["close_to_extreme_frac"] for r in rows
           if r["close_to_extreme_frac"] is not None]
    if ext:
        near = sum(1 for e in ext if e <= 0.10)
        print(f"entry bar closes within 10% of the day's extreme so far: "
              f"{near}/{len(ext)} ({pct(near, len(ext)):.0f}%)")
        print(f"median distance close->extreme (fraction of day range) : "
              f"{statistics.median(ext):.3f}")

    print()
    by_src = Counter(r["src"] for r in rows)
    for src, n in by_src.most_common():
        print(f"  {n:>4}  {src}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"summary": out_summary, "entries": rows}, fh, indent=1)
        print(f"\nwrote {args.json}")


def _selfcheck():
    """The measurement, on a bar we control. Fails loudly if the orientation of
    pos_in_bar or slip flips -- the two things easy to get backwards."""
    class B:
        def __init__(s, o, h, l, c):
            s.open, s.high, s.low, s.close = o, h, l, c

    bars = [B(10, 11, 9, 10.5), B(10.5, 12, 10, 11.8)]
    # LONG entering at 10.4 on bar 1 (range 10..12). Close 11.8 is worse for a
    # long, so slip must be positive and pos_in_bar near the favourable low.
    row = {"symbol": "T", "date": "d", "entry_i": 1, "entry_p": 10.4,
           "stop_p": 9.9, "side": "L", "_src": "x"}
    m = measure(row, bars)
    assert m is not None
    assert abs(m["pos_in_bar"] - 0.2) < 1e-9, m["pos_in_bar"]
    assert m["slip_px"] > 0 and m["slip_r"] > 0, m
    assert not m["at_close"]
    # SHORT entering at 11.9: close 11.8 is BETTER than his fill, so a short
    # that waited would have got a worse price -> slip positive again.
    row_s = dict(row, entry_p=11.9, stop_p=12.1, side="S")
    ms = measure(row_s, bars)
    assert abs(ms["pos_in_bar"] - 0.05) < 1e-9, ms["pos_in_bar"]
    assert ms["slip_px"] > 0, ms
    # Entry at the close is flagged as such.
    assert measure(dict(row, entry_p=11.8), bars)["at_close"]
    # A stop that is really a timestamp is refused, not repaired.
    assert clean_stop({"entry_p": 277.91, "stop_p": 931}) is None
    assert clean_stop({"entry_p": 277.91, "stop_p": 278.10}) == 278.10
    # An entry price outside its own bar is unmeasurable, not clamped.
    assert measure(dict(row, entry_p=99.0), bars) is None
    print("selfcheck ok")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        main()
