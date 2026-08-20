"""Trend gate (OMEN 5.2, T4).

`is_trending(symbol, date, entry_i, side) -> bool` decides whether a trade
entry is *trending* using **only bars at or before `entry_i`** (RTH 1-min bars
from `research.levels.load_rth_bars`, which start at 09:30 ET — `entry_i` is an
index into that same RTH series, confirmed in `research/v52_paths.md`).

Three components; trending = **>= 2 of 3**:

1. **Index alignment** — the market index is moving the same direction as the
   trade from 09:30 to `entry_i`. Index is **QQQ** for TSLA / QQQ trades and
   **SPY** for SPY trades. "Same direction by a margin": the index's close at
   `entry_i` vs its 09:30 open must move **>= INDEX_MARGIN_BPS (5 bps)** in the
   trade's favour (long: up, short: down). 5 bps is a scale-free nudge that
   filters out dead-flat index prints without demanding a real trend.

2. **Structure** — the traded symbol has made **higher highs AND higher lows**
   on the 1-min bars since 09:30 (mirror for shorts). Implementation: split the
   window `bars[0 .. entry_i]` into first and second halves and require the
   second half's max-high > first half's max-high **and** second half's min-low
   > first half's min-low (mirror: lower highs and lower lows for shorts). This
   is a clean, causally-derivable proxy for "rising/falling structure".

3. **Earliness** — `entry_i` is at or before **09:50 ET**. RTH bars start at
   09:30 (index 0), so 09:50 is index 20; `entry_i <= 20` passes.

The `side` argument is `"L"`/`"long"` (case-insensitive, first char `l`) for
longs, anything else short.
"""

from __future__ import annotations
import os, sys, json

# --- thresholds (documented above) ---------------------------------------
INDEX_MARGIN_BPS = 5.0       # index 09:30-open -> entry_i-close move, in bps
EARLY_ENTRY_I = 20           # 09:50 ET == RTH bar index 20 (09:30 == 0)


def _load_bars(symbol: str, day: str):
    """RTH 1-min bars for symbol/day via the shared loader; None if absent."""
    try:
        from research.levels import load_rth_bars  # package-style import
    except Exception:
        _here = os.path.dirname(os.path.abspath(__file__))
        if _here not in sys.path:
            sys.path.insert(0, _here)
        from levels import load_rth_bars
    return load_rth_bars(symbol, day)


def _is_long(side: str) -> bool:
    return bool(side) and side.strip()[0].lower() == "l"


def _index_symbol(symbol: str) -> str:
    """QQQ benchmarks TSLA and QQQ trades; SPY benchmarks SPY trades."""
    s = symbol.upper()
    return "SPY" if s == "SPY" else "QQQ"


def comp_index_alignment(symbol, date, entry_i, side):
    """Component 1: index 09:30-open -> entry_i-close moves >= 5 bps in trade's favour."""
    idx = _index_symbol(symbol)
    bars = _load_bars(idx, date)
    if not bars or entry_i >= len(bars):
        return False, "F(no idx bars)"
    o = bars[0]["o"]
    c = bars[entry_i]["c"]
    bps = (c - o) / o * 1e4
    long = _is_long(side)
    passed = (bps >= INDEX_MARGIN_BPS) if long else (bps <= -INDEX_MARGIN_BPS)
    sign = "+" if bps >= 0 else ""
    return passed, f"{'T' if passed else 'F'}({sign}{bps:.1f}bps)"


def comp_structure(symbol, date, entry_i, side):
    """Component 2: higher highs & higher lows since 09:30 (mirror for shorts)."""
    bars = _load_bars(symbol, date)
    if not bars or entry_i >= len(bars) or entry_i < 1:
        return False, "F(no bars)"
    win = bars[: entry_i + 1]
    mid = len(win) // 2
    if mid < 1:
        return False, "F(<2 bars/half)"
    first, second = win[:mid], win[mid:]
    fh, fl = max(b["h"] for b in first), min(b["l"] for b in first)
    sh, sl = max(b["h"] for b in second), min(b["l"] for b in second)
    long = _is_long(side)
    if long:
        passed = sh > fh and sl > fl
        tag = "HH/HL" if passed else "noHH/HL"
    else:
        passed = sh < fh and sl < fl
        tag = "LH/LL" if passed else "noLH/LL"
    return passed, f"{'T' if passed else 'F'}({tag})"


def comp_earliness(entry_i):
    """Component 3: entry_i <= 20 (09:50 ET)."""
    passed = entry_i <= EARLY_ENTRY_I
    t = _i_to_time(entry_i)
    return passed, f"{'T' if passed else 'F'}({t})"


def _i_to_time(entry_i):
    """RTH bar index -> HH:MM (09:30 base). For display only."""
    total = 9 * 60 + 30 + entry_i
    return f"{total // 60:02d}:{total % 60:02d}"


def is_trending(symbol, date, entry_i, side) -> bool:
    """Trending = at least 2 of 3 components, computed only from bars <= entry_i."""
    votes = [
        comp_index_alignment(symbol, date, entry_i, side)[0],
        comp_structure(symbol, date, entry_i, side)[0],
        comp_earliness(entry_i)[0],
    ]
    return sum(votes) >= 2


# --- scoring against Austin's day_type labels ----------------------------
MARKS_FILES = [
    "research/marks/deck_marks_index_2026-08-19.jsonl",
    "research/marks/deck_marks_tsla_2026-08-20.jsonl",
]
# trend -> trending; chop, range -> not trending; reversal & blank excluded
SCORED = {"trend": True, "chop": False, "range": False}


def _load_marks():
    days, trades = {}, {}
    for fn in MARKS_FILES:
        with open(fn, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                if r.get("type") == "day":
                    days[r["card_id"]] = r
                elif r.get("type") == "trade":
                    trades.setdefault(r["card_id"], []).append(r)
    return days, trades


def _scored_days():
    """One row per scored day: the day's first (lowest trade_no) trade."""
    days, trades = _load_marks()
    rows = []
    for cid, d in sorted(days.items(), key=lambda kv: (kv[1]["symbol"], kv[1]["date"])):
        dt = d.get("day_type", "")
        if dt not in SCORED:
            continue  # reversal / blank excluded
        ts = sorted(trades.get(cid, []), key=lambda t: t.get("trade_no", 0))
        if not ts:
            continue  # no entry to gate on -> unscored
        t = ts[0]
        rows.append({
            "symbol": d["symbol"], "date": d["date"], "day_type": dt,
            "entry_i": t["entry_i"], "side": t["side"],
        })
    return rows


def _write_agreement(path="research/trend_gate_agreement.md"):
    rows = _scored_days()
    agree = 0
    dis = []
    for r in rows:
        gate = is_trending(r["symbol"], r["date"], r["entry_i"], r["side"])
        expected = SCORED[r["day_type"]]
        if gate == expected:
            agree += 1
        else:
            ia = comp_index_alignment(r["symbol"], r["date"], r["entry_i"], r["side"])[1]
            st = comp_structure(r["symbol"], r["date"], r["entry_i"], r["side"])[1]
            ea = comp_earliness(r["entry_i"])[1]
            dis.append((r, gate, expected, ia, st, ea))
    frac = agree / len(rows) if rows else 0.0
    frac_str = f"{frac:.4f}".rstrip("0").rstrip(".") or "0"

    L = []
    L.append("# Trend gate vs Austin's day_type labels (T4)")
    L.append("")
    L.append("Gate: `research/trend_gate.py :: is_trending(symbol, date, entry_i, side)` — "
             "trending = >= 2 of 3 components (index alignment, structure, earliness), "
             "computed only from RTH bars at or before `entry_i`. Thresholds documented at "
             "the top of that file.")
    L.append("")
    L.append("Scoring set: every marked day whose `day_type` is in {trend, chop, range} and "
             "which carries a trade mark, evaluated at the day's first (earliest) trade. "
             "`trend` -> trending, `chop`/`range` -> not trending, `reversal` and blank "
             "day_type are excluded from the agreement count (no directional expectation / "
             "no entry to gate on).")
    L.append("")
    L.append(f"Scored days: {len(rows)}. Agreement: {agree}/{len(rows)}.")
    L.append("")
    L.append("```")
    L.append(f"gate_vs_austin_agreement: {frac_str}")
    L.append("```")
    L.append("")
    L.append("## Disagreements (gate != day_type expectation)")
    L.append("")
    L.append("| symbol date | side | entry_i | index | structure | earliness |")
    L.append("|---|---|---|---|---|---|")
    for r, gate, expected, ia, st, ea in dis:
        L.append(f"| {r['symbol']} {r['date']} | {r['side']} | {r['entry_i']} "
                 f"({_i_to_time(r['entry_i'])}) | {ia} | {st} | {ea} |")
    if not dis:
        L.append("| _none_ | | | | | |")
    L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return frac, len(rows), agree


if __name__ == "__main__":
    frac, n, a = _write_agreement()
    print(f"agreement {a}/{n} = {frac:.4f}")
