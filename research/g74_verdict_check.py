"""g74_verdict_check.py -- adversarial re-test of the G7.4 headline.

CLAIM UNDER TEST
    "The one-candle rule is the engine's most accurate detector at 80%, and it is
     blocked from trading by gates rather than by bad detection."

Inputs, all read-only:
    research/marks/probe_g71_homework_s3_2026-08-29_complete.jsonl   30 answers
    research/decks/g71-homework-s3-manifest.jsonl                    what was served
    research/bt2y_trades.json                                        the 2-year book

Output: research/g74_verdict_check.json + the same tables on stdout.
Touches no engine code, no mark file, no book.

    python research/g74_verdict_check.py
"""
from __future__ import annotations
import json, math, os, random, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
MARKS = os.path.join(HERE, "marks", "probe_g71_homework_s3_2026-08-29_complete.jsonl")
MANI = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")
BOOK = os.path.join(HERE, "bt2y_trades.json")
OUT = os.path.join(HERE, "g74_verdict_check.json")

Z = 1.959963984540054
RNG = random.Random(74)
OUTJ = {}


def wilson(k, n, z=Z):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def newcombe(k1, n1, k2, n2, z=Z):
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    d = k1 / n1 - k2 / n2
    lo = d - z * math.sqrt(l1 * (1 - l1) / n1 + u2 * (1 - u2) / n2)
    hi = d + z * math.sqrt(u1 * (1 - u1) / n1 + l2 * (1 - l2) / n2)
    return d, lo, hi


def _lchoose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher2(a, b, c, d):
    n = a + b + c + d
    r1 = a + b
    c1 = a + c

    def pr(x):
        return math.exp(_lchoose(r1, x) + _lchoose(n - r1, c1 - x) - _lchoose(n, c1))

    obs = pr(a)
    tot = 0.0
    lo = max(0, c1 - (n - r1))
    hi = min(r1, c1)
    for x in range(lo, hi + 1):
        p = pr(x)
        if p <= obs * (1 + 1e-9):
            tot += p
    return min(1.0, tot)


def perm_diff_means(a, b, iters=100000):
    obs = sum(a) / len(a) - sum(b) / len(b)
    pool = list(a) + list(b)
    na = len(a)
    hit = 0
    for _ in range(iters):
        RNG.shuffle(pool)
        d = sum(pool[:na]) / na - sum(pool[na:]) / (len(pool) - na)
        if abs(d) >= abs(obs) - 1e-12:
            hit += 1
    return obs, (hit + 1) / (iters + 1)


def mww(a, b, iters=20000):
    def U(x, y):
        s = 0.0
        for xi in x:
            for yi in y:
                s += 1.0 if xi > yi else (0.5 if xi == yi else 0.0)
        return s

    obs = U(a, b) / (len(a) * len(b))
    pool = list(a) + list(b)
    na = len(a)
    hit = 0
    for _ in range(iters):
        RNG.shuffle(pool)
        v = U(pool[:na], pool[na:]) / (na * (len(pool) - na))
        if abs(v - 0.5) >= abs(obs - 0.5) - 1e-12:
            hit += 1
    return obs, (hit + 1) / (iters + 1)


def mean(x):
    return sum(x) / len(x) if x else float("nan")


def med(x):
    s = sorted(x)
    n = len(s)
    if not n:
        return float("nan")
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


# ---------------------------------------------------------------- load
marks = [json.loads(l) for l in open(MARKS, encoding="utf-8")]
mani = {json.loads(l)["card_id"]: json.loads(l) for l in open(MANI, encoding="utf-8")}
cards = []
for m in marks:
    r = dict(mani[m["card_id"]])
    r["yes"] = 1 if m["answers"]["is_s"][0] == "yes" else 0
    r["why"] = m["answers"].get("why_not", [])
    r["note"] = " ".join(str(v) for v in (m.get("notes") or {}).values())
    cards.append(r)
BUCKETS = ["OCR", "BR", "84"]
by_b = {b: [c for c in cards if c["bucket"] == b] for b in BUCKETS}
assert len(cards) == 30 and all(len(v) == 10 for v in by_b.values())

print("=" * 78)
print("1. PRECISION AND ITS ERROR BAR  (independent reimplementation)")
print("=" * 78)
prec = {}
for b in BUCKETS + ["ALL"]:
    g = cards if b == "ALL" else by_b[b]
    k = sum(c["yes"] for c in g)
    n = len(g)
    lo, hi = wilson(k, n)
    prec[b] = dict(k=k, n=n, p=k / n, lo=lo, hi=hi, width=hi - lo)
    print("  %-4s %2d/%2d = %5.1f%%   95%% CI [%4.1f, %4.1f]  width %4.1f pts"
          % (b, k, n, 100 * k / n, 100 * lo, 100 * hi, 100 * (hi - lo)))
pairs = {}
for x, y in (("OCR", "84"), ("OCR", "BR"), ("BR", "84"), ("OCR", "ALL")):
    gx = cards if x == "ALL" else by_b[x]
    gy = cards if y == "ALL" else by_b[y]
    kx, nx = sum(c["yes"] for c in gx), len(gx)
    ky, ny = sum(c["yes"] for c in gy), len(gy)
    d, lo, hi = newcombe(kx, nx, ky, ny)
    p = fisher2(kx, nx - kx, ky, ny - ky)
    tag = "%s-%s" % (x, y)
    pairs[tag] = dict(d=d, lo=lo, hi=hi, fisher=p)
    print("  %-8s diff %+5.1f pts  95%% CI [%+5.1f, %+5.1f]  Fisher p=%.3f  %s"
          % (tag, 100 * d, 100 * lo, 100 * hi, p,
             "SEPARATED" if (lo > 0 or hi < 0) else "NOT separated"))


def n_needed(p1, p2):
    za, zb = 1.959963984540054, 0.8416212335729143
    pb = (p1 + p2) / 2
    return math.ceil(((za * math.sqrt(2 * pb * (1 - pb))
                       + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2)
                     / ((p1 - p2) ** 2))


nn = n_needed(0.8, 0.6)
print("  to separate 80%% from 60%% at 95%%/80%%: n = %d PER ARM (%d more cards total)"
      % (nn, 3 * (nn - 10)))
OUTJ["precision"] = dict(arms=prec, pairs=pairs, n_needed_per_arm=nn)

print()
print("=" * 78)
print("2. DID HIS 'YES' TRACK THE MONEY?  (R of the signal each card was built from)")
print("=" * 78)


def rstats(g, label):
    rs = [c["r"] for c in g]
    wins = sum(1 for c in g if c["outcome"] == "win")
    opens = sum(1 for c in g if c["outcome"] == "open")
    ex = [c["r"] for c in g if abs(c["r"]) < 20]
    print("  %-24s n=%2d  meanR %+8.3f  medR %+6.3f  win %2d/%-2d  ex-tail meanR %+6.3f"
          % (label, len(g), mean(rs), med(rs), wins, len(g), mean(ex)))
    return dict(n=len(g), mean_r=mean(rs), median_r=med(rs), wins=wins,
                opens=opens, mean_r_ex_outlier=mean(ex), rs=rs)


money = {}
money["yes"] = rstats([c for c in cards if c["yes"]], "he said YES")
money["no"] = rstats([c for c in cards if not c["yes"]], "he said NO")
print()
for b in BUCKETS:
    money["arm_" + b] = rstats(by_b[b], "arm %s (all 10)" % b)
print()
for b in BUCKETS:
    money["armyes_" + b] = rstats([c for c in by_b[b] if c["yes"]], "arm %s, his YES only" % b)
ry = [c["r"] for c in cards if c["yes"]]
rn = [c["r"] for c in cards if not c["yes"]]
u, pu = mww(ry, rn)
print("\n  yes-vs-no rank test (tail-proof): P(R_yes > R_no) = %.3f, perm p = %.3f  -> %s"
      % (u, pu, "correlated" if pu < 0.05 else "NOT distinguishable"))
money["yes_vs_no_rank"] = dict(auc=u, p=pu)
rank_agree = sorted(BUCKETS, key=lambda b: -prec[b]["p"])
rank_money = sorted(BUCKETS, key=lambda b: -mean([c["r"] for c in by_b[b] if abs(c["r"]) < 20]))
print("  ranking by HIS AGREEMENT : %s" % " > ".join(rank_agree))
print("  ranking by THE MONEY     : %s" % " > ".join(rank_money))
money["rank_agreement"] = rank_agree
money["rank_money"] = rank_money
OUTJ["money"] = money

print()
print("=" * 78)
print("3. WERE THE OCR CARDS EASIER?  (confounds the arms do not share)")
print("=" * 78)


def arm_table(key, fn, fmt="%7.4f"):
    row = {b: mean([fn(c) for c in by_b[b]]) for b in BUCKETS}
    print(("  %-28s " + "  ".join("%s=" + fmt for _ in BUCKETS))
          % ((key,) + sum(((b, row[b]) for b in BUCKETS), ())))
    return row


conf = {}
conf["er_session"] = arm_table("session trendiness (ER)", lambda c: c["prefilter"]["er_session"])
conf["impulse_atr"] = arm_table("impulse / ATR", lambda c: c["prefilter"]["impulse_atr"])
conf["price"] = arm_table("level price ($)", lambda c: c["level_px"], "%7.1f")
conf["tripped"] = arm_table("engine downgrades tripped", lambda c: int(c["tripped"] or 0))
conf["n_s"] = arm_table("S signals that day", lambda c: c["s_signals_that_day"], "%7.2f")
conf["et_min"] = arm_table("engine entry (min after 9:30)",
                           lambda c: (int(c["et"][:2]) - 9) * 60 + int(c["et"][3:]) - 30, "%7.1f")
ETF = {"SPY", "QQQ", "IWM", "DIA"}
conf["etf_share"] = arm_table("index ETF share", lambda c: 1.0 if c["symbol"] in ETF else 0.0, "%7.2f")
print()
for b in BUCKETS:
    print("  %-4s symbols: %s" % (b, ", ".join(c["symbol"] for c in by_b[b])))

ery = [c["prefilter"]["er_session"] for c in cards if c["yes"]]
ern = [c["prefilter"]["er_session"] for c in cards if not c["yes"]]
d, p = perm_diff_means(ery, ern)
uer, per = mww(ery, ern)
print("\n  TRENDINESS vs HIS ANSWER: yes-cards ER %.4f  no-cards ER %.4f  diff %+0.4f"
      % (mean(ery), mean(ern), d))
print("  permutation p = %.4f ; rank AUC %.3f p = %.4f  -> %s"
      % (p, uer, per, "ER SEPARATES his answers" if p < 0.05 else "not separated"))
conf["er_yes"] = mean(ery)
conf["er_no"] = mean(ern)
conf["er_perm_p"] = p
conf["er_auc"] = uer
conf["er_auc_p"] = per

srt = sorted(cards, key=lambda c: c["prefilter"]["er_session"])
half = len(srt) // 2
for name, grp in (("LOW-trend half (choppy)", srt[:half]), ("HIGH-trend half", srt[half:])):
    line = []
    for b in BUCKETS:
        g = [c for c in grp if c["bucket"] == b]
        line.append("%s %d/%d" % (b, sum(c["yes"] for c in g), len(g)))
    print("  %-24s %s   overall %d/%d"
          % (name, "  ".join(line), sum(c["yes"] for c in grp), len(grp)))
conf["strata"] = {name: {b: [sum(c["yes"] for c in grp if c["bucket"] == b),
                             len([c for c in grp if c["bucket"] == b])] for b in BUCKETS}
                  for name, grp in (("low_trend", srt[:half]), ("high_trend", srt[half:]))}

print("\n  ENGINE BELIEF STRENGTH (deck sorted clean-first, so arms are unmatched):")
for b in BUCKETS:
    c0 = [c for c in by_b[b] if int(c["tripped"] or 0) == 0]
    c1 = [c for c in by_b[b] if int(c["tripped"] or 0) > 0]
    print("    %-4s clean-S %d/%-2d = %5.1f%%   bought-S %d/%-2d = %s"
          % (b, sum(c["yes"] for c in c0), len(c0),
             100 * mean([c["yes"] for c in c0]) if c0 else float("nan"),
             sum(c["yes"] for c in c1), len(c1),
             ("%5.1f%%" % (100 * mean([c["yes"] for c in c1]))) if c1 else "  n/a"))
conf["belief"] = {b: dict(clean=[sum(c["yes"] for c in by_b[b] if int(c["tripped"] or 0) == 0),
                                 len([c for c in by_b[b] if int(c["tripped"] or 0) == 0])],
                          bought=[sum(c["yes"] for c in by_b[b] if int(c["tripped"] or 0) > 0),
                                  len([c for c in by_b[b] if int(c["tripped"] or 0) > 0])])
                  for b in BUCKETS}
kx = conf["belief"]["OCR"]["clean"]
ky = conf["belief"]["84"]["clean"]
d, lo, hi = newcombe(kx[0], kx[1], ky[0], ky[1])
print("    clean-S only, OCR vs 84: %+5.1f pts CI [%+5.1f,%+5.1f]  (n=%d vs %d)"
      % (100 * d, 100 * lo, 100 * hi, kx[1], ky[1]))
conf["clean_only_ocr_vs_84"] = dict(d=d, lo=lo, hi=hi)
OUTJ["confounds"] = conf

print()
print("=" * 78)
print("4. THE POPULATION THE ARMS WERE DRAWN FROM  (selection intensity)")
print("=" * 78)
book = json.load(open(BOOK, encoding="utf-8"))["trades"]
SETUP_OF = {"break_and_retest": "BR", "one_candle_rule": "OCR", "reentry_84_rule": "84"}
pop = defaultdict(Counter)
rs_by = defaultdict(list)
days_any = defaultdict(set)
days_s = defaultdict(set)
for r in book:
    b = SETUP_OF.get(r["setup"])
    if not b:
        continue
    pop[b]["signals"] += 1
    days_any[b].add((r["sym"], r["day"]))
    rs_by[(b, "all")].append(r["r"])
    if r.get("sgrade") == "S":
        pop[b]["s_signals"] += 1
        days_s[b].add((r["sym"], r["day"]))
        rs_by[(b, "S")].append(r["r"])
    else:
        rs_by[(b, "nonS")].append(r["r"])
    if r.get("traded"):
        pop[b]["traded"] += 1
        rs_by[(b, "traded")].append(r["r"])
sel = {}
for b in BUCKETS:
    sel[b] = dict(signals=pop[b]["signals"], s_signals=pop[b]["s_signals"],
                  s_days=len(days_s[b]), any_days=len(days_any[b]),
                  traded=pop[b]["traded"])
    print("  %-4s %7d signals  %6d S signals  %5d S symbol-days  %5d traded"
          % (b, pop[b]["signals"], pop[b]["s_signals"], len(days_s[b]), pop[b]["traded"]))
print()
print("  mean R of the signal population, by grade:")
for b in BUCKETS:
    print("    %-4s all %+6.3f (n=%6d)  S %+6.3f (n=%5d)  non-S %+6.3f (n=%6d)  traded %+6.3f (n=%5d)"
          % (b, mean(rs_by[(b, "all")]), len(rs_by[(b, "all")]),
             mean(rs_by[(b, "S")]), len(rs_by[(b, "S")]),
             mean(rs_by[(b, "nonS")]), len(rs_by[(b, "nonS")]),
             mean(rs_by[(b, "traded")]), len(rs_by[(b, "traded")])))
    sel[b]["mean_r_all"] = mean(rs_by[(b, "all")])
    sel[b]["mean_r_S"] = mean(rs_by[(b, "S")])
    sel[b]["mean_r_nonS"] = mean(rs_by[(b, "nonS")])
    sel[b]["mean_r_traded"] = mean(rs_by[(b, "traded")])
OUTJ["population"] = sel

print()
print("=" * 78)
print("5. WOULD THE UNLOCKED OCR TRADES LOOK LIKE THE 10 HE GRADED?")
print("=" * 78)
ocr = [r for r in book if r["setup"] == "one_candle_rule"]
ocr_s = [r for r in ocr if r.get("sgrade") == "S"]
his6 = {"PDH", "PDL", "PMH", "PML", "HOD", "LOD"}


def onhis6(r):
    return (r.get("level_name") or "") in his6


graded_like = [r for r in ocr_s if onhis6(r)]
rest = [r for r in ocr if not (r.get("sgrade") == "S" and onhis6(r))]
print("  OCR signals in the book                  : %6d" % len(ocr))
print("  ... that reach S on Austin's ladder      : %6d (%.1f%%)"
      % (len(ocr_s), 100 * len(ocr_s) / len(ocr)))
print("  ... AND name one of his six levels       : %6d (%.1f%% of all OCR)"
      % (len(graded_like), 100 * len(graded_like) / len(ocr)))
print("  the 10 cards were drawn from that last slice.")
print()
print("  mean R  OCR S-on-his-six      %+6.3f (n=%d)"
      % (mean([r["r"] for r in graded_like]) if graded_like else float("nan"), len(graded_like)))
print("  mean R  every OTHER OCR signal %+6.3f (n=%d)"
      % (mean([r["r"] for r in rest]), len(rest)))
ocr_days = defaultdict(list)
for r in ocr:
    ocr_days[(r["sym"], r["day"])].append(r)
g_days = set((r["sym"], r["day"]) for r in graded_like)
print("  OCR symbol-days total %d ; S-on-his-six symbol-days %d (%.1f%%)"
      % (len(ocr_days), len(g_days), 100 * len(g_days) / max(1, len(ocr_days))))
print("  median entry price   S-on-his-six $%.2f   everything else $%.2f"
      % (med([r.get("entry") or 0.0 for r in graded_like]) if graded_like else float("nan"),
         med([r.get("entry") or 0.0 for r in rest])))
# level_name census for OCR
lvl = Counter((r.get("level_name") or "?") for r in ocr)
print("  OCR level_name census: %s" % dict(lvl.most_common(8)))
OUTJ["resemblance"] = dict(ocr_signals=len(ocr), ocr_s=len(ocr_s),
                           graded_like=len(graded_like),
                           graded_like_pct=100 * len(graded_like) / len(ocr),
                           mean_r_graded_like=(mean([r["r"] for r in graded_like])
                                               if graded_like else None),
                           mean_r_rest=mean([r["r"] for r in rest]),
                           ocr_days=len(ocr_days), graded_like_days=len(g_days),
                           level_census=dict(lvl.most_common(12)))

json.dump(OUTJ, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
print("\nwrote %s" % OUT)
