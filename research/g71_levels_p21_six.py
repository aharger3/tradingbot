"""G7.1 track `levels` -- re-run P21's "is there a 2R target at entry?" on
Austin's SIX levels instead of the nine-level roster P21 used.

P21 (`research/p21_target_availability.md`) tested ballot b4 ("if there are no
other levels to target ... harder to trade") against a roster of NINE: his six
plus HOD, LOD and every T10 swing pivot. It came back BACKWARDS -- losers had a
2R target MORE often than winners -- and was written up as a negative result for
Austin's rule. Austin: "i only have 6 day trade levels."

This script asks the same question three ways off the same book, so the roster
is the only thing that changes:

    six     PDH PDL PMH PML ORH ORL          -- his roster
    +hodlod six + causal session HOD/LOD
    nine    +hodlod + T10 pivots             -- exactly what P21 measured

Usage:
    python research/g71_levels_p21_six.py [--inp research/bt2y_trades.json]
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(os.path.dirname(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, HERE)

import p21_target_availability as p21  # noqa: E402

SIX = ("PDH", "PDL", "PMH", "PML", "ORH", "ORL")
HODLOD = ("HOD", "LOD")


def subset(levels, mode):
    if mode == "six":
        return {k: v for k, v in levels.items() if k in SIX}
    if mode == "hodlod":
        return {k: v for k, v in levels.items() if k in SIX + HODLOD}
    return levels          # "nine" -- everything, pivots included


def agg(rs):
    return p21.agg(rs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inp", default="research/bt2y_trades.json")
    args = ap.parse_args()

    raw = json.loads((ROOT / args.inp).read_text(encoding="utf-8"))
    meta = raw["meta"]
    book = [t for t in raw["trades"] if t["traded"]]
    print("%d traded signals, %s..%s" % (len(book), meta["first"], meta["last"]))

    modes = ("six", "hodlod", "nine")
    flags = {m: [] for m in modes}
    n_levels = {m: [] for m in modes}
    for n, t in enumerate(book, 1):
        entry_i = t.get("entry_i")
        if entry_i is None:
            entry_i = p21.entry_index(t["sym"], t["day"], t["et"])
        levels = p21.levels_for_entry(t["sym"], t["day"], entry_i)
        for m in modes:
            lv = subset(levels, m) if levels else {}
            n_levels[m].append(len(lv))
            if not lv:
                flags[m].append(None)
            else:
                ok, _nm, _px = p21.has_2r_target(lv, t["entry"], t["stop"], t["dir"])
                flags[m].append(ok)
        if n % 500 == 0:
            print("  %d/%d" % (n, len(book)))

    L = ["# G7.1 `levels` -- P21 re-run on Austin's six", "",
         "Book: `%s`, %d traded signals %s..%s." % (args.inp, len(book),
                                                    meta["first"], meta["last"]),
         "", "## Roster size actually seen at entry", "",
         "| roster | mean levels/signal | max |", "|---|---:|---:|"]
    for m in modes:
        v = n_levels[m]
        L.append("| %s | %.2f | %d |" % (m, sum(v) / len(v), max(v)))

    L += ["", "## has-2R-target split, by roster", "",
          "| roster | slice | n | win% | mean R | total R |",
          "|---|---|---:|---:|---:|---:|"]
    summary = {}
    for m in modes:
        for label, want in (("has 2R target", True), ("no 2R target", False)):
            idx = [i for i, f in enumerate(flags[m]) if f is want]
            rs = [book[i]["r"] for i in idx]
            n, wr, mr, tr = agg(rs)
            L.append("| %s | %s | %d | %.1f | %+.3f | %+.1f |" % (m, label, n, wr, mr, tr))
            summary[(m, want)] = (n, wr, mr, tr)

    L += ["", "## The directional test Austin's rule makes", "",
          "His b4 says a setup with no level to target is HARDER. So losers "
          "should lack a target MORE often than winners. `no-target share` "
          "below is that share; a POSITIVE gap (losers > winners) is the rule "
          "working.", "",
          "| roster | no-target share of losers | of winners | gap |",
          "|---|---:|---:|---:|"]
    lose_idx = [i for i, t in enumerate(book) if t["r"] <= 0]
    win_idx = [i for i, t in enumerate(book) if t["r"] > 0]
    for m in modes:
        lo = [i for i in lose_idx if flags[m][i] is not None]
        wi = [i for i in win_idx if flags[m][i] is not None]
        ls = sum(1 for i in lo if flags[m][i] is False) / len(lo) * 100
        ws = sum(1 for i in wi if flags[m][i] is False) / len(wi) * 100
        L.append("| %s | %.1f%% (n=%d) | %.1f%% (n=%d) | %+.1f pts |"
                 % (m, ls, len(lo), ws, len(wi), ls - ws))

    # Austin's own S rows only
    L += ["", "## Austin's S grade only", "",
          "| roster | slice | n | win% | mean R | total R |",
          "|---|---|---:|---:|---:|---:|"]
    s_idx = [i for i, t in enumerate(book) if t.get("sgrade") == "S"]
    for m in modes:
        for label, want in (("has 2R target", True), ("no 2R target", False)):
            idx = [i for i in s_idx if flags[m][i] is want]
            rs = [book[i]["r"] for i in idx]
            n, wr, mr, tr = agg(rs)
            L.append("| %s | %s | %d | %.1f | %+.3f | %+.1f |" % (m, label, n, wr, mr, tr))

    out = ROOT / "research" / "g71_levels_p21_six.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print("wrote %s" % out)


if __name__ == "__main__":
    main()
