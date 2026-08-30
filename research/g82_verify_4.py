"""Adversarial re-check of the master homework page.

Recomputes, without trusting the builder's own printout:
  1. the no-repeat guarantee -- every symbol-day on the page, pulled out of the
     SHIPPED HTML (not the manifest), intersected with build_deck's judged set
     and its served set (the page's own manifest excluded);
  2. the card count, the symbol spread and the per-section symbol cap;
  3. that the page depends on no external network resource, saves to
     localStorage, restores on load, exports .jsonl, and draws inline SVG.

Run: python research/g82_verify_4.py
"""
import json, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import build_deck as bd

HTML = os.path.join(HERE, "probes", "omen-master-homework.html")
MAN = os.path.join(HERE, "probes", "omen-master-homework-manifest.jsonl")

raw = open(HTML, encoding="utf-8").read()
print("page: %s (%d bytes)" % (HTML, os.path.getsize(HTML)))

# ---- 1. card ids straight out of the shipped page -------------------------
cids = re.findall(r'data-cid="([^"]+)"', raw)
print("data-cid attributes in the page: %d (%d distinct)" % (len(cids), len(set(cids))))

def symday(c):
    m = re.match(r"^(?:[a-z0-9]+_)?([A-Z][A-Z0-9.\-]*)_(\d{4}-\d{2}-\d{2})", c)
    return "%s_%s" % (m.group(1), m.group(2)) if m else None

page_days, ballot = set(), []
for c in cids:
    k = symday(c)
    (page_days.add(k) if k else ballot.append(c))
print("chart symbol-days on the page: %d   ballot/other cids: %d"
      % (len(page_days), len(ballot)))

judged = bd.marked_card_ids()
served = bd.served_card_ids(MAN)          # exclude this page's own manifest
seen = judged | served
print("judged=%d  served-only=%d  seen=%d" % (len(judged), len(served - judged), len(seen)))

hit_j = sorted(page_days & judged)
hit_s = sorted(page_days & (served - judged))
print("INTERSECTION with judged : %d %s" % (len(hit_j), hit_j))
print("INTERSECTION with served : %d %s" % (len(hit_s), hit_s))

dupes = [c for c, n in Counter(cids).items() if n > 1]
print("duplicate cids on the page: %d %s" % (len(dupes), dupes))

# ---- 2. spread ------------------------------------------------------------
syms = Counter(k.rsplit("_", 1)[0] for k in page_days)
print("distinct symbols: %d   max per page: %d" % (len(syms), max(syms.values())))
per_sec = Counter()
for c in cids:
    k = symday(c)
    if k:
        per_sec[(c.split("_")[0], k.rsplit("_", 1)[0])] += 1
print("max per (section,symbol): %d" % max(per_sec.values()))

# ---- 3. manifest agrees with the page ------------------------------------
rows = [json.loads(l) for l in open(MAN, encoding="utf-8") if l.strip()]
man_days = {r["card_id"] for r in rows if r.get("card_id") and re.match(r"^[A-Z]", str(r["card_id"]))}
print("manifest rows: %d   manifest symbol-days: %d   page-vs-manifest diff: %s"
      % (len(rows), len(man_days), sorted(page_days ^ man_days) or "none"))

# ---- 4. delivery contract, read off the file ------------------------------
ext = re.findall(r'(?:src|href)\s*=\s*["\'](https?:|//)', raw)
fetches = re.findall(r'\b(fetch\s*\(|XMLHttpRequest|WebSocket|importScripts)', raw)
print("external src/href refs: %d   network calls: %s" % (len(ext), fetches or "none"))
for label, pat in (("localStorage.setItem", r"localStorage\.setItem"),
                   ("localStorage.getItem", r"localStorage\.getItem"),
                   ("restore on load", r"(DOMContentLoaded|window\.onload|restore\s*\()"),
                   ("jsonl export", r"jsonl"),
                   ("inline <svg>", r"<svg"),
                   ("<canvas>", r"<canvas")):
    print("  %-22s %d" % (label, len(re.findall(pat, raw, re.I))))

ok = not hit_j and not hit_s and not dupes and not ext and not fetches
print("\nVERDICT: %s" % ("no repeat, no external dependency" if ok else "PROBLEM -- see above"))
