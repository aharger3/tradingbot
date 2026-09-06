"""t1_referee.py -- independent re-derivation for the T1 referee note.

Refutes-or-upholds row T1 (research/build_tape.py -> research/tape/omen-tape.html,
builder commit a94948d93c0ce06d389b620830185a2099979448) WITHOUT trusting the
builder's own code paths: every number below is recomputed here from the stamped
.json.gz books in research/tape/ and from the JSON payload physically embedded
in the shipped HTML.

Run: python research/t1_referee.py
Companion: research/t1_referee_pagejs.js (runs the page's own JS under a DOM shim).
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
TAPE = ROOT / "research" / "tape"
HTML = TAPE / "omen-tape.html"
RISK = 1000.0

CORE11 = ["TSLA", "NVDA", "AAPL", "AMD", "META", "GOOGL", "AMZN", "MSFT",
          "PLTR", "QQQ", "SPY"]

SOURCES = [
    ("baseline", "close", "baseline_2026-09-05.json.gz", "rich"),
    ("baseline", "phantom", "baseline_2026-09-05_published.json.gz", "trim"),
    ("L1_on", "close", "book_MIN_PT1_R_on.json.gz", "trim"),
    ("L2_on", "close", "book_RULE84_DECIDED_on.json.gz", "trim"),
    ("L3_on", "close", "book_OCR_RETEST_DISPLACEMENT_on.json.gz", "trim"),
    ("L4_on", "close", "book_TREND_DEF_on.json.gz", "trim"),
    ("L5_on", "close", "book_DAY_POLICY_on.json.gz", "trim"),
]

NEW_FACETS = ["source", "fillmode", "lane", "policy", "wk", "exitmodel", "instrument"]


def load_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def iso_week(day):
    y, w, _ = date.fromisoformat(day).isocalendar()
    return "%04d-W%02d" % (y, w)


def metrics(rows, n_sessions):
    """$/day, mean R, avg win / avg loss, win rate, months green, weeks green,
    max drawdown -- all on the blended trade-level pnl column, 1R = $1,000."""
    if not rows:
        return {"trades": 0}
    pnls = [r.get("pnl", 0.0) for r in rows]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    total = sum(pnls)
    by_m, by_w = defaultdict(float), defaultdict(float)
    for r in rows:
        by_m[r["day"][:7]] += r.get("pnl", 0.0)
        by_w[iso_week(r["day"])] += r.get("pnl", 0.0)
    cum = peak = worst = 0.0
    for r in sorted(rows, key=lambda x: (x["day"], x.get("et") or "")):
        cum += r.get("pnl", 0.0)
        peak = max(peak, cum)
        worst = max(worst, peak - cum)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = -sum(losses) / len(losses) if losses else 0.0
    return {
        "trades": len(rows),
        "total": round(total, 0),
        "per_day": round(total / n_sessions, 0) if n_sessions else 0,
        "mean_r": round(total / len(rows) / RISK, 4),
        "avg_win": round(avg_win, 0),
        "avg_loss": round(avg_loss, 0),
        "awal": round(avg_win / avg_loss, 3) if avg_loss else None,
        "win_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 1)
                   if (wins or losses) else 0.0,
        "months": len(by_m),
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "weeks": len(by_w),
        "weeks_green": sum(1 for v in by_w.values() if v > 0),
        "max_dd": round(worst, 0),
    }


# --------------------------------------------------------- independent merge

def my_up_to_3(rows):
    """His day policy, re-implemented here from the spec sentence rather than
    imported: candidates are fired-and-traded rows plus the account-wide
    halted rows; per day, take up to 3 in (et, sym) order, stop after the
    first winner or after the second loser."""
    byday = defaultdict(list)
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday[r["day"]].append(r)
    out = []
    for day in sorted(byday):
        losses = taken = 0
        for r in sorted(byday[day], key=lambda x: (x.get("et") or "", x.get("sym") or "")):
            if taken >= 3:
                break
            out.append(r)
            taken += 1
            p = r.get("pnl", 0.0)
            if p > 0:
                break
            if p < 0:
                losses += 1
                if losses >= 2:
                    break
    return out


def merged_rows():
    """The same 7-source merge build_tape.py performs, rebuilt here."""
    out = []
    for src, fill, fname, mode in SOURCES:
        _meta, rows = load_gz(TAPE / fname)
        if mode == "rich":
            rows = [r for r in rows if r.get("status") != "skipped_d"]
        else:
            rows = [r for r in rows if r.get("traded") or r.get("status") == "halted"]
        for r in rows:
            r["_source"] = src
            r["_fill"] = fill
        out.extend(rows)
    return out


# ------------------------------------------------------------ page payload

def page_payload():
    s = HTML.read_text(encoding="utf-8")
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', s, re.S)
    return json.loads(m.group(1)), s


def page_passes(cols, multi, sel, i):
    """The page's own passes(i), transcribed to Python."""
    for k, codes in sel.items():
        if not codes:
            continue
        if k in multi:
            if not (set(cols[k][i]) & codes):
                return False
        elif cols[k][i] not in codes:
            return False
    return True


def main():
    print("=" * 78)
    print("T1 REFEREE -- builder commit a94948d93c0ce06d389b620830185a2099979448")
    print("=" * 78)

    payload, html = page_payload()
    dicts, cols = payload["dicts"], payload["cols"]
    facet_names = [f[0] for f in payload["facets"]]

    # -------------------------------------------------- CHECK A: facet coverage
    print("\n[A] Do the page's declared facets exist in its embedded data?")
    missing = [f for f in facet_names if f not in dicts or f not in cols]
    print("    facets declared : %d" % len(facet_names))
    print("    missing from dicts/cols : %r" % (missing,))
    print("    -> the seven facets T1 was built to add are %s"
          % ("ALL MISSING" if set(missing) == set(NEW_FACETS) else "partly present"))

    # -------------------------------------------------- CHECK B: default select
    # The page's defaultSel() picks source=baseline, fillmode=close,
    # lane=core11, policy=up_to_3. Try it against the real embedded dicts.
    print("\n[B] Can the page's own defaultSel() run against its own data?")
    for field, value in [("source", "baseline"), ("fillmode", "close"),
                         ("lane", "core11"), ("policy", "up_to_3")]:
        d = dicts.get(field)
        print("    dicts[%-9s] -> %s" % (field, "MISSING (JS throws here)" if d is None
                                         else "code %d" % d.index(value)))

    # -------------------------------------------------- CHECK C: the R3 number
    print("\n[C] Independent re-derivation of the R3 default selection")
    _mb, base = load_gz(TAPE / "baseline_2026-09-05.json.gz")
    sessions = len({r["day"] for r in base})
    core = [r for r in base if r.get("tier") == "core"]
    up3 = my_up_to_3(core)
    m = metrics(up3, sessions)
    print("    unit: up-to-3-a-day stop-after-a-win-or-2-losses, core-11,")
    print("          honest close fill, shipped ladder exit, 1R=$1,000")
    print("    sessions in book: %d" % sessions)
    print("    " + json.dumps(m))
    print("    loop.json baseline_figures.whole: trades 769, per_day -52,")
    print("          mean_r -0.0335, win 45.0, months_green 11/25,")
    print("          avg_win 801, avg_loss 716, awal 1.119")
    # core-11 sanity: which symbols does tier==core actually admit?
    syms = sorted({r["sym"] for r in core})
    print("    tier=='core' symbols (%d): %s" % (len(syms), syms))
    print("    universe.CORE_SYMBOLS (%d): %s" % (len(CORE11), sorted(CORE11)))

    # -------------------------------------------------- CHECK D: duplicates
    print("\n[D] Duplicate rows -- the spec's key is (symbol, day, entry minute)")
    rows = merged_rows()
    traded = [r for r in rows if r.get("traded")]
    print("    merged traded rows: %d (builder reported 26,803)" % len(traded))
    for keyname, keyfn in [
        ("spec key  (sym, day, et) within one source+fill",
         lambda r: (r["_source"], r["_fill"], r["sym"], r["day"], r.get("et"))),
        ("builder key (+dir, entry, stop, pnl, status, level_name)",
         lambda r: (r["_source"], r["_fill"], r["sym"], r["day"], r.get("et"),
                    r.get("dir"), round(r.get("entry") or 0.0, 4),
                    round(r.get("stop") or 0.0, 4), round(r.get("pnl") or 0.0, 4),
                    r.get("status"), r.get("level_name"))),
    ]:
        c = Counter(keyfn(r) for r in traded)
        d = {k: n for k, n in c.items() if n > 1}
        print("    %-58s dupe keys: %d, extra rows: %d"
              % (keyname, len(d), sum(n - 1 for n in d.values())))
        for k, n in list(d.items())[:3]:
            print("        e.g. %r x%d" % (k, n))
    # and inside the published default selection
    up3c = Counter((r["sym"], r["day"], r.get("et")) for r in up3)
    dd = {k: n for k, n in up3c.items() if n > 1}
    print("    inside the R3 default selection (769 rows): %d dupe keys, %d extra rows"
          % (len(dd), sum(n - 1 for n in dd.values())))
    for k, n in list(dd.items())[:5]:
        print("        %r x%d" % (k, n))

    # -------------------------------------------------- CHECK E: five combos
    print("\n[E] Five filter combinations, page filter logic vs the books")
    multi = {"tags", "downgrades", "lane", "policy"}
    rnd = random.Random(20260905)
    pool_fields = ["sym", "setup", "dir", "grade", "level", "slot", "dow",
                   "yr", "sgrade", "out", "status", "book"]
    combos = []
    while len(combos) < 5:
        fs = rnd.sample(pool_fields, 2)
        pick = {}
        ok = True
        for f in fs:
            if f not in dicts:
                ok = False
                break
            pick[f] = rnd.choice(dicts[f])
        if ok and pick not in [c for c, _ in combos]:
            combos.append((pick, fs))
    # the two combos the row's verify actually demands, which cannot be run:
    blocked = [{"source": "baseline", "fillmode": "close", "lane": "core11",
                "policy": "up_to_3"},
               {"source": "L3_on", "fillmode": "close", "lane": "index3"}]

    for n, (pick, _fs) in enumerate(combos, 1):
        sel = {f: {dicts[f].index(v)} for f, v in pick.items()}
        idxs = [i for i in range(len(cols["day"])) if page_passes(cols, multi, sel, i)]
        # the page's own stats() are R-based and count every matching row
        page_rows = [{"day": dicts["day"][cols["day"][i]],
                      "et": dicts["et"][cols["et"][i]],
                      "pnl": cols["pnl"][i], "r": cols["r"][i]} for i in idxs]
        pm = metrics(page_rows, 499) if page_rows else {"trades": 0}
        # the same filter applied to the baseline/close source only
        def match(r):
            for f, v in pick.items():
                rv = r.get(f)
                if f == "book":
                    rv = ("traded" if r.get("traded") else
                          "alert only (C)" if r.get("alert") else
                          "tight-stop skip" if r.get("status") == "skipped_tight_stop"
                          else "filtered (X)")
                rv = "yes" if rv is True else "no" if rv is False else str(rv)
                if rv != v:
                    return False
            return True
        base_only = [r for r in rows
                     if r["_source"] == "baseline" and r["_fill"] == "close" and match(r)]
        bm = metrics(base_only, 499) if base_only else {"trades": 0}
        print("\n    combo %d: %s" % (n, json.dumps(pick)))
        print("      page (all 7 books merged, no source facet to separate them):")
        print("        " + json.dumps(pm))
        print("      baseline/close book alone (what the reader would want):")
        print("        " + json.dumps(bm))
        if pm.get("trades") and bm.get("trades"):
            print("      inflation factor on trades: %.2fx"
                  % (pm["trades"] / bm["trades"]))

    print("\n    Two combinations the row's own verify demands, and their status:")
    for b in blocked:
        need = [f for f in b if f not in dicts]
        print("      %s -> UNRUNNABLE, fields absent from the page: %r"
              % (json.dumps(b), need))

    # -------------------------------------------------- CHECK F: page hygiene
    print("\n[F] Page hygiene")
    print("    <canvas> occurrences        : %d" % html.lower().count("<canvas"))
    print("    external <script src>       : %d" % len(re.findall(r'<script[^>]*\bsrc=', html, re.I)))
    print("    external <link rel=stylesheet>: %r"
          % re.findall(r'<link[^>]*stylesheet[^>]*>', html))
    print("    size                        : %.2f MB" % (HTML.stat().st_size / 1e6))

    # -------------------------------------------------- CHECK G: stamps
    print("\n[G] Stamp check on every book the page reads")
    for src, fill, fname, _m in SOURCES:
        meta, _t = load_gz(TAPE / fname)
        st = meta.get("stamp", {})
        git = st.get("git", {})
        print("    %-9s %-8s %-42s book_id %s commit %s built %s"
              % (src, fill, fname, st.get("book_id"),
                 (git.get("commit") or "?")[:10], st.get("built_at")))


if __name__ == "__main__":
    main()
