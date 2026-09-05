"""W9 -- the vision eye-test score.

Reads his grades (research/g210_cards/index.json, his_grade) against two model reader sets
(research/g211_reads_haiku.json, research/g211_reads_sonnet.json -- Claude Haiku and Claude
Sonnet, each independently reading the same 100 blind PNG charts cut at the entry bar and
grading S/A/C/none off the rulebook digest). Question: does a model reading the chart alone
reproduce his S marks, at or above the 30.5% graded-day precision baseline named in the spec
(omen-9-0-spec.md W9)?

Usage: python research/g211_eye_test.py
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX_PATH = ROOT / "g210_cards" / "index.json"
HAIKU_PATH = ROOT / "g211_reads_haiku.json"
SONNET_PATH = ROOT / "g211_reads_sonnet.json"

BASELINE_PRECISION = 0.305  # the 30.5% graded-day precision baseline named in the W9 spec row
N_BOOTSTRAP = 10000
SEED = 20260905


def load_his_grades():
    cards = json.load(open(INDEX_PATH, encoding="utf-8"))
    return {c["card_id"]: c["his_grade"] for c in cards}


def load_reads(path):
    rows = json.load(open(path, encoding="utf-8"))
    return {r["card_id"]: r for r in rows}


def confusion(his, model):
    """his, model: dict card_id -> grade. Returns confusion counts for S vs not-S."""
    tp = fp = fn = tn = 0
    for cid, his_grade in his.items():
        m = model.get(cid)
        m_grade = m["grade"] if m else "none"
        his_s = his_grade == "S"
        model_s = m_grade == "S"
        if his_s and model_s:
            tp += 1
        elif (not his_s) and model_s:
            fp += 1
        elif his_s and (not model_s):
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


def precision_recall(tp, fp, fn, tn):
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    return precision, recall


def full_agreement(his, model):
    """Exact S/A/C/none match rate against his ladder (model 'none' fills missing cards)."""
    n = len(his)
    agree = 0
    for cid, his_grade in his.items():
        m = model.get(cid)
        m_grade = m["grade"] if m else "none"
        if m_grade == his_grade:
            agree += 1
    return agree, n


def bootstrap_precision_band(his, model, n_boot=N_BOOTSTRAP, seed=SEED):
    """Bootstrap 95% CI on precision-for-S, resampling cards with replacement."""
    rng = random.Random(seed)
    card_ids = list(his.keys())
    n = len(card_ids)
    precisions = []
    for _ in range(n_boot):
        sample = [card_ids[rng.randrange(n)] for _ in range(n)]
        tp = fp = 0
        for cid in sample:
            his_s = his[cid] == "S"
            m = model.get(cid)
            m_grade = m["grade"] if m else "none"
            model_s = m_grade == "S"
            if model_s and his_s:
                tp += 1
            elif model_s and not his_s:
                fp += 1
        if tp + fp > 0:
            precisions.append(tp / (tp + fp))
    if not precisions:
        return (float("nan"), float("nan"))
    precisions.sort()
    lo = precisions[int(0.025 * len(precisions))]
    hi = precisions[min(int(0.975 * len(precisions)), len(precisions) - 1)]
    return lo, hi


def both_said_s_he_said_none(his, haiku, sonnet, limit=10):
    rows = []
    for cid, his_grade in his.items():
        h = haiku.get(cid)
        s = sonnet.get(cid)
        h_grade = h["grade"] if h else "none"
        s_grade = s["grade"] if s else "none"
        if his_grade == "none" and h_grade == "S" and s_grade == "S":
            rows.append({
                "card_id": cid,
                "haiku_reason": h.get("reason", ""),
                "sonnet_reason": s.get("reason", ""),
            })
    return rows[:limit]


def he_said_s_both_said_none(his, haiku, sonnet, limit=10):
    rows = []
    for cid, his_grade in his.items():
        h = haiku.get(cid)
        s = sonnet.get(cid)
        h_grade = h["grade"] if h else "none"
        s_grade = s["grade"] if s else "none"
        if his_grade == "S" and h_grade == "none" and s_grade == "none":
            rows.append({
                "card_id": cid,
                "haiku_reason": h.get("reason", ""),
                "sonnet_reason": s.get("reason", ""),
            })
    return rows[:limit]


def print_model_report(name, his, model):
    tp, fp, fn, tn = confusion(his, model)
    precision, recall = precision_recall(tp, fp, fn, tn)
    agree, n = full_agreement(his, model)
    lo, hi = bootstrap_precision_band(his, model)
    print(f"\n=== {name} ===")
    print("Confusion matrix (S vs not-S), n=%d cards" % len(his))
    print(f"  {'':>12}{'his S':>10}{'his not-S':>12}")
    print(f"  {'model S':>12}{tp:>10}{fp:>12}")
    print(f"  {'model not-S':>12}{fn:>10}{tn:>12}")
    print(f"precision (S) = {precision:.3f}  recall (S) = {recall:.3f}")
    print(f"exact S/A/C/none agreement with his ladder = {agree}/{n} = {agree/n:.3f}")
    print(f"baseline precision (30.5% graded-day) = {BASELINE_PRECISION:.3f}")
    print(f"delta vs baseline = {precision - BASELINE_PRECISION:+.3f}")
    print(f"bootstrap 95% band on precision (n={N_BOOTSTRAP}) = [{lo:.3f}, {hi:.3f}]")
    above_baseline = lo > BASELINE_PRECISION
    print(f"band clears baseline (lo > baseline)? {above_baseline}")
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall,
        "agree": agree, "n": n,
        "band": (lo, hi),
        "above_baseline": above_baseline,
    }


def main():
    his = load_his_grades()
    haiku = load_reads(HAIKU_PATH)
    sonnet = load_reads(SONNET_PATH)

    print("W9 eye-test: reading %d cards, %d marked S by Austin" % (
        len(his), sum(1 for g in his.values() if g == "S")))

    haiku_stats = print_model_report("Claude Haiku (reader)", his, haiku)
    sonnet_stats = print_model_report("Claude Sonnet (reader)", his, sonnet)

    print("\n=== 10 false positives: both models said S, he said none ===")
    fps = both_said_s_he_said_none(his, haiku, sonnet, limit=10)
    if not fps:
        print("(none -- no card had both models saying S while he said none)")
    for r in fps:
        print(f"- {r['card_id']}")
        print(f"    haiku:  {r['haiku_reason']}")
        print(f"    sonnet: {r['sonnet_reason']}")

    print("\n=== 10 misses: he said S, both models said none ===")
    misses = he_said_s_both_said_none(his, haiku, sonnet, limit=10)
    if not misses:
        print("(none -- no card had him saying S while both models said none)")
    for r in misses:
        print(f"- {r['card_id']}")
        print(f"    haiku:  {r['haiku_reason']}")
        print(f"    sonnet: {r['sonnet_reason']}")

    print("\n=== counts for the false-positive / miss tables (may exceed 10 shown) ===")
    print(f"both-S-he-none count = {len(both_said_s_he_said_none(his, haiku, sonnet, limit=10**6))}")
    print(f"he-S-both-none count = {len(he_said_s_both_said_none(his, haiku, sonnet, limit=10**6))}")


if __name__ == "__main__":
    main()
