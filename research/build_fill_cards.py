#!/usr/bin/env python3
"""Generate omen-5.1-fill-cards.html — card deck of every flipped trade.

Reads research/t51_fill_flip.jsonl and builds one card per row with an inline
SVG 1-minute candle chart showing the 09:30-11:00 window.
"""
import csv, json, math, os, sys
from collections import namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARCHIVE = os.path.join(ROOT, "data_archive")
FLIP_PATH = os.path.join(HERE, "t51_fill_flip.jsonl")
OUT_PATH = os.path.join(HERE, "omen-5.1-fill-cards.html")

Candle = namedtuple("Candle", "i time open high low close")


def hhmm(dt_str):
    """Extract HH:MM from ISO datetime string like 2024-09-23T09:41:00-04:00."""
    return dt_str[11:16]


def load_candles(symbol, day, start_idx=0, end_idx=90):
    """Return list of Candle for [start_idx, end_idx) from the 09:30-16:00 RTH session."""
    path = os.path.join(ARCHIVE, symbol, f"{day}.csv")
    if not os.path.exists(path):
        return None
    all_rth = []
    with open(path) as f:
        for r in csv.DictReader(f):
            t = hhmm(r["Datetime"])
            if t < "09:30" or t >= "16:00":
                continue
            all_rth.append(Candle(
                i=len(all_rth),
                time=t + ":00",
                open=float(r["Open"]),
                high=float(r["High"]),
                low=float(r["Low"]),
                close=float(r["Close"]),
            ))
    return all_rth[start_idx:end_idx]


def price_range(candles, entry, stop, target):
    if not candles:
        return 0, 1
    lo = min(c.low for c in candles)
    lo = min(lo, entry, stop, target)
    hi = max(c.high for c in candles)
    hi = max(hi, entry, stop, target)
    pad = (hi - lo) * 0.15 if hi > lo else 1.0
    return lo - pad, hi + pad


def candle_svg(candles, entry, stop, target, entry_i, flip_bar_i, width_px=800):
    """Return SVG string for candle chart."""
    if not candles:
        return "<svg width='800' height='300'><text x='10' y='20'>No candle data</text></svg>"

    n = len(candles)
    y_lo, y_hi = price_range(candles, entry, stop, target)
    y_range = y_hi - y_lo
    if y_range < 0.001:
        y_range = 1.0

    h_px = 360  # chart area height
    margin = {"l": 60, "r": 20, "t": 20, "b": 50}
    plot_w = width_px - margin["l"] - margin["r"]

    bar_w = max(4, min(10, plot_w / n - 1))
    gap = max(1, bar_w * 0.2)
    step = bar_w + gap

    def y2px(price):
        return margin["t"] + h_px * (1 - (price - y_lo) / y_range)

    def vline(price, label, color, dash="", label_side="right"):
        yy = y2px(price)
        cls = f" class='hl'"
        dash_attr = f" stroke-dasharray='{dash}'" if dash else ""
        lines = [f"<line x1='{margin['l']}' y1='{yy}' x2='{margin['l'] + plot_w}' y2='{yy}'{dash_attr} stroke='{color}' stroke-width='1.5'/>"]
        lx = margin["l"] + plot_w - 4 if label_side == "right" else margin["l"] + 4
        anchor = "end" if label_side == "right" else "start"
        lines.append(f"<text x='{lx}' y='{yy - 3}' text-anchor='{anchor}' fill='{color}' font-size='11'>{label} {price:.4f}</text>")
        return "\n".join(lines)

    # Build SVG
    lines = [f"<svg width='{width_px}' height='{margin['t'] + h_px + margin['b']}' xmlns='http://www.w3.org/2000/svg' font-family='Consolas,monospace'>"]

    # Background
    lines.append(f"<rect x='0' y='0' width='{width_px}' height='{margin['t'] + h_px + margin['b']}' fill='#1a1a2e'/>")

    # Grid lines (horizontal, every ~20px)
    n_grid = 8
    for gi in range(1, n_grid):
        yy = margin["t"] + h_px * gi / n_grid
        price = y_hi - y_range * gi / n_grid
        lines.append(f"<line x1='{margin['l']}' y1='{yy}' x2='{margin['l'] + plot_w}' y2='{yy}' stroke='#2a2a4e' stroke-width='0.5'/>")
        lines.append(f"<text x='{margin['l'] - 4}' y='{yy + 3}' text-anchor='end' fill='#888' font-size='9'>{price:.2f}</text>")

    # Entry, stop, target lines
    lines.append(vline(entry, "Entry", "#4da6ff", "6,3"))
    lines.append(vline(stop, "Stop", "#ff5555", "4,3"))
    lines.append(vline(target, "Target", "#50fa7b", "4,3"))

    # Candles
    for ci, c in enumerate(candles):
        x = margin["l"] + ci * step + step / 2 - bar_w / 2
        is_bull = c.close >= c.open
        body_color = "#50fa7b" if is_bull else "#ff5555"
        wick_color = "#aabbcc"

        # Determine bar index in the full-day RTH (start_idx offset accounted via candles list)
        # entry_i and flip_bar_i are relative to the full RTH session (0 = 09:30)
        bar_offset = entry_i  # entry_i is the same as candle index in RTH session
        flip_offset = flip_bar_i

        bar_open = c.open
        bar_close = c.close

        # Highlight flip bar: purple background
        if ci == flip_offset:
            lines.append(f"<rect x='{x - 1}' y='{y2px(max(bar_open, bar_close)) + 1}' width='{bar_w + 2}' height='{y2px(min(bar_open, bar_close)) - y2px(max(bar_open, bar_close)) - 2}' fill='rgba(189,147,249,0.25)' stroke='#bd93f9' stroke-width='1.5'/>")

        # Wick
        lines.append(f"<line x1='{x + bar_w/2}' y1='{y2px(c.high)}' x2='{x + bar_w/2}' y2='{y2px(c.low)}' stroke='{wick_color}' stroke-width='1'/>")

        # Body
        body_top = y2px(max(bar_open, bar_close))
        body_bot = y2px(min(bar_open, bar_close))
        body_h = max(1, body_bot - body_top)
        lines.append(f"<rect x='{x}' y='{body_top}' width='{bar_w}' height='{body_h}' fill='{body_color}' opacity='0.9'/>")

        # Entry bar outline
        if ci == entry_i:
            lines.append(f"<rect x='{x - 2}' y='{y2px(c.high) - 2}' width='{bar_w + 4}' height='{y2px(c.low) - y2px(c.high) + 4}' fill='none' stroke='#ffb86c' stroke-width='2'/>")

    # Time labels every 30 min
    label_minutes = {0, 30, 60, 90}
    for ci, c in enumerate(candles):
        if ci in label_minutes:
            hr = c.time[:5]
            tx = margin["l"] + ci * step + step / 2
            lines.append(f"<text x='{tx}' y='{margin['t'] + h_px + 16}' text-anchor='middle' fill='#888' font-size='10'>{hr}</text>")

    lines.append("</svg>")
    return "\n".join(lines)


def make_card(row):
    """Return HTML for one card."""
    sym = row["symbol"]
    day = row["date"]
    dir_label = row["dir"].upper()
    grade = row["grade"]
    setup = row["setup"].replace("_", " ")
    entry_i = row["entry_i"]
    flip_i = row["flip_bar_i"]

    # Load candles for the 09:30-11:00 window (bars 0-89)
    candles = load_candles(sym, day, start_idx=0, end_idx=95)

    delta_r = abs(row["old_r"] - row["new_r"])

    chart = candle_svg(candles, row["entry"], row["stop"], row["target"],
                       entry_i, flip_i)

    # Caption
    caption = (
        f"This bar touched the target at {row['target']:.4f} AND closed at {row['close']:.4f}, "
        f"beyond the stop at {row['stop']:.4f}. "
        f"Old model: {row['old_outcome']} {row['old_r']:+.4f}R. "
        f"New model: {row['new_outcome']} {row['new_r']:+.4f}R."
    )

    # Badge for non-counted
    badge_html = ""
    if not row["counted"]:
        badge_html = f"<span class='badge'>not a traded signal ({row['status']})</span>"

    return f"""<div class="card">
  <div class="card-header">
    <span class="card-title">{sym} &middot; {day} &middot; <span class="dir-{dir_label}">{dir_label}</span> &middot; {grade} &middot; {setup}</span>
    <span class="delta-badge">&Delta;R {delta_r:.4f}</span>
    {badge_html}
  </div>
  <div class="card-chart">
  {chart}
  </div>
  <div class="card-caption">{caption}</div>
</div>"""


def main():
    rows = []
    with open(FLIP_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    # Sort by abs(old_r - new_r) descending (rounded to avoid float quirk)
    rows.sort(key=lambda r: -round(abs(r["old_r"] - r["new_r"]), 10))

    # Count stats for header
    n_total = len(rows)
    n_traded = sum(1 for r in rows if r["counted"])
    n_change_outcome = sum(1 for r in rows if r["old_outcome"] != r["new_outcome"])
    # Zero counted trades changed outcome (from the report)
    counted_change_outcome = sum(
        1 for r in rows if r["counted"] and r["old_outcome"] != r["new_outcome"]
    )

    cards_html = "\n".join(make_card(r) for r in rows)

    outcome_note = (
        "Zero counted trades changed outcome — every flip in this deck is an "
        "R-reduction on a signal the engine never took."
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OMEN 5.1 — Fill-Rule Flip Cards</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0f0f23; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; }}
  h1 {{ color: #f8f8f2; font-size: 1.6em; margin-bottom: 4px; }}
  .subtitle {{ color: #6272a4; font-size: 0.95em; margin-bottom: 20px; line-height: 1.5; }}
  .deck-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(820px, 1fr));
    gap: 20px;
  }}
  .card {{
    background: #1e1e3a;
    border: 1px solid #3a3a5c;
    border-radius: 10px;
    overflow: hidden;
    padding: 16px;
  }}
  .card-header {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }}
  .card-title {{
    font-weight: 600;
    font-size: 1.05em;
    color: #f8f8f2;
  }}
  .dir-CALL {{ color: #50fa7b; }}
  .dir-PUT {{ color: #ff5555; }}
  .delta-badge {{
    background: #3a3a5c;
    color: #bd93f9;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.8em;
    font-weight: 600;
  }}
  .badge {{
    background: #ffb86c;
    color: #1e1e3a;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.8em;
    font-weight: 600;
  }}
  .card-chart {{
    margin-bottom: 10px;
  }}
  .card-chart svg {{
    display: block;
    max-width: 100%;
    height: auto;
  }}
  .card-caption {{
    font-size: 0.85em;
    color: #c0c0d0;
    line-height: 1.4;
    padding: 8px 10px;
    background: #16162e;
    border-radius: 6px;
  }}
  @media (max-width: 860px) {{
    .deck-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<h1>OMEN 5.1 — Fill-Rule Flip Cards</h1>
<p class="subtitle">
  {n_total} total fills moved ({n_traded} traded). {n_change_outcome} change outcome label.
  {outcome_note}<br>
  Cards sorted by |&Delta;R| descending. Generated from <code>research/t51_fill_flip.jsonl</code>.
</p>
<div class="deck-grid">
{cards_html}
</div>
</body>
</html>"""

    with open(OUT_PATH, "w") as f:
        f.write(html)
    print(f"Wrote {OUT_PATH} ({n_total} cards)")


if __name__ == "__main__":
    main()