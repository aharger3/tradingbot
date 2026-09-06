"""t1_referee_pass3.py -- T1 referee, THIRD pass.

The builder reported T1 "landed" at commit 380667a6 with no change this turn,
so this pass asks one question: are pass 2's open defects still open at HEAD,
and does anything the builder's report says fail on its own terms?

Everything is re-derived here. Nothing is imported from build_tape.py except
in the one clearly-marked block that re-checks the published 769-row unit.

Run: python research/t1_referee_pass3.py
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TAPE = ROOT / "research" / "tape"


def load_gz(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


PAIRS = [
    ("MIN_PT1_R", "book_MIN_PT1_R_off.json.gz", "book_MIN_PT1_R_on.json.gz"),
    ("RULE84_DECIDED", "book_RULE84_DECIDED_off.json.gz", "book_RULE84_DECIDED_on.json.gz"),
    ("OCR_RETEST_DISPLACEMENT", "book_OCR_RETEST_DISPLACEMENT_off.json.gz",
     "book_OCR_RETEST_DISPLACEMENT_on.json.gz"),
    ("TREND_DEF", "book_TREND_DEF_off.json.gz", "book_TREND_DEF_on.json.gz"),
    ("DAY_POLICY", "book_DAY_POLICY_off.json.gz", "book_DAY_POLICY_on.json.gz"),
]


def main():
    base_meta, base_rows = load_gz(TAPE / "baseline_2026-09-05.json.gz")
    base_id = base_meta["stamp"]["book_id"]
    print("== is the baseline really every Phase-L flag's OFF arm? ==")
    print("  baseline book_id = %s (commit %s)"
          % (base_id, base_meta["stamp"]["git"]["commit"][:10]))
    for flag, off, on in PAIRS:
        mo, _ = load_gz(TAPE / off)
        mn, _ = load_gz(TAPE / on)
        oid = mo["stamp"]["book_id"]
        print("  %-24s off=%s %-6s  on=%s   off_commit=%s on_commit=%s"
              % (flag, oid, "SAME" if oid == base_id else "DIFF",
                 mn["stamp"]["book_id"], mo["stamp"]["git"]["commit"][:10],
                 mn["stamp"]["git"]["commit"][:10]))

    print("\n== the duplicate identity, three ways, on the baseline/close book ==")
    traded = [r for r in base_rows if r.get("traded")]
    print("  traded rows: %d" % len(traded))

    def count(keyfn, label):
        c = Counter(keyfn(r) for r in traded)
        d = {k: v for k, v in c.items() if v > 1}
        print("  %-58s keys>1=%-5d extra rows=%-5d" % (label, len(d), sum(v - 1 for v in d.values())))
        return d

    spec = count(lambda r: (r.get("sym"), r.get("day"), r.get("et")),
                 "spec identity (sym, day, entry minute)")
    count(lambda r: (r.get("sym"), r.get("day"), r.get("et"), r.get("dir"),
                     round(r.get("entry") or 0, 4), round(r.get("stop") or 0, 4),
                     round(r.get("pnl") or 0, 4), r.get("status")),
          "builder identity MINUS level_name")
    count(lambda r: (r.get("sym"), r.get("day"), r.get("et"), r.get("dir"),
                     round(r.get("entry") or 0, 4), round(r.get("stop") or 0, 4),
                     round(r.get("pnl") or 0, 4), r.get("status"), r.get("level_name")),
          "builder identity (with level_name) -- what the build asserts is 0")

    # how many of the spec-identity duplicates are P&L-identical twins?
    by = defaultdict(list)
    for r in traded:
        by[(r.get("sym"), r.get("day"), r.get("et"))].append(r)
    same_pnl = diff_pnl = 0
    dollars_double = 0.0
    for k in spec:
        rs = by[k]
        pnls = {round(x.get("pnl") or 0, 2) for x in rs}
        if len(pnls) == 1:
            same_pnl += len(rs) - 1
            dollars_double += (len(rs) - 1) * list(pnls)[0]
        else:
            diff_pnl += len(rs) - 1
    print("  of the extra rows: %d are P&L-identical twins ($%.0f counted twice), "
          "%d differ in P&L" % (same_pnl, dollars_double, diff_pnl))

    ex = sorted(spec.items())[:6]
    print("  examples:")
    for k, n in ex:
        rs = by[k]
        print("    %s x%d -> %s" % (str(k), n,
              [(x.get("level_name"), round(x.get("entry") or 0, 2),
                round(x.get("pnl") or 0, 0), x.get("setup")) for x in rs]))

    print("\n== the 5 duplicates inside R3's own 769-trade unit ==")
    from research.build_tape import load_rich_sources
    rows, _ = load_rich_sources()
    unit = [r for r in rows if r["source"] == "baseline" and r["fillmode"] == "close"
            and "up_to_3" in r["policy"]]
    cu = Counter((r["sym"], r["day"], r["et"]) for r in unit)
    byu = defaultdict(list)
    for r in unit:
        byu[(r["sym"], r["day"], r["et"])].append(r)
    tot = 0.0
    for k, n in sorted(cu.items()):
        if n > 1:
            rs = byu[k]
            print("  %s x%d -> %s" % (str(k), n,
                  [(x.get("level_name"), round(x.get("entry") or 0, 2),
                    round(x.get("pnl") or 0, 0)) for x in rs]))
            tot += sum(x.get("pnl") or 0 for x in rs[1:])
    print("  dollars the duplicate rows add to the 769-trade unit: $%.0f "
          "(of $%.0f total)" % (tot, sum(r.get("pnl") or 0 for r in unit)))

    # ---- pass 2 Defect A, re-measured on the page's own embedded payload --
    print("\n== what the page prints, one chip away from the default ==")
    import re
    html = (TAPE / "omen-tape.html").read_text(encoding="utf-8")
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>',
                  html, re.DOTALL)
    payload = json.loads(m.group(1))
    dicts, cols = payload["dicts"], payload["cols"]
    MULTI = {"tags", "downgrades", "lane", "policy"}
    N = len(cols["day"])

    def select(picks):
        sel = {f: {dicts[f].index(v) for v in vals if v in dicts[f]}
               for f, vals in picks.items()}
        out = []
        for i in range(N):
            ok = True
            for k, s in sel.items():
                if not s:
                    continue
                if k in MULTI:
                    if not (set(cols[k][i]) & s):
                        ok = False; break
                elif cols[k][i] not in s:
                    ok = False; break
            if ok:
                out.append(i)
        return out

    def scoreboard(idxs):
        sumR = 0.0
        bym, days = defaultdict(float), set()
        for i in idxs:
            r = cols["r"][i]
            sumR += r
            bym[dicts["ym"][cols["ym"][i]]] += r
            days.add(dicts["day"][cols["day"][i]])
        nd = len(days) or 1
        return (len(idxs), round(sumR * 1000.0 / nd, 1),
                round(sumR / len(idxs), 4) if idxs else 0.0,
                sum(1 for v in bym.values() if v > 0), len(bym), nd)

    views = [
        ("the default view (honest close fill)",
         {"source": ["baseline"], "fillmode": ["close"], "lane": ["core11"],
          "policy": ["up_to_3"]}),
        ("+ the second Fill mode chip (close AND phantom)",
         {"source": ["baseline"], "fillmode": ["close", "phantom"],
          "lane": ["core11"], "policy": ["up_to_3"]}),
        ("phantom alone",
         {"source": ["baseline"], "fillmode": ["phantom"], "lane": ["core11"],
          "policy": ["up_to_3"]}),
        ("cleared the source chip",
         {"fillmode": ["close"], "lane": ["core11"], "policy": ["up_to_3"]}),
        ("TRULY unfiltered -- every chip cleared (what the page opens to "
         "if defaultSel is skipped)", {}),
    ]
    print("  %-58s %8s %11s %9s %8s %6s" %
          ("view", "rows", "$/day", "mean R", "green", "days"))
    for label, picks in views:
        n, pd, mr, g, mo, nd = scoreboard(select(picks))
        print("  %-58s %8d %11.1f %9.4f %5d/%-2d %6d" % (label, n, pd, mr, g, mo, nd))

    print("\n  occurrences of the word 'phantom' outside the JSON payload: %d"
          % (html.count("phantom") - json.dumps(payload).count("phantom")
             if "phantom" in html else 0))
    shell = re.sub(r'<script id="data" type="application/json">.*?</script>',
                   "", html, flags=re.DOTALL)
    shell = re.sub(r'<script id="fillarmdata" type="application/json">.*?</script>',
                   "", shell, flags=re.DOTALL)
    print("  'phantom' in the page shell (payload stripped): %d" % shell.count("phantom"))
    print("  'published fill' / warning words in the shell  : phantom=%d void=%d "
          "unobtainable=%d" % (shell.count("phantom"), shell.count("void"),
                               shell.count("unobtainable")))


if __name__ == "__main__":
    main()
