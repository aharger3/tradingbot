"""Render a 1-min candidate chart PNG: 9:30 -> candidate time.

Pure matplotlib (no mplfinance dependency). Draws OHLC candles, the
opening-range box, the trade level, entry/stop/target lines, and
highlights the trigger candle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display on the PC or in tests
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


@dataclass
class Candidate:
    """One candidate setup to render + send. Times are naive ET strings
    'HH:MM:SS' matching the bars index, so charts/tests never depend on tz.
    """

    candidate_id: str
    symbol: str          # e.g. "MNQ" / "NQ"
    direction: str        # "LONG" / "SHORT"
    trigger_time: str     # "HH:MM:SS" ET, bar the setup fires on
    entry: float
    stop: float
    targets: list[float]
    level: float                 # the level being traded (OCR/OB/etc)
    level_label: str = "Level"
    setup: str = ""               # e.g. "ORB+OCR"
    reason: str = ""
    or_high: float | None = None  # opening range 9:30-9:45 high
    or_low: float | None = None
    extra: dict = field(default_factory=dict)


def _bars_up_to(bars, trigger_time: str):
    """bars: list of dicts with time/open/high/low/close, ascending, 9:30 start.
    Returns the slice through and including trigger_time.
    """
    out = []
    for b in bars:
        out.append(b)
        if b["time"] == trigger_time:
            break
    return out


def render_candidate_chart(candidate: Candidate, bars: list[dict], out_path: str | Path) -> Path:
    """Render the PNG and return its path. `bars` covers >= 9:30 -> trigger_time."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    window = _bars_up_to(bars, candidate.trigger_time)
    if not window or window[-1]["time"] != candidate.trigger_time:
        raise ValueError(f"no bars up to trigger_time {candidate.trigger_time!r}")

    fig, ax = plt.subplots(figsize=(7.2, 4.8), dpi=150)
    xs = range(len(window))

    for x, b in zip(xs, window):
        is_trigger = b["time"] == candidate.trigger_time
        up = b["close"] >= b["open"]
        color = "#1a9850" if up else "#d73027"
        if is_trigger:
            color = "#f0a500"  # highlight the trigger candle
        ax.plot([x, x], [b["low"], b["high"]], color=color, linewidth=1, zorder=2)
        body_lo, body_hi = sorted([b["open"], b["close"]])
        height = max(body_hi - body_lo, 1e-6)
        ax.add_patch(Rectangle((x - 0.3, body_lo), 0.6, height,
                                facecolor=color, edgecolor=color,
                                linewidth=1.4 if is_trigger else 0, zorder=3))

    # opening range box (9:30-9:45, first 15 bars if present)
    if candidate.or_high is not None and candidate.or_low is not None:
        or_len = min(15, len(window))
        ax.add_patch(Rectangle((-0.5, candidate.or_low), or_len, candidate.or_high - candidate.or_low,
                                facecolor="#4575b4", alpha=0.12, edgecolor="#4575b4",
                                linewidth=1, zorder=1))

    def hline(y, label, color, style="--"):
        ax.axhline(y, color=color, linestyle=style, linewidth=1.1, zorder=1)
        ax.text(len(window) - 0.5, y, f" {label} {y:g}", color=color, fontsize=8,
                va="center", ha="left")

    hline(candidate.level, candidate.level_label, "#4575b4", "-")
    hline(candidate.entry, "Entry", "#333333")
    hline(candidate.stop, "Stop", "#d73027")
    for i, t in enumerate(candidate.targets, start=1):
        hline(t, f"T{i}", "#1a9850")

    ax.set_xlim(-1, len(window) + 3)
    step = max(1, len(window) // 8)
    ax.set_xticks(list(xs)[::step])
    ax.set_xticklabels([window[i]["time"][:5] for i in range(0, len(window), step)],
                        rotation=0, fontsize=8)
    ax.set_title(f"{candidate.symbol} {candidate.direction} · {candidate.setup} · "
                 f"{candidate.trigger_time} ET", fontsize=10)
    ax.set_ylabel("price")
    ax.grid(alpha=0.15)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return out_path
