"""G7.1 adversarial verify of track `ladder` claim 3 ("ENABLE_SAC_LADDER=1 does
not kill B -- a live defect").

Read-only. Publishes the numbers quoted in the verify verdict:

  * the 582 x-lifted traded rows are counted on research/bt2y_trades.json, the
    flag-OFF HEAD book (meta traded=2437) -- not on any ENABLE_SAC_LADDER=1 book
    (none exists: research/ has head/noab/sac_xlift/sac_all, no `sac`).
  * every x-lifted row entered `_route` graded `X`, so with the flag ON
    `_sac_ladder_grade` early-returns on it (signal_runner.py:2109) and writes
    nothing. No ladder verdict is overwritten on any of the 582.
  * the rows where the ladder's OWN verdict would be overwritten are a
    different set: net>=3 -> SAC_TIER["X"], then `_apply_x_lift` re-promotes.
"""
import json, os, collections

BOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bt2y_trades.json")


def net(t):
    return len(t.get("downgrades") or []) - (1 if t.get("confluence") == "yes" else 0)


def main():
    d = json.load(open(BOOK))
    rows, meta = d["trades"], d["meta"]
    traded = [t for t in rows if t.get("traded")]
    print("book generated=%s signals=%d traded=%d" % (
        meta["generated"], meta["signals"], meta["traded"]))

    xl = [t for t in rows if "[x-lift" in (t.get("reason") or "")]
    xlt = [t for t in xl if t.get("traded")]
    print("x-lift rows=%d traded=%d = %.2f%% of traded (%d)"
          % (len(xl), len(xlt), 100.0 * len(xlt) / len(traded), len(traded)))
    print("  grade of x-lifted:", dict(collections.Counter(t.get("grade") for t in xl)))
    print("  sgrade of x-lifted:", dict(collections.Counter(t.get("sgrade") for t in xl)))
    print("  -> all entered _route as X, so _sac_ladder_grade returns at :2109")

    nonx = [t for t in rows if t.get("grade") not in ("X", "D")]
    cand = [t for t in nonx if "[x-lift" not in (t.get("reason") or "") and net(t) >= 3]
    clean = [t for t in cand if "[clean]" in (t.get("reason") or "")]
    print("REAL overlap (ladder writes X, then x-lift re-promotes to B):")
    print("  non-X rows=%d  net>=3 (ladder -> X)=%d  of those [clean] B&R=%d"
          % (len(nonx), len(cand), len(clean)))
    print("  setups among the [clean] set:",
          dict(collections.Counter(t.get("setup") for t in clean)))

    for a in ("head", "sac", "sac_xlift", "sac_all"):
        p = os.path.join(os.path.dirname(BOOK), "g71_ladder_recall_%s.json" % a)
        if not os.path.exists(p):
            continue
        s = json.load(open(p))["sweep"]
        print("recall %-9s %d/%d" % (a, s["fired_on_S"], s["n_S"]))


if __name__ == "__main__":
    main()
