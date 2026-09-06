"""T1 referee, pass 4 -- refute the repair at commit fc2372a1.

Independent re-derivation. Nothing here is imported from research/build_tape.py.
The only shared imports are `universe` (the single source of symbols, guarded by
its own test) and R3's own day-policy helpers (`research.loop_cycle.up_to_3_rows`,
`research.g72_suppress_price.oneaday_rows`) -- those define the UNIT, they are not
T1's code, and re-implementing them would measure a different unit.

Checks:
  A  default selection reproduces (page-side and book-side)
  B  the exclusive-select repair: is a source/fillmode UNION still reachable?
  C  duplicate count on the spec's (sym, day, et) key
  D  5 random filter combinations, page-side vs book-side
  E  stamps on every merged book
  F  hygiene: canvas / external script / external link / hard-coded dollars
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

import universe                                            # noqa: E402
from research.loop_cycle import up_to_3_rows               # noqa: E402
from research.g72_suppress_price import oneaday_rows       # noqa: E402
from research.build_bt2y_report import book_of             # noqa: E402

TAPE = ROOT / "research" / "tape"
HTML = TAPE / "omen-tape.html"
RISK = 1000.0
SEED = 20260906_4

CORE = frozenset(universe.CORE_SYMBOLS)
INDEX = frozenset(universe.INDEX_POOL_SET)


# ------------------------------------------------------------------ payload
def load_payload():
    h = HTML.read_text(encoding="utf-8")
    tag = '<script id="data" type="application/json">'
    s = h.index(tag) + len(tag)
    e = h.index("</script>", s)
    return h, json.loads(h[s:e])


def page_multi(html):
    m = re.search(r"var MULTI = \{([^}]*)\}", html)
    return {k.strip(): 1 for k in re.findall(r"(\w+)\s*:\s*1", m.group(1))}


def passes(sel, cols, multi, i):
    """Exactly the page's passes(): an EMPTY set means no filter at all."""
    for k, s in sel.items():
        if not s:
            continue
        if multi.get(k):
            if not any(c in s for c in cols[k][i]):
                return False
        elif cols[k][i] not in s:
            return False
    return True


def sel_from(dicts, spec):
    """spec: {field: [values]} -> {field: set(codes)}."""
    out = {}
    for f, vals in spec.items():
        codes = set()
        for v in vals:
            if v in dicts[f]:
                codes.add(dicts[f].index(v))
        out[f] = codes
    return out


def page_stats(idxs, cols, dicts):
    n = len(idxs)
    w = l = sc = dec = 0
    sumR = gp = gl = 0.0
    winP = lossP = 0.0
    winN = lossN = 0
    eq = peak = dd = 0.0
    byMonth, byWeek, days = defaultdict(float), defaultdict(float), set()
    for i in idxs:
        r = cols["r"][i]
        o = dicts["out"][cols["out"][i]]
        sumR += r
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
        p = r * RISK
        if p > 0:
            winP += p; winN += 1
        elif p < 0:
            lossP += p; lossN += 1
        eq += r
        if eq > peak:
            peak = eq
        if peak - eq > dd:
            dd = peak - eq
        byMonth[dicts["ym"][cols["ym"][i]]] += r
        byWeek[dicts["wk"][cols["wk"][i]]] += r
        days.add(dicts["day"][cols["day"][i]])
    nd = len(days)
    return {
        "n": n, "sumR": round(sumR, 4), "meanR": round(sumR / n, 4) if n else 0,
        "winPct": round(w / dec * 100, 1) if dec else 0,
        "months": len(byMonth), "green": sum(1 for v in byMonth.values() if v > 0),
        "weeks": len(byWeek), "weeksGreen": sum(1 for v in byWeek.values() if v > 0),
        "days": nd, "perDay": round(sumR * RISK / nd, 1) if nd else 0,
        "firesPerDay": round(n / nd, 3) if nd else 0,
        "avgWin": round(winP / winN, 0) if winN else 0,
        "avgLoss": round(lossP / lossN, 0) if lossN else 0,
        "maxDD_R": round(dd, 2),
        "pf": round(gp / gl, 3) if gl else None,
    }


# ------------------------------------------------------------------- books
SOURCES = [
    ("baseline", "close", "baseline_2026-09-05.json.gz", False),
    ("baseline", "phantom", "baseline_2026-09-05_published.json.gz", True),
    ("L1_on", "close", "book_MIN_PT1_R_on.json.gz", True),
    ("L2_on", "close", "book_RULE84_DECIDED_on.json.gz", True),
    ("L3_on", "close", "book_OCR_RETEST_DISPLACEMENT_on.json.gz", True),
    ("L4_on", "close", "book_TREND_DEF_on.json.gz", True),
    ("L5_on", "close", "book_DAY_POLICY_on.json.gz", True),
]


def lane_of(sym):
    lanes = []
    if sym in CORE:
        lanes.append("core11")
    if sym in INDEX:
        lanes.append("index3")
    lanes.append("full29")
    return lanes


def week_of(day):
    try:
        y, w, _ = date.fromisoformat(day).isocalendar()
        return "%d-W%02d" % (y, w)
    except Exception:
        return "n/a"


def load_books():
    """My own merge, my own tagging."""
    all_rows = []
    stamps = {}
    for src, fill, fname, tradedonly in SOURCES:
        with gzip.open(TAPE / fname, "rt", encoding="utf-8") as f:
            b = json.load(f)
        meta, trades = b["meta"], b["trades"]
        stamps["%s/%s" % (src, fill)] = (fname, meta.get("stamp", {}))
        if tradedonly:
            rows = [r for r in trades if r.get("traded") or r.get("status") == "halted"]
        else:
            rows = [r for r in trades if r.get("status") != "skipped_d"]
        for r in rows:
            r["book"] = book_of(r)
            r["source"] = src
            r["fillmode"] = fill
            r["lane"] = lane_of(r.get("sym", ""))
            r["wk"] = week_of(r.get("day", ""))
            r["policy"] = []
        # day policy on the core lane, R3's own definition
        core = [r for r in rows if r.get("tier") == "core"]
        cand = [r for r in core
                if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted"]
        first_ids = {id(r) for r in oneaday_rows(core)}
        up3_ids = {id(r) for r in up_to_3_rows(core)}
        for r in cand:
            t = ["every_signal"]
            if id(r) in first_ids:
                t.append("first_of_day")
            if id(r) in up3_ids:
                t.append("up_to_3")
            r["policy"] = t
        all_rows.extend(rows)
    return all_rows, stamps


def book_stats(rows):
    n = len(rows)
    sumR = 0.0
    w = dec = 0
    winP = lossP = 0.0
    winN = lossN = 0
    eq = peak = dd = 0.0
    gp = gl = 0.0
    byMonth, byWeek, days = defaultdict(float), defaultdict(float), set()
    for r in rows:
        rr = r.get("r", 0.0)
        sumR += rr
        o = r.get("out")
        if o == "win":
            w += 1; dec += 1
        elif o == "loss":
            dec += 1
        if rr > 0:
            gp += rr
        else:
            gl += -rr
        p = rr * RISK
        if p > 0:
            winP += p; winN += 1
        elif p < 0:
            lossP += p; lossN += 1
        eq += rr
        if eq > peak:
            peak = eq
        if peak - eq > dd:
            dd = peak - eq
        byMonth[r["day"][:7]] += rr
        byWeek[week_of(r["day"])] += rr
        days.add(r["day"])
    nd = len(days)
    return {
        "n": n, "sumR": round(sumR, 4), "meanR": round(sumR / n, 4) if n else 0,
        "winPct": round(w / dec * 100, 1) if dec else 0,
        "months": len(byMonth), "green": sum(1 for v in byMonth.values() if v > 0),
        "weeks": len(byWeek), "weeksGreen": sum(1 for v in byWeek.values() if v > 0),
        "days": nd, "perDay": round(sumR * RISK / nd, 1) if nd else 0,
        "firesPerDay": round(n / nd, 3) if nd else 0,
        "avgWin": round(winP / winN, 0) if winN else 0,
        "avgLoss": round(lossP / lossN, 0) if lossN else 0,
        "maxDD_R": round(dd, 2),
        "pf": round(gp / gl, 3) if gl else None,
    }


def book_filter(rows, spec, multi):
    out = []
    for r in rows:
        ok = True
        for f, vals in spec.items():
            if not vals:
                continue
            v = r.get(f)
            if f in multi or isinstance(v, list):
                if not set(vals) & set(v or []):
                    ok = False; break
            else:
                if v not in vals:
                    ok = False; break
        if ok:
            out.append(r)
    return out


# ---------------------------------------------------------------------- run
def main():
    html, p = load_payload()
    dicts, cols = p["dicts"], p["cols"]
    multi = page_multi(html)
    N = len(cols["r"])
    print("payload rows:", N, " facets:", len(p["facets"]), " MULTI:", sorted(multi))
    print("meta:", {k: p["meta"][k] for k in ("sessions", "signals", "traded", "risk_dollars",
                                              "first", "last")})

    rows, stamps = load_books()
    print("book-side merged rows:", len(rows))

    DEFAULT = {"source": ["baseline"], "fillmode": ["close"],
               "lane": ["core11"], "policy": ["up_to_3"]}

    def page_run(spec):
        sel = sel_from(dicts, spec)
        idxs = [i for i in range(N) if passes(sel, cols, multi, i)]
        return page_stats(idxs, cols, dicts), idxs

    # ---- A: default cell
    st, idxs = page_run(DEFAULT)
    bs = book_stats(book_filter(rows, DEFAULT, multi))
    print("\n=== A default (source=baseline, fillmode=close, lane=core11, policy=up_to_3)")
    print("  page:", st)
    print("  book:", bs)
    print("  AGREE:", st == bs)

    # ---- B: is the union still reachable through the rail?
    print("\n=== B exclusive-select escape hatch")
    src = re.search(r"var EXCLUSIVE_SELECT[\s\S]{0,600}?\}\);", html).group(0)
    print(src)
    hatches = {
        "B1 one click on the ACTIVE fillmode chip -> fillmode empty":
            {"source": ["baseline"], "fillmode": [], "lane": ["core11"], "policy": ["up_to_3"]},
        "B2 one click on the ACTIVE source chip -> source empty":
            {"source": [], "fillmode": ["close"], "lane": ["core11"], "policy": ["up_to_3"]},
        "B3 both cleared":
            {"source": [], "fillmode": [], "lane": ["core11"], "policy": ["up_to_3"]},
        "B4 phantom alone (one click on the phantom chip)":
            {"source": ["baseline"], "fillmode": ["phantom"], "lane": ["core11"],
             "policy": ["up_to_3"]},
    }
    for name, spec in hatches.items():
        s, _ = page_run(spec)
        b = book_stats(book_filter(rows, spec, multi))
        print(" ", name)
        print("    page:", {k: s[k] for k in ("n", "perDay", "meanR", "green", "months", "days")})
        print("    book:", {k: b[k] for k in ("n", "perDay", "meanR", "green", "months", "days")},
              " AGREE:", s == b)

    # ---- C: duplicates on the spec key
    print("\n=== C duplicates on the spec key (symbol, day, entry minute)")
    tradedcode = dicts["status"].index("fired") if "fired" in dicts["status"] else None
    # page-side "traded": use r!=0 is wrong; use the `book` facet == traded
    bookdict = dicts["book"]
    tcode = bookdict.index("traded") if "traded" in bookdict else None
    for scope, pred in [
        ("all merged sources, traded rows, key=(source,fillmode,sym,day,et)",
         lambda i: cols["book"][i] == tcode),
    ]:
        c = Counter()
        for i in range(N):
            if not pred(i):
                continue
            c[(cols["source"][i], cols["fillmode"][i], cols["sym"][i],
               cols["day"][i], cols["et"][i])] += 1
        d = {k: v for k, v in c.items() if v > 1}
        print("  %s: %d dupe keys, %d extra rows" % (scope, len(d), sum(v - 1 for v in d.values())))
    # strict spec key: ignore source/fillmode entirely, inside baseline/close only
    for label, sfilter in [
        ("baseline/close only", lambda i: dicts["source"][cols["source"][i]] == "baseline"
                                and dicts["fillmode"][cols["fillmode"][i]] == "close"),
    ]:
        c = Counter()
        for i in range(N):
            if cols["book"][i] != tcode or not sfilter(i):
                continue
            c[(cols["sym"][i], cols["day"][i], cols["et"][i])] += 1
        d = {k: v for k, v in c.items() if v > 1}
        print("  %s, key=(sym,day,et): %d dupe keys, %d extra rows"
              % (label, len(d), sum(v - 1 for v in d.values())))
    # inside the published default unit
    c = Counter()
    for i in idxs:
        c[(cols["sym"][i], cols["day"][i], cols["et"][i])] += 1
    d = {k: v for k, v in c.items() if v > 1}
    groups = defaultdict(list)
    for i in idxs:
        k = (cols["sym"][i], cols["day"][i], cols["et"][i])
        if k in d:
            groups[k].append(i)
    all_involved = [i for g in groups.values() for i in g]
    extras = [g[1] for g in groups.values()]          # the 2nd row of each pair
    print("  inside the published 769-row default unit: %d dupe keys, %d extra rows"
          % (len(d), sum(v - 1 for v in d.values())))
    print("    both rows of each pair: %d rows, sum r = %.4f ($%.0f)"
          % (len(all_involved), sum(cols["r"][i] for i in all_involved),
             sum(cols["r"][i] for i in all_involved) * RISK))
    print("    the 2nd row of each pair only: %d rows, sum r = %.4f ($%.0f)"
          % (len(extras), sum(cols["r"][i] for i in extras),
             sum(cols["r"][i] for i in extras) * RISK))
    for k, g in groups.items():
        print("      %s  ->  %s"
              % (tuple(dicts[f][cols[f][g[0]]] for f in ("sym", "day", "et")),
                 [(dicts["level"][cols["level"][i]], round(cols["r"][i], 4)) for i in g]))

    # ---- C2: the docstring's stated REASON for the old key's zero
    print("\n=== C2 does level_name 'always differ' between the two rows of a duplicate?")
    g2 = defaultdict(list)
    for i in range(N):
        if cols["book"][i] != tcode:
            continue
        if dicts["source"][cols["source"][i]] != "baseline":
            continue
        if dicts["fillmode"][cols["fillmode"][i]] != "close":
            continue
        g2[(cols["sym"][i], cols["day"][i], cols["et"][i])].append(i)
    pairs = [v for v in g2.values() if len(v) > 1]
    same_level = [v for v in pairs
                  if len({dicts["level"][cols["level"][i]] for i in v}) == 1]
    same_r = [v for v in pairs if len({round(cols["r"][i], 6) for i in v}) == 1]
    print("  baseline/close duplicate groups: %d" % len(pairs))
    print("  groups where every row shares the SAME level name: %d" % len(same_level))
    print("  groups where every row shares the SAME r: %d" % len(same_r))

    # ---- D: 5 random filter combinations
    print("\n=== D five random filter combinations (seed %d)" % SEED)
    rnd = random.Random(SEED)
    fields = ["source", "fillmode", "lane", "policy", "sym", "setup", "grade",
              "sgrade", "dir", "dow", "yr", "book", "out"]
    agree = 0
    for k in range(5):
        spec = {}
        nf = rnd.randint(2, 4)
        for f in rnd.sample(fields, nf):
            vals = [v for v in dicts[f] if v is not None]
            if not vals:
                continue
            spec[f] = [rnd.choice(vals)]
        s, _ = page_run(spec)
        b = book_stats(book_filter(rows, spec, multi))
        ok = (s == b)
        agree += ok
        print("  combo %d: %s" % (k + 1, spec))
        print("    page:", s)
        print("    book:", b)
        print("    AGREE:", ok)
    print("  combos agreeing: %d/5" % agree)

    # ---- E: stamps
    print("\n=== E stamps")
    for name, (fname, st_) in stamps.items():
        g = st_.get("git", {})
        print("  %-18s %-42s book_id=%s commit=%s dirty=%s built=%s window=%s..%s"
              % (name, fname, st_.get("book_id"), (g.get("commit") or "?")[:10],
                 g.get("dirty_py_count", g.get("dirty")), st_.get("built_at", st_.get("built")),
                 st_.get("window", {}).get("first"), st_.get("window", {}).get("last")))

    # ---- F: hygiene
    print("\n=== F hygiene")
    print("  <canvas>:", html.count("<canvas"))
    print("  <script src:", html.count("<script src"))
    print("  external <link href>:", re.findall(r'<link[^>]+href="(https?://[^"]+)"', html))
    tag = '<script id="data" type="application/json">'
    s0 = html.index(tag)
    shell = html[:s0] + html[html.index("</script>", s0):]
    print("  shell bytes:", len(shell), " 'phantom' in shell:", shell.lower().count("phantom"))
    bt = (ROOT / "research" / "build_tape.py").read_text(encoding="utf-8")
    print("  '127 pairs' in build_tape.py:", "127 pairs" in bt)
    print("  hardcoded $ literals in build_tape.py:",
          sorted(set(re.findall(r"\$[0-9][0-9,\.]*", bt))))


if __name__ == "__main__":
    main()
