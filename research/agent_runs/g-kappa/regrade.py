"""g-kappa blind re-grade deck: 40 v7 signals (20 S / 20 not-S), shuffled
(seed 7), rendered with eye_card/chart.py cut at the signal bar, and sent as
the existing S / Not S ntfy card with id KAPPA-<n>. Symbol, date and his
old grade are hidden from the card; the answer key stays on disk (key.csv).

PAPER / research only. Nothing here places an order.

  python research/agent_runs/g-kappa/regrade.py                 # render 40 PNGs + key.csv
  python research/agent_runs/g-kappa/regrade.py --dry-run-labels deck/labels_dryrun.csv
  python research/agent_runs/g-kappa/regrade.py --send          # push the 40 cards
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from eye_card.chart import Candidate, render_candidate_chart  # noqa: E402
from eye_card.labels import append_label  # noqa: E402

V7_SRC = "austin_marks_v7.jsonl"
_ST = Path("research") / "agent_runs" / "eye1" / "s_trades.csv"  # untracked; main checkout holds it
S_TRADES = next((p for p in (ROOT / _ST, ROOT.parent / "tradingbot" / _ST) if p.exists()), ROOT / _ST)
DECK = HERE / "deck"


def data_archive() -> Path:
    env = os.environ.get("OMEN_DATA_ARCHIVE")
    for p in ([Path(env)] if env else []) + [ROOT / "data_archive",
                                              ROOT.parent / "tradingbot" / "data_archive"]:
        if p.is_dir():
            return p
    raise FileNotFoundError("data_archive not found; set OMEN_DATA_ARCHIVE")


def binary(grade: str) -> str:
    return "S" if grade.strip() == "S" else "notS"


def pick(rows: list[dict], n_each: int = 20, seed: int = 7) -> list[dict]:
    """v7 marks with bars, one row per sig_id, n_each S + n_each not-S, shuffled.
    Returns rows with kappa_id KAPPA-01.. in show order."""
    seen, pool = set(), {"S": [], "notS": []}
    for r in sorted(rows, key=lambda r: r["sig_id"]):
        if r.get("mark_src") != V7_SRC or str(r.get("has_bars")) != "1" or r["sig_id"] in seen:
            continue
        seen.add(r["sig_id"])
        pool[binary(r["grade"])].append(r)
    rng = random.Random(seed)
    if min(len(pool["S"]), len(pool["notS"])) < n_each:
        raise ValueError(f"need {n_each} per class, have S={len(pool['S'])} notS={len(pool['notS'])}")
    deck = rng.sample(pool["S"], n_each) + rng.sample(pool["notS"], n_each)
    rng.shuffle(deck)
    width = len(str(len(deck)))
    return [dict(r, kappa_id=f"KAPPA-{i:0{width}d}", prior=binary(r["grade"]))
            for i, r in enumerate(deck, 1)]


def load_bars(archive: Path, sym: str, day: str) -> list[dict]:
    out = []
    with open(archive / sym / f"{day}.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t = r["Datetime"][11:19]
            if not ("09:30:00" <= t <= "16:00:00"):
                continue
            try:
                out.append(dict(time=t, open=float(r["Open"]), high=float(r["High"]),
                                low=float(r["Low"]), close=float(r["Close"])))
            except ValueError:
                pass
    return out


def _f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def to_candidate(r: dict, bars: list[dict]) -> Candidate:
    """Blind card: no symbol, no date, no grade, no engine tags."""
    trig = r["sig_t"] + ":00"
    sig_bar = next(b for b in bars if b["time"] == trig)
    d = 1 if r["side"] == "L" else -1
    entry = sig_bar["close"]
    stop = _f(r.get("eng_stop"))
    if stop is None or (entry - stop) * d <= 0:
        stop = sig_bar["low"] if d > 0 else sig_bar["high"]
    risk = abs(entry - stop) or 0.01
    return Candidate(
        candidate_id=r["kappa_id"], symbol="BLIND", direction="LONG" if d > 0 else "SHORT",
        trigger_time=trig, entry=round(entry, 4), stop=round(stop, 4),
        targets=[round(entry + d * k * risk, 4) for k in (1, 2)],
        level=_f(r.get("level_px"), entry), level_label="Level", setup="re-grade",
        reason="S or not S?", or_high=_f(r.get("orh15")), or_low=_f(r.get("orl15")))


KEY_FIELDS = ["kappa_id", "sig_id", "prior", "grade", "sym", "date", "sig_t", "side", "png"]


def build(out: Path = DECK, s_trades: Path = S_TRADES, archive: Path | None = None,
          seed: int = 7, n_each: int = 20):
    archive = archive or data_archive()
    with open(s_trades, encoding="utf-8") as fh:
        deck = pick(list(csv.DictReader(fh)), n_each=n_each, seed=seed)
    out.mkdir(parents=True, exist_ok=True)
    cards = []
    for r in deck:
        bars = load_bars(archive, r["sym"], r["date"])
        cand = to_candidate(r, bars)
        png = render_candidate_chart(cand, bars, out / f"{r['kappa_id']}.png")
        r["png"] = png.name
        cards.append((cand, png))
    with open(out / "key.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=KEY_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(deck)
    return deck, cards


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DECK)
    ap.add_argument("--s-trades", type=Path, default=S_TRADES)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--dry-run-labels", type=Path, help="write 40 all-agree label rows here (no send)")
    ap.add_argument("--send", action="store_true", help="push the cards to ntfy")
    ap.add_argument("--gap", type=float, default=3.0, help="seconds between pushes")
    ap.add_argument("--token", default=os.environ.get("EYE_LABEL_TOKEN", "dev-local-only"))
    a = ap.parse_args(argv)
    deck, cards = build(a.out, a.s_trades, seed=a.seed)
    print(f"deck: {len(cards)} PNGs, S={sum(r['prior'] == 'S' for r in deck)} -> {a.out}")
    if a.dry_run_labels:
        if a.dry_run_labels.exists():
            a.dry_run_labels.unlink()
        for r in deck:
            append_label(a.dry_run_labels, r["kappa_id"], r["prior"], source_ip="dry-run")
        print(f"dry-run labels: {len(deck)} rows -> {a.dry_run_labels}")
    if a.send:
        from eye_card.notify import send_card
        for i, (cand, png) in enumerate(cards, 1):
            res = send_card(cand, png, a.token, test_title_prefix=f"KAPPA {i}/{len(cards)}")
            print(cand.candidate_id, res.status_code)
            time.sleep(a.gap)


if __name__ == "__main__":
    main()
