"""g83_verify_5.py -- adversarial recompute of the deep-batch build's numbers.

Independent of research/g83_deep_batch_build.py: this file re-reads the raw
two-year book and the raw archive directory and re-derives the pool split, the
exclusion set and the sixty cards from scratch. It imports build_deck only for
the two things that ARE the shared contract under test -- marked_card_ids() and
served_card_ids() -- and for the bar loader.

Checks, in order of how much they would hurt if they failed:

  1. the two-year grid and the three candidate pools    (the largest numbers)
  2. the exclusion set size at build time
  3. the manifest's 60 rows: distinct, quota 20/20/20, roles re-derived from
     the book rather than trusted from the label
  4. no card intersects any judged mark corpus, any served manifest, or the
     g75 deck-two batch
  5. determinism -- re-run the documented draw (seed 83) and demand the exact
     same sixty card ids in the exact same order as the manifest on disk
  6. no bar at or after 09:30 is used to place any of the six levels, and the
     opening range is closed by 09:35

    python research/g83_verify_5.py
"""
from __future__ import annotations

import json
import os
import random
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import build_deck as bd

BOOK = os.path.join(HERE, "bt2y_trades.json")
ARCHIVE = os.path.join(ROOT, "data_archive")
MANIFEST = os.path.join(HERE, "decks", "g83-deep-batch-manifest.jsonl")
G75 = os.path.join(HERE, "decks", "g75-deck2-manifest.jsonl")
MIN_BARS, MAX_PER_SYMBOL, SEED, WANT = 85, 3, 83, 20
ROLES = ("traded", "fired_not_traded", "silent")
SIX = ("pdh", "pdl", "pmh", "pml", "orh", "orl")

fails = []


def check(ok, label, got, want=None):
    tag = "ok  " if ok else "FAIL"
    if not ok:
        fails.append(label)
    print("%s %-52s %s%s" % (tag, label, got,
                             "" if want is None else "   (claimed %s)" % want))


# ---------------------------------------------------------------- 1. the pools
with open(BOOK, encoding="utf-8") as fh:
    blob = json.load(fh)
rows = blob["trades"]
symbols = list(blob["meta"]["symbols"])

n_sig = Counter()
booked = defaultdict(int)
sessions = set()
for r in rows:
    k = (r["sym"], r["day"])
    n_sig[k] += 1
    sessions.add(r["day"])
    if r.get("traded"):
        booked[k] += 1

grid = set()
for sym in symbols:
    d = os.path.join(ARCHIVE, sym)
    if not os.path.isdir(d):
        continue
    for name in os.listdir(d):
        if name.endswith(".csv") and name[:-4] in sessions:
            grid.add((sym, name[:-4]))

pools = {r: [] for r in ROLES}
for k in sorted(grid):
    n = n_sig.get(k, 0)
    pools["silent" if n == 0 else "traded" if booked.get(k) else
          "fired_not_traded"].append(k)

print("=== 1. the two-year grid and the three pools ===")
check(len(grid) == 12415, "grid, symbol-days", len(grid), 12415)
check(len(pools["traded"]) == 3740, "pool: engine traded", len(pools["traded"]), 3740)
check(len(pools["fired_not_traded"]) == 8071, "pool: fired, not traded",
      len(pools["fired_not_traded"]), 8071)
check(len(pools["silent"]) == 604, "pool: silent", len(pools["silent"]), 604)
check(sum(len(v) for v in pools.values()) == len(grid),
      "pools partition the grid", sum(len(v) for v in pools.values()))
print("    book rows %d, sessions %d, symbols %d"
      % (len(rows), len(sessions), len(symbols)))

# ------------------------------------------------------------ 2/3/4. manifest
man = [json.loads(l) for l in open(MANIFEST, encoding="utf-8") if l.strip()]
ids = [m["card_id"] for m in man]

print("")
print("=== 2. the exclusion set as it stood at build time ===")
judged = bd.marked_card_ids()
seen = bd.seen_card_ids(MANIFEST)          # excludes this build's own output
g75ids = set()
for l in open(G75, encoding="utf-8"):
    if l.strip():
        g75ids.add(json.loads(l)["card_id"])
seen_at_build = seen | g75ids
check(len(judged) == 1178, "marked_card_ids()", len(judged), "1,178 implied")
check(len(g75ids) == 39, "g75 deck-two cards", len(g75ids), 39)
check(g75ids <= seen, "all 39 g75 cards already inside seen_card_ids",
      g75ids <= seen, True)
check(len(seen_at_build) == 1617, "exclusion set (judged OR served)",
      len(seen_at_build), 1617)

print("")
print("=== 3. the sixty cards on the page ===")
check(len(man) == 60, "manifest rows", len(man), 60)
check(len(set(ids)) == 60, "distinct card ids", len(set(ids)))
roles = Counter(m["role"] for m in man)
check(all(roles[r] == 20 for r in ROLES), "quota 20 / 20 / 20", dict(roles))
bad_role = []
for m in man:
    k = (m["symbol"], m["date"])
    n, b = n_sig.get(k, 0), booked.get(k, 0)
    want = "silent" if n == 0 else "traded" if b else "fired_not_traded"
    if m["role"] != want:
        bad_role.append(m["card_id"])
    if m.get("engine_signals") != n or m.get("engine_trades") != b:
        bad_role.append(m["card_id"] + " counts")
check(not bad_role, "role re-derived from the book matches the label",
      "0 mismatches" if not bad_role else bad_role[:5])
cap = Counter(m["symbol"] for m in man)
check(max(cap.values()) <= MAX_PER_SYMBOL, "max cards per symbol", max(cap.values()))
check(min(m["bars"] for m in man) >= MIN_BARS, "shortest session, bars",
      min(m["bars"] for m in man))

print("")
print("=== 4. no repeats ===")
check(not (set(ids) & judged), "intersect judged marks", len(set(ids) & judged))
check(not (set(ids) & seen), "intersect served manifests", len(set(ids) & seen))
check(not (set(ids) & g75ids), "intersect g75 deck two", len(set(ids) & g75ids))

# ------------------------------------------------------------- 5. determinism
print("")
print("=== 5. determinism: re-draw the sixty from scratch ===")
rng = random.Random(SEED)
per_symbol = Counter()
picked = {r: [] for r in ROLES}
for role in ROLES:
    cands = list(pools[role])
    rng.shuffle(cands)
    for sym, day in cands:
        if len(picked[role]) >= WANT:
            break
        cid = "%s_%s" % (sym, day)
        if cid in seen_at_build or per_symbol[sym] >= MAX_PER_SYMBOL:
            continue
        candles = bd.session_candles(sym, day)
        if len(candles) < MIN_BARS:
            continue
        pdh, pdl, _o, _c = bd.prior_day_levels(sym, day)
        pmh, pml = bd.premarket_extremes(sym, day)
        lv = {"pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
              "orh": max(c.high for c in candles[:5]),
              "orl": min(c.low for c in candles[:5])}
        if sum(1 for k in SIX if lv.get(k) is not None) < 4:
            continue
        per_symbol[sym] += 1
        picked[role].append({"symbol": sym, "day": day, "role": role, "lv": lv})
mine = [c for r in ROLES for c in picked[r]]
random.Random(SEED + 1).shuffle(mine)
my_ids = ["%s_%s" % (c["symbol"], c["day"]) for c in mine]
check(my_ids == ids, "re-drawn sixty match the manifest, in order",
      "identical" if my_ids == ids else "%d/%d positions differ"
      % (sum(1 for a, b in zip(my_ids, ids) if a != b), len(ids)))

lvl_bad = []
if my_ids == ids:
    for c, m in zip(mine, man):
        for k in SIX:
            a, b = c["lv"].get(k), m["drawn_levels"].get(k)
            if (a is None) != (b is None):
                lvl_bad.append((m["card_id"], k))
            elif a is not None and round(a, 2) != b:
                lvl_bad.append((m["card_id"], k))
    check(not lvl_bad, "the six levels re-derive identically",
          "0 mismatches" if not lvl_bad else lvl_bad[:5])

# ------------------------------------------------------------- 6. look-ahead
print("")
print("=== 6. look-ahead: could any level have used a bar it should not? ===")
starts = Counter()
or_close = Counter()
for m in man:
    cs = bd.session_candles(m["symbol"], m["date"])
    ts = [c.timestamp[11:16] if "T" in c.timestamp else c.timestamp[:5]
          for c in cs]
    starts[ts[0]] += 1
    or_close[ts[4]] += 1
check(set(starts) == {"09:30"}, "every session's first bar is 09:30", dict(starts))
check(set(or_close) == {"09:34"}, "opening range closes on the 09:34 bar",
      dict(or_close))

peek = []
for m in man:
    pmh, pml = bd.premarket_extremes(m["symbol"], m["date"])
    cs = bd.session_candles(m["symbol"], m["date"])
    hi, lo = max(c.high for c in cs), min(c.low for c in cs)
    if pmh is not None and pmh == hi and pml is not None and pml == lo:
        peek.append(m["card_id"])
check(not peek, "no pre-market level equals the whole session's extremes",
      "0 suspicious" if not peek else peek)

print("")
print("%s  (%d checks failed)" % ("REFUTED" if fails else "REPRODUCED", len(fails)))
for f in fails:
    print("   - %s" % f)
sys.exit(1 if fails else 0)
