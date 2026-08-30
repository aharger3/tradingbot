"""g81_verify_1.py -- adversarial recompute of the two largest g81 numbers.

Independent path. Where g81_displacement.py recomputes the displacement check
from bars and reads the OTHER seven downgrades off the book, this script does
the reverse first: it reads EVERYTHING off the book's own stored fields
(`downgrades`, `confluence`, `sgrade`), which were written by backtest_2y.py
at book-build time and never touched by the g81 rig. Then it repeats the
recall table their way (recomputing confluence from bars) to see whether the
two paths land in the same place.

Numbers under test:
  1. shipped displacement trip rate over the whole book (claim: 49.8% of 134,012)
  2. the recall table, S days 206/269 -> 170/269, refusals 358/476 -> 301/476

Read-only over every mark corpus and over the book. Writes nothing but stdout.
"""
from __future__ import annotations
import json, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)

import marks_pool                      # noqa: E402
import downgrade as dg                 # noqa: E402
import polygon_feed as pf              # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades.json")
book = json.load(open(BOOK, encoding="utf-8"))
rows = book["trades"]
print("book signals: %d  traded: %d" % (len(rows), book["meta"]["traded"]))

# ---------------------------------------------------------------- 1. trip rate
# straight off the book's own stored downgrade lists -- nothing recomputed
n = len(rows)
book_nodisp = sum(1 for r in rows if "no_displacement" in (r.get("downgrades") or []))
print("\n[1] SHIPPED TRIP RATE, from the book's own stored downgrades")
print("    no_displacement present on %d / %d = %.2f%%" % (book_nodisp, n, 100.0*book_nodisp/n))

# how many rows even have an entry_i + stop (the g81 rig's scoring precondition)
have = sum(1 for r in rows if r.get("entry_i") is not None and r.get("stop") is not None)
print("    rows with entry_i and stop: %d" % have)

# ------------------------------------------------------- 2. the recall table
pool = marks_pool.canonical_pool()
gc = Counter(e.grade for e in pool.values())
print("\npool: %d symbol-days  %s" % (len(pool), dict(gc)))
xonly = marks_pool.x_only_days(pool)
print("    of the 'none' bucket, X-only (engine refusal, not a day refusal): %d" % len(xonly))

by_day = defaultdict(list)
for idx, r in enumerate(rows):
    by_day[(r["sym"], r["day"])].append(idx)

def conf_stored(r):
    return str(r.get("confluence", "")).lower() in ("yes", "true", "1")

def others_stored(r):
    return len([d for d in (r.get("downgrades") or []) if d != "no_displacement"])

def recall_table(pred_on, pred_off, restrict=None):
    """pred_*(row) -> bool 'this signal grades S'. Day is a hit if any signal does."""
    hit = {"S": [0, 0], "none": [0, 0]}
    for key, idxs in by_day.items():
        e = pool.get("%s_%s" % key)
        if e is None or e.grade not in ("S", "none"):
            continue
        if restrict is not None and key not in restrict:
            continue
        on = any(pred_on(rows[i]) for i in idxs)
        off = any(pred_off(rows[i]) for i in idxs)
        hit[e.grade][0] += 1 if off else 0   # slot0 = OFF (check disabled)
        hit[e.grade][1] += 1
        hit.setdefault(("on", e.grade), [0, 0])
        hit[("on", e.grade)][0] += 1 if on else 0
        hit[("on", e.grade)][1] += 1
    return hit

# --- path A: book fields only -------------------------------------------------
def on_book(r):     # displacement check ON == the book's own stored grade
    return r.get("sgrade") == "S"
def off_book(r):    # displacement check OFF
    return others_stored(r) - (1 if conf_stored(r) else 0) <= 0

h = recall_table(on_book, off_book)
print("\n[2a] RECALL TABLE from the book's stored fields only (no bars read)")
for g in ("S", "none"):
    k_off, nd = h[g]
    k_on = h[("on", g)][0]
    print("     %-5s n=%3d   OFF %3d (%.1f%%)   ON %3d (%.1f%%)   cost %.1f pp"
          % (g, nd, k_off, 100.0*k_off/nd, k_on, 100.0*k_on/nd,
             100.0*(k_off-k_on)/nd))
gapoff = 100.0*h["S"][0]/h["S"][1] - 100.0*h["none"][0]/h["none"][1]
gapon  = 100.0*h[("on","S")][0]/h["S"][1] - 100.0*h[("on","none")][0]/h["none"][1]
print("     gap OFF %+.1f pp   gap ON %+.1f pp" % (gapoff, gapon))

# --- path B: their way -- recompute confluence and the shipped check from bars
print("\n[2b] RECALL TABLE their way (confluence + displacement recomputed from bars)")
judged = set()
for key in by_day:
    e = pool.get("%s_%s" % key)
    if e is not None and e.grade in ("S", "none"):
        judged.add(key)
print("     judged symbol-days with book signals: %d" % len(judged))

cache = {}
def dbars(sym, day):
    k = (sym, day)
    if k not in cache:
        try:
            r = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            r = []
        cache[k] = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
                    for c in r] if r else []
        if len(cache) > 900:
            pass
    return cache[k]

hit2 = {"S": [0, 0, 0], "none": [0, 0, 0]}   # [off_hits, on_hits, n]
conf_agree = conf_dis = 0
disp_agree = disp_dis = 0
scored = skipped = 0
for key in sorted(judged):
    sym, day = key
    bars = dbars(sym, day)
    e = pool["%s_%s" % key]
    any_on = any_off = False
    for i in by_day[key]:
        r = rows[i]
        ei, lvl = r.get("entry_i"), r.get("stop")
        if not bars or ei is None or lvl is None or ei >= len(bars):
            skipped += 1
            continue
        scored += 1
        is_long = (r["dir"] == "call")
        conf = dg.has_confluence(bars, ei, lvl, is_long)
        disp = dg.no_displacement(bars, ei, lvl, is_long)
        if conf == conf_stored(r): conf_agree += 1
        else: conf_dis += 1
        if disp == ("no_displacement" in (r.get("downgrades") or [])): disp_agree += 1
        else: disp_dis += 1
        base = others_stored(r) - (1 if conf else 0)
        if base <= 0: any_off = True
        if base + (1 if disp else 0) <= 0: any_on = True
    hit2[e.grade][0] += 1 if any_off else 0
    hit2[e.grade][1] += 1 if any_on else 0
    hit2[e.grade][2] += 1

print("     scored %d signals on judged days (%d skipped)" % (scored, skipped))
print("     confluence recompute vs book: %d agree, %d disagree (%.2f%%)"
      % (conf_agree, conf_dis, 100.0*conf_dis/max(1, conf_agree+conf_dis)))
print("     displacement recompute vs book: %d agree, %d disagree (%.2f%%)"
      % (disp_agree, disp_dis, 100.0*disp_dis/max(1, disp_agree+disp_dis)))
for g in ("S", "none"):
    off, on, nd = hit2[g]
    print("     %-5s n=%3d   OFF %3d (%.1f%%)   ON %3d (%.1f%%)   cost %.1f pp"
          % (g, nd, off, 100.0*off/nd, on, 100.0*on/nd, 100.0*(off-on)/nd))
g_off = 100.0*hit2["S"][0]/hit2["S"][2] - 100.0*hit2["none"][0]/hit2["none"][2]
g_on  = 100.0*hit2["S"][1]/hit2["S"][2] - 100.0*hit2["none"][1]/hit2["none"][2]
print("     gap OFF %+.1f pp   gap ON %+.1f pp" % (g_off, g_on))

# --- how much of the 'none' group is an ENGINE refusal, not a day refusal -----
nX = sum(1 for key in judged if pool["%s_%s" % key].grade == "none"
         and "%s_%s" % key in xonly)
nN = sum(1 for key in judged if pool["%s_%s" % key].grade == "none")
print("\n[3] COMPOSITION of the 'days he refused' group: %d of %d (%.0f%%) are X-only"
      % (nX, nN, 100.0*nX/max(1, nN)))


# =============================================================== part 2
# (a) the money decomposition claim, (b) a LOOK-AHEAD probe on the new
# separation variant: it reads bars[br:i+1], i.e. the ENTRY BAR's own completed
# high/low. Re-measure with the entry bar excluded (bars[br:i]) and see whether
# any published number moves.
print("\n" + "=" * 70)
print("PART 2 -- money decomposition and a look-ahead probe on `separation`")

def sep_atr(bars, i, level, is_long, incl_entry=True):
    br = dg._break_bar(bars, i, level, is_long)
    if br is None:
        return None, None
    a = dg._atr(bars, i)
    if a <= 0:
        return None, br
    end = (i + 1) if incl_entry else i
    seg = bars[br:end]
    if not seg:
        return None, br
    if is_long:
        d = max(b["h"] for b in seg) - level
    else:
        d = level - min(b["l"] for b in seg)
    return d / a, br

THR = 1.0
traded = [r for r in rows if r.get("traded") and r.get("r") is not None]
print("traded signals with an R: %d" % len(traded))

res = {}
for incl in (True, False):
    keep, drop = [], []
    ocr_in_drop = ocr_in_keep = 0
    for r in traded:
        bars = dbars(r["sym"], r["day"])
        ei, lvl = r.get("entry_i"), r.get("stop")
        if not bars or ei is None or lvl is None or ei >= len(bars):
            continue
        s, br = sep_atr(bars, ei, lvl, r["dir"] == "call", incl_entry=incl)
        trip = True if br is None else (False if s is None else s < THR)
        is_ocr = "one_candle" in str(r.get("setup", "")) or r.get("setup_label") == "OCR"
        if trip:
            drop.append(float(r["r"])); ocr_in_drop += 1 if is_ocr else 0
        else:
            keep.append(float(r["r"])); ocr_in_keep += 1 if is_ocr else 0
    def stat(v):
        w = [x for x in v if x > 0]; l = [x for x in v if x <= 0]
        return (len(v), sum(v)/len(v) if v else 0, len(w)/len(v) if v else 0,
                sum(w)/len(w) if w else 0, sum(l)/len(l) if l else 0)
    kn, km, kw, kwin, kloss = stat(keep)
    dn, dm, dw, dwin, dloss = stat(drop)
    tag = "entry bar INCLUDED (as published)" if incl else "entry bar EXCLUDED (causal)"
    print("\n  %s" % tag)
    print("    present  n=%4d meanR %+.4f win %.1f%%  winner %+.3fR loser %+.3fR"
          % (kn, km, 100*kw, kwin, kloss))
    print("    tripped  n=%4d meanR %+.4f win %.1f%%  winner %+.3fR loser %+.3fR"
          % (dn, dm, 100*dw, dwin, dloss))
    print("    delta %+.4fR   |  OCR-labelled in tripped bucket: %d/%d (%.1f%%)"
          % (km - dm, ocr_in_drop, dn, 100*ocr_in_drop/max(1, dn)))
    res[incl] = (kn, dn, km - dm)

print("\n  look-ahead sensitivity: tripped-bucket size %d -> %d when the entry bar's"
      % (res[True][1], res[False][1]))
print("  own completed range is removed; money delta %+.4fR -> %+.4fR"
      % (res[True][2], res[False][2]))

# --------------------------------------------------- (c) his six cards
print("\n" + "=" * 70)
print("PART 3 -- the six displacement cards")
CARDS = {"AMD_2025-09-08": ("no", "10:37"), "NVDA_2025-06-24": ("no", None),
         "QQQ_2025-12-22": ("no", None), "MSFT_2025-08-29": ("yes", "9:38"),
         "SPY_2026-06-17": ("yes", "9:48"), "QQQ_2024-08-26": ("yes", "9:56")}
bd2 = defaultdict(list)
for idx, r in enumerate(rows):
    bd2["%s_%s" % (r["sym"], r["day"])].append(idx)
def mins(s):
    try:
        h, m = s.split(":"); return int(h)*60 + int(m)
    except Exception:
        return None
n_trip_on_no = 0
for card, (verdict, minute) in sorted(CARDS.items()):
    idxs = bd2.get(card, [])
    if not idxs:
        print("  %-16s he=%-3s  NO ENGINE SIGNAL ALL DAY" % (card, verdict)); continue
    tgt = mins(minute) if minute else None
    pick = (min(idxs, key=lambda i: abs((mins(rows[i]["et"]) or 0) - tgt)) if tgt is not None
            else min(idxs, key=lambda i: (mins(rows[i]["et"]) or 0)))
    r = rows[pick]
    bars = dbars(r["sym"], r["day"])
    il = r["dir"] == "call"
    s, br = sep_atr(bars, r["entry_i"], r["stop"], il)
    ship = dg.no_displacement(bars, r["entry_i"], r["stop"], il)
    sepT = True if br is None else (False if s is None else s < THR)
    off = abs((mins(r["et"]) or 0) - tgt) if tgt is not None else None
    if verdict == "no" and ship:
        n_trip_on_no += 1
    print("  %-16s he=%-3s his=%-5s engine=%s (off %s min, %d signals) sep=%s "
          "shipped_trips=%s sep_trips=%s book_sgrade=%s"
          % (card, verdict, minute or "-", r["et"], off if off is not None else "-",
             len(idxs), ("%.2f" % s) if s is not None else "none", ship, sepT,
             r.get("sgrade")))
print("\n  shipped check trips on %d of the 3 cards he refused FOR no displacement"
      % n_trip_on_no)
