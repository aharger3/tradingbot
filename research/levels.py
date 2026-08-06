"""Level-node generator for the Omen target autopsy (omen-3.4, T4).

The trader describes his targets as "usually 2R, HOD/LOD and whole psychological
numbers, as well as longer timeframe levels and pivot structures." This module
reconstructs the level node set visible at a mark's entry bar from the only 1-minute
bar material present in the checkout: `data_archive/<SYMBOL>/<YYYY-MM-DD>.csv`
(Polygon 1m bars, pre-market 04:00 through close). Where a mark's day is outside the
archive window (pre-2024-07 or an un-archived symbol), only the price-derivable nodes
(whole psychological numbers) survive; the classifier is told so via `bar_coverage`.

A "node" is a dict {price, type, weight}. Types mirror the documented exit ladder
(research/exit-management-dossier.md):

    HOD/LOD (always) -> PDH/PDL -> PMH/PML -> psych numbers
                       -> old highs/lows -> floor pivots (pivot structures)

Weights (>=2.0 qualifies a node for the at_level test):
    HOD/LOD            3.0      # the named #1 target
    PDH/PDL/PMH/PML    2.5      # longer-timeframe liquidity
    psych $50 mult     3.0
    psych $10 mult     2.5
    psych $5 mult      2.3
    psych whole $1     2.0      # "whole psychological numbers"
    psych $0.50        1.5      # weaker, reported but does not trigger at_level alone
    floor pivots       2.0      # "pivot structures"
    swing pivots       2.0      # market-structure pivots (old highs/lows)

entry_i semantics (verified against data_archive): it is an index into RTH bars
(09:30 ET start), NOT the full 04:00 CSV. HOD/LOD and ATR are therefore taken over
the RTH window so they line up with the index the trader actually used.
"""

from __future__ import annotations
import csv, os, glob
from collections import defaultdict

TICK = 0.01  # minimum price increment for every instrument in the corpus

ARCHIVE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data_archive")

# ATR fallback: median(risk / ATR_1m) over the 59 archived marks with >=14 RTH bars
# was 0.84, i.e. the trader's stops sit at ~0.84x the 1-minute ATR. Used only when a
# mark has no archived bars at all, so the at_level tolerance still has a data-grounded
# scale instead of collapsing to 2 ticks.
RISK_ATR_RATIO_MEDIAN = 0.84


def _to_min(dtstr: str) -> str:
    return dtstr[11:16]


def load_rth_bars(symbol: str, day: str):
    """Return RTH (>=09:30) 1m bars for symbol/day as list of dicts, or None.

    Bars are dicts {t, o, h, l, c} with float OHLC and 't' as 'HH:MM'.
    """
    p = os.path.join(ARCHIVE, symbol, f"{day}.csv")
    if not os.path.exists(p):
        return None
    rows = []
    with open(p) as f:
        for row in csv.DictReader(f):
            rows.append(row)
    rth = [r for r in rows if _to_min(r["Datetime"]) >= "09:30"]
    if not rth:
        return None
    return [{"t": _to_min(r["Datetime"]), "o": float(r["Open"]), "h": float(r["High"]),
             "l": float(r["Low"]), "c": float(r["Close"])} for r in rth]


def atr_1m(symbol: str, day: str, entry_i: int, n: int = 14):
    """14-bar 1-minute ATR over RTH bars up to and including entry_i. None if no bars."""
    bars = load_rth_bars(symbol, day)
    if not bars:
        return None
    seg = bars[: entry_i + 1]
    if len(seg) < 2:
        return None
    trs = []
    for i in range(1, len(seg)):
        h, l, pc = seg[i]["h"], seg[i]["l"], seg[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    window = trs[-n:]
    return sum(window) / len(window) if window else None


def atr_fallback(entry: float, stop: float) -> float:
    """Data-grounded ATR_1m estimate when no bars exist: risk / 0.84."""
    risk = abs(entry - stop)
    return risk / RISK_ATR_RATIO_MEDIAN if risk > 0 else 0.0


def psych_nodes(price_lo: float, price_hi: float):
    """Whole psychological numbers (and weaker .50/sub-dollar levels) in a window."""
    lo = min(price_lo, price_hi)
    hi = max(price_lo, price_hi)
    span = hi - lo
    pad = max(span, 1.0) * 0.5 + 1.0
    lo, hi = lo - pad, hi + pad
    nodes = []
    # sub-dollar grid only for very low-priced names
    if hi < 5.0:
        step = 0.1
        k = 0
        v = step * (int(lo / step))
        while v <= hi:
            if v >= lo - 1e-9:
                nodes.append({"price": round(v, 4), "type": "psych_sub", "weight": 1.5})
            v = round(v + step, 4); k += 1
            if k > 100000:
                break
        return nodes
    # whole-dollar + half-dollar grid
    start = int(round(lo))
    end = int(round(hi)) + 1
    for dollar in range(start, end):
        if dollar < lo - 1e-9 or dollar > hi + 1e-9:
            continue
        if dollar % 50 == 0:
            w = 3.0
        elif dollar % 10 == 0:
            w = 2.5
        elif dollar % 5 == 0:
            w = 2.3
        else:
            w = 2.0
        nodes.append({"price": float(dollar), "type": "psych", "weight": w})
        # half-dollar companion (weaker)
        half = dollar + 0.5
        if lo - 1e-9 <= half <= hi + 1e-9 and hi < 100.0:
            nodes.append({"price": float(half), "type": "psych_half", "weight": 1.5})
    return nodes


def hod_lod_nodes(bars, entry_i):
    """High/low of the RTH session up to entry_i."""
    seg = bars[: entry_i + 1]
    if not seg:
        return []
    hod = max(b["h"] for b in seg)
    lod = min(b["l"] for b in seg)
    return [{"price": round(hod, 4), "type": "HOD", "weight": 3.0},
            {"price": round(lod, 4), "type": "LOD", "weight": 3.0}]


def _prior_day(symbol: str, day: str):
    files = sorted(glob.glob(os.path.join(ARCHIVE, symbol, "*.csv")))
    names = [os.path.basename(f)[:-4] for f in files]
    if day not in names:
        return None
    i = names.index(day)
    return names[i - 1] if i > 0 else None


def prior_day_nodes(symbol: str, day: str):
    """PDH/PDL plus classic floor pivots from the prior archived trading day."""
    prev = _prior_day(symbol, day)
    if not prev:
        return []
    bars = load_rth_bars(symbol, prev)
    if not bars or len(bars) < 2:
        return []
    pdh = max(b["h"] for b in bars)
    pdl = min(b["l"] for b in bars)
    pc = bars[-1]["c"]
    pp = (pdh + pdl + pc) / 3.0
    r1 = 2 * pp - pdl
    s1 = 2 * pp - pdh
    r2 = pp + (pdh - pdl)
    s2 = pp - (pdh - pdl)
    out = [
        {"price": round(pdh, 4), "type": "PDH", "weight": 2.5},
        {"price": round(pdl, 4), "type": "PDL", "weight": 2.5},
        {"price": round(pp, 4), "type": "pivot_PP", "weight": 2.0},
        {"price": round(r1, 4), "type": "pivot_R1", "weight": 2.0},
        {"price": round(s1, 4), "type": "pivot_S1", "weight": 2.0},
        {"price": round(r2, 4), "type": "pivot_R2", "weight": 2.0},
        {"price": round(s2, 4), "type": "pivot_S2", "weight": 2.0},
    ]
    return out


def prior_month_nodes(symbol: str, day: str):
    """PMH/PML across the prior calendar month archived for the symbol."""
    y, m, _ = (int(x) for x in day.split("-"))
    pm, py = (m - 1, y) if m > 1 else (12, y - 1)
    label = f"{py:04d}-{pm:02d}"
    files = sorted(glob.glob(os.path.join(ARCHIVE, symbol, "*.csv")))
    days = [os.path.basename(f)[:-4] for f in files if os.path.basename(f)[:7] == label]
    if not days:
        return []
    hi, lo = -1e18, 1e18
    for d in days:
        b = load_rth_bars(symbol, d)
        if not b:
            continue
        hi = max(hi, max(x["h"] for x in b))
        lo = min(lo, min(x["l"] for x in b))
    if hi == -1e18:
        return []
    return [{"price": round(hi, 4), "type": "PMH", "weight": 2.5},
            {"price": round(lo, 4), "type": "PML", "weight": 2.5}]


def swing_pivots(bars, entry_i):
    """3-bar fractal swing highs/lows before entry_i (old highs/lows)."""
    seg = bars[: entry_i + 1]
    out = []
    for i in range(1, len(seg) - 1):
        h, l = seg[i]["h"], seg[i]["l"]
        if h > seg[i - 1]["h"] and h > seg[i + 1]["h"]:
            out.append({"price": round(h, 4), "type": "swing_high", "weight": 2.0})
        if l < seg[i - 1]["l"] and l < seg[i + 1]["l"]:
            out.append({"price": round(l, 4), "type": "swing_low", "weight": 2.0})
    return out


def levels_at_bar(symbol: str, day: str, entry_i: int, entry: float, stop: float, target: float):
    """Full node set visible at the entry bar.

    Returns (nodes, bar_coverage) where bar_coverage is one of:
      'rth'   - archived 1m RTH bars available (HOD/LOD, swings, ATR all real)
      'prior' - day itself not archived, but a prior-day archive exists (PDH/pivots real,
                no HOD/LOD/swings; ATR via fallback)
      'none'  - no archived bars at all (psych nodes only; ATR via fallback)
    """
    lo = min(entry, stop, target)
    hi = max(entry, stop, target)
    bars = load_rth_bars(symbol, day)
    nodes = psych_nodes(lo, hi)
    if bars is not None:
        nodes += hod_lod_nodes(bars, entry_i)
        nodes += swing_pivots(bars, entry_i)
        nodes += prior_day_nodes(symbol, day)
        nodes += prior_month_nodes(symbol, day)
        cov = "rth"
    elif _prior_day(symbol, day) is not None:
        # day not archived but prior day is (rare): use prior-day structural levels only
        nodes += prior_day_nodes(symbol, day)
        nodes += prior_month_nodes(symbol, day)
        cov = "prior"
    else:
        cov = "none"
    # de-dup identical prices keeping max weight (smeared analysis uses the full pre-dup set)
    return nodes, cov


# Distinct rule-source families for the "smeared" attribution test. A target is
# smeared when 2+ of these families each have a weight>=2 node within tolerance.
SOURCE_FAMILY = {
    "psych": {"psych", "psych_half", "psych_sub"},
    "HOD": {"HOD"},
    "LOD": {"LOD"},
    "PDH": {"PDH"},
    "PDL": {"PDL"},
    "PMH": {"PMH"},
    "PML": {"PML"},
    "pivot": {"pivot_PP", "pivot_R1", "pivot_S1", "pivot_R2", "pivot_S2"},
    "swing": {"swing_high", "swing_low"},
}


def source_families_within(nodes, target, tol):
    """Set of source-family names with a weight>=2 node within `tol` of target."""
    fams = set()
    for nd in nodes:
        if nd["weight"] >= 2.0 and abs(nd["price"] - target) <= tol + 1e-9:
            for fam, types in SOURCE_FAMILY.items():
                if nd["type"] in types:
                    fams.add(fam)
                    break
    return fams
