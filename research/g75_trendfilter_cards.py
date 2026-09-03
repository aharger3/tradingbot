"""g75_trendfilter_cards.py -- step 1 and 2 of the trendfilter track.

1. Reproduce the finding: session trendiness 0.145 (his yes) vs 0.072 (his no),
   p=0.014, on the 30 cards of
   research/marks/probe_g71_homework_s3_2026-08-29_complete.jsonl -- from bars,
   not by re-reading the manifest's cached number.
2. Ask the only question that matters for trading: how much of that separation
   survives when the score may only use bars that exist BEFORE the trade?

Mark file is opened read-only. Writes research/g75_trendfilter_cards.json.
"""
from __future__ import annotations
import json, os, random, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import g75_trendfilter_lib as L  # noqa: E402

MARKS = os.path.join(HERE, "marks", "probe_g71_homework_s3_2026-08-29_complete.jsonl")
MANI = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")
OUT = os.path.join(HERE, "g75_trendfilter_cards.json")
RNG = random.Random(751)


def mean(x):
    return sum(x) / len(x) if x else float("nan")


def mww(a, b, iters=20000):
    """Mann-Whitney AUC + exact-ish permutation p. Same routine g74 used."""
    def U(x, y):
        return sum(1.0 if xi > yi else (0.5 if xi == yi else 0.0) for xi in x for yi in y)
    obs = U(a, b) / (len(a) * len(b))
    pool = list(a) + list(b); na = len(a); hit = 0
    for _ in range(iters):
        RNG.shuffle(pool)
        v = U(pool[:na], pool[na:]) / (na * (len(pool) - na))
        if abs(v - 0.5) >= abs(obs - 0.5) - 1e-12:
            hit += 1
    return obs, (hit + 1) / (iters + 1)


marks = [json.loads(l) for l in open(MARKS, encoding="utf-8") if l.strip()]
mani = {json.loads(l)["card_id"]: json.loads(l) for l in open(MANI, encoding="utf-8") if l.strip()}
cards = []
for m in marks:
    r = dict(mani[m["card_id"]])
    r["yes"] = 1 if m["answers"]["is_s"][0] == "yes" else 0
    r["why_not"] = (m["answers"].get("why_not") or [])
    r["note"] = " ".join(str(v) for v in (m.get("notes") or {}).values())
    cards.append(r)
assert len(cards) == 30, len(cards)
OUTJ = {"n_cards": len(cards), "n_yes": sum(c["yes"] for c in cards)}

print("=" * 84)
print("1. REPRODUCING THE FINDING FROM BARS")
print("=" * 84)
drift = []
for c in cards:
    v = L.er_session(c["symbol"], c["date"])
    c["er_session"] = v
    cached = c["prefilter"]["er_session"]
    drift.append(abs(v - cached))
print("  recomputed er_session for all 30 cards straight off data_archive.")
print("  worst disagreement with the manifest's cached value: %.6f" % max(drift))
yes = [c["er_session"] for c in cards if c["yes"]]
no = [c["er_session"] for c in cards if not c["yes"]]
auc, p = mww(yes, no)
print("  his YES days  mean ER %.4f  (n=%d)" % (mean(yes), len(yes)))
print("  his NO  days  mean ER %.4f  (n=%d)" % (mean(no), len(no)))
print("  AUC %.3f   permutation p = %.4f   <- g74 reported 0.145 / 0.072 / p=0.014"
      % (auc, p))
srt = sorted(cards, key=lambda c: c["er_session"])
for lab, g in (("10 CHOPPIEST", srt[:10]), ("10 middle", srt[10:20]), ("10 TRENDIEST", srt[20:])):
    print("    %-14s he said yes to %2d of 10   (ER %.3f - %.3f)"
          % (lab, sum(c["yes"] for c in g), g[0]["er_session"], g[-1]["er_session"]))
OUTJ["repro"] = {"yes_mean": mean(yes), "no_mean": mean(no), "auc": auc, "p": p,
                 "max_drift_vs_manifest": max(drift)}

print()
print("  his own words on the cards he refused:")
ch = [c for c in cards if not c["yes"]
      and ("chop" in c["why_not"] or "chop" in c["note"].lower())]
for c in ch:
    print("    %-20s ER %.3f  tags %-24s \"%s\"" % (c["card_id"], c["er_session"], ",".join(c["why_not"]), c["note"][:52]))
print("  'chop' cards mean ER %.4f vs all-30 mean %.4f"
      % (mean([c["er_session"] for c in ch]), mean([c["er_session"] for c in cards])))
OUTJ["chop_cards"] = {c["card_id"]: c["er_session"] for c in ch}

print()
print("=" * 84)
print("2. THE SAME TEST, BUT THE SCORE MAY ONLY SEE BARS FROM BEFORE THE TRADE")
print("=" * 84)
print("  %-24s %-9s %8s %8s %7s %8s" % ("score", "known at", "yes", "no", "AUC", "p"))
res = {}
FAM = [("er_session_0930_1100", L.HINDSIGHT, "11:00 (!)"),
       *[(k, L.CAUSAL_0929, "09:29") for k in L.CAUSAL_0929],
       *[(k, L.CAUSAL_LATER, "later") for k in L.CAUSAL_LATER]]
for name, fam, when in FAM:
    fn = fam[name]
    vals = [(c, fn(c["symbol"], c["date"], c.get("et"))) for c in cards]
    ok = [(c, v) for c, v in vals if v is not None]
    a = [v for c, v in ok if c["yes"]]
    b = [v for c, v in ok if not c["yes"]]
    if len(a) < 4 or len(b) < 4:
        print("  %-24s %-9s  too few scoreable cards (%d/%d)" % (name, when, len(a), len(b)))
        continue
    auc, p = mww(a, b)
    res[name] = {"known_at": when, "n": len(ok), "yes": mean(a), "no": mean(b),
                 "auc": auc, "p": p}
    print("  %-24s %-9s %8.4f %8.4f %7.3f %8.4f %s"
          % (name, when, mean(a), mean(b), auc, p, "**" if p < 0.05 else ""))
    for c, v in ok:
        c[name] = v
OUTJ["scores"] = res
OUTJ["cards"] = [{k: c.get(k) for k in
                  ["card_id", "symbol", "date", "bucket", "et", "yes", "er_session",
                   *L.CAUSAL_0929, *L.CAUSAL_LATER]} for c in cards]
json.dump(OUTJ, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
print("\nwrote %s" % OUT)
