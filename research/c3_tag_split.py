"""C3 tag-performance split + skip-tag stacking test.

Per-tag split (full-pop + within-tier) for [disp]/[nodisp]/[chase]/[vwap-] on
the latest 12mo baseline (research/c1_off_charts.json = b4_baseline_charts.json,
671 traded / 866 signals). Stacking test: S>=4+[hammer] tier baseline vs tier +
skip-tag variants and combinations.

[vwap-] was REMOVED 2026-07-11 (signal_runner:354) -> 0 occurrences in data;
skip-[vwap-] is a no-op, reported as such.

Reuses b4_analyze.py gstats + tier_sim logic verbatim (S>=4 + hammer, max 2/day,
stop-when-green).
Usage: py -3.13 c3_tag_split.py
"""
import json, re
from collections import defaultdict

CHARTS = "research/c1_off_charts.json"
TAGS = ["[disp]", "[nodisp]", "[chase]", "[vwap-]"]


def load_all(path):
    return json.load(open(path))


def s_score(rec):
    m = re.search(r" S(\d+)", rec["reason"])
    return int(m.group(1)) if m else None


def is_hammer(rec):
    c = rec["candles"][rec["entry_i"]]
    body = abs(c["c"] - c["o"]); rng = c["h"] - c["l"]
    if rng == 0:
        return False
    if rec["direction"] == "call":
        return min(c["o"], c["c"]) - c["l"] >= body and c["c"] >= c["l"] + 0.5 * rng
    return c["h"] - max(c["o"], c["c"]) >= body and c["c"] <= c["h"] - 0.5 * rng


def has_tag(rec, tag):
    return tag in rec["reason"]


def gstats(recs):
    counted = [r for r in recs if not r["alert_only"]]
    w = sum(1 for r in counted if r["outcome"] == "win")
    l = sum(1 for r in counted if r["outcome"] == "loss")
    pnl = sum(r["pnl"] for r in counted)
    wr = w / (w + l) * 100 if (w + l) else 0.0
    return len(counted), w, l, pnl, wr


def tier_sim(recs, min_s=4, max_n=2, skip_tags=None):
    """S>=4+hammer tier, max 2/day, stop-when-green. skip_tags = set of tags
    whose signals are refused at the tier gate (stacking test)."""
    skip_tags = skip_tags or set()
    recs = [r for r in recs if not r["alert_only"]]
    byday = defaultdict(list)
    for r in recs:
        byday[r["day"]].append(r)
    tot = w = n = 0
    taken_ids = []  # (id(rec), pnl, outcome, tag-string) for within-tier split
    for day, rs in byday.items():
        rs.sort(key=lambda r: r["candles"][r["entry_i"]]["t"])
        taken = pnl_day = 0
        for r in rs:
            if taken >= max_n or pnl_day > 0:
                break
            s = s_score(r)
            if s is None or s < min_s or not is_hammer(r):
                continue
            if any(has_tag(r, t) for t in skip_tags):
                continue
            taken += 1; n += 1; pnl_day += r["pnl"]; tot += r["pnl"]
            w += r["outcome"] == "win"
            taken_ids.append(r)
    wr = w / n * 100 if n else 0.0
    return n, wr, tot, taken_ids


def main():
    recs = load_all(CHARTS)
    n, w, l, pnl, wr = gstats(recs)
    print("# C3 — tag split + skip-tag stacking (baseline 12mo)")
    print(f"Baseline: {n} traded  {w}W {l}L  {wr:.1f}%W  ${pnl:,.0f}  (866 signals incl alert-only)\n")

    # --- per-tag split, full population (traded only) ---
    print("## Per-tag split — full population (traded A+/A/B only)")
    print(f"{'tag':10} {'trades':>6} {'W':>4} {'L':>4} {'win%':>6} {'P&L':>10}")
    for t in TAGS:
        sub = [r for r in recs if not r["alert_only"] and has_tag(r, t)]
        n2, w2, l2, p2, wr2 = gstats(sub)
        print(f"{t:10} {n2:>6} {w2:>4} {l2:>4} {wr2:>5.1f}% ${p2:>9,.0f}")
    # complement (tag absent) for context
    print(f"{'(no tag)':10}  -- context: [disp]+[nodisp] partition all traded; [chase] is a subset tag\n")

    # --- within-tier per-tag split: among trades the tier actually takes ---
    tn, twr, tpnl, taken = tier_sim(recs)
    print("## Per-tag split — within tier (S>=4+[hammer] tier, n=%d)" % tn)
    print(f"{'tag':10} {'of-tier':>7} {'W':>4} {'L':>4} {'win%':>6} {'P&L':>9}")
    for t in TAGS:
        sub = [r for r in taken if has_tag(r, t)]
        w2 = sum(1 for r in sub if r["outcome"] == "win")
        l2 = sum(1 for r in sub if r["outcome"] == "loss")
        p2 = sum(r["pnl"] for r in sub)
        wr2 = w2 / (w2 + l2) * 100 if (w2 + l2) else 0.0
        print(f"{t:10} {len(sub):>7} {w2:>4} {l2:>4} {wr2:>5.1f}% ${p2:>8,.0f}")
    print()

    # --- stacking test: baseline tier vs tier + skip-tag(s) ---
    print("## Stacking test — tier (S>=4+[hammer]) vs tier + skip-tag")
    print(f"{'config':38} {'tr/yr':>5} {'win%':>6} {'$/yr':>9}")
    configs = [
        ("tier baseline (S-score alone)", set()),
        ("tier + skip-[nodisp]", {"[nodisp]"}),
        ("tier + skip-[disp]", {"[disp]"}),
        ("tier + skip-[chase]", {"[chase]"}),
        ("tier + skip-[vwap-]  (no-op)", {"[vwap-]"}),
        ("tier + skip-[nodisp]+[chase]", {"[nodisp]", "[chase]"}),
        ("tier + skip-[disp]+[chase]", {"[disp]", "[chase]"}),
        ("tier + skip-[nodisp]+[disp]  (=kill B&R)", {"[nodisp]", "[disp]"}),
    ]
    rows = []
    for label, sk in configs:
        n2, wr2, p2, _ = tier_sim(recs, skip_tags=sk)
        rows.append((label, n2, wr2, p2))
        print(f"{label:38} {n2:>5} {wr2:>5.1f}% ${p2:>8,.0f}")

    # verdict
    base = rows[0]
    print("\n## Verdict")
    winners = [r for r in rows[1:] if r[2] > base[2] and r[3] > base[3]]
    if winners:
        print("YES — skip-tag stack beats S-score alone on BOTH win% and $/yr:")
        for label, n2, wr2, p2 in winners:
            print(f"  {label}: {n2} tr  {wr2:.1f}%W (vs {base[2]:.1f}%)  ${p2:,.0f}/yr (vs ${base[3]:,.0f})")
    else:
        print("NO — no skip-tag stack beats S-score alone on BOTH win% and $/yr.")
        print("Best $/yr:")
        best = max(rows[1:], key=lambda r: r[3])
        print(f"  {best[0]}: {best[1]} tr  {best[2]:.1f}%W  ${best[3]:,.0f}/yr "
              f"(base {base[1]} tr  {base[2]:.1f}%W  ${base[3]:,.0f})")


if __name__ == "__main__":
    main()
