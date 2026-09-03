"""g74_verdict_check2.py -- pass 2 of the adversarial re-test.

Answers the four questions pass 1 raised:
  A. what the 30 cards actually were (traded? stop width? is the P&L column usable?)
  B. selection intensity -- how deep into each population the deck had to reach
  C. entry-minute: whose trade did he say yes to?
  D. which measured variable predicts his yes -- the setup label, or the day?

Read-only. Writes research/g74_verdict_check2.json.
"""
from __future__ import annotations
import json, math, os, random, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

MARKS = os.path.join(HERE, "marks", "probe_g71_homework_s3_2026-08-29_complete.jsonl")
MANI = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")
BOOK = os.path.join(HERE, "bt2y_trades.json")
OUT = os.path.join(HERE, "g74_verdict_check2.json")
RNG = random.Random(742)
OUTJ = {}


def mean(x):
    return sum(x) / len(x) if x else float("nan")


def med(x):
    s = sorted(x)
    n = len(s)
    if not n:
        return float("nan")
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def mww(a, b, iters=20000):
    def U(x, y):
        return sum(1.0 if xi > yi else (0.5 if xi == yi else 0.0) for xi in x for yi in y)
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


marks = [json.loads(l) for l in open(MARKS, encoding="utf-8")]
mani = {json.loads(l)["card_id"]: json.loads(l) for l in open(MANI, encoding="utf-8")}
cards = []
for m in marks:
    r = dict(mani[m["card_id"]])
    r["yes"] = 1 if m["answers"]["is_s"][0] == "yes" else 0
    r["note"] = " ".join(str(v) for v in (m.get("notes") or {}).values())
    cards.append(r)
BUCKETS = ["OCR", "BR", "84"]
by_b = {b: [c for c in cards if c["bucket"] == b] for b in BUCKETS}

book = json.load(open(BOOK, encoding="utf-8"))["trades"]
idx = {}
for r in book:
    idx.setdefault((r["sym"], r["day"], r["et"], r["setup"]), []).append(r)
SETUP_OF = {"break_and_retest": "BR", "one_candle_rule": "OCR", "reentry_84_rule": "84"}
ENG = {"BR": "break_and_retest", "OCR": "one_candle_rule", "84": "reentry_84_rule"}

print("=" * 82)
print("A. WHAT THE 30 CARDS ACTUALLY WERE -- and whether their P&L column means anything")
print("=" * 82)
rows = []
for c in cards:
    key = (c["symbol"], c["date"], c["et"], c["engine_setup"])
    hit = [r for r in idx.get(key, []) if r.get("sgrade") == "S"]
    r = hit[0] if hit else None
    c["stop_pct"] = r["stop_pct"] if r else None
    c["stopb"] = r["stopb"] if r else None
    c["status"] = r["status"] if r else None
    c["risk_cents"] = round(abs(r["entry"] - r["stop"]) * 100, 1) if r else None
    rows.append(c)
missing = [c["card_id"] for c in cards if c["stop_pct"] is None]
print("  matched %d/30 cards back to their book row (unmatched: %s)"
      % (30 - len(missing), missing or "none"))
print()
print("  %-4s  traded  status-census                                risk (cents)  stop-band")
for b in BUCKETS:
    g = by_b[b]
    st = Counter(c["status"] for c in g)
    sb = Counter(c["stopb"] for c in g)
    print("  %-4s  %d/10    %-42s med %5.1f      %s"
          % (b, sum(1 for c in g if c["traded"]), str(dict(st)),
             med([c["risk_cents"] for c in g if c["risk_cents"] is not None]), dict(sb)))
print()
print("  every card, cheapest stop first:")
for c in sorted(cards, key=lambda c: (c["risk_cents"] if c["risk_cents"] is not None else 1e9)):
    print("    %-22s %-4s risk %6.1fc  stop_pct %6.3f%%  %-6s traded=%-5s  R=%+9.3f  he said %s"
          % (c["card_id"], c["bucket"], c["risk_cents"], c["stop_pct"], c["stopb"],
             c["traded"], c["r"], "yes" if c["yes"] else "NO"))
tiny = [c for c in cards if (c["risk_cents"] or 99) <= 5]
print()
print("  cards whose whole risk is 5 cents or less: %d of 30 (%s)"
      % (len(tiny), ", ".join(c["card_id"] for c in tiny)))
print("  cards the engine never traded: %d of 30" % sum(1 for c in cards if not c["traded"]))
OUTJ["cards"] = [{k: c[k] for k in ("card_id", "bucket", "yes", "r", "outcome", "traded",
                                    "status", "stop_pct", "stopb", "risk_cents", "et",
                                    "tripped", "legacy_grade", "s_signals_that_day")}
                 for c in cards]

print()
print("=" * 82)
print("B. SELECTION INTENSITY -- how deep into each population the deck had to reach")
print("=" * 82)
pop = defaultdict(Counter)
sdays = defaultdict(set)
for r in book:
    b = SETUP_OF.get(r["setup"])
    if not b:
        continue
    pop[b]["sig"] += 1
    if r.get("sgrade") == "S":
        pop[b]["s"] += 1
        sdays[b].add((r["sym"], r["day"]))
print("  arm   S signals   S symbol-days   deck drew   sampled 1 in")
for b in BUCKETS:
    n = len(sdays[b])
    print("  %-4s  %8d     %9d       %2d          %6.1f" % (b, pop[b]["s"], n, 10, n / 10.0))
OUTJ["selection"] = {b: dict(s_signals=pop[b]["s"], s_days=len(sdays[b]),
                             one_in=len(sdays[b]) / 10.0) for b in BUCKETS}
print()
print("  the deck sorted candidates CLEAN-FIRST (fewest downgrades). Where each arm ran out:")
for b in BUCKETS:
    g = by_b[b]
    print("    %-4s zero-downgrade cards taken: %2d of 10   (population zero-downgrade S days: see below)"
          % (b, sum(1 for c in g if int(c["tripped"] or 0) == 0)))
zero = defaultdict(set)
for r in book:
    b = SETUP_OF.get(r["setup"])
    if b and r.get("sgrade") == "S" and int(r.get("tripped") or 0) == 0:
        zero[b].add((r["sym"], r["day"]))
for b in BUCKETS:
    print("    %-4s zero-downgrade S symbol-days in the book: %d" % (b, len(zero[b])))
OUTJ["selection_zero"] = {b: len(zero[b]) for b in BUCKETS}

print()
print("=" * 82)
print("C. WHOSE TRADE DID HE SAY YES TO?  (his minute vs the engine's)")
print("=" * 82)
import re
TOK = re.compile(r"\b(\d{1,2})[:;.](\d{2})\b")


def his_minute(note):
    m = TOK.search(note or "")
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h < 9 or h > 11:
        return None
    t = (h - 9) * 60 + mi - 30
    return t if 0 <= t <= 95 else None


off = defaultdict(list)
for c in cards:
    if not c["yes"]:
        continue
    hm = his_minute(c["note"])
    if hm is None:
        continue
    em = (int(c["et"][:2]) - 9) * 60 + int(c["et"][3:]) - 30
    off[c["bucket"]].append((c["card_id"], hm, em, em - hm))
print("  arm   n   median offset   within 4 min   his median clock   engine median clock")
allo = []
for b in BUCKETS:
    o = off[b]
    allo += [x[3] for x in o]
    if not o:
        continue
    print("  %-4s %2d   %+6.0f min      %d of %-2d        9:%02d               %s"
          % (b, len(o), med([x[3] for x in o]),
             sum(1 for x in o if abs(x[3]) <= 4), len(o),
             30 + int(med([x[1] for x in o])) if med([x[1] for x in o]) < 30 else int(med([x[1] for x in o])),
             "%d:%02d" % (9 + (30 + int(med([x[2] for x in o]))) // 60,
                          (30 + int(med([x[2] for x in o]))) % 60)))
print("  all yes-cards with a clock: n=%d, median offset %+0.0f min" % (len(allo), med(allo)))
for b in BUCKETS:
    for cid, hm, em, d in off[b]:
        print("    %-4s %-22s he %d:%02d   engine %d:%02d   %+d min"
              % (b, cid, 9 + (30 + hm) // 60, (30 + hm) % 60,
                 9 + (30 + em) // 60, (30 + em) % 60, d))
OUTJ["minutes"] = {b: [list(x) for x in off[b]] for b in BUCKETS}

print()
print("=" * 82)
print("D. WHAT ACTUALLY PREDICTS HIS YES -- the setup label, or the day?")
print("=" * 82)
feats = {
    "session trendiness (ER)": lambda c: c["prefilter"]["er_session"],
    "impulse / ATR": lambda c: c["prefilter"]["impulse_atr"],
    "engine entry minute": lambda c: (int(c["et"][:2]) - 9) * 60 + int(c["et"][3:]) - 30,
    "reach to 2R (R)": lambda c: c["prefilter"]["reach_r"],
    "engine downgrades": lambda c: int(c["tripped"] or 0),
    "S signals that day": lambda c: float(c["s_signals_that_day"]),
    "risk (cents)": lambda c: float(c["risk_cents"] or 0),
}
res = {}
for name, fn in feats.items():
    a = [fn(c) for c in cards if c["yes"]]
    b_ = [fn(c) for c in cards if not c["yes"]]
    auc, p = mww(a, b_)
    res[name] = dict(yes=mean(a), no=mean(b_), auc=auc, p=p)
    print("  %-24s yes %8.4f   no %8.4f   AUC %.3f   p=%.4f  %s"
          % (name, mean(a), mean(b_), auc, p, "**" if p < 0.05 else ""))
print("  %-24s %s" % ("setup label (OCR vs rest)", "Fisher p=0.696 (from pass 1) -- not separated"))
print()
srt = sorted(cards, key=lambda c: c["prefilter"]["er_session"])
for lab, g in (("10 CHOPPIEST days", srt[:10]), ("10 middle", srt[10:20]), ("10 TRENDIEST days", srt[20:])):
    print("  %-20s he said yes to %2d of 10   (OCR cards in there: %d)"
          % (lab, sum(c["yes"] for c in g), sum(1 for c in g if c["bucket"] == "OCR")))
OUTJ["predictors"] = res

json.dump(OUTJ, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
print("\nwrote %s" % OUT)
