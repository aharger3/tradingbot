"""Grade card: a zoomed break->retest chart plus an S-trait checklist panel.

Built from what separates Austin's S marks from his one-offs (ship plan v3 s5,
re-checked in research/agent_runs/g-card-ux): early in the session, few bars
from break to entry, shallow retest with no close back through, trigger close
well past the level, gap in the trade direction. The card puts those six
answers next to the chart so he grades by reading one column, not by
re-measuring the chart.

Pure matplotlib, same Candidate + bars contract as chart.render_candidate_chart.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from eye_card.chart import Candidate, _bars_up_to

# thresholds = his S side of the s5 split (S median 18.5 min after open vs 28;
# <=6 bars break->entry; retest <=0.35 ATR; trigger close >=0.5 ATR past level)
EARLY_MIN = 20
FAST_BARS = 6
SHALLOW_ATR = 0.35
TRIG_PAST_ATR = 0.5
PRE_BREAK_BARS = 8


def _minute(hhmmss: str) -> int:
    h, m = int(hhmmss[:2]), int(hhmmss[3:5])
    return (h * 60 + m) - 570


def s_traits(candidate: Candidate, bars: list[dict]) -> list[tuple[str, str, bool | None]]:
    """(label, value text, passes) for each S trait. Uses candidate.extra keys
    from candidates.py features: atr, retest_bars_after_break, retest_depth_atr,
    gap_in_direction. Missing inputs -> passes=None (shown grey)."""
    x = candidate.extra or {}
    side = 1 if candidate.direction.upper() == "LONG" else -1
    window = _bars_up_to(bars, candidate.trigger_time)
    trig = window[-1]
    mins = _minute(candidate.trigger_time)
    atr = x.get("atr")
    nb = x.get("retest_bars_after_break")
    # wick penetration past the level on the retest bar (candidates.py's
    # retest_depth_atr is the trigger CLOSE distance, i.e. the Trigger row)
    wick = (candidate.level - trig["low"]) if side > 0 else (trig["high"] - candidate.level)
    depth = max(wick, 0.0) / atr if atr else None
    gap = x.get("gap_in_direction")
    brk_min = mins - nb if nb is not None else None
    thru = None
    if brk_min is not None:
        seg = [b for b in window if brk_min < _minute(b["time"]) <= mins]
        thru = any((b["close"] - candidate.level) * side <= 0 for b in seg)
    past = ((trig["close"] - candidate.level) * side / atr) if atr else None
    return [
        ("Early", f"{mins}m after open", mins <= EARLY_MIN),
        ("Fast", f"{nb} bars brk->retest" if nb is not None else "n/a",
         None if nb is None else nb <= FAST_BARS),
        ("Shallow", f"wick {depth:.2f} ATR past lvl" if depth is not None else "n/a",
         None if depth is None else depth <= SHALLOW_ATR),
        ("Held", "no close thru" if thru is False else ("closed thru" if thru else "n/a"),
         None if thru is None else not thru),
        ("Trigger", f"close {past:+.2f} ATR past" if past is not None else "n/a",
         None if past is None else past >= TRIG_PAST_ATR),
        ("Gap with", "yes" if gap else ("no" if gap is False else "n/a"),
         None if gap is None else bool(gap)),
    ]


def render_grade_card(candidate: Candidate, bars: list[dict], out_path: str | Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    window = _bars_up_to(bars, candidate.trigger_time)
    if not window or window[-1]["time"] != candidate.trigger_time:
        raise ValueError(f"no bars up to trigger_time {candidate.trigger_time!r}")
    traits = s_traits(candidate, bars)
    nb = (candidate.extra or {}).get("retest_bars_after_break")
    mins = _minute(candidate.trigger_time)
    brk_min = mins - nb if nb is not None else None
    start_min = max(0, (brk_min if brk_min is not None else mins - 20) - PRE_BREAK_BARS)
    view = [b for b in window if _minute(b["time"]) >= start_min]

    fig = plt.figure(figsize=(7.2, 4.8), dpi=150)
    gs = fig.add_gridspec(1, 2, width_ratios=[3.1, 1.25], wspace=0.05)
    ax = fig.add_subplot(gs[0])
    side_ax = fig.add_subplot(gs[1])
    side_ax.axis("off")

    for x, b in enumerate(view):
        is_trig = b["time"] == candidate.trigger_time
        is_brk = brk_min is not None and _minute(b["time"]) == brk_min
        up = b["close"] >= b["open"]
        color = "#f0a500" if is_trig else ("#1a9850" if up else "#d73027")
        ax.plot([x, x], [b["low"], b["high"]], color=color, linewidth=1.1, zorder=2)
        lo, hi = sorted([b["open"], b["close"]])
        ax.add_patch(Rectangle((x - 0.32, lo), 0.64, max(hi - lo, 1e-6),
                               facecolor=color, edgecolor=color, zorder=3))
        if is_brk:
            ax.annotate("BRK", (x, b["high"] if candidate.direction.upper() == "LONG" else b["low"]),
                        xytext=(0, 8 if candidate.direction.upper() == "LONG" else -14),
                        textcoords="offset points", ha="center", fontsize=7, color="#4575b4",
                        fontweight="bold")
        if is_trig:
            ax.annotate("RETEST", (x, b["low"] if candidate.direction.upper() == "LONG" else b["high"]),
                        xytext=(0, -14 if candidate.direction.upper() == "LONG" else 8),
                        textcoords="offset points", ha="center", fontsize=7, color="#b36b00",
                        fontweight="bold")

    n = len(view)

    def hline(y, label, color, style="--", lw=1.0):
        ax.axhline(y, color=color, linestyle=style, linewidth=lw, zorder=1)
        ax.text(n - 0.4, y, f" {label}", color=color, fontsize=7.5, va="center", ha="left")

    hline(candidate.level, f"{candidate.level_label} {candidate.level:g}", "#4575b4", "-", 1.6)
    hline(candidate.stop, "", "#d73027")
    for i, t in enumerate(candidate.targets, start=1):
        hline(t, f"T{i}", "#1a9850", ":")
    ax.set_xlim(-0.8, n + 2.6)
    step = max(1, n // 6)
    ax.set_xticks(list(range(0, n, step)))
    ax.set_xticklabels([view[i]["time"][:5] for i in range(0, n, step)], fontsize=7.5)
    ax.tick_params(axis="y", labelsize=7.5)
    ax.grid(alpha=0.15)
    ax.set_title(f"{candidate.symbol} {candidate.direction}  {candidate.trigger_time[:5]} ET  "
                 f"({mins}m after open)", fontsize=10, loc="left")

    passed = sum(1 for _, _, ok in traits if ok)
    known = sum(1 for _, _, ok in traits if ok is not None)
    side_ax.text(0.02, 0.97, f"S traits {passed}/{known}", fontsize=13, fontweight="bold",
                 va="top", transform=side_ax.transAxes)
    y = 0.84
    for label, val, ok in traits:
        mark, col = ("+", "#1a9850") if ok else (("-", "#d73027") if ok is False else ("?", "#888888"))
        side_ax.text(0.02, y, mark, fontsize=13, color=col, fontweight="bold", va="center",
                     transform=side_ax.transAxes)
        side_ax.text(0.16, y + 0.025, label, fontsize=9, fontweight="bold", va="center",
                     transform=side_ax.transAxes)
        side_ax.text(0.16, y - 0.035, val, fontsize=7.5, color="#444444", va="center",
                     transform=side_ax.transAxes)
        y -= 0.125
    side_ax.text(0.02, 0.04, f"entry {candidate.entry:g}\nstop {candidate.stop:g}",
                 fontsize=7.5, color="#333333", transform=side_ax.transAxes)
    fig.subplots_adjust(left=0.09, right=0.99, top=0.92, bottom=0.08)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path
