"""Adversarial recompute of research/g83_futures_arm.json.

Written to REFUTE, not to agree. Nothing here imports g83_futures_arm.py or
g80_options_honest.py -- the bar loader, the RTH filter, the flat-2R
simulation, the stop trigger/fill and the futures contract arithmetic are all
re-typed from the rules in CLAUDE.md and stop_rule.py's docstring, so a bug
shared by those two files cannot hide in this one.

Checks, in order:

  1. index-eligible day count on the CURRENT book (the claim: 230 / 500),
     plus the narrower "global first trade of the day happened to be an index
     name" reading (the claim: 31 / 500).
  2. bar alignment -- does data_archive[sym][day][entry_i] actually carry the
     minute stamped in row["et"]? If entry_i pointed one bar late, "the close
     of the signal minute" would be a bar the decision could not have seen.
     This is the look-ahead check.
  3. the futures dollars-a-day headline ($54.64/day), months green (13/25),
     win rate (40.4%) and distance to Austin's $397/day bar ($342.36 short).
  4. the same-230-trades shares column ($58.17/day).
  5. contract-spec self-consistency: multiplier * tick_size == tick_value.

Run: python research/g83_verify_2.py
Reads only. Opens no mark file. Makes no network call -- every bar comes from
data_archive/ CSVs already on disk.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "research" / "bt2y_trades.json"
ARCHIVE = ROOT / "data_archive"
CLAIM = ROOT / "research" / "g83_futures_arm.json"

SESSIONS = 500
RISK_DOLLARS = 1000.0
FLOOR_R = 1.25
DAILY_BAR = 397.0
INDEX_POOL = {"SPY", "QQQ", "IWM"}

FUT = {
    "SPY": ("MES", 5.0, 0.25, 1.25, 10.0),
    "QQQ": ("MNQ", 2.0, 0.25, 0.50, 41.09),
    "IWM": ("M2K", 5.0, 0.10, 0.50, 9.91),
}


# ------------------------------------------------------------------- bars

_cache: dict = {}


def rth_bars(sym, day):
    """RTH 1-minute bars straight off the archive CSV. Own parser, own filter."""
    key = (sym, day)
    if key in _cache:
        return _cache[key]
    p = ARCHIVE / sym / f"{day}.csv"
    out = []
    if p.is_file():
        with open(p, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                hhmm = r["Datetime"][11:19]
                if "09:30:00" <= hhmm < "16:00:00":
                    out.append({
                        "t": r["Datetime"][11:16],
                        "o": float(r["Open"]), "h": float(r["High"]),
                        "l": float(r["Low"]), "c": float(r["Close"]),
                    })
    if len(_cache) > 200:
        _cache.clear()
    _cache[key] = out
    return out


# ------------------------------------------------------------ the flat 2R

def simulate(entry, stop, long, b, i):
    """Stop triggers on the CLOSE, fills at that close, floored at -1.25R.
    Target is a resting limit and fills on TOUCH. Management starts at i+1."""
    risk = (entry - stop) if long else (stop - entry)
    if risk <= 0.005:
        return None
    target = entry + 2.0 * risk if long else entry - 2.0 * risk
    for j in range(i + 1, len(b)):
        c = b[j]
        triggered = c["c"] <= stop if long else c["c"] >= stop
        if triggered:
            fill = c["c"]
            if long:
                fill = max(fill, entry - FLOOR_R * risk)
                r = (fill - entry) / risk
            else:
                fill = min(fill, entry + FLOOR_R * risk)
                r = (entry - fill) / risk
            return round(r, 4)
        if (long and c["h"] >= target) or ((not long) and c["l"] <= target):
            return 2.0
    if len(b) <= i + 1:
        return None
    last = b[-1]["c"]
    r = (last - entry) / risk if long else (entry - last) / risk
    return round(max(r, -FLOOR_R), 4)


def futures_pnl(r, sym, entry, stop):
    _c, mult, tick_size, tick_value, ratio = FUT[sym]
    index_points = ratio * abs(entry - stop)
    ticks = max(1, round(index_points / tick_size))
    risk_per_contract = ticks * tick_value
    contracts = math.floor(RISK_DOLLARS / risk_per_contract)
    if contracts <= 0:
        return None, ticks, 0
    realised = contracts * risk_per_contract
    return r * realised, ticks, contracts


# ---------------------------------------------------------------- the book

def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    rows = book["trades"]
    meta = book["meta"]
    traded = [r for r in rows if r.get("traded")]
    all_days = sorted({r["day"] for r in rows})

    print(f"book: {len(rows)} signals, {len(traded)} traded rows "
          f"(meta.traded={meta.get('traded')}), {len(all_days)} sessions")

    # --- 1. day counts -----------------------------------------------------
    idx_by_day = {}
    for r in traded:
        if r["sym"] in INDEX_POOL:
            idx_by_day.setdefault(r["day"], []).append(r)
    index_days = len(idx_by_day)

    glob_by_day = {}
    for r in traded:
        glob_by_day.setdefault(r["day"], []).append(r)
    narrow = 0
    for day, rs in glob_by_day.items():
        first = sorted(rs, key=lambda x: (x["et"], x["sym"]))[0]
        if first["sym"] in INDEX_POOL:
            narrow += 1

    print(f"\n[1] index-eligible days (index-only first-of-day): "
          f"{index_days} / {SESSIONS} ({index_days/SESSIONS*100:.1f}%)   claim 230 (46.0%)")
    print(f"    narrow reading (global first-of-day WAS an index name): "
          f"{narrow} / {SESSIONS}   claim 31")

    picked = []
    for day, rs in idx_by_day.items():
        picked.append(sorted(rs, key=lambda x: (x["et"], x["sym"]))[0])
    picked.sort(key=lambda x: x["day"])

    # --- 2. look-ahead: does entry_i carry the signal minute? --------------
    mismatch, missing, checked = [], 0, 0
    for row in picked:
        b = rth_bars(row["sym"], row["day"])
        if not b:
            missing += 1
            continue
        i = row["entry_i"]
        if i >= len(b):
            mismatch.append((row["day"], row["sym"], row["et"], "index past end"))
            continue
        checked += 1
        if b[i]["t"] != row["et"]:
            mismatch.append((row["day"], row["sym"], row["et"], b[i]["t"]))
    print(f"\n[2] bar alignment: {checked} rows checked, {missing} with no bars, "
          f"{len(mismatch)} where bars[entry_i] is NOT the minute in row['et']")
    for m in mismatch[:8]:
        print(f"    MISALIGNED {m}")

    # --- 3/4. the money ----------------------------------------------------
    fut, sha, skipped = [], [], 0
    for row in picked:
        b = rth_bars(row["sym"], row["day"])
        if not b or row["entry_i"] >= len(b) - 1:
            skipped += 1
            continue
        i = row["entry_i"]
        entry = b[i]["c"]                      # market at the close of the signal minute
        long = row["dir"] == "call"
        r = simulate(entry, row["stop"], long, b, i)
        if r is None:
            skipped += 1
            continue
        pnl, ticks, contracts = futures_pnl(r, row["sym"], entry, row["stop"])
        if pnl is None:
            skipped += 1
            continue
        fut.append({"day": row["day"], "sym": row["sym"], "d": pnl})
        sha.append({"day": row["day"], "sym": row["sym"], "d": r * RISK_DOLLARS})

    def block(rs, label, claim_day, claim_green, claim_win):
        vals = [x["d"] for x in rs]
        total = sum(vals)
        per_day = total / SESSIONS
        wins = sum(1 for v in vals if v > 0)
        losses = sum(1 for v in vals if v < 0)
        by_m = {}
        for x in rs:
            by_m[x["day"][:7]] = by_m.get(x["day"][:7], 0.0) + x["d"]
        green = sum(1 for v in by_m.values() if v > 0)
        win = wins / (wins + losses) * 100 if wins + losses else 0.0
        print(f"\n[{label}] trades={len(rs)}  win%={win:.1f} (claim {claim_win})  "
              f"$/day={per_day:.2f} (claim {claim_day})  total=${total:,.0f}")
        print(f"    months green {green}/{len(by_m)} (claim {claim_green})   "
              f"short of $397/day by ${DAILY_BAR - per_day:.2f} "
              f"= {per_day/DAILY_BAR*100:.1f}% of the bar")
        return per_day, green, win

    print(f"\n    {skipped} picked rows dropped (no bars / unsizeable)")
    f_day, f_green, f_win = block(fut, "3 futures", 54.64, 13, 40.4)
    s_day, s_green, s_win = block(sha, "4 shares, same 230 trades", 58.17, 13, 40.4)

    # --- 5. contract specs -------------------------------------------------
    print("\n[5] contract specs")
    for sym, (c, mult, ts, tv, ratio) in FUT.items():
        ok = abs(mult * ts - tv) < 1e-9
        print(f"    {c} ({sym}): {mult} x {ts} = {mult*ts} vs stated tick value {tv} "
              f"-> {'ok' if ok else 'INCONSISTENT'}   ETF:index ratio {ratio}")

    # --- verdict -----------------------------------------------------------
    claim = json.load(open(CLAIM, encoding="utf-8"))
    cs = claim["summary"]
    print("\n=== deltas vs research/g83_futures_arm.json ===")
    print(f"    index days   mine {index_days}      theirs "
          f"{claim['day_count']['index_eligible_days_current_book']}")
    print(f"    futures $/d  mine {f_day:.2f}  theirs {cs['futures']['per_day']}")
    print(f"    shares  $/d  mine {s_day:.2f}  theirs {cs['shares_index_only']['per_day']}")
    print(f"    fut green    mine {f_green}      theirs {cs['futures']['months_green']}")
    print(f"    fut win%     mine {f_win:.1f}   theirs {cs['futures']['win_pct']}")
    print(f"    misaligned entry bars: {len(mismatch)}")


if __name__ == "__main__":
    main()
