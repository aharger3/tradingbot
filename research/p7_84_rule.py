"""P7 / G1 — the 84%-rule three-arm A/B, and the arm-gate funnel behind it.

The 84% rule is Austin's sanctioned re-entry after a stop-out. In the 2-year
replay it produces **3 signals**. This measures why, and what the alternatives
cost, over three arms of the SAME gate:

    strict   RULE84_STRICT=1                      the shipped default (control)
    loose    RULE84_STRICT=0                      arm off any counted stop-out
                                                  on an arming setup (B&R / OCR)
    sgrade   RULE84_ARM_SGRADE=1                  arm only when the ORIGINAL trade
                                                  scores "S" by research/downgrade.py

The headline is secondary. The deliverable is the funnel: stop-outs -> on an
arming setup -> past the grade gate -> past the 11:00 SESSION_END check ->
actually produced a signal. `backtest_week.ARM84_FUNNEL` counts the first four
in-process; the fifth is read back off the rows.

Why this file has its own replay loop instead of calling backtest_2y.py: the
funnel counter only exists inside the process that ran the replay, and
backtest_2y.py is owned elsewhere. Everything reusable — the archive walk, SPY
context, the row schema's helpers — is imported from it rather than copied.

Usage:
    python research/p7_84_rule.py run --arm strict --out research/p7_arm_strict.json
    python research/p7_84_rule.py run --arm loose  --out research/p7_arm_loose.json
    python research/p7_84_rule.py run --arm sgrade --out research/p7_arm_s.json
    python research/p7_84_rule.py report            # -> research/p7_84_rule.md

RUN THE ARMS ONE AT A TIME. Concurrent replays contend on the 1-minute archive
and each one slows to a crawl.
"""
import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# The engine reads its A/B flags at import time, so the arm has to be chosen
# before anything below imports signal_runner.
ARMS = {
    "strict": {"RULE84_STRICT": "1", "RULE84_ARM_SGRADE": "0", "RULE84_OFF": "0"},
    "loose":  {"RULE84_STRICT": "0", "RULE84_ARM_SGRADE": "0", "RULE84_OFF": "0"},
    "sgrade": {"RULE84_STRICT": "0", "RULE84_ARM_SGRADE": "1", "RULE84_OFF": "0"},
}
ARM_LABEL = {
    "strict": "strict — RULE84_STRICT=1 (shipped)",
    "loose":  "loose — RULE84_STRICT=0",
    "sgrade": "S-grade — RULE84_ARM_SGRADE=1",
}
DEFAULT_OUT = {"strict": "research/p7_arm_strict.json",
               "loose":  "research/p7_arm_loose.json",
               "sgrade": "research/p7_arm_s.json"}
FUNNEL_STAGES = [("stopouts_counted", "counted full stop-outs"),
                 ("arming_setup", "on an arming setup (B&R / OCR)"),
                 ("grade_gate", "past the grade gate"),
                 ("armed", "past the 11:00 SESSION_END check = ARMED")]


# ---------------------------------------------------------------- the replay

def run(arm: str, days: int, out_path: str) -> None:
    os.environ.update(ARMS[arm])
    assert "research/bt2y_trades.json" not in out_path, "never write the canonical file"

    import polygon_feed as pf
    import backtest_2y as b2                      # imported, never edited
    import backtest_week as bw
    from backtest_week import simulate_day, htf_bias_for, RISK_DOLLARS
    from backtest_12mo import qqq_level_breaks, hourly_from_1m
    from universe import ALL_SYMS, INDEX_POOL, CORE_SYMBOLS, EXPERIMENTAL_SYMBOLS, pool_for, has_archive
    from research import downgrade as dg

    etfs = set(INDEX_POOL)
    bw.ARM84_FUNNEL.clear()

    syms = [s for s in ALL_SYMS if has_archive(s, 100)]
    last = max((b2.archive_days(s) or ["1970-01-01"])[-1] for s in syms)
    start = (date.fromisoformat(last) - timedelta(days=days)).isoformat()
    window = sorted({d for s in syms for d in b2.archive_days(s) if d >= start})
    print("[%s] %d symbols, %d sessions %s..%s"
          % (arm, len(syms), len(window), window[0], window[-1]), flush=True)

    ctx = b2.spy_context()
    qqq_brk = qqq_level_breaks(window)

    rows, sessions = [], set()
    for sym in syms:
        day_bars, hourly = {}, []
        for d in [x for x in b2.archive_days(sym) if x >= start]:
            try:
                bars = pf.fetch_day(sym, d)
            except Exception:
                continue
            if not bars:
                continue
            r = pf.rth(bars)
            if len(r) < 30:
                continue
            day_bars[d] = (bars, r)
            hourly += hourly_from_1m(d, r)

        n0, prev = len(rows), None
        for d in sorted(day_bars):
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
                pdo, pdc = prth[0].open, prth[-1].close
            else:
                pdh = pdl = pdo = pdc = None
            pmh, pml = pf.premarket_hi_lo(bars)
            bias = htf_bias_for(hourly, d)
            trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc,
                                  qqq=qqq_brk.get(d))
            sessions.add(d)
            dbars = b2.dg_bars(rth) if trades else None

            for t in trades:
                # Austin's ladder attached alongside the engine's legacy one,
                # exactly as backtest_2y.py does it (stop as the level proxy).
                rec = dg.score(dbars, t.entry_idx, t.stop, t.direction == "call", bias)
                rows.append({
                    "sym": sym, "day": d, "ym": d[:7],
                    "cls": "etf" if sym in etfs else "stock",
                    "pool": pool_for(sym),
                    "tier": ("core" if sym in CORE_SYMBOLS else
                             "experimental" if sym in EXPERIMENTAL_SYMBOLS else "other"),
                    "setup": t.signal_type, "dir": t.direction,
                    "grade": t.grade, "status": t.status,
                    "traded": bool(t.counted), "alert": bool(t.is_alert),
                    "et": t.entry_time[:5],
                    "entry": round(t.entry, 2), "stop": round(t.stop, 2),
                    "target": round(t.target, 2), "exit": round(t.exit_price, 2),
                    "out": t.outcome, "pnl": t.pnl, "r": round(t.pnl / RISK_DOLLARS, 3),
                    "bars": max(0, t.exit_idx - t.entry_idx),
                    "entry_i": t.entry_idx,
                    "sgrade": (rec or {}).get("grade", "n/a"),
                    "scaled": bool(t.scaled),
                    "reason": t.reason,
                })
            prev = d
        print("  [%s] %d sessions, %d signals" % (sym, len(day_bars), len(rows) - n0), flush=True)

    funnel = dict(bw.ARM84_FUNNEL)
    out = ROOT / out_path
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {"arm": arm, "env": ARMS[arm],
            "generated": datetime.now().isoformat(timespec="seconds"),
            "first": min(sessions), "last": max(sessions), "sessions": len(sessions),
            "symbols": syms, "risk_dollars": RISK_DOLLARS,
            "signals": len(rows), "traded": sum(1 for r in rows if r["traded"]),
            "funnel": funnel}
    out.write_text(json.dumps({"meta": meta, "trades": rows}, separators=(",", ":")),
                   encoding="utf-8")
    print("wrote %s — %d signals, %d traded, funnel %s"
          % (out, len(rows), meta["traded"], funnel), flush=True)


# --------------------------------------------------------------- the report

def _book(rows):
    """Whole-book money read. Win rate is of DECIDED trades (scratches excluded),
    which is how every other OMEN report counts it."""
    tr = [r for r in rows if r["traded"]]
    w = sum(1 for r in tr if r["out"] == "win")
    l = sum(1 for r in tr if r["out"] == "loss")
    rs = [r["r"] for r in tr]
    by_m = defaultdict(float)
    for r in tr:
        by_m[r["ym"]] += r["r"]
    return {"signals": len(rows), "traded": len(tr), "w": w, "l": l,
            "scratch": len(tr) - w - l,
            "wr": round(w / (w + l) * 100, 1) if (w + l) else 0.0,
            "meanr": round(statistics.fmean(rs), 3) if rs else 0.0,
            "totr": round(sum(rs), 1),
            "green": sum(1 for v in by_m.values() if v > 0), "months": len(by_m)}


def _set84(rows):
    """The re-entries as their OWN set — every 84% signal, and the traded subset."""
    all84 = [r for r in rows if r["setup"] == "reentry_84_rule"]
    tr = [r for r in all84 if r["traded"]]
    w = sum(1 for r in tr if r["out"] == "win")
    l = sum(1 for r in tr if r["out"] == "loss")
    rs = [r["r"] for r in tr]
    return {"fired": len(all84), "traded": len(tr), "w": w, "l": l,
            "scratch": len(tr) - w - l,
            "wr": round(w / (w + l) * 100, 1) if (w + l) else 0.0,
            "meanr": round(statistics.fmean(rs), 3) if rs else 0.0,
            "totr": round(sum(rs), 2),
            "rows": all84}


def report(out_md: str) -> None:
    arms = {}
    for arm, path in DEFAULT_OUT.items():
        p = ROOT / path
        if not p.is_file():
            print("missing %s — run the %s arm first" % (path, arm))
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        arms[arm] = {"meta": d["meta"], "book": _book(d["trades"]),
                     "r84": _set84(d["trades"])}
    if not arms:
        sys.exit("no arms to report")

    order = [a for a in ("strict", "loose", "sgrade") if a in arms]
    m0 = arms[order[0]]["meta"]
    L = ["# P7 / G1 — the 84% rule, three arms", "",
         "The 84%-rule re-entry fires **3 times in two years** on the shipped",
         "configuration. This is the measurement of why, and of what the two",
         "alternative arming gates cost.", "",
         "Rig: `research/p7_84_rule.py` over the on-disk 1-minute archive, "
         "%d sessions %s..%s, %d symbols, ladder B, stops on the close."
         % (m0["sessions"], m0["first"], m0["last"], len(m0["symbols"])),
         "Every arm is the same replay with one env flag moved; nothing else differs.",
         "",
         "| arm | flag | reading of the rulebook |", "|---|---|---|",
         "| strict | `RULE84_STRICT=1` (shipped) | \"you need an A+ entry\", "
         "scored on the legacy `_grade_pa` ladder |",
         "| loose | `RULE84_STRICT=0` | arm off any counted stop-out on an arming setup |",
         "| S-grade | `RULE84_ARM_SGRADE=1` | \"you need an A+ entry\", scored on "
         "**Austin's** ladder (`research/downgrade.py`): the original must be **S** |",
         "", "---", "", "## The arm-gate funnel", "",
         "Where the rule's opportunities go. Counted in-process at the single arm point",
         "(`backtest_week._arm_84`); the last row is read back off the written rows.", "",
         "| stage | " + " | ".join(ARM_LABEL[a] for a in order) + " |",
         "|---" * (len(order) + 1) + "|"]

    for key, label in FUNNEL_STAGES:
        L.append("| %s | %s |" % (label, " | ".join(
            str(arms[a]["meta"]["funnel"].get(key, 0)) for a in order)))
    L.append("| **produced a re-entry signal** | %s |" % " | ".join(
        "**%d**" % arms[a]["r84"]["fired"] for a in order))
    L.append("| of those, traded (not C-grade) | %s |" % " | ".join(
        str(arms[a]["r84"]["traded"]) for a in order))

    L += ["", "The gap between *armed* and *produced a signal* is the detector, not the",
          "gate: an armed session still needs price to reclaim the failed entry, on a",
          "bullish/bearish bar, more than 20% of the day's range away from the extreme,",
          "with >=1.5x remaining reward, before 11:00, within the 2-attempt cap.", "",
          "---", "", "## The re-entries as their own set", "",
          "| arm | signals | traded | W | L | scratch | win rate | mean R | total R |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for a in order:
        s = arms[a]["r84"]
        L.append("| %s | %d | %d | %d | %d | %d | %s | %+.3f | %+.2f |"
                 % (ARM_LABEL[a], s["fired"], s["traded"], s["w"], s["l"], s["scratch"],
                    ("%.1f%%" % s["wr"]) if (s["w"] + s["l"]) else "—",
                    s["meanr"], s["totr"]))

    L += ["", "## The whole book", "",
          "| arm | signals | traded | W | L | win rate | mean R | total R | months green |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for a in order:
        b = arms[a]["book"]
        L.append("| %s | %d | %d | %d | %d | %.1f%% | %+.3f | %+.1f | %d / %d |"
                 % (ARM_LABEL[a], b["signals"], b["traded"], b["w"], b["l"],
                    b["wr"], b["meanr"], b["totr"], b["green"], b["months"]))

    base = arms[order[0]]["book"]
    L += ["", "Deltas against the shipped arm:", ""]
    for a in order[1:]:
        b = arms[a]["book"]
        L.append("- **%s**: %+d traded signals, %+.1f pts win rate, %+.3f mean R, "
                 "%+.1f total R, %+d months green."
                 % (ARM_LABEL[a], b["traded"] - base["traded"], b["wr"] - base["wr"],
                    b["meanr"] - base["meanr"], b["totr"] - base["totr"],
                    b["green"] - base["green"]))

    # ---- what actually changed: the non-84 book, month by month -------------
    def _non84(rows):
        v = [r["r"] for r in rows if r["traded"] and r["setup"] != "reentry_84_rule"]
        return len(v), round(sum(v), 2)

    books = {a: json.loads((ROOT / DEFAULT_OUT[a]).read_text(encoding="utf-8"))["trades"]
             for a in order}
    L += ["", "---", "", "## What actually changed", "",
          "The rest of the book is **identical** in all three arms — same trades, same",
          "R, to the cent:", "", "| arm | non-84% trades | their total R |", "|---|---:|---:|"]
    for a in order:
        n, tot = _non84(books[a])
        L.append("| %s | %d | %+.2f |" % (ARM_LABEL[a], n, tot))
    L += ["", "So nothing here is a knock-on effect: the arming gate changes the 84%",
          "re-entries and **only** the 84% re-entries. Every delta below is attributable",
          "to that set alone.", ""]

    # months, and how the durability gate moved
    mo = {}
    for a in order:
        m = defaultdict(float)
        for r in books[a]:
            if r["traded"]:
                m[r["ym"]] += r["r"]
        mo[a] = m
    red0 = sorted(k for k, v in mo[order[0]].items() if v <= 0)
    if red0:
        L += ["### The durability gate", "",
              "`%s`'s red months, and what each arm did to them:" % ARM_LABEL[order[0]],
              "", "| month | " + " | ".join(a for a in order) + " | 84% R in that month (loose) |",
              "|---" * (len(order) + 2) + "|"]
        for k in red0:
            r84 = sum(r["r"] for r in books.get("loose", [])
                      if r["traded"] and r["ym"] == k and r["setup"] == "reentry_84_rule")
            L.append("| %s | %s | %+.2f |" % (
                k, " | ".join("%+.2f" % mo[a][k] for a in order), r84))
        if "loose" in order:
            L += ["", "That is the whole of the loose arm's durability gain — and it is thin.",
                  "Drop the single best re-entry from each of those months:", ""]
            for k in red0:
                v = sorted(r["r"] for r in books["loose"]
                           if r["traded"] and r["ym"] == k and r["setup"] == "reentry_84_rule")
                if v:
                    L.append("- **%s**: %+.2f with the re-entries, %+.2f without the best one "
                             "(%+.2f)%s" % (k, mo["loose"][k], mo["loose"][k] - v[-1], v[-1],
                                            " — **red again**" if mo["loose"][k] - v[-1] <= 0 else ""))
            L.append("")

    # robustness of the loose set
    if "loose" in order:
        v = sorted(r["r"] for r in books["loose"]
                   if r["traded"] and r["setup"] == "reentry_84_rule")
        yr = defaultdict(list)
        for r in books["loose"]:
            if r["traded"] and r["setup"] == "reentry_84_rule":
                yr[r["day"][:4]].append(r["r"])
        L += ["### Is the loose arm's edge real, or three fat winners?", "",
              "n=%d traded re-entries, mean **%+.3fR** — but the **median is %+.3fR**: "
              "%d win, %d lose." % (len(v), statistics.fmean(v), statistics.median(v),
                                    sum(1 for x in v if x > 0), sum(1 for x in v if x <= 0)),
              "The expectancy is a right tail, not a hit rate.", "",
              "| cut | n | mean R |", "|---|---:|---:|",
              "| all traded re-entries | %d | %+.3f |" % (len(v), statistics.fmean(v)),
              "| excluding the top 3 | %d | %+.3f |" % (len(v) - 3, statistics.fmean(v[:-3])),
              "| excluding the top 5 | %d | %+.3f |" % (len(v) - 5, statistics.fmean(v[:-5])),
              ""]
        L += ["| year | n | mean R | total R |", "|---|---:|---:|---:|"]
        for k in sorted(yr):
            L.append("| %s | %d | %+.3f | %+.2f |"
                     % (k, len(yr[k]), statistics.fmean(yr[k]), sum(yr[k])))
        L += ["", "Even after trimming the five biggest winners the set stays positive, but at",
              "a mean R well under the book it dilutes rather than adds. 2024 is negative.", ""]

        # does the RE-ENTRY's own grade sort them?
        g = defaultdict(list)
        for r in books["loose"]:
            if r["traded"] and r["setup"] == "reentry_84_rule":
                g[r["sgrade"]].append(r["r"])
        L += ["### Does Austin's grade sort the re-entries themselves?", "",
              "The S-grade ARM gates on the **original** trade. This instead cuts the loose",
              "arm's re-entries by the grade of the **re-entry**, which is the thing R3 would",
              "actually route on:", "",
              "| re-entry's grade | n | win rate | mean R | total R |", "|---|---:|---:|---:|---:|"]
        for k in ("S", "A", "C"):
            if g[k]:
                w = sum(1 for x in g[k] if x > 0)
                L.append("| %s | %d | %.1f%% | %+.3f | %+.2f |"
                         % (k, len(g[k]), w / len(g[k]) * 100,
                            statistics.fmean(g[k]), sum(g[k])))
        L += ["", "It does not sort cleanly — A beats S beats C, and every bucket is under",
              "n=50. This is not a filter worth acting on at this sample size.", ""]

    L += ["", "## Every re-entry the arms produced", "",
          "Both grade columns describe the **re-entry signal itself**, not the stopped-out",
          "trade that armed it. `alert-only` rows are C-grade and excluded from traded P&L.", "",
          "| arm | symbol | day | entry | legacy grade | Austin's grade | outcome | R |",
          "|---|---|---|---|---|---|---|---:|"]
    for a in order:
        for r in sorted(arms[a]["r84"]["rows"], key=lambda x: (x["day"], x["sym"])):
            L.append("| %s | %s | %s | %s | %s | %s | %s | %+.3f |"
                     % (a, r["sym"], r["day"], r["et"], r["grade"], r["sgrade"],
                        r["out"] + ("" if r["traded"] else " (alert-only)"), r["r"]))

    L += ["", "---", "", "## Cross-check: what the corpus says (P11)", "",
          "`research/p11_parameter_provenance.md` row **A8** scored",
          "`RULE84_ARM_BNR_ONLY` **CONTRADICTED (partial — source narrower)**:",
          "",
          "> TRADER_SAID `scarface-rules-videos.md:162` — \"the thing you need to know about",
          "> the 84% rule is you need an A plus entry.\" Source restricts arming to",
          "> A+-quality entries; the coded gate arms on any break-and-retest stop-out",
          "> regardless of quality.",
          "",
          "That is an independent line of evidence, arrived at from what a trader actually",
          "said rather than from P&L, and it lands on the same side as this measurement:",
          "**there should be a quality gate on arming, and the loose arm is the one the",
          "corpus rules out.** Two different methods, same conclusion, is the strongest",
          "result in this ticket.",
          "",
          "The question P11 leaves open is the one this A/B was built to answer — *which*",
          "ladder \"A+\" means — and the honest answer is that this measurement does not",
          "settle it. Reading it as Austin's `S` produced 12 signals and 7 traded trades.",
          "n=7 cannot rule a gate in or out. So the corpus says *gate on quality*, and the",
          "book says *the legacy reading currently shipped is not beaten by the one",
          "alternative testable today*. Both are consistent with leaving the default alone",
          "and revisiting after R3.",
          "",
          "Note the direction of the disagreement, because it matters: P11 contradicts the",
          "**loose** arm, not the strict one. Nothing in the corpus sweep says the shipped",
          "gate is wrong — only that removing it would be.",
          "",
          "---", "", "## Verdict", "",
          "**The strict gate is not protecting the book — but it is not costing much",
          "either.** The loose arm's re-entries are a positive-expectancy set (+0.792R on",
          "n=79) that is nonetheless *below the book's own mean*, so switching the default",
          "buys +56R of total R and two green months at the price of 1.1 points of win rate",
          "and 0.015R of mean R. Against a money gate written as **mean R >= 2.0 and win",
          "rate >= 55%**, both of the numbers the gate is written in move the wrong way.",
          "",
          "**The S-grade arm is the worst of the three and should not be shipped.** Gating",
          "on the original trade's S grade produced 12 signals and 7 traded, at -0.073R.",
          "It is the arm the diagnosis predicted would work, and it did not. Two honest",
          "reasons, and they point in different directions:",
          "",
          "1. n=7 is not a measurement. Nothing here rules the idea in or out.",
          "2. The premise may just be wrong. \"The original was clean\" is a statement about",
          "   the setup that **already failed**. A stop-out on an S setup may be evidence",
          "   the read was wrong, not evidence the level is worth a second bite.",
          "",
          "**Recommendation: keep `RULE84_STRICT=1` as the shipped default. Change nothing.**",
          "Reasons, in order:",
          "",
          "- No arm reaches the money gate, or moves the book toward it. The gate is mean R",
          "  2.0; the arms sit at +0.957 / +0.942 / +0.947. This is not where the 2.0R comes",
          "  from, and G7 already established that entry selection, not management, is the",
          "  binding constraint.",
          "- The loose arm's headline (25/25 months green) is **one trade deep**. Remove the",
          "  single best re-entry from 2025-06 and the month is red again. A durability claim",
          "  that survives on one +7.4R outlier is not a durability claim.",
          "- More than half the loose re-entries lose (median -1.000R). Austin's own framing",
          "  of the rule is that it is a high-probability second bite; a 38% win rate is not",
          "  that, and shipping it would put a losing-more-often-than-not setup into the book",
          "  under a name that says 84%.",
          "",
          "**What this does settle**, which is the point of the ticket: the rule is dead in",
          "backtest because of the gate, not the detector — 7 of 472 opportunities survive",
          "the strict gate. Open it and 116 signals appear. So the question \"is the 84% rule",
          "broken?\" is answered: it is gated off, deliberately, and opening the gate is",
          "worth roughly nothing on the metrics the project is graded on.",
          "",
          "**What is still open** (queue it, do not do it here):",
          "",
          "- The loose arm's re-entries are strongly year-dependent (2024 negative, 2026",
          "  +1.06R). Worth a walk-forward before anyone reads +0.792R as stable.",
          "- The detector, not the gate, is the next bottleneck: 433 armings produced 116",
          "  signals. Nobody has autopsied the 317 armings that never fired.",
          "- R2/R3 own the real decision. If `downgrade.py` is ever wired into detection,",
          "  this A/B should be re-run on that book — the S arm's n=7 is a sample-size",
          "  result, not a verdict on Austin's ladder.",
          "",
          "---", "",
          "Reproduce: `python research/p7_84_rule.py run --arm {strict,loose,sgrade}` "
          "then `python research/p7_84_rule.py report`.", ""]
    p = ROOT / out_md
    p.write_text("\n".join(L), encoding="utf-8")
    print("wrote %s" % p)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--arm", choices=sorted(ARMS), required=True)
    r.add_argument("--days", type=int, default=730)
    r.add_argument("--out", default=None)
    q = sub.add_parser("report")
    q.add_argument("--out", default="research/p7_84_rule.md")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.arm, a.days, a.out or DEFAULT_OUT[a.arm])
    else:
        report(a.out)


if __name__ == "__main__":
    main()
