"""g-kappa: join his blind KAPPA-<n> taps (eye_card/labels.csv) to the answer key
(deck/key.csv -> s_trades.csv grade) and report Cohen's kappa + a label-noise
estimate eta. Research only.

eta model: each grade is an independent noisy copy of a latent truth with a
symmetric flip rate eta. Two copies agree with p_o = (1-eta)^2 + eta^2, so
eta = (1 - sqrt(2 p_o - 1)) / 2. With the balanced 20/20 deck kappa ~ (1-2 eta)^2.

  python research/agent_runs/g-kappa/kappa.py [--labels eye_card/labels.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
KEY = HERE / "deck" / "key.csv"
LABELS = ROOT / "eye_card" / "labels.csv"
_ST = Path("research") / "agent_runs" / "eye1" / "s_trades.csv"  # untracked; main checkout holds it
S_TRADES = next((p for p in (ROOT / _ST, ROOT.parent / "tradingbot" / _ST) if p.exists()), ROOT / _ST)


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("need two equal, non-empty label lists")
    cats = sorted(set(a) | set(b))
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def eta_from_agreement(po: float) -> float:
    return (1 - math.sqrt(max(2 * po - 1, 0.0))) / 2


def join(labels_path: Path, key_path: Path, s_trades_path: Path | None = None) -> list[dict]:
    """Last tap per KAPPA id wins. Old grade comes from s_trades by sig_id when
    available, else from the key's own prior column."""
    with open(key_path, encoding="utf-8") as fh:
        key = {r["kappa_id"]: r for r in csv.DictReader(fh)}
    grade = {}
    if s_trades_path and Path(s_trades_path).exists():
        with open(s_trades_path, encoding="utf-8") as fh:
            grade = {r["sig_id"]: ("S" if r["grade"].strip() == "S" else "notS")
                     for r in csv.DictReader(fh)}
    taps = {}
    with open(labels_path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["candidate_id"] in key:
                taps[r["candidate_id"]] = r["label"]
    return [dict(kappa_id=k, sig_id=key[k]["sig_id"], old=grade.get(key[k]["sig_id"], key[k]["prior"]),
                 new=taps[k]) for k in sorted(taps)]


def stats(pairs: list[dict], boot: int = 2000, seed: int = 7) -> dict:
    old, new = [p["old"] for p in pairs], [p["new"] for p in pairs]
    n = len(pairs)
    po = sum(x == y for x, y in zip(old, new)) / n
    k = cohen_kappa(old, new)
    rng = random.Random(seed)
    ks, es = [], []
    for _ in range(boot):
        idx = [rng.randrange(n) for _ in range(n)]
        o, w = [old[i] for i in idx], [new[i] for i in idx]
        ks.append(cohen_kappa(o, w))
        es.append(eta_from_agreement(sum(x == y for x, y in zip(o, w)) / n))
    ks.sort(); es.sort()
    lo, hi = int(0.025 * boot), int(0.975 * boot) - 1
    eta = eta_from_agreement(po)
    if eta <= 0.15:
        verdict = "eta<=.15: tap on - QBC order, ~190 taps (g/label-efficiency step 2)"
    elif eta >= 0.25:
        verdict = "eta~.3: stop tapping for the model - change features first (~1,000 taps otherwise)"
    else:
        verdict = "eta .15-.25: grey zone - ~400-1,000 taps; add features before QBC"
    table = {f"{a}->{b}": sum(1 for x, y in zip(old, new) if (x, y) == (a, b))
             for a in ("S", "notS") for b in ("S", "notS")}
    return dict(n=n, agreement=round(po, 3), kappa=round(k, 3),
                kappa_ci95=[round(ks[lo], 3), round(ks[hi], 3)], eta=round(eta, 3),
                eta_ci95=[round(es[lo], 3), round(es[hi], 3)], table=table, verdict=verdict)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, default=LABELS)
    ap.add_argument("--key", type=Path, default=KEY)
    ap.add_argument("--s-trades", type=Path, default=S_TRADES)
    ap.add_argument("--out", type=Path, default=HERE / "kappa_results.json")
    a = ap.parse_args(argv)
    pairs = join(a.labels, a.key, a.s_trades)
    if not pairs:
        print("no KAPPA taps yet"); return 1
    res = stats(pairs)
    a.out.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
