"""Score the blind re-grade: Cohen's kappa between the original v7 grade
(S vs not-S, from manifest.json) and Austin's fresh taps (labels.csv).
Last tap per card wins; cards not yet tapped are reported, not guessed.

    python -m eye_card.regrade.kappa
    python -m eye_card.regrade.kappa --labels eye_card/labels.csv --deck research/agent_runs/regrade-deck
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .build_deck import OUT

DEFAULT_LABELS = Path(__file__).resolve().parents[1] / "labels.csv"


def load_taps(labels_csv: Path, card_ids: set[str]) -> dict[str, str]:
    taps: dict[str, str] = {}
    if not Path(labels_csv).exists():
        return taps
    with open(labels_csv, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("candidate_id") in card_ids and r.get("label") in ("S", "notS"):
                taps[r["candidate_id"]] = r["label"]  # file is append-order: last wins
    return taps


def cohen_kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    if n == 0:
        return float("nan")
    po = sum(a == b for a, b in pairs) / n
    cats = {"S", "notS"}
    pe = sum((sum(a == c for a, _ in pairs) / n) * (sum(b == c for _, b in pairs) / n)
             for c in cats)
    if pe == 1.0:
        return 1.0 if po == 1.0 else float("nan")
    return (po - pe) / (1 - pe)


def score(manifest: dict, taps: dict[str, str]) -> dict:
    orig = {c["card_id"]: c["orig_bin"] for c in manifest["cards"]}
    pairs = [(orig[k], taps[k]) for k in orig if k in taps]
    n = len(pairs)
    return {
        "n_cards": len(orig),
        "n_answered": n,
        "missing": sorted(k for k in orig if k not in taps),
        "kappa": cohen_kappa(pairs),
        "agreement_pct": (100.0 * sum(a == b for a, b in pairs) / n) if n else float("nan"),
        "S_to_notS": sum(a == "S" and b == "notS" for a, b in pairs),
        "notS_to_S": sum(a == "notS" and b == "S" for a, b in pairs),
    }


def report(res: dict) -> str:
    lines = [
        f"answered {res['n_answered']}/{res['n_cards']}",
        f"kappa {res['kappa']:.3f}",
        f"agreement {res['agreement_pct']:.1f}%",
        f"flips S->notS {res['S_to_notS']}  notS->S {res['notS_to_S']}",
    ]
    if res["missing"]:
        lines.append(f"missing {len(res['missing'])}: {' '.join(res['missing'])}")
    return "\n".join(lines)


def main(labels: Path = DEFAULT_LABELS, deck: Path = OUT) -> dict:
    manifest = json.loads((Path(deck) / "manifest.json").read_text(encoding="utf-8"))
    ids = {c["card_id"] for c in manifest["cards"]}
    res = score(manifest, load_taps(labels, ids))
    print(report(res))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    ap.add_argument("--deck", type=Path, default=OUT)
    a = ap.parse_args()
    main(a.labels, a.deck)
