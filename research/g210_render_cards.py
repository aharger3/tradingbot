"""g210_render_cards.py -- render the S-sweep probe deck as blind PNG charts.

W9 (OMEN 9.0 wave 2 row): render every card in
research/marks/probe_s_sweep_2026-08-28.jsonl (read-only, ~100 symbol-days,
34 S) as a PNG chart cut at his entry bar (blind -- nothing after the cut),
with premarket high/low, prior-day high/low, and opening-range high/low drawn
as labelled horizontal lines, plus a small 5-minute panel. No grade or engine
field appears anywhere on the image; his grade is recorded ONLY in the index
json, for a downstream reader (a human, or an LLM given the index separately)
to be scored against.

Bars come from data_archive/<SYMBOL>/<DAY>.csv via research.t4_engine_recall
(rth_candles, premarket_extremes, prior_day_levels) -- the same loaders
research/build_deck.py uses. Nothing here mutates a mark file.

Run: python research/g210_render_cards.py
Writes: research/g210_cards/<card_id>.png (gitignored -- readers read from disk)
        research/g210_cards/index.json
        research/g210_render_cards.md (report)
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from research.t4_engine_recall import rth_candles, premarket_extremes, prior_day_levels

MARKS = os.path.join(ROOT, "research", "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_DIR = os.path.join(ROOT, "research", "g210_cards")
INDEX_PATH = os.path.join(OUT_DIR, "index.json")
REPORT_PATH = os.path.join(ROOT, "research", "g210_render_cards.md")

DEFAULT_CUT = "10:00:00"


def load_cards(path):
    cards = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cards.append(json.loads(line))
    return cards


def entry_time_from_notes(card):
    """His entry time, if the card's notes carry one. probe_s_sweep cards use
    notes.min = 'H:MM' (24h, no leading zero) for the minute he'd have entered
    on an S/A card. Cards graded 'no' rarely carry a min; treat that as blind
    to 10:00 per the row spec."""
    notes = card.get("notes") or {}
    raw = notes.get("min") or notes.get("entry") or notes.get("time")
    if not raw:
        return None
    raw = str(raw).strip()
    if not raw:
        return None
    # accept "9:44", "09:44", "9:44:00"
    parts = raw.split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return None
    if len(parts) == 2:
        h, m = parts
        s = 0
    elif len(parts) == 3:
        h, m, s = parts
    else:
        return None
    return "%02d:%02d:%02d" % (h, m, s)


def his_grade_from_card(card):
    """The card's grade field as he wrote it. probe_s_sweep stores the real
    verdict under answers.s (['s'] or ['no']); the top-level 'grade' field is
    always 'none' in this file (unscored placeholder), so prefer answers.s."""
    ans = (card.get("answers") or {}).get("s")
    if ans:
        v = str(ans[0]).strip().lower()
        if v == "s":
            return "S"
        if v == "no":
            return "none"
    g = card.get("grade")
    return g if g else "none"


def bars_up_to(bars, cut_time):
    return [b for b in bars if b.timestamp <= cut_time]


def opening_range(bars):
    orb = [b for b in bars if b.timestamp < "09:35:00"]
    if not orb:
        return (None, None)
    return (max(b.high for b in orb), min(b.low for b in orb))


def resample_5m(bars):
    """Group 1-minute Candle objects into 5-minute OHLC bars, RTH-aligned to
    :30/:35/:40..."""
    buckets = {}
    order = []
    for b in bars:
        h, m, s = b.timestamp.split(":")
        bucket_min = (int(m) // 5) * 5
        key = "%s:%02d:00" % (h, bucket_min)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(b)
    out = []
    for key in order:
        grp = buckets[key]
        out.append(dict(
            timestamp=key,
            open=grp[0].open,
            high=max(g.high for g in grp),
            low=min(g.low for g in grp),
            close=grp[-1].close,
        ))
    return out


def draw_candles(ax, bars, is_5m=False):
    xs = range(len(bars))
    width = 0.7
    for i, b in enumerate(bars):
        o = b["open"] if is_5m else b.open
        h = b["high"] if is_5m else b.high
        l = b["low"] if is_5m else b.low
        c = b["close"] if is_5m else b.close
        color = "#2a9d5c" if c >= o else "#d1495b"
        ax.plot([i, i], [l, h], color=color, linewidth=0.8, zorder=2)
        y0 = min(o, c)
        height = max(abs(c - o), 0.001)
        ax.add_patch(Rectangle((i - width / 2, y0), width, height,
                                facecolor=color, edgecolor=color, zorder=3))
    return xs


def tick_labels(bars, is_5m=False, max_ticks=8):
    n = len(bars)
    if n == 0:
        return [], []
    step = max(1, n // max_ticks)
    idxs = list(range(0, n, step))
    labels = [(bars[i]["timestamp"] if is_5m else bars[i].timestamp)[:5] for i in idxs]
    return idxs, labels


def draw_level(ax, y, label, color, n_bars):
    if y is None:
        return
    ax.axhline(y, color=color, linestyle="--", linewidth=1.0, zorder=1, alpha=0.85)
    ax.text(n_bars - 0.5, y, " " + label, color=color, fontsize=7,
            va="center", ha="left", clip_on=False)


def render_card(card, out_path):
    symbol = card["symbol"]
    day = card["date"]
    card_id = card["card_id"]

    bars_full = rth_candles(symbol, day)
    if not bars_full:
        return None, "no bars"

    entry_t = entry_time_from_notes(card)
    cut_t = entry_t if entry_t else DEFAULT_CUT
    bars = bars_up_to(bars_full, cut_t)
    if not bars:
        return None, "no bars before cut"

    pmh, pml = premarket_extremes(symbol, day)
    pdh, pdl, _o, _c = prior_day_levels(symbol, day)
    orh, orl = opening_range(bars)

    bars_5m = resample_5m(bars)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8), dpi=100,
        gridspec_kw={"height_ratios": [3, 1]})

    draw_candles(ax1, bars, is_5m=False)
    idxs, labels = tick_labels(bars, is_5m=False)
    ax1.set_xticks(idxs)
    ax1.set_xticklabels(labels, fontsize=7)
    ax1.set_xlim(-1, len(bars) + 4)
    ax1.set_title("%s  %s  (1-min, cut %s)" % (symbol, day, cut_t[:5]), fontsize=11)
    ax1.grid(True, alpha=0.2)

    draw_level(ax1, pmh, "PMH", "#e08a1e", len(bars))
    draw_level(ax1, pml, "PML", "#e08a1e", len(bars))
    draw_level(ax1, pdh, "PDH", "#6a4fbf", len(bars))
    draw_level(ax1, pdl, "PDL", "#6a4fbf", len(bars))
    draw_level(ax1, orh, "ORH", "#1e7fe0", len(bars))
    draw_level(ax1, orl, "ORL", "#1e7fe0", len(bars))

    draw_candles(ax2, bars_5m, is_5m=True)
    idxs5, labels5 = tick_labels(bars_5m, is_5m=True, max_ticks=6)
    ax2.set_xticks(idxs5)
    ax2.set_xticklabels(labels5, fontsize=7)
    ax2.set_xlim(-1, len(bars_5m) + 1)
    ax2.set_title("5-min", fontsize=9)
    ax2.grid(True, alpha=0.2)

    fig.tight_layout()
    fig.savefig(out_path, dpi=100)
    plt.close(fig)

    # verify actual pixel size
    return cut_t, None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cards = load_cards(MARKS)

    index = []
    n_ok = 0
    n_fail = 0
    n_s = 0
    fail_reasons = []

    for card in cards:
        card_id = card["card_id"]
        symbol = card["symbol"]
        day = card["date"]
        out_path = os.path.join(OUT_DIR, "%s.png" % card_id)
        his_grade = his_grade_from_card(card)
        if his_grade == "S":
            n_s += 1
        cut_t, err = render_card(card, out_path)
        if err:
            n_fail += 1
            fail_reasons.append("%s: %s" % (card_id, err))
            continue
        n_ok += 1
        index.append(dict(
            card_id=card_id,
            symbol=symbol,
            day=day,
            png_path=os.path.relpath(out_path, ROOT).replace("\\", "/"),
            his_grade=his_grade,
            entry_t=entry_time_from_notes(card),
            cut_bar_time=cut_t,
        ))

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    sample = index[:3]
    lines = []
    lines.append("Rendered the probe_s_sweep_2026-08-28 deck (%d cards) to blind PNG charts "
                  "cut at his entry bar or 10:00; %d rendered, %d failed (missing bars)."
                  % (len(cards), n_ok, n_fail))
    lines.append("")
    lines.append("| metric | value |")
    lines.append("|---|---:|")
    lines.append("| total cards | %d |" % len(cards))
    lines.append("| rendered | %d |" % n_ok)
    lines.append("| failed | %d |" % n_fail)
    lines.append("| S-graded (his answers.s) | %d |" % n_s)
    lines.append("")
    if fail_reasons:
        lines.append("Failures:")
        for r in fail_reasons:
            lines.append("- %s" % r)
        lines.append("")
    lines.append("Sample paths:")
    for s in sample:
        lines.append("- `%s` (card_id=%s, his_grade=%s, entry_t=%s, cut=%s)"
                      % (s["png_path"], s["card_id"], s["his_grade"], s["entry_t"], s["cut_bar_time"]))
    lines.append("")
    lines.append("Index: `research/g210_cards/index.json` (%d entries, gitignored dir, read from disk)."
                  % len(index))
    lines.append("No grade or engine field is drawn on any PNG -- his_grade lives only in the index.")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("rendered %d / %d, %d S" % (n_ok, len(cards), n_s))


if __name__ == "__main__":
    main()
