"""Build the blind re-grade deck: 40 v7 signals (20 S / 20 not-S), shuffled,
rendered with eye_card.chart cropped at the trigger bar, no grade anywhere
on the card. The original grade lives only in manifest.json.

Run:  python -m eye_card.regrade.build_deck            (writes research/agent_runs/regrade-deck/)

Paper only. Nothing here sends anything.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import random
from collections import defaultdict
from pathlib import Path

from ..chart import Candidate, render_candidate_chart

REPO = Path(__file__).resolve().parents[2]
_DS = Path("research") / "agent_runs" / "v3-s-dataset"
# the dataset is untracked (.git/info/exclude); a worktree falls back to the main checkout
DATASET = next((p for p in (REPO / _DS, REPO.parent / "tradingbot" / _DS) if p.exists()), REPO / _DS)
OUT = REPO / "research" / "agent_runs" / "regrade-deck"
V7_SOURCE = "austin_marks_v7.jsonl"
EXCLUDE_SOURCE_WORDS = ("probe", "autopsy")
SEED = 20260927


def binarize(grade: str) -> str:
    return "S" if grade.strip() == "S" else "notS"


def eligible(rows: list[dict]) -> list[dict]:
    """v7 rows only (the mixed-grade source); never an S-only probe/autopsy source."""
    out = []
    for r in rows:
        src = r.get("mark_src", "")
        if any(w in src.lower() for w in EXCLUDE_SOURCE_WORDS):
            continue
        if src != V7_SOURCE:
            continue
        out.append(r)
    return out


def stratified_pick(rows: list[dict], n: int, rng: random.Random) -> list[dict]:
    """Round-robin over symbols (shuffled order, shuffled within symbol) so no
    single ticker dominates the n picks."""
    by_sym: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_sym[r["sym"]].append(r)
    syms = sorted(by_sym)
    rng.shuffle(syms)
    for s in syms:
        by_sym[s].sort(key=lambda r: r["sig_id"])
        rng.shuffle(by_sym[s])
    picked: list[dict] = []
    while len(picked) < n and any(by_sym[s] for s in syms):
        for s in syms:
            if by_sym[s] and len(picked) < n:
                picked.append(by_sym[s].pop())
    if len(picked) < n:
        raise ValueError(f"only {len(picked)} eligible rows, need {n}")
    return picked


def select_deck(rows: list[dict], n_per_bin: int = 20, seed: int = SEED) -> list[dict]:
    """20 S + 20 not-S, stratified by symbol, then shuffled together."""
    rng = random.Random(seed)
    pool = eligible(rows)
    s_rows = [r for r in pool if binarize(r["grade"]) == "S"]
    n_rows = [r for r in pool if binarize(r["grade"]) == "notS"]
    deck = stratified_pick(s_rows, n_per_bin, rng) + stratified_pick(n_rows, n_per_bin, rng)
    rng.shuffle(deck)
    return deck


def _f(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def to_candidate(card_id: str, row: dict, trig_bar: dict) -> Candidate:
    """Neutral card: symbol, side, level, OR box, entry at trigger close.
    setup/reason/candidate_id carry NO grade and NO sig_id."""
    long = row["side"].strip().upper() == "L"
    entry = trig_bar["close"]
    stop = _f(row.get("eng_stop"))
    if stop is None or (long and stop >= entry) or (not long and stop <= entry):
        stop = trig_bar["low"] if long else trig_bar["high"]
    risk = abs(entry - stop) or max(trig_bar["high"] - trig_bar["low"], 1e-4)
    target = entry + 2 * risk if long else entry - 2 * risk
    return Candidate(
        candidate_id=card_id,
        symbol=row["sym"],
        direction="LONG" if long else "SHORT",
        trigger_time=trig_bar["time"],
        entry=round(entry, 4),
        stop=round(stop, 4),
        targets=[round(target, 4)],
        level=_f(row.get("level_px"), entry),
        level_label="Level",
        setup="regrade",
        reason="",
        or_high=_f(row.get("orh15")),
        or_low=_f(row.get("orl15")),
    )


def load_bars(path: Path) -> dict[str, list[dict]]:
    bars: dict[str, list[dict]] = defaultdict(list)
    with gzip.open(path, "rt", newline="") as fh:
        for b in csv.DictReader(fh):
            bars[b["sig_id"]].append({
                "time": b["t"] + ":00", "open": float(b["o"]), "high": float(b["h"]),
                "low": float(b["l"]), "close": float(b["c"]),
            })
    for v in bars.values():
        v.sort(key=lambda b: b["time"])
    return bars


def build(dataset: Path = DATASET, out: Path = OUT, seed: int = SEED) -> dict:
    with open(dataset / "s_trades.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    bars = load_bars(dataset / "s_bars_0930_1100.csv.gz")
    deck = select_deck(rows, seed=seed)
    cards = []
    for i, row in enumerate(deck, start=1):
        card_id = f"RG0927-{i:02d}"
        trig_t = row["sig_t"] + ":00"
        day = bars[row["sig_id"]]
        trig = next(b for b in day if b["time"] == trig_t)
        cand = to_candidate(card_id, row, trig)
        png = out / "cards" / f"{card_id}.png"
        render_candidate_chart(cand, day, png)
        cards.append({
            "card_id": card_id, "n": i, "png": f"cards/{card_id}.png",
            "sig_id": row["sig_id"], "grade_orig": row["grade"],
            "orig_bin": binarize(row["grade"]), "mark_src": row["mark_src"],
            "candidate": {k: getattr(cand, k) for k in (
                "symbol", "direction", "trigger_time", "entry", "stop", "targets",
                "level", "level_label", "setup", "reason", "or_high", "or_low")},
        })
    manifest = {
        "deck": "regrade-v7-2026-09-27", "seed": seed, "n": len(cards),
        "source": f"research/agent_runs/v3-s-dataset/s_trades.csv (mark_src={V7_SOURCE})",
        "note": "HIDDEN: grade_orig is the answer key. Never put it on a card.",
        "cards": cards,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--dataset", type=Path, default=DATASET)
    a = ap.parse_args()
    m = build(dataset=a.dataset, out=a.out, seed=a.seed)
    print(f"{m['n']} cards -> {a.out}")
