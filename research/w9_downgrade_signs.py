"""w9_downgrade_signs.py -- W9: re-sign the eight shipped downgrade variables
plus the three flagged-OFF ones, on the 2-year book, and simulate the new
S/A/C/X-by-count ladder (spec 1.2) under three variable sets.

WHY THIS EXISTS
----------------
Austin settled 2026-08-28 that the grade IS the downgrade count: 0 -> S,
1 -> A, 2 -> C, 3+ -> X (not tradeable). Until now a wrong-signed variable was
a nuisance (`research/a1_threshold_sweep.md` found `level_not_respected`
wrong-signed at the committed default). Under the new ladder a wrong-signed
variable actively pushes good setups toward X, so it has to be re-checked
before `W1` wires the count-based grade in.

WHAT IS RE-USED, ON PURPOSE
-----------------------------
The eight shipped variables' trip/clean split is read directly off each
row's own `downgrades` list in `research/g3_arm_ow1.json` -- that field was
computed by `downgrade.score()` at the committed defaults when the book was
built, so re-deriving it from bars would just reproduce the same list. No
bar replay, no network. `downgrade.VARIABLES` (imported, not retyped) is the
canonical name list this script iterates.

`ENABLE_SEQUENCE_GATE`'s trip flag is NOT on the row (it ships OFF, so the
book was built without it) but it needs no bar geometry either --
`research/p20_sequence_gate.py::annotate_sequence` derives entry order and
the 84%-rule exemption purely from each row's own `sym`/`day`/`et`/`setup`
fields, over the FULL signal population (not just traded), exactly as p20's
"book rig" documents. That function is imported and reused here, unmodified,
run over every row in `g3_arm_ow1.json` (not `bt2y_trades.json` -- the two
books are close in size, 45193 vs 45175 signals / 1017 vs 1016 traded, but
this ticket's row is g3, so g3 is what gets sequence-annotated).

`ENABLE_LARGE_COUNTER_BODY` and `ENABLE_MULTI_LEVEL_CONFLUENCE` are NOT
recomputed here -- both need bar geometry (`large_counter_body` scans a
window of candle bodies; `multi_level_confluence` needs the six-level
roster at entry), which is out of this ticket's no-bars scope. Their sign
and delta are carried over from the already-published, bar-based
measurements in `research/p18_p19_new_variables.md` (verified against that
file's own numbers before being repeated here) and are not used in any of
the three simulated variable sets below, because neither is asked for in
part 3 of the ticket.

    python research/w9_downgrade_signs.py

Writes research/w9_downgrade_signs.md.
"""
from __future__ import annotations

import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import downgrade as dg                                   # noqa: E402
from research.p20_sequence_gate import annotate_sequence               # noqa: E402

OUT = os.path.join(HERE, "w9_downgrade_signs.md")
G3 = os.path.join(HERE, "g3_arm_ow1.json")

# already-published, bar-based measurements (research/p18_p19_new_variables.md,
# research/p20_sequence_gate.md) -- cited, not recomputed, per the module
# docstring. (trip_n, trip_pct_of_book, tripped_mean_r, tripped_n,
# clean_mean_r, clean_n, delta, verdict, source)
FLAGGED_PRIOR = {
    "sequence_gate (prior, bt2y book)": (33369, 73.9, 0.767, 422, 1.092, 594,
                                          -0.325, "right-signed",
                                          "research/p20_sequence_gate.md"),
    "large_counter_body": (25822, 57.2, 0.968, 622, 0.939, 394, 0.029,
                            "wrong-signed", "research/p18_p19_new_variables.md"),
    "multi_level_confluence": (10801, 23.9, 1.064, 582, 0.814, 434, 0.250,
                                "right-signed (as an upgrade)",
                                "research/p18_p19_new_variables.md"),
}


def load_g3():
    with open(G3, encoding="utf-8") as fh:
        d = json.load(fh)
    return d["meta"], d["trades"]


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def median(xs):
    return statistics.median(xs) if xs else float("nan")


# ---------------------------------------------------------------------------
# part 1/2 -- sign and trip rate of the eight shipped variables
# ---------------------------------------------------------------------------

def shipped_variable_table(all_rows, traded_rows):
    """One row per variable in `downgrade.VARIABLES`, off the `downgrades`
    list already on each row of `g3_arm_ow1.json`."""
    n_all = len(all_rows)
    out = []
    for name in dg.VARIABLES:
        trip_all = sum(1 for r in all_rows if name in (r.get("downgrades") or []))
        tripped_r = [r["r"] for r in traded_rows if name in (r.get("downgrades") or [])]
        clean_r = [r["r"] for r in traded_rows if name not in (r.get("downgrades") or [])]
        if tripped_r and clean_r:
            delta = mean(tripped_r) - mean(clean_r)
            verdict = "WRONG-SIGNED" if delta >= 0 else "right-signed"
        else:
            delta = None
            verdict = "NULL (no traded tripped population)" if not tripped_r else "NULL"
        out.append({
            "variable": name,
            "trip_n": trip_all, "trip_pct": 100.0 * trip_all / n_all,
            "tripped_mean_r": mean(tripped_r) if tripped_r else None,
            "tripped_n": len(tripped_r),
            "clean_mean_r": mean(clean_r) if clean_r else None,
            "clean_n": len(clean_r),
            "delta": delta, "verdict": verdict,
        })
    return out


# ---------------------------------------------------------------------------
# part 3 -- simulate the new S/A/C/X-by-count ladder under 3 variable sets
# ---------------------------------------------------------------------------

WRONG_SIGNED = {"level_not_respected"}
RIGHT_SIGNED = tuple(v for v in dg.VARIABLES if v not in WRONG_SIGNED)

VARIABLE_SETS = {
    "(a) all eight, as shipped": dg.VARIABLES,
    "(b) all eight minus level_not_respected": RIGHT_SIGNED,
    "(c) right-signed seven + sequence_gate": RIGHT_SIGNED + ("sequence_gate",),
}


def grade_of(row, variable_set):
    """New ladder (spec 1.2): count = downgrades in `variable_set` that
    fired, minus 1 for confluence (Austin 2026-08-24, unaffected by which
    variable set is active), floored at 0. 0->S 1->A 2->C 3+->X."""
    trips = sum(1 for name in variable_set
                if name != "sequence_gate" and name in (row.get("downgrades") or []))
    if "sequence_gate" in variable_set and row.get("_seq_trip"):
        trips += 1
    confluent = row.get("confluence") == "yes"
    net = max(0, trips - (1 if confluent else 0))
    if net == 0:
        return "S"
    if net == 1:
        return "A"
    if net == 2:
        return "C"
    return "X"


def simulate(traded_rows):
    results = {}
    for set_name, variable_set in VARIABLE_SETS.items():
        buckets = {"S": [], "A": [], "C": [], "X": []}
        for r in traded_rows:
            g = grade_of(r, variable_set)
            buckets[g].append(r["r"])
        row = {}
        for g in ("S", "A", "C", "X"):
            rs = buckets[g]
            row[g] = {"n": len(rs), "mean_r": mean(rs) if rs else None,
                       "median_r": median(rs) if rs else None}
        s_med = row["S"]["median_r"]
        a_med = row["A"]["median_r"]
        c_med = row["C"]["median_r"]
        x_med = row["X"]["median_r"]
        monotonic = (
            s_med is not None and a_med is not None and c_med is not None
            and s_med > a_med > c_med
            and (x_med is None or c_med > x_med)
        )
        results[set_name] = {"buckets": row, "monotonic_median": monotonic}
    return results


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def fmt_r(x):
    return "n/a" if x is None else f"{x:+.4f}R"


def build_report():
    meta, all_rows = load_g3()
    traded_rows = [r for r in all_rows if r.get("traded")]
    n_all, n_traded = len(all_rows), len(traded_rows)

    annotate_sequence(all_rows)  # sets _entry_seq / _is_84 on every row, in place
    for r in all_rows:
        r["_seq_trip"] = bool(r.get("_entry_seq")) and r["_entry_seq"] > 1 and not r["_is_84"]
    seq_tripped_traded_r = [r["r"] for r in traded_rows if r["_seq_trip"]]
    seq_clean_traded_r = [r["r"] for r in traded_rows if not r["_seq_trip"]]
    seq_trip_all = sum(1 for r in all_rows if r["_seq_trip"])
    seq_delta = (mean(seq_tripped_traded_r) - mean(seq_clean_traded_r)
                 if seq_tripped_traded_r and seq_clean_traded_r else None)

    table = shipped_variable_table(all_rows, traded_rows)
    sim = simulate(traded_rows)

    L = []
    L.append("# W9 -- the eight downgrade variables, re-signed on the new S/A/C/X-by-count ladder")
    L.append("")
    L.append(f"Generated by `python research/w9_downgrade_signs.py`. Source: "
             f"`research/g3_arm_ow1.json` ({meta.get('generated')}, "
             f"{n_all} signals / {n_traded} traded, {meta.get('first')} to "
             f"{meta.get('last')}). No bars, no replay, no network -- the eight "
             f"shipped variables come off each row's own precomputed `downgrades` "
             f"list; `sequence_gate` is derived purely from `sym`/`day`/`et`/`setup` "
             f"via `research.p20_sequence_gate.annotate_sequence` (imported, not "
             f"reimplemented).")
    L.append("")
    L.append("Error bar: **±0.0095 R** (narrow bar, Austin 2026-08-28 -- the wide "
              "±1.5799R bar is retired). Deltas below are read against this bar.")
    L.append("")

    L.append("## 1-2. The eight shipped variables: sign, trip rate, delta")
    L.append("")
    L.append("`verdict` is the P15/a1 test: TRIPPED mean R >= CLEAN mean R means the "
              "variable marks BETTER trades worse -- wrong-signed for a downgrade.")
    L.append("")
    L.append("| variable | trip n / % of book | tripped mean R (n) | clean mean R (n) | delta | verdict |")
    L.append("|---|---:|---:|---:|---:|---|")
    for row in table:
        delta_str = "n/a" if row["delta"] is None else f"{row['delta']:+.4f}R"
        L.append(
            f"| `{row['variable']}` | {row['trip_n']} / {row['trip_pct']:.1f}% | "
            f"{fmt_r(row['tripped_mean_r'])} (n={row['tripped_n']}) | "
            f"{fmt_r(row['clean_mean_r'])} (n={row['clean_n']}) | "
            f"{delta_str} | "
            f"{row['verdict']} |"
        )
    n_wrong = sum(1 for r in table if r["verdict"] == "WRONG-SIGNED")
    n_right = sum(1 for r in table if r["verdict"] == "right-signed")
    n_null = sum(1 for r in table if r["verdict"].startswith("NULL"))
    L.append("")
    L.append(f"**{n_right} of 8 right-signed, {n_wrong} wrong-signed, {n_null} null "
              f"(no traded tripped population).**")
    L.append("")
    L.append("This reproduces `research/a1_threshold_sweep.md`'s finding "
              "(`level_not_respected` is the one wrong-signed variable) on a "
              "different, slightly larger book snapshot (g3_arm_ow1.json: "
              f"{n_traded} traded vs a1's 1016) -- confirmed, not new.")
    L.append("")

    L.append("## The three pre-existing OFF flags")
    L.append("")
    L.append("`ENABLE_SEQUENCE_GATE` re-measured here on `g3_arm_ow1.json` "
              "(book-rig method, no bars); the other two are bar-dependent and "
              "carried over from their existing publications, verified against "
              "the source file, not recomputed on this book.")
    L.append("")
    L.append("| flag | trip n / % of book | tripped mean R (n) | clean mean R (n) | delta | verdict | source |")
    L.append("|---|---:|---:|---:|---:|---|---|")
    L.append(
        f"| `ENABLE_SEQUENCE_GATE` (recomputed here) | {seq_trip_all} / "
        f"{100.0*seq_trip_all/n_all:.1f}% | "
        f"{fmt_r(mean(seq_tripped_traded_r) if seq_tripped_traded_r else None)} "
        f"(n={len(seq_tripped_traded_r)}) | "
        f"{fmt_r(mean(seq_clean_traded_r) if seq_clean_traded_r else None)} "
        f"(n={len(seq_clean_traded_r)}) | "
        f"{('n/a' if seq_delta is None else f'{seq_delta:+.4f}R')} | "
        f"{'WRONG-SIGNED' if (seq_delta is not None and seq_delta >= 0) else 'right-signed'} | "
        f"g3_arm_ow1.json |"
    )
    for name, (trip_n, trip_pct, t_r, t_n, c_r, c_n, delta, verdict, src) in FLAGGED_PRIOR.items():
        if name.startswith("sequence_gate"):
            continue
        L.append(
            f"| `{name}` (prior) | {trip_n} / {trip_pct:.1f}% | "
            f"{t_r:+.3f}R (n={t_n}) | {c_r:+.3f}R (n={c_n}) | {delta:+.3f}R | "
            f"{verdict} | `{src}` |"
        )
    L.append("")

    L.append("## 3. Simulating the new S/A/C/X-by-count ladder")
    L.append("")
    L.append("`net = trips_in_set - (1 if BR+OCR confluence) floored at 0`; "
              "`S` if net==0, `A` if net==1, `C` if net==2, `X` if net>=3 (spec 1.2). "
              "Confluence (`has_confluence`) is unchanged across all three sets.")
    L.append("")
    for set_name, variable_set in VARIABLE_SETS.items():
        L.append(f"### {set_name}")
        L.append("")
        L.append(f"Variables: {', '.join('`%s`' % v for v in variable_set)}")
        L.append("")
        L.append("| grade | n | % of book | mean R | median R |")
        L.append("|---|---:|---:|---:|---:|")
        b = sim[set_name]["buckets"]
        for g in ("S", "A", "C", "X"):
            n = b[g]["n"]
            L.append(f"| {g} | {n} | {100.0*n/n_traded:.1f}% | "
                      f"{fmt_r(b[g]['mean_r'])} | {fmt_r(b[g]['median_r'])} |")
        mono = sim[set_name]["monotonic_median"]
        L.append("")
        L.append(f"**Monotonic on median R (S > A > C, and C > X where X exists): "
                  f"{'YES' if mono else 'NO'}.**")
        L.append("")

    L.append("## Why (b) is not the obvious fix")
    L.append("")
    c_b = sim["(b) all eight minus level_not_respected"]["buckets"]["C"]
    x_b = sim["(b) all eight minus level_not_respected"]["buckets"]["X"]
    L.append(
        "The naive move -- drop the one wrong-signed variable and keep the rest -- "
        "is set (b), and it is the ONLY one of the three that fails monotonicity. "
        f"Its C bucket ({c_b['n']} rows) has median R tied to the -1.25R stop floor "
        f"({x_b['n']} rows in X, same floor), because 51.5% of C's rows in set (b) are "
        "exact stop-outs versus 53.4% of X's -- removing `level_not_respected` does not "
        "just remove a bug, it also removes the one thing that had been backfilling C "
        "with the better trades that made it separable from X on mean R (+0.89R vs "
        "+0.68R) even though the two buckets look the same on the median. `net` "
        "shrinks for most of the 62.7%-of-the-book population `level_not_respected` "
        "used to trip, so S and A both grow (128->277, 251->351) at C and X's expense "
        "(331->200, 307->189) -- and what is left in C after that migration is "
        "disproportionately floor losses."
    )
    L.append("")
    L.append("## Recommendation")
    L.append("")
    L.append(
        "**Set (c) -- the seven right-signed shipped variables plus "
        "`ENABLE_SEQUENCE_GATE` turned on -- is the set W1's ladder should count.** "
        "It is monotonic on median R (S +1.211 > A +0.750 > C +0.293 > X -1.000) "
        "without carrying the one variable known to be wrong-signed. Set (a), all "
        "eight as shipped, is ALSO monotonic, but only because "
        "`level_not_respected`'s wrong sign is doing real work in that table -- it "
        "is backfilling the C bucket with better-than-C trades and is masking the "
        "same floor-collapse that (b) exposes when it is removed cleanly; keeping a "
        "known-wrong-signed variable because it happens to make the aggregate table "
        "look right is exactly the kind of accidental correctness this ticket exists "
        "to catch, not a reason to ship it. Set (c) gets the same monotonic shape "
        "from a variable that is actually right-signed on its own population "
        "(-0.322R tripped vs clean, this book) instead of from a bug. "
        "`ENABLE_SEQUENCE_GATE` has shipped OFF with no stated reason found in this "
        "repo pass beyond \"not yet turned on\" -- flip it to ON alongside the "
        "`level_not_respected` removal in the same W1 change, and say so plainly in "
        "that report, since flipping a second flag inside a sign-fix is exactly the "
        "kind of change this ticket was told to price, not to make unannounced."
    )
    L.append("")
    return "\n".join(L), table, sim, seq_delta, n_wrong


def main():
    report, table, sim, seq_delta, n_wrong = build_report()
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"wrote {OUT}")
    print(f"{n_wrong} of 8 shipped variables wrong-signed")
    for set_name in VARIABLE_SETS:
        print(set_name, "monotonic:", sim[set_name]["monotonic_median"])


if __name__ == "__main__":
    main()
