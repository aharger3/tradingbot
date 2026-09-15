"""OMEN 10.0 V5: writes journal/candidates_<YYYY-MM-DD>.json for tap-to-fire.

live_scanner.py calls `record_candidate()` once per fired S/A signal it sees
in the 09:30-10:30 ET window. It appends the candidate (with a chart PNG
rendered the same way `research/g210_render_cards.py` renders the homework
deck -- 1-min candles, PMH/PML/PDH/PDL/ORH/ORL as labelled lines, cut at the
signal bar, no lookahead) to the day's file, capped at 3, arrival order,
never replaced or re-ordered once written (`docs/rows/v5-contract.md` is the
exact file-shape contract the stage-manager reads against).

This module owns the file and the chart only. Booking the paper order for a
candidate (`--arm engine` already happens in live_scanner.py's existing
Alpaca path; `--arm austin` is `research/paper_order.py`) is not this
module's job.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
JOURNAL_DIR = ROOT / "journal"
CHARTS_DIR = JOURNAL_DIR / "candidate_charts"

MAX_CANDIDATES_PER_DAY = 3
WINDOW_START = "09:30:00"
WINDOW_END = "10:30:00"
PASS_CUTOFF = "10:35:00"  # docs/rows/v5-contract.md: unanswered by 10:35 = pass


def candidates_path(day: str) -> Path:
    return JOURNAL_DIR / f"candidates_{day}.json"


def make_candidate_id(symbol: str, day: str, ts: str) -> str:
    """`<SYMBOL>_<DAY>_<HHMM>` -- stable, human-legible, and the id
    `research/paper_order.py --id` matches against."""
    hhmm = ts.replace(":", "")[:4]
    return f"{symbol}_{day}_{hhmm}"


def in_candidate_window(ts: str) -> bool:
    return WINDOW_START <= ts <= WINDOW_END


def _load(day: str) -> dict:
    path = candidates_path(day)
    if not path.exists():
        return {"day": day, "candidates": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"day": day, "candidates": []}


def _save(day: str, doc: dict) -> None:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    path = candidates_path(day)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


def render_chart(symbol: str, day: str, cut_time: str, entry: float, stop: float,
                  pt1: float, direction: str, level_name: str, out_path: Path) -> bool:
    """Render the candidate's chart PNG, reusing g210_render_cards.py's
    matplotlib pipeline (same candle draw, same level lines, same loaders).
    Returns True on success; False (no PNG written) if bars can't be loaded --
    the caller still records the candidate, just without a chart path.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle

        from research.t4_engine_recall import rth_candles, premarket_extremes, prior_day_levels
        from research.g210_render_cards import (
            bars_up_to, opening_range, resample_5m, draw_candles,
            tick_labels, draw_level,
        )
    except ImportError:
        return False

    bars_full = rth_candles(symbol, day)
    if not bars_full:
        return False
    bars = bars_up_to(bars_full, cut_time)
    if not bars:
        return False

    pmh, pml = premarket_extremes(symbol, day)
    pdh, pdl, _o, _c = prior_day_levels(symbol, day)
    orh, orl = opening_range(bars)
    bars_5m = resample_5m(bars)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8), dpi=100, gridspec_kw={"height_ratios": [3, 1]})

    draw_candles(ax1, bars, is_5m=False)
    idxs, labels = tick_labels(bars, is_5m=False)
    ax1.set_xticks(idxs)
    ax1.set_xticklabels(labels, fontsize=7)
    ax1.set_xlim(-1, len(bars) + 4)
    ax1.set_title(f"{symbol}  {day}  (1-min, cut {cut_time[:5]})", fontsize=11)
    ax1.grid(True, alpha=0.2)

    draw_level(ax1, pmh, "PMH", "#e08a1e", len(bars))
    draw_level(ax1, pml, "PML", "#e08a1e", len(bars))
    draw_level(ax1, pdh, "PDH", "#6a4fbf", len(bars))
    draw_level(ax1, pdl, "PDL", "#6a4fbf", len(bars))
    draw_level(ax1, orh, "ORH", "#1e7fe0", len(bars))
    draw_level(ax1, orl, "ORL", "#1e7fe0", len(bars))
    draw_level(ax1, entry, "ENTRY", "#2a2a2a", len(bars))
    draw_level(ax1, stop, "STOP", "#d1495b", len(bars))
    draw_level(ax1, pt1, "PT1", "#2a9d5c", len(bars))

    draw_candles(ax2, bars_5m, is_5m=True)
    idxs5, labels5 = tick_labels(bars_5m, is_5m=True, max_ticks=6)
    ax2.set_xticks(idxs5)
    ax2.set_xticklabels(labels5, fontsize=7)
    ax2.set_xlim(-1, len(bars_5m) + 1)
    ax2.set_title("5-min", fontsize=9)
    ax2.grid(True, alpha=0.2)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=100)
    plt.close(fig)
    return True


def record_candidate(day: str, symbol: str, ts: str, setup: str, level_name: str,
                      direction: str, entry: float, stop: float, pt1: float,
                      grade: str) -> dict | None:
    """Append one S/A candidate to journal/candidates_<day>.json.

    Idempotent on id (an already-recorded id is a no-op, returns the existing
    row). Capped at MAX_CANDIDATES_PER_DAY, arrival order, never replaced.
    Returns the candidate dict written (or already present), or None if the
    day's cap was already hit and this id is new.
    """
    if not in_candidate_window(ts):
        return None
    doc = _load(day)
    cands = doc["candidates"]
    cid = make_candidate_id(symbol, day, ts)
    for c in cands:
        if c["id"] == cid:
            return c  # already recorded -- idempotent
    if len(cands) >= MAX_CANDIDATES_PER_DAY:
        return None

    chart_path = CHARTS_DIR / f"{cid}.png"
    ok = render_chart(symbol, day, ts, entry, stop, pt1, direction, level_name, chart_path)
    rel_chart = os.path.relpath(chart_path, ROOT).replace("\\", "/") if ok else None

    cand = {
        "id": cid, "symbol": symbol, "day": day, "ts": ts,
        "setup": setup, "level": level_name, "direction": direction,
        "entry": entry, "stop": stop, "pt1": pt1, "grade": grade,
        "chart_png": rel_chart,
    }
    cands.append(cand)
    _save(day, doc)
    return cand
