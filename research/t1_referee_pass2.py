"""t1_referee_pass2.py -- second-pass referee for row T1 (the two-year tape).

Builder commit under review: 380667a6293b380bb7c539798a956c011e6461ab
("T1 repair"), which answers research/t1_referee.md's pass-1 refutation.

Nothing here imports research/build_tape.py. Every number is re-derived two
independent ways and compared:

  (A) PAGE SIDE -- the JSON physically embedded in research/tape/omen-tape.html
      is parsed, and the page's OWN client-side filter (`passes`) and scoreboard
      (`stats`, as patched by build_tape.py's TEMPLATE) are re-implemented here
      line-for-line in Python. This is what a reader actually sees.

  (B) BOOK SIDE -- the stamped .json.gz books in research/tape/ are loaded
      directly, re-tagged with lane/week/policy by this file's own code (the
      day-policy rule re-implemented from the spec sentence, not imported), and
      the same filter applied.

A disagreement between (A) and (B) is a page defect. Agreement between (A) and
(B) but disagreement with the published headline is a reporting defect.

Run: python research/t1_referee_pass2.py
"""
from __future__ import annotations

import gzip
import json
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TAPE = ROOT / "research" / "tape"
HTML = TAPE / "omen-tape.html"
RISK = 1000.0

CORE = frozenset("TSLA NVDA AAPL AMD META GOOGL AMZN MSFT PLTR QQQ SPY".split())
INDEX = frozenset("QQQ SPY IWM".split())

SEED = 20260905


# --------------------------------------------------------------- page side

def load_payload():
    html = HTML.read_text(encoding="utf-8")
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>',
                  html, re.DOTALL)
    if not m:
        raise SystemExit("no embedded payload")
    return html, json.loads(m.group(1))


class Page:
    """The page's own filter + scoreboard, re-implemented from the JS."""

    # var MULTI = {tags:1, downgrades:1, lane:1, policy:1};
    MULTI = {"tags", "downgrades", "lane", "policy"}

    def __init__(self, payload):
        self.d = payload["dicts"]
        self.c = payload["cols"]
        self.n = len(self.c["day"])
        self.facets = [f[0] for f in payload["facets"]]

    def val(self, f, i):
        return self.d[f][self.c[f][i]]

    def code(self, f, v):
        try:
            return self.d[f].index(v)
        except ValueError:
            return -1

    def passes(self, i, sel):
        for k, s in sel.items():
            if not s:
                continue
            if k in self.MULTI:
                if not any(cc in s for cc in self.c[k][i]):
                    return False
            elif self.c[k][i] not in s:
                return False
        return True

    def select(self, picks):
        """picks: {field: [values]} -> list of row indexes, page semantics."""
        sel = {}
        for f, vals in picks.items():
            codes = set()
            for v in vals:
                cc = self.code(f, v)
                if cc < 0:
                    raise SystemExit("pick %s=%r does not resolve" % (f, v))
                codes.add(cc)
            sel[f] = codes
        return [i for i in range(self.n) if self.passes(i, sel)]

    def stats(self, idxs):
        """build_tape.py's patched stats(), transcribed."""
        n = len(idxs)
        w = l = sc = dec = 0
        sumR = gp = gl = bars = 0.0
        winPnl = lossPnl = 0.0
        winN = lossN = 0
        eq = peak = dd = 0.0
        byMonth, byWeek, days = defaultdict(float), defaultdict(float), set()
        for i in idxs:
            r = self.c["r"][i]
            o = self.val("out", i)
            sumR += r
            bars += self.c["bars"][i]
            if o == "win":
                w += 1; dec += 1
            elif o == "loss":
                l += 1; dec += 1
            else:
                sc += 1
            if r > 0:
                gp += r
            else:
                gl += -r
            pnl = r * RISK
            if pnl > 0:
                winPnl += pnl; winN += 1
            elif pnl < 0:
                lossPnl += pnl; lossN += 1
            eq += r
            if eq > peak:
                peak = eq
            if peak - eq > dd:
                dd = peak - eq
            byMonth[self.val("ym", i)] += r
            byWeek[self.val("wk", i)] += r
            days.add(self.val("day", i))
        months = sorted(byMonth)
        weeks = sorted(byWeek)
        green = sum(1 for m in months if byMonth[m] > 0)
        wgreen = sum(1 for x in weeks if byWeek[x] > 0)
        nd = len(days)
        return {
            "n": n, "sumR": round(sumR, 4),
            "meanR": round(sumR / n, 4) if n else 0.0,
            "win_pct": round(w / dec * 100, 1) if dec else 0.0,
            "months": len(months), "months_green": green,
            "weeks": len(weeks), "weeks_green": wgreen,
            "days_in_selection": nd,
            "per_day_page": round(sumR * RISK / nd, 1) if nd else 0.0,
            "avg_win": round(winPnl / winN, 1) if winN else 0.0,
            "avg_loss": round(lossPnl / lossN, 1) if lossN else 0.0,
            "fires_per_day": round(n / nd, 3) if nd else 0.0,
            "max_dd_R": round(dd, 3),
        }


# --------------------------------------------------------------- book side

SOURCES = [
    # (source label, fillmode, filename, trim)
    ("baseline", "close", "baseline_2026-09-05.json.gz", "drop_skipped_d"),
    ("baseline", "phantom", "baseline_2026-09-05_published.json.gz", "traded_or_halted"),
    ("L1_on", "close", "book_MIN_PT1_R_on.json.gz", "traded_or_halted"),
    ("L2_on", "close", "book_RULE84_DECIDED_on.json.gz", "traded_or_halted"),
    ("L3_on", "close", "book_OCR_RETEST_DISPLACEMENT_on.json.gz", "traded_or_halted"),
    ("L4_on", "close", "book_TREND_DEF_on.json.gz", "traded_or_halted"),
    ("L5_on", "close", "book_DAY_POLICY_on.json.gz", "traded_or_halted"),
]


def load_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def lane_of(sym):
    out = []
    if sym in CORE:
        out.append("core11")
    if sym in INDEX:
        out.append("index3")
    out.append("full29")
    return out


def week_of(day):
    try:
        y, w, _ = date.fromisoformat(day).isocalendar()
        return "%d-W%02d" % (y, w)
    except Exception:
        return "n/a"


def day_policy_tags(rows):
    """His day policy, re-implemented here from the spec sentence rather than
    imported: candidates are the day's fired-and-traded rows plus the rows the
    account-wide two-loss halt blocked; first_of_day is the earliest; up_to_3
    walks the day in time order taking up to three, stopping after the first
    win or the second loss."""
    byday = defaultdict(list)
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday[r["day"]].append(r)
    first_ids, up3_ids, cand_ids = set(), set(), set()
    for day in sorted(byday):
        drows = sorted(byday[day], key=lambda r: (r.get("et") or "", r.get("sym") or ""))
        for r in drows:
            cand_ids.add(id(r))
        first_ids.add(id(drows[0]))
        losses = taken = 0
        for r in drows:
            if taken >= 3:
                break
            up3_ids.add(id(r))
            taken += 1
            pnl = r.get("pnl", 0.0)
            if pnl > 0:
                break
            if pnl < 0:
                losses += 1
                if losses >= 2:
                    break
    return cand_ids, first_ids, up3_ids


def load_books():
    rows = []
    stamps = {}
    for src, fm, fname, trim in SOURCES:
        meta, trades = load_gz(TAPE / fname)
        if trim == "drop_skipped_d":
            trades = [t for t in trades if t.get("status") != "skipped_d"]
        else:
            trades = [t for t in trades if t.get("traded") or t.get("status") == "halted"]
        for t in trades:
            t["source"] = src
            t["fillmode"] = fm
            t["lane"] = lane_of(t.get("sym", ""))
            t["wk"] = week_of(t.get("day", ""))
            t["policy"] = []
        core_rows = [t for t in trades if t.get("tier") == "core"]
        cand, first, up3 = day_policy_tags(core_rows)
        for t in core_rows:
            if id(t) in cand:
                tags = ["every_signal"]
                if id(t) in first:
                    tags.append("first_of_day")
                if id(t) in up3:
                    tags.append("up_to_3")
                t["policy"] = tags
        rows.extend(trades)
        st = meta.get("stamp", {})
        stamps["%s/%s" % (src, fm)] = {
            "file": fname, "built_at": st.get("built_at"),
            "commit": (st.get("git", {}) or {}).get("commit", "")[:10],
            "dirty_py_count": (st.get("git", {}) or {}).get("dirty_py_count"),
            "dirty_engine_py": (st.get("git", {}) or {}).get("dirty_engine_py"),
            "book_id": st.get("book_id"),
            "kept": len(trades),
        }
    return rows, stamps


def book_select(rows, picks):
    MULTI = {"lane", "policy", "tags", "downgrades"}
    out = []
    for r in rows:
        ok = True
        for f, vals in picks.items():
            if f in MULTI:
                if not (set(r.get(f) or []) & set(vals)):
                    ok = False
                    break
            else:
                v = r.get(f)
                v = "yes" if v is True else "no" if v is False else str(v)
                if v not in [str(x) for x in vals]:
                    ok = False
                    break
        if ok:
            out.append(r)
    return out


def book_stats(rows):
    n = len(rows)
    if not n:
        return {"n": 0}
    sumR = sum(r.get("r", 0.0) for r in rows)
    dec = sum(1 for r in rows if r.get("out") in ("win", "loss"))
    w = sum(1 for r in rows if r.get("out") == "win")
    byM, byW, days = defaultdict(float), defaultdict(float), set()
    winP = lossP = 0.0
    winN = lossN = 0
    for r in rows:
        rr = r.get("r", 0.0)
        byM[r["day"][:7]] += rr
        byW[week_of(r["day"])] += rr
        days.add(r["day"])
        p = rr * RISK
        if p > 0:
            winP += p; winN += 1
        elif p < 0:
            lossP += p; lossN += 1
    nd = len(days)
    return {
        "n": n, "sumR": round(sumR, 4),
        "meanR": round(sumR / n, 4),
        "win_pct": round(w / dec * 100, 1) if dec else 0.0,
        "months": len(byM), "months_green": sum(1 for v in byM.values() if v > 0),
        "weeks": len(byW), "weeks_green": sum(1 for v in byW.values() if v > 0),
        "days_in_selection": nd,
        "per_day_page": round(sumR * RISK / nd, 1) if nd else 0.0,
        "avg_win": round(winP / winN, 1) if winN else 0.0,
        "avg_loss": round(lossP / lossN, 1) if lossN else 0.0,
        "fires_per_day": round(n / nd, 3) if nd else 0.0,
    }


COMPARE_KEYS = ["n", "sumR", "meanR", "win_pct", "months", "months_green",
                "weeks", "weeks_green", "days_in_selection", "per_day_page",
                "avg_win", "avg_loss", "fires_per_day"]


def main():
    html, payload = load_payload()
    page = Page(payload)
    rows, stamps = load_books()
    print("page rows: %d   book rows: %d" % (page.n, len(rows)))
    print()

    print("=== stamps ===")
    for k, v in stamps.items():
        print("  %-18s %s  built %s  commit %s  dirty_py=%s dirty_engine=%s  kept=%d"
              % (k, v["file"], v["built_at"], v["commit"], v["dirty_py_count"],
                 v["dirty_engine_py"], v["kept"]))
    print()

    # ---- default selection --------------------------------------------
    default_picks = {"source": ["baseline"], "fillmode": ["close"],
                     "lane": ["core11"], "policy": ["up_to_3"]}
    print("=== DEFAULT SELECTION (what defaultSel() picks) ===")
    a = page.stats(page.select(default_picks))
    b = book_stats(book_select(rows, default_picks))
    print("  page:", json.dumps(a))
    print("  book:", json.dumps(b))
    print("  agree:", all(a.get(k) == b.get(k) for k in COMPARE_KEYS))
    print("  published headline: 769 trades, -$52/day, mean R -0.0335, 11/25 green")
    n_sessions_baseline_close = len({r["day"] for r in rows
                                     if r["source"] == "baseline" and r["fillmode"] == "close"})
    print("  sessions in baseline/close book: %d" % n_sessions_baseline_close)
    print("  $/day if divided by SESSIONS (g72_stats' definition): %.1f"
          % (a["sumR"] * RISK / n_sessions_baseline_close))
    print("  $/day the page prints (divided by days in selection): %.1f" % a["per_day_page"])
    print()

    # ---- 5 random filter combinations ---------------------------------
    rnd = random.Random(SEED)
    fields = ["source", "fillmode", "lane", "policy", "sym", "setup", "dir",
              "sgrade", "grade", "dow", "yr", "slot", "level", "status",
              "book", "ym", "out", "tier", "pool"]
    combos = []
    tries = 0
    while len(combos) < 5 and tries < 4000:
        tries += 1
        k = rnd.choice([2, 3, 3, 4])
        picks = {}
        for f in rnd.sample(fields, k):
            vals = page.d.get(f) or []
            if not vals:
                continue
            nv = 1 if len(vals) < 4 else rnd.choice([1, 1, 2])
            picks[f] = rnd.sample(vals, min(nv, len(vals)))
        if len(picks) < 2:
            continue
        idxs = page.select(picks)
        if len(idxs) < 30:      # sample-size rule: skip cells too small to discuss
            continue
        combos.append((picks, idxs))

    print("=== 5 RANDOM FILTER COMBINATIONS (seed %d) ===" % SEED)
    all_agree = True
    for i, (picks, idxs) in enumerate(combos, 1):
        a = page.stats(idxs)
        b = book_stats(book_select(rows, picks))
        agree = all(a.get(k) == b.get(k) for k in COMPARE_KEYS)
        all_agree = all_agree and agree
        print("\ncombo %d: %s" % (i, json.dumps(picks)))
        print("  page: %s" % json.dumps(a))
        print("  book: %s" % json.dumps(b))
        print("  AGREE" if agree else "  MISMATCH: %s"
              % {k: (a.get(k), b.get(k)) for k in COMPARE_KEYS if a.get(k) != b.get(k)})
    print("\nall five agree page-vs-book:", all_agree)
    print()

    # ---- duplicates on the row's own stated key ------------------------
    print("=== DUPLICATES on (symbol, day, entry minute) ===")
    for scope, pred in [
        ("baseline/close, traded rows",
         lambda r: r["source"] == "baseline" and r["fillmode"] == "close" and r.get("traded")),
        ("all 7 sources, traded rows", lambda r: r.get("traded")),
    ]:
        c = Counter((r.get("source"), r.get("fillmode"), r.get("sym"), r.get("day"), r.get("et"))
                    for r in rows if pred(r))
        dk = {k: v for k, v in c.items() if v > 1}
        print("  %-32s dupe keys %4d   extra rows %4d   of %d"
              % (scope, len(dk), sum(v - 1 for v in dk.values()), sum(c.values())))
    sel = book_select(rows, default_picks)
    c = Counter((r.get("sym"), r.get("day"), r.get("et")) for r in sel)
    dk = {k: v for k, v in c.items() if v > 1}
    print("  %-32s dupe keys %4d   extra rows %4d   of %d"
          % ("inside the 769-row default", len(dk), sum(v - 1 for v in dk.values()), len(sel)))
    for k, v in sorted(dk.items())[:6]:
        print("      %s x%d" % (k, v))
    print()

    # ---- README claim: "every OFF arm equals the baseline exactly" -----
    print("=== README claim check: 'every OFF arm equals the baseline exactly,")
    print("    so off is just source=baseline' ===")
    base = book_stats(book_select(rows, default_picks))
    print("  baseline (source=baseline, close, core11, up_to_3): n=%d sumR=%s green=%d/%d"
          % (base["n"], base["sumR"], base["months_green"], base["months"]))
    for fname, label in [("book_MIN_PT1_R_off.json.gz", "L1 OFF"),
                         ("book_MIN_PT1_R_off_postfix.json.gz", "L1 OFF (postfix)"),
                         ("book_RULE84_DECIDED_off.json.gz", "L2 OFF"),
                         ("book_OCR_RETEST_DISPLACEMENT_off.json.gz", "L3 OFF"),
                         ("book_TREND_DEF_off.json.gz", "L4 OFF"),
                         ("book_DAY_POLICY_off.json.gz", "L5 OFF")]:
        p = TAPE / fname
        if not p.exists():
            print("  %-20s MISSING" % label)
            continue
        _meta, tr = load_gz(p)
        tr = [t for t in tr if t.get("traded") or t.get("status") == "halted"]
        core_rows = [t for t in tr if t.get("tier") == "core"]
        _c, _f, up3 = day_policy_tags(core_rows)
        picked = [t for t in core_rows if id(t) in up3]
        s = book_stats(picked)
        same = (s["n"] == base["n"] and abs(s["sumR"] - base["sumR"]) < 1e-6)
        print("  %-20s n=%4d sumR=%9.3f green=%2d/%2d  %s"
              % (label, s["n"], s["sumR"], s["months_green"], s["months"],
                 "== baseline" if same else "!= BASELINE"))
    print()

    # ---- what the page prints when a reader touches one chip -----------
    print("=== ONE CHIP AWAY FROM THE DEFAULT ===")
    for label, picks in [
        ("the default view", default_picks),
        ("source chip cleared (6 books stacked)",
         {"fillmode": ["close"], "lane": ["core11"], "policy": ["up_to_3"]}),
        ("both fill modes selected (honest + phantom summed)",
         {"source": ["baseline"], "fillmode": ["close", "phantom"],
          "lane": ["core11"], "policy": ["up_to_3"]}),
        ("fillmode=close, nothing else", {"fillmode": ["close"]}),
    ]:
        s = page.stats(page.select(picks))
        print("  %-52s n=%6d  $/day=%9.1f  meanR=%8.4f  green=%2d/%2d"
              % (label, s["n"], s["per_day_page"], s["meanR"],
                 s["months_green"], s["months"]))
    print()

    # ---- what the near-duplicates actually are -------------------------
    print("=== character of the (symbol, day, minute) duplicates, baseline/close ===")
    grp = defaultdict(list)
    for r in rows:
        if r["source"] == "baseline" and r["fillmode"] == "close" and r.get("traded"):
            grp[(r["sym"], r["day"], r["et"])].append(r)
    dup = {k: v for k, v in grp.items() if len(v) > 1}
    print("  dupe keys: %d" % len(dup))
    print("  identical pnl across the pair:   %d" %
          sum(1 for v in dup.values() if len({round(x["pnl"], 2) for x in v}) == 1))
    print("  identical entry price:           %d" %
          sum(1 for v in dup.values() if len({round(x["entry"], 4) for x in v}) == 1))
    print("  identical stop (same risk):      %d" %
          sum(1 for v in dup.values() if len({round(x["stop"], 4) for x in v}) == 1))
    sel769 = book_select(rows, default_picks)
    g2 = defaultdict(list)
    for r in sel769:
        g2[(r["sym"], r["day"], r["et"])].append(r)
    d2 = {k: v for k, v in g2.items() if len(v) > 1}
    extra = sum(sum(x["pnl"] for x in v[1:]) for v in d2.values())
    print("  inside the published 769-row unit: %d keys, extra rows carry $%.0f "
          "of the book's $%.0f total"
          % (len(d2), extra, sum(x["pnl"] for x in sel769)))
    for k, v in sorted(d2.items()):
        print("      %s  %s" % (k, [(round(x["entry"], 2), round(x["stop"], 2),
                                     round(x["pnl"], 2), x["sgrade"], x["level_name"])
                                    for x in v]))
    print()

    # ---- page shell hygiene -------------------------------------------
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.DOTALL)
    shell = html[:m.start()] + html[m.end():]
    print("=== page shell ===")
    print("  <canvas> in whole file:", html.lower().count("<canvas"))
    print("  external <script src>:", len(re.findall(r'<script[^>]*\bsrc=', html, re.I)))
    print("  external <link href=http>:", len(re.findall(r'<link[^>]*href="https?:', html, re.I)))
    print("  word 'phantom' in the page shell (outside the data payload):",
          len(re.findall("phantom", shell, re.I)))
    print("  word 'phantom' anywhere in the file:", len(re.findall("phantom", html, re.I)))
    print("  file size MB: %.2f" % (HTML.stat().st_size / 1e6))
    print()

    # ---- tier vs lane -------------------------------------------------
    tiers = Counter((r.get("tier"), "core11" in r["lane"]) for r in rows)
    print("=== tier=='core' vs lane 'core11' ===")
    for k, v in sorted(tiers.items(), key=lambda x: str(x[0])):
        print("  tier=%-14s core11=%s  rows=%d" % (k[0], k[1], v))


if __name__ == "__main__":
    main()
