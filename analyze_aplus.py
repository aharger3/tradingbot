"""Measure each mastermind A+ filter on the 12mo backtest before wiring it in.

Reads backtest_charts_12mo.json (377 signal records w/ candles).
Outputs: MFE-then-loss stats, BE-after-structure sim, hammer-entry split,
QQQ-alignment split. ponytail: measurement only, no production changes.
"""
import csv
import json
from pathlib import Path

RECS = [r for r in json.load(open("backtest_charts_12mo.json"))
        if not r["alert_only"]]
print(f"{len(RECS)} traded signals")


def r_mult(rec, price):
    risk = abs(rec["entry"] - rec["stop"])
    if risk == 0:
        return 0.0
    sign = 1 if rec["direction"] == "call" else -1
    return sign * (price - rec["entry"]) / risk


def mfe(rec):
    """Max favorable excursion in R after entry, before exit bar."""
    cs = rec["candles"][rec["entry_i"]:rec["exit_i"] + 1]
    if rec["direction"] == "call":
        return max(r_mult(rec, c["h"]) for c in cs)
    return max(r_mult(rec, c["l"]) for c in cs)


# ---- 1. Austin's pain: how many LOSSES got close to 2R first? ----
losses = [r for r in RECS if r["outcome"] == "loss"]
wins = [r for r in RECS if r["outcome"] == "win"]
print(f"\nwins {len(wins)}  losses {len(losses)}")
for thresh in (1.0, 1.25, 1.5, 1.75):
    n = sum(1 for r in losses if mfe(r) >= thresh)
    print(f"losses that first reached >= {thresh}R: {n} ({n/len(losses):.0%})")

# ---- 2. BE-after-favorable-structure sim (proxy: BE armed once MFE >= X) ----
# Bar-by-bar: after price reaches armR, stop moves to entry. Win still = target.
def sim_be(rec, arm_r):
    risk = abs(rec["entry"] - rec["stop"])
    long = rec["direction"] == "call"
    armed = False
    # entry is at the entry bar's CLOSE — its wick predates the entry
    for c in rec["candles"][rec["entry_i"] + 1:]:
        hi_r = r_mult(rec, c["h"] if long else c["l"])
        lo = c["l"] if long else c["h"]
        # stop check first (conservative, same as backtester)
        if not armed and ((long and c["l"] <= rec["stop"]) or
                          (not long and c["h"] >= rec["stop"])):
            return -1.0
        if armed and ((long and c["l"] <= rec["entry"]) or
                      (not long and c["h"] >= rec["entry"])):
            return 0.0
        if (long and c["h"] >= rec["target"]) or (not long and c["l"] <= rec["target"]):
            return 2.0
        if hi_r >= arm_r:
            armed = True
    return r_mult(rec, rec["candles"][-1]["c"])  # EOD scratch


print("\nBE-stop-once-structure-favorable sim ($1k risk):")
base = sum({"win": 2000, "loss": -1000}.get(r["outcome"],
           r["pnl"]) for r in RECS)
print(f"  blind 2R baseline: ${base:,.0f}")
for arm in (1.0, 1.25, 1.5):
    tot = sum(sim_be(r, arm) * 1000 for r in RECS)
    green = sum(1 for r in RECS if sim_be(r, arm) > 0)
    print(f"  BE armed at {arm}R: ${tot:,.0f}  ({green/len(RECS):.0%} trades end green)")

# ---- 3. Hammer entry candle split ----
def is_confirm_candle(rec):
    c = rec["candles"][rec["entry_i"]]
    body = abs(c["c"] - c["o"])
    rng = c["h"] - c["l"]
    if rng == 0:
        return False
    if rec["direction"] == "call":   # hammer: lower wick >= body, closes upper half
        lower = min(c["o"], c["c"]) - c["l"]
        return lower >= body and c["c"] >= c["l"] + 0.5 * rng
    upper = c["h"] - max(c["o"], c["c"])  # inverted hammer / shooting star
    return upper >= body and c["c"] <= c["h"] - 0.5 * rng


def split(name, pred):
    a = [r for r in RECS if pred(r)]
    b = [r for r in RECS if not pred(r)]
    for label, grp in ((f"{name}=YES", a), (f"{name}=no ", b)):
        if not grp:
            continue
        w = sum(1 for r in grp if r["outcome"] == "win")
        pnl = sum({"win": 2000, "loss": -1000}.get(r["outcome"], r["pnl"]) for r in grp)
        print(f"  {label}: {len(grp)} tr, {w/len(grp):.1%} win, ${pnl:,.0f}")


print("\nHammer/inv-hammer entry candle:")
split("hammer", is_confirm_candle)

# ---- 4. QQQ alignment: QQQ broke its OR in signal direction by entry time ----
QDIR = Path("data_archive/QQQ")
_qqq_cache = {}


def qqq_bars(day):
    if day not in _qqq_cache:
        f = QDIR / f"{day}.csv"
        rows = []
        if f.exists():
            for row in csv.DictReader(open(f)):
                t = row["Datetime"][11:19]
                rows.append((t, float(row["High"]), float(row["Low"]),
                             float(row["Close"])))
        _qqq_cache[day] = rows
    return _qqq_cache[day]


def qqq_aligned(rec):
    bars = qqq_bars(rec["day"])
    if not bars:
        return None
    entry_t = rec["candles"][rec["entry_i"]]["t"]
    orb = [b for b in bars if "09:30:00" <= b[0] < "09:35:00"]
    if not orb:
        return None
    orh, orl = max(b[1] for b in orb), min(b[2] for b in orb)
    pre = [b for b in bars if b[0] <= entry_t]
    if rec["direction"] == "call":
        return any(b[3] > orh for b in pre)
    return any(b[3] < orl for b in pre)


have = [r for r in RECS if qqq_aligned(r) is not None]
print(f"\nQQQ OR-break alignment (data for {len(have)}/{len(RECS)}):")
split("qqq_aligned", lambda r: qqq_aligned(r) is True)


# ---- 5. Combined tier: hammer + S>=4, max 2/day, stop when green ----
import re
from collections import defaultdict


def s_score(rec):
    m = re.search(r" S(\d+)", rec["reason"])  # S can reach 10 with F4 qqq +1
    return int(m.group(1)) if m else None


def day_sim(min_s, need_hammer, max_n=2, stop_green=True):
    byday = defaultdict(list)
    for r in RECS:
        byday[r["day"]].append(r)
    tot = w = n = 0
    for day, rs in byday.items():
        rs.sort(key=lambda r: r["candles"][r["entry_i"]]["t"])
        taken = pnl_day = 0
        for r in rs:
            if taken >= max_n or (stop_green and pnl_day > 0):
                break
            s = s_score(r)
            if s is None or s < min_s:
                continue
            if need_hammer and not is_confirm_candle(r):
                continue
            p = {"win": 2000, "loss": -1000}.get(r["outcome"], r["pnl"])
            taken += 1; n += 1; pnl_day += p; tot += p
            w += r["outcome"] == "win"
    if n:
        print(f"  S>={min_s} hammer={need_hammer}: {n} tr, {w/n:.1%} win, "
              f"${tot:,.0f}/yr (${tot/12:,.0f}/mo)")


print("\nCombined discipline tier (max 2/day, stop when green):")
for ms in (0, 2, 4):
    for h in (False, True):
        day_sim(ms, h)

# ---- 6. Audit-tag splits (2026-07-11: [vwap±] [chase] [pdwick], 84% [hammer]) ----
print("\nAudit tag splits (B&R traded only):")
bnr = [r for r in RECS if r["setup"] == "break_and_retest"]


def tag_split(name, tag, grp=bnr):
    a = [r for r in grp if tag in r["reason"]]
    b = [r for r in grp if tag not in r["reason"]]
    for label, g in ((f"{name}=YES", a), (f"{name}=no ", b)):
        if not g:
            continue
        w = sum(1 for r in g if r["outcome"] == "win")
        pnl = sum({"win": 2000, "loss": -1000}.get(r["outcome"], r["pnl"]) for r in g)
        print(f"  {label}: {len(g)} tr, {w/len(g):.1%} win, ${pnl:,.0f}")


tag_split("vwap_aligned", "[vwap+]")
tag_split("chase", "[chase]")
tag_split("pdwick", "[pdwick]")
r84 = [r for r in RECS if r["setup"] == "reentry_84_rule"]
if r84:
    print(f"\n84% re-entries ({len(r84)}):")
    tag_split("hammer", "[hammer]", r84)


# ---- 7. Take-tier under tag filters (S>=4 + hammer, max 2/day, stop green) ----
def day_sim_pred(label, pred, min_s=4, max_n=2):
    byday = defaultdict(list)
    for r in RECS:
        byday[r["day"]].append(r)
    tot = w = n = 0
    for day, rs in byday.items():
        rs.sort(key=lambda r: r["candles"][r["entry_i"]]["t"])
        taken = pnl_day = 0
        for r in rs:
            if taken >= max_n or pnl_day > 0:
                break
            s = s_score(r)
            if s is None or s < min_s or not is_confirm_candle(r) or not pred(r):
                continue
            p = {"win": 2000, "loss": -1000}.get(r["outcome"], r["pnl"])
            taken += 1; n += 1; pnl_day += p; tot += p
            w += r["outcome"] == "win"
    if n:
        print(f"  {label}: {n} tr, {w/n:.1%} win, ${tot:,.0f}/yr (${tot/12:,.0f}/mo)")


print("\nTake-tier (S>=4 + hammer, max 2/day, stop green) under audit filters:")
day_sim_pred("baseline (no extra filter)", lambda r: True)
day_sim_pred("+ exclude [chase]", lambda r: "[chase]" not in r["reason"])
day_sim_pred("+ exclude [pdwick]", lambda r: "[pdwick]" not in r["reason"])
day_sim_pred("+ require [vwap+]", lambda r: "[vwap+]" in r["reason"])
day_sim_pred("+ all three", lambda r: "[chase]" not in r["reason"]
             and "[pdwick]" not in r["reason"] and "[vwap+]" in r["reason"])
