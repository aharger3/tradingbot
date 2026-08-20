"""omen-5.1 T6: Build two self-contained HTML day-decks + manifest.

Usage: python research/t51_build_deck.py

Generates:
  research/omen-5.1-tsla-day-deck.html    — 60 most recent TSLA trading days
  research/omen-5.1-index-day-deck.html   — 30 most recent QQQ + 30 most recent SPY
  research/t51_day_deck_manifest.jsonl     — 120 rows with engine fire counts

Both decks export grades as JSONL via download and clipboard, persist via
localStorage, and show NO engine-derived overlays.
"""

from __future__ import annotations
import csv
import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from research.t4_engine_recall import run_day, rth_candles

ARCHIVE = os.path.join(ROOT, "data_archive")
TSLA_DECK = os.path.join(HERE, "omen-5.1-tsla-day-deck.html")
INDEX_DECK = os.path.join(HERE, "omen-5.1-index-day-deck.html")
MANIFEST = os.path.join(HERE, "t51_day_deck_manifest.jsonl")

# 09:30-11:00 ET session window
SESSION_START = "09:30"
SESSION_END = "11:00"


def _trading_days(symbol: str) -> list[str]:
    """All archived trading days for a symbol, sorted ascending."""
    pat = os.path.join(ARCHIVE, symbol, "*.csv")
    names = sorted(os.path.basename(f)[:-4] for f in glob.glob(pat))
    return names


def _to_min(ts: str) -> str:
    """Extract HH:MM from ISO timestamp."""
    return ts[11:16] if "T" in ts else ts[:5]


def _filter_session(candles) -> list:
    """Return candles in 09:30-11:00 ET window."""
    out = []
    for c in candles:
        t = _to_min(c.timestamp)
        if SESSION_START <= t < SESSION_END:
            out.append(c)
    return out


def _load_session_candles(symbol: str, day: str) -> list:
    """Load 09:30-11:00 1-min candles for (symbol, day)."""
    candles = rth_candles(symbol, day)
    if not candles:
        return []
    return _filter_session(candles)


def _candle_to_dict(c) -> dict:
    return {
        "t": c.timestamp,
        "o": round(c.open, 2),
        "h": round(c.high, 2),
        "l": round(c.low, 2),
        "c": round(c.close, 2),
        "v": int(c.volume),
    }


def _engine_fire_count(symbol: str, day: str) -> int:
    """Count how many signals the engine fires (accepts) on this (symbol, day).

    Uses run_day from t4_engine_recall which already replays bar-by-bar with
    deduplication. Returns 0 when the engine cannot run (no archived data).
    """
    entries, all_sigs, _raw = run_day(symbol, day)
    if entries is None:
        return 0
    return len(entries)


# ── HTML template parts ──────────────────────────────────────────────────────

# Deck front-end (HTML/CSS/JS) lives in deck_ui.py as of 5.2.
import deck_ui


def build_deck(days: list[tuple[str, str, list, float, float]],
               label: str, out_path: str) -> None:
    """Build a self-contained HTML deck.

    days: list of (symbol, date, session_candles, prior_hi, prior_lo)
    Each card shows the pure 09:30-11:00 candlestick chart with NO engine marks.
    """
    day_data = {}
    prior_levels = {}
    card_ids = []
    card_htmls = []

    for symbol, date, candles, pdh, pdl in days:
        cid = f"{symbol}_{date}"
        card_ids.append(cid)
        day_data[cid] = [_candle_to_dict(c) for c in candles]
        prior_levels[cid] = {"pdh": round(pdh, 2) if pdh else None,
                             "pdl": round(pdl, 2) if pdl else None}

        card_htmls.append(deck_ui.render_card(cid, symbol))

    full = deck_ui.HTML_HEAD.replace("__LABEL__", label)
    full = full.replace("__TOTAL__", str(len(card_ids)))
    full += "\n".join(card_htmls)

    script = deck_ui.HTML_SCRIPT_PREAMBLE
    script = script.replace("__DAY_DATA__", json.dumps(day_data))
    script = script.replace("__PRIOR_LEVELS__", json.dumps(prior_levels))
    script = script.replace("__CARD_IDS__", json.dumps(card_ids))
    script = script.replace("__SETUPS__", json.dumps(deck_ui.SETUPS))

    full += script

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full)
    print(f"Wrote {out_path} ({len(card_ids)} cards)")


def main():
    # ── 1. Gather trading days ────────────────────────────────────────────
    tsla_days = _trading_days("TSLA")
    qqq_days = _trading_days("QQQ")
    spy_days = _trading_days("SPY")

    n_tsla = len(tsla_days)
    n_qqq = len(qqq_days)
    n_spy = len(spy_days)
    print(f"TSLA: {n_tsla} days, QQQ: {n_qqq} days, SPY: {n_spy} days")

    # Take the 60 most recent TSLA days, 30 most recent QQQ, 30 most recent SPY
    tsla_take = min(60, n_tsla)
    qqq_take = min(30, n_qqq)
    spy_take = min(30, n_spy)

    tsla_selected = tsla_days[-tsla_take:]
    qqq_selected = qqq_days[-qqq_take:]
    spy_selected = spy_days[-spy_take:]

    print(f"TSLA selected: {tsla_selected[0]} .. {tsla_selected[-1]} ({len(tsla_selected)} days)")
    print(f"QQQ selected:  {qqq_selected[0]} .. {qqq_selected[-1]} ({len(qqq_selected)} days)")
    print(f"SPY selected:  {spy_selected[0]} .. {spy_selected[-1]} ({len(spy_selected)} days)")

    # ── 2. Load session candles + compute engine fire counts ──────────────
    # TSLA deck
    tsla_cards = []
    for day in tsla_selected:
        candles = _load_session_candles("TSLA", day)
        if not candles:
            print(f"  WARNING: TSLA {day} has no session candles, skipping")
            continue
        # Prior-day levels (from t4_engine_recall)
        from research.t4_engine_recall import prior_day_levels
        pdh, pdl, _pdo, _pdc = prior_day_levels("TSLA", day)
        tsla_cards.append(("TSLA", day, candles, pdh, pdl))

    print(f"TSLA deck: {len(tsla_cards)} usable days (wanted {tsla_take})")

    # QQQ + SPY deck (30 each, contiguous blocks)
    index_cards = []
    for day in qqq_selected:
        candles = _load_session_candles("QQQ", day)
        if not candles:
            print(f"  WARNING: QQQ {day} has no session candles, skipping")
            continue
        pdh, pdl, _pdo, _pdc = prior_day_levels("QQQ", day)
        index_cards.append(("QQQ", day, candles, pdh, pdl))

    for day in spy_selected:
        candles = _load_session_candles("SPY", day)
        if not candles:
            print(f"  WARNING: SPY {day} has no session candles, skipping")
            continue
        pdh, pdl, _pdo, _pdc = prior_day_levels("SPY", day)
        index_cards.append(("SPY", day, candles, pdh, pdl))

    print(f"Index deck: {len(index_cards)} usable days (wanted 60)")

    # ── 3. Engine fire counts ─────────────────────────────────────────────
    # Run the engine on each (symbol, day) and record fire counts.
    # This modifies signal_runner module-level flags, so we need to save/restore.
    manifest_rows = []

    all_cards = tsla_cards + index_cards
    print(f"\nComputing engine fire counts for {len(all_cards)} days...")
    for idx, (symbol, day, _candles, _pdh, _pdl) in enumerate(all_cards):
        count = _engine_fire_count(symbol, day)
        deck = "tsla" if symbol == "TSLA" else "index"
        manifest_rows.append({
            "card_id": f"{symbol}_{day}",
            "symbol": symbol,
            "date": day,
            "deck": deck,
            "engine_fires_that_day": count,
        })
        if (idx + 1) % 20 == 0:
            print(f"  {idx + 1}/{len(all_cards)} done (last: {symbol}_{day} fires={count})")

    # ── 4. Write manifest ─────────────────────────────────────────────────
    with open(MANIFEST, "w", encoding="utf-8") as f:
        for row in manifest_rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    print(f"\nWrote {MANIFEST} ({len(manifest_rows)} rows)")

    # ── 5. Build HTML decks ───────────────────────────────────────────────
    build_deck(tsla_cards, "TSLA — 60 days", TSLA_DECK)
    build_deck(index_cards, "QQQ/SPY — 60 days", INDEX_DECK)

    # ── 6. Summary ────────────────────────────────────────────────────────
    tsla_fires = sum(r["engine_fires_that_day"] for r in manifest_rows
                     if r["symbol"] == "TSLA")
    qqq_fires = sum(r["engine_fires_that_day"] for r in manifest_rows
                    if r["symbol"] == "QQQ")
    spy_fires = sum(r["engine_fires_that_day"] for r in manifest_rows
                    if r["symbol"] == "SPY")
    print(f"\n=== Summary ===")
    print(f"TSLA: {len(tsla_cards)} cards, {tsla_fires} engine fires across all days")
    print(f"QQQ:  {len(qqq_selected)} days selected, {qqq_fires} engine fires")
    print(f"SPY:  {len(spy_selected)} days selected, {spy_fires} engine fires")


if __name__ == "__main__":
    main()