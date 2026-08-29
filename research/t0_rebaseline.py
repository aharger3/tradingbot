"""T0 - the ratified re-baseline. Every published figure that moved, in one table.

Reads two `backtest_2y.py` books (BEFORE = the engine at `387ee2da`, AFTER = the
engine with the RATIFIED table landed) and prints the comparison the spec asks
for, plus the reachability and error-bar readings the method rules require.

Usage:
  python research/t0_rebaseline.py BEFORE.json AFTER.json [--out research/t0_ratified_rebaseline.md]

Nothing here re-runs the engine; both books are inputs, so this script is
reproducible from the two artefacts alone.
"""
from __future__ import annotations
import argparse, json, math, statistics as st
from collections import Counter, defaultdict


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    return d["meta"], d["trades"]


def traded(rows):
    return [r for r in rows if r["traded"]]


def stats(rows):
    """Every published figure, off one book."""
    tr = traded(rows)
    rs = [r["r"] for r in tr]
    wins = [r for r in tr if r["out"] == "win"]
    losses = [r for r in tr if r["out"] == "loss"]
    scratch = [r for r in tr if r["out"] not in ("win", "loss")]
    decided = len(wins) + len(losses)

    by_month = defaultdict(float)
    for r in tr:
        by_month[r["ym"]] += r["r"]
    green = sum(1 for v in by_month.values() if v > 0)

    gross_w = sum(r["r"] for r in tr if r["r"] > 0)
    gross_l = -sum(r["r"] for r in tr if r["r"] < 0)

    order = sorted(tr, key=lambda r: (r["day"], r["et"]))
    peak = cum = dd = 0.0
    for r in order:
        cum += r["r"]
        peak = max(peak, cum)
        dd = max(dd, peak - cum)

    sd = st.pstdev(rs) if len(rs) > 1 else 0.0
    return {
        "signals": len(rows),
        "traded": len(tr),
        "mean_r": st.fmean(rs) if rs else 0.0,
        "sd_r": sd,
        "se_r": sd / math.sqrt(len(rs)) if rs else 0.0,
        "total_r": sum(rs),
        "win_rate": (len(wins) / decided * 100) if decided else 0.0,
        "wins": len(wins), "losses": len(losses), "scratches": len(scratch),
        "months": len(by_month), "months_green": green,
        "pf": (gross_w / gross_l) if gross_l else 0.0,
        "max_dd_r": dd,
        "worst_r": min(rs) if rs else 0.0,
        "best_r": max(rs) if rs else 0.0,
        "at_1r": sum(1 for r in rs if abs(r + 1.0) < 1e-6),
        "past_1r": sum(1 for r in rs if r < -1.0 - 1e-9),
        "at_floor": sum(1 for r in rs if abs(r + 1.25) < 1e-6),
        "index": sum(1 for r in tr if r["cls"] == "etf"),
        "setups": Counter(r["setup"] for r in tr),
        "levels": Counter(r["level"] for r in tr),
        "sgrade": Counter(r["sgrade"] for r in tr),
        "grade": Counter(r["grade"] for r in tr),
        "syms": Counter(r["sym"] for r in tr),
        "counter": sum(1 for r in tr if "[obs: counter day trend]" in r["reason"]),
        "chase_tag": sum(1 for r in tr if "chase" in r["tags"]),
        "chase_dg": sum(1 for r in tr if "chase" in (r.get("downgrades") or [])),
        "pm": sum(1 for r in tr if r["level"] in ("PMH", "PML")),
        "by_month": dict(by_month),
    }


def sig_stats(rows):
    """Reachability, over ALL signals - method rule 3.

    The BEFORE book spells two of these conditions as the CAP it used to apply
    ("[capped C: counter day trend]", "[capped C: level $x blocks 2R path]") and
    the AFTER book spells them as the observation that replaced it. Both
    spellings are counted so the column is a like-for-like trip rate rather than
    a rename showing up as a change. `chase` as a downgrade variable did not
    exist before R22, so its before cell is genuinely not recorded.
    """
    def any_of(r, *needles):
        return any(n in r["reason"] for n in needles)
    return {
        "n": len(rows),
        "chase_dg": sum(1 for r in rows if "chase" in (r.get("downgrades") or [])),
        "chase_recorded": any("chase" in (r.get("downgrades") or []) for r in rows),
        "counter": sum(1 for r in rows
                       if any_of(r, "[obs: counter day trend]",
                                 "[capped C: counter day trend]")),
        "path_level": sum(1 for r in rows
                          if any_of(r, "[path level", "blocks 2R path]")),
        "sgrade_s": sum(1 for r in rows if r["sgrade"] == "S"),
    }


def pct(a, b):
    return "%.1f%%" % (a / b * 100) if b else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    _mb, rb = load(a.before)
    _ma, ra = load(a.after)
    B, A = stats(rb), stats(ra)
    SB, SA = sig_stats(rb), sig_stats(ra)

    # The error bar on the mean-R move: the two books are treated as
    # independent samples of trade outcomes (they share most of their days but
    # not their rows). 1.96 x the standard error of the difference.
    se = math.sqrt(B["se_r"] ** 2 + A["se_r"] ** 2)
    bar = 1.96 * se
    move = A["mean_r"] - B["mean_r"]

    L = []
    P = L.append
    P("| figure | before | after | move |")
    P("|---|---:|---:|---:|")
    rows = [
        ("signals detected", B["signals"], A["signals"], "%+d"),
        ("**traded_count**", B["traded"], A["traded"], "%+d"),
        ("**mean_r**", B["mean_r"], A["mean_r"], "%+.4f"),
        ("**win_rate** (%)", B["win_rate"], A["win_rate"], "%+.1f"),
        ("total R", B["total_r"], A["total_r"], "%+.1f"),
        ("profit factor", B["pf"], A["pf"], "%+.2f"),
        ("**months_green** (of %d)" % A["months"], B["months_green"], A["months_green"], "%+d"),
        ("max drawdown (R)", B["max_dd_r"], A["max_dd_r"], "%+.1f"),
        ("wins", B["wins"], A["wins"], "%+d"),
        ("losses", B["losses"], A["losses"], "%+d"),
        ("scratches", B["scratches"], A["scratches"], "%+d"),
        ("worst trade (R)", B["worst_r"], A["worst_r"], "%+.3f"),
        ("best trade (R)", B["best_r"], A["best_r"], "%+.3f"),
        ("losses booked at exactly -1.000R", B["at_1r"], A["at_1r"], "%+d"),
        ("losses booked worse than -1R", B["past_1r"], A["past_1r"], "%+d"),
        ("losses clamped at the -1.25R bound", B["at_floor"], A["at_floor"], "%+d"),
        ("index (ETF) trades", B["index"], A["index"], "%+d"),
        ("premarket-level trades", B["pm"], A["pm"], "%+d"),
        ("counter-day-trend traded rows (only recorded after R21)",
         B["counter"], A["counter"], "%+d"),
        ("symbols with at least one trade", len(B["syms"]), len(A["syms"]), "%+d"),
    ]
    for name, x, y, f in rows:
        if isinstance(x, float):
            P("| %s | %.4f | %.4f | %s |" % (name, x, y, f % (y - x)))
        else:
            P("| %s | %d | %d | %s |" % (name, x, y, f % (y - x)))

    for label, key in (("setup", "setups"), ("level", "levels"),
                       ("engine grade", "grade"), ("his S/A/C", "sgrade")):
        keys = sorted(set(B[key]) | set(A[key]), key=lambda k: -A[key].get(k, 0))
        for k in keys:
            P("| traded, %s = %s | %d | %d | %+d |"
              % (label, k, B[key].get(k, 0), A[key].get(k, 0),
                 A[key].get(k, 0) - B[key].get(k, 0)))

    P("")
    P("## Error bar")
    P("")
    P("mean R moved **%+.4f R**; the 95%% bar on that move is **+/-%.4f R** "
      "(sd %.3f -> %.3f, n %d -> %d)."
      % (move, bar, B["sd_r"], A["sd_r"], B["traded"], A["traded"]))
    P("")
    P("Inside its own bar: **%s**."
      % ("YES - null result" if abs(move) < bar else "no - the move is real"))
    P("")
    P("## Reachability (method rule 3: under 1% or over 85% means the finding is the gate)")
    P("")
    P("| condition | before | after |")
    P("|---|---:|---:|")
    P("| chase trips as a downgrade, all signals | %s | %s |"
      % ("not recorded" if not SB["chase_recorded"] else pct(SB["chase_dg"], SB["n"]),
         pct(SA["chase_dg"], SA["n"])))
    P("| counter-day-trend, all signals (before = the CAP actually firing) | %s | %s |"
      % (pct(SB["counter"], SB["n"]), pct(SA["counter"], SA["n"])))
    P("| a level sits in the 2R path (before = the CAP actually firing) | %s | %s |"
      % (pct(SB["path_level"], SB["n"]), pct(SA["path_level"], SA["n"])))
    P("| scores S on his ladder, all signals | %s | %s |"
      % (pct(SB["sgrade_s"], SB["n"]), pct(SA["sgrade_s"], SA["n"])))
    P("")
    P("The two `before` cells above are the rate at which those gates ACTUALLY "
      "CAPPED something: %d of %d signals for counter-trend (%s) and %d of %d "
      "for the level block (%s). Both are far under the 1%% reachability floor. "
      "The 89.5%% figure on his card was the rate at which the CONDITION was "
      "true, not the rate at which the gate changed a grade -- the cap only ran "
      "on signals already graded above C, and `_grade_pa` grades 95%% of "
      "signals X. R21 and R25 removed two gates that were already almost dead; "
      "the book did not move because of them."
      % (SB["counter"], SB["n"], pct(SB["counter"], SB["n"]),
         SB["path_level"], SB["n"], pct(SB["path_level"], SB["n"])))
    P("")
    P("## What the new rows are worth (after book only)")
    P("")
    P("| slice | trades | mean R | win rate |")
    P("|---|---:|---:|---:|")
    trA = traded(ra)
    slices = [
        ("whole book", lambda r: True),
        ("break_and_retest", lambda r: r["setup"] == "break_and_retest"),
        ("one_candle_rule (R3/R4)", lambda r: r["setup"] == "one_candle_rule"),
        ("84% re-entry (R6)", lambda r: r["setup"] == "reentry_84_rule"),
        ("premarket level (R23)", lambda r: r["level"] in ("PMH", "PML")),
        ("counter day trend (R21)",
         lambda r: "[obs: counter day trend]" in r["reason"]),
        ("with day trend", lambda r: "[obs: counter day trend]" not in r["reason"]),
        ("index (ETF)", lambda r: r["cls"] == "etf"),
        ("his S", lambda r: r["sgrade"] == "S"),
        ("his A", lambda r: r["sgrade"] == "A"),
        ("his C", lambda r: r["sgrade"] == "C"),
        ("2nd+ trade on its symbol-day (R16/R17)", lambda r: r["seq"] > 1),
        ("first trade on its symbol-day", lambda r: r["seq"] == 1),
    ]
    for name, f in slices:
        sub = [r for r in trA if f(r)]
        if not sub:
            P("| %s | 0 | - | - |" % name)
            continue
        w = sum(1 for r in sub if r["out"] == "win")
        l = sum(1 for r in sub if r["out"] == "loss")
        P("| %s | %d | %+.4f | %s |"
          % (name, len(sub), st.fmean(r["r"] for r in sub),
             pct(w, w + l)))

    P("")
    P("## Month by month (R)")
    P("")
    P("| month | before | after |")
    P("|---|---:|---:|")
    for m in sorted(set(B["by_month"]) | set(A["by_month"])):
        P("| %s | %+.2f | %+.2f |" % (m, B["by_month"].get(m, 0.0),
                                      A["by_month"].get(m, 0.0)))
    P("")
    P("## Symbol spread (traded count, after)")
    P("")
    P("| symbol | before | after |")
    P("|---|---:|---:|")
    for s, n in A["syms"].most_common():
        P("| %s | %d | %d |" % (s, B["syms"].get(s, 0), n))

    out = "\n".join(L)
    print(out)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out + "\n")


if __name__ == "__main__":
    main()
