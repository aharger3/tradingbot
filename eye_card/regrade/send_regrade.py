"""Push the blind re-grade deck to the phone via eye_card.notify, one card per
message titled 'REGRADE n/40 ...' with S / Not S buttons that hit the existing
label endpoint (eye_card.server -> labels.csv). No grade is ever sent.

Dry run (default) prints what would go out and touches no network:
    python -m eye_card.regrade.send_regrade
Real send (needs EYE_LABEL_TOKEN set and `python -m eye_card.server` running):
    python -m eye_card.regrade.send_regrade --send

Paper only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from ..chart import Candidate
from ..notify import send_card
from .build_deck import OUT


def load_manifest(deck: Path) -> dict:
    return json.loads((deck / "manifest.json").read_text(encoding="utf-8"))


def card_candidate(card: dict) -> Candidate:
    c = card["candidate"]
    return Candidate(candidate_id=card["card_id"], **c)


def run(deck: Path = OUT, *, send: bool = False, start: int = 1, sleep: float = 3.0,
        session=None, token: str | None = None, out=sys.stdout) -> int:
    m = load_manifest(deck)
    cards = sorted(m["cards"], key=lambda c: c["n"])
    total = len(cards)
    if send:
        token = token or os.environ.get("EYE_LABEL_TOKEN")
        if not token:
            raise SystemExit("EYE_LABEL_TOKEN not set; refusing to send")
    sent = 0
    for card in cards:
        if card["n"] < start:
            continue
        prefix = f"REGRADE {card['n']}/{total}"
        cand = card_candidate(card)
        png = deck / card["png"]
        if not send:
            print(f"[dry] {prefix} {cand.symbol} {cand.direction} -> {png.name}", file=out)
            continue
        res = send_card(cand, png, token, session=session, test_title_prefix=prefix)
        print(f"{prefix} {card['card_id']} ok={res.ok} status={res.status_code}", file=out)
        if not res.ok:
            print(f"stopped; resume with --start {card['n']}", file=out)
            return sent
        sent += 1
        if sleep:
            time.sleep(sleep)
    return sent


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", type=Path, default=OUT)
    ap.add_argument("--send", action="store_true", help="actually push to ntfy")
    ap.add_argument("--start", type=int, default=1, help="resume from card n")
    ap.add_argument("--sleep", type=float, default=3.0)
    a = ap.parse_args()
    run(a.deck, send=a.send, start=a.start, sleep=a.sleep)
