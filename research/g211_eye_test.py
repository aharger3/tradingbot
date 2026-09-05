"""
W9 score: does a model reading the chart reproduce Austin's S marks?

Inputs (all on disk under research/):
  g210_cards/index.json       - his grades, 100 cards (S vs none only in this deck)
  g211_reads_haiku.json       - Claude Haiku's independent read of the same 100 chart cards
  g211_reads_sonnet.json      - Claude Sonnet's independent read of the same 100 chart cards

For each model this prints:
  - confusion matrix, S vs not-S (his grade is S/A/C/none -> collapsed to S vs not-S)
  - precision and recall for S
  - raw agreement with his full S/A/C/none label
  - precision at the 30.5% graded-day S baseline (a naive "always guess S" classifier
    would hit 30.5% precision on a deck at that S rate; this deck's own S rate is
    reported alongside it since it need not equal 30.5%)
  - a bootstrap 95% band on precision (2000 resamples, seeded for reproducibility)
  - the 10 cards where BOTH models said S and he said none (false positives)
  - the 10 cards where he said S and BOTH models said none (misses)

No trade money, no fills, no market data touched -- this is a pure label-agreement
measurement, run once, no dependency on signal_runner/live_scanner/etc.
"""
import json
import random
import sys
from collections import Counter

BASELINE_PRECISION = 0.305  # the graded-day S baseline named in the row spec
N_BOOT = 2000
SEED = 1102025  # fixed so the printed band is reproducible


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def by_id(rows):
    return {r["card_id"]: r for r in rows}


def confusion(his, model):
    """his, model: dict card_id -> grade. Returns TP,FP,FN,TN counts for S vs not-S."""
    tp = fp = fn = tn = 0
    for cid, his_grade in his.items():
        his_s = his_grade == "S"
        model_s = model.get(cid, {}).get("grade") == "S"
        if his_s and model_s:
            tp += 1
        elif not his_s and model_s:
            fp += 1
        elif his_s and not model_s:
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


def precision_recall(tp, fp, fn):
    prec = tp / (tp + fp) if (tp + fp) else float("nan")
    rec = tp / (tp + fn) if (tp + fn) else float("nan")
    return prec, rec


def raw_agreement(his, model):
    n = len(his)
    match = sum(1 for cid, g in his.items() if model.get(cid, {}).get("grade") == g)
    return match, n


def bootstrap_precision_band(his, model, n_boot=N_BOOT, seed=SEED):
    """Bootstrap resample the card set (with replacement) and recompute S-precision
    each time; return (lo, hi) 2.5/97.5 percentiles. Cards with no model S-calls in
    a resample contribute no precision draw for that resample (skipped)."""
    rng = random.Random(seed)
    ids = list(his.keys())
    n = len(ids)
    draws = []
    for _ in range(n_boot):
        sample = [ids[rng.randrange(n)] for _ in range(n)]
        tp = fp = 0
        for cid in sample:
            his_s = his[cid] == "S"
            model_s = model.get(cid, {}).get("grade") == "S"
            if model_s:
                if his_s:
                    tp += 1
                else:
                    fp += 1
        if tp + fp > 0:
            draws.append(tp / (tp + fp))
    if not draws:
        return float("nan"), float("nan")
    draws.sort()
    lo = draws[int(0.025 * len(draws))]
    hi = draws[min(int(0.975 * len(draws)), len(draws) - 1)]
    return lo, hi


def find_false_positives(his, model_a, model_b, limit=10):
    """Both models said S, he said none."""
    out = []
    for cid, his_grade in his.items():
        if his_grade != "none":
            continue
        a = model_a.get(cid, {})
        b = model_b.get(cid, {})
        if a.get("grade") == "S" and b.get("grade") == "S":
            out.append((cid, a.get("reason", ""), b.get("reason", "")))
    return out[:limit]


def find_misses(his, model_a, model_b, limit=10):
    """He said S, both models said none."""
    out = []
    for cid, his_grade in his.items():
        if his_grade != "S":
            continue
        a = model_a.get(cid, {})
        b = model_b.get(cid, {})
        if a.get("grade") == "none" and b.get("grade") == "none":
            out.append((cid, a.get("reason", ""), b.get("reason", "")))
    return out[:limit]


def print_model_report(name, his, model):
    tp, fp, fn, tn = confusion(his, model)
    prec, rec = precision_recall(tp, fp, fn)
    match, n = raw_agreement(his, model)
    lo, hi = bootstrap_precision_band(his, model)

    print(f"\n=== {name} ===")
    print("Confusion matrix (S vs not-S), rows=his, cols=model:")
    print(f"{'':>14}{'model S':>10}{'model not-S':>14}")
    print(f"{'his S':>14}{tp:>10}{fn:>14}")
    print(f"{'his not-S':>14}{fp:>10}{tn:>14}")
    print(f"Precision (S): {prec:.3f}   Recall (S): {rec:.3f}")
    print(f"Raw label agreement (S/A/C/none, exact): {match}/{n} = {match/n:.3f}")
    print(f"Precision at 30.5% graded-day baseline: model={prec:.3f} vs baseline={BASELINE_PRECISION:.3f}"
          f"  ({'above' if prec > BASELINE_PRECISION else 'at/below'} baseline)")
    print(f"Bootstrap 95% band on precision (n={N_BOOT}): [{lo:.3f}, {hi:.3f}]")
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec, "recall": rec,
            "agreement": match / n, "boot_lo": lo, "boot_hi": hi}


def print_examples(title, rows, count):
    print(f"\n{title} ({count} shown of possibly fewer/more found):")
    if not rows:
        print("  (none found)")
        return
    for cid, reason_a, reason_b in rows:
        print(f"  {cid}")
        print(f"    haiku:  {reason_a[:200]}")
        print(f"    sonnet: {reason_b[:200]}")


def main():
    idx = load("research/g210_cards/index.json")
    his = {c["card_id"]: c["his_grade"] for c in idx}
    s_rate = sum(1 for g in his.values() if g == "S") / len(his)

    haiku_rows = load("research/g211_reads_haiku.json")
    sonnet_rows = load("research/g211_reads_sonnet.json")
    haiku = by_id(haiku_rows)
    sonnet = by_id(sonnet_rows)

    missing_h = set(his) - set(haiku)
    missing_s = set(his) - set(sonnet)
    if missing_h or missing_s:
        print(f"WARNING: missing cards - haiku:{len(missing_h)} sonnet:{len(missing_s)}", file=sys.stderr)

    print(f"Deck: research/g210_cards/index.json, {len(his)} cards, "
          f"his S rate in this deck = {s_rate:.3f} (named baseline is 30.5% across the full graded corpus)")

    print_model_report("Haiku", his, haiku)
    print_model_report("Sonnet", his, sonnet)

    fps = find_false_positives(his, haiku, sonnet, limit=10)
    misses = find_misses(his, haiku, sonnet, limit=10)
    print_examples("Both models said S, he said none (false positives)", fps, len(fps))
    print_examples("He said S, both models said none (misses)", misses, len(misses))


if __name__ == "__main__":
    main()
