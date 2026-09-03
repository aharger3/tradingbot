"""G7.1 / track `ladder` -- does the legacy A+/A/B/C/X ladder select anything?

Counts, over the committed 2-year book (`research/bt2y_trades.json`, the T0
re-baselined run of 2026-08-29 03:14), how many TRADED rows are `B` and how
many of those `B`s exist only because `signal_runner._calibration_grade`
floors the first with-trend signal of the day inside 90 minutes from `C` to
`B`. That floor writes a literal tag into `reason`:

    " [floor B: first with-trend signal of the day]"

so the count is a substring test on the row, not a re-simulation.

Read-only. Publishes the numbers in research/g71_ladder.md.
"""
import json, collections, sys, os

BOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bt2y_trades.json")
FLOOR_TAG = "[floor B: first with-trend signal of the day]"
CAP_TAG = "[capped C: counter day trend]"


def main():
    d = json.load(open(BOOK))
    rows = d["trades"]
    traded = [t for t in rows if t.get("traded")]
    alerts = [t for t in rows if not t.get("traded")]

    def dist(rs, key):
        return collections.Counter(r.get(key) for r in rs)

    print("meta:", json.dumps(d["meta"]))
    print("rows=%d traded=%d alert=%d" % (len(rows), len(traded), len(alerts)))
    print("\n-- traded by legacy grade --")
    for g, n in dist(traded, "grade").most_common():
        print("  %-3s %6d  %5.1f%%" % (g, n, 100.0 * n / len(traded)))
    print("\n-- ALL rows by legacy grade --")
    for g, n in dist(rows, "grade").most_common():
        print("  %-3s %6d  %5.1f%%" % (g, n, 100.0 * n / len(rows)))
    print("\n-- traded by Austin ladder (sgrade, measured-only column) --")
    for g, n in dist(traded, "sgrade").most_common():
        print("  %-4s %6d  %5.1f%%" % (g, n, 100.0 * n / len(traded)))

    floored = [t for t in traded if FLOOR_TAG in (t.get("reason") or "")]
    print("\n-- the arrival-order floor --")
    print("  traded rows carrying the C->B floor tag: %d / %d = %.1f%%"
          % (len(floored), len(traded), 100.0 * len(floored) / len(traded)))
    b = [t for t in traded if t.get("grade") == "B"]
    bf = [t for t in b if FLOOR_TAG in (t.get("reason") or "")]
    print("  traded B: %d; of those floored: %d = %.1f%% of B"
          % (len(b), len(bf), 100.0 * len(bf) / max(1, len(b))))
    print("  traded B NOT floored (earned B from _grade_pa shape): %d"
          % (len(b) - len(bf)))

    # what would survive if the floor were deleted: the row's pre-floor grade is
    # `C` by construction (the floor only fires on grade == "C"), and `C` is
    # alert-only, so every floored row leaves the traded book.
    surv = [t for t in traded if FLOOR_TAG not in (t.get("reason") or "")]
    print("\n-- counterfactual: delete the floor, keep everything else --")
    print("  traded would fall %d -> %d" % (len(traded), len(surv)))
    for label, rs in (("HEAD", traded), ("no-floor", surv)):
        n = len(rs)
        if not n:
            continue
        wins = sum(1 for t in rs if (t.get("r") or 0) > 0)
        mr = sum((t.get("r") or 0) for t in rs) / n
        print("  %-9s n=%4d  win=%5.1f%%  meanR=%+.4f  totalR=%+.1f"
              % (label, n, 100.0 * wins / n, mr, mr * n))

    # cross-tab: legacy grade vs Austin's downgrade count on the SAME traded rows
    print("\n-- traded rows: legacy grade x sgrade --")
    ct = collections.Counter((t.get("grade"), t.get("sgrade")) for t in traded)
    for (g, s), n in sorted(ct.items(), key=lambda kv: -kv[1]):
        print("  %-3s x %-4s %6d" % (g, s, n))

    # per-sgrade money on the traded book -- what the gate would buy
    print("\n-- traded rows sliced by Austin's ladder --")
    by = collections.defaultdict(list)
    for t in traded:
        by[t.get("sgrade")].append(t)
    for s, rs in sorted(by.items(), key=lambda kv: str(kv[0])):
        n = len(rs)
        wins = sum(1 for t in rs if (t.get("r") or 0) > 0)
        mr = sum((t.get("r") or 0) for t in rs) / n
        print("  sgrade %-4s n=%4d  win=%5.1f%%  meanR=%+.4f  totalR=%+.1f"
              % (s, n, 100.0 * wins / n, mr, mr * n))

    # and over EVERY row (traded or not) -- the pool an S-only gate could reach
    print("\n-- ALL rows sliced by Austin's ladder (the reachable pool) --")
    by = collections.defaultdict(list)
    for t in rows:
        by[t.get("sgrade")].append(t)
    for s, rs in sorted(by.items(), key=lambda kv: str(kv[0])):
        n = len(rs)
        scored = [t for t in rs if t.get("r") is not None]
        if not scored:
            print("  sgrade %-4s n=%5d  (no R -- never entered)" % (s, n))
            continue
        wins = sum(1 for t in scored if t["r"] > 0)
        mr = sum(t["r"] for t in scored) / len(scored)
        print("  sgrade %-4s n=%5d  scored=%5d win=%5.1f%%  meanR=%+.4f"
              % (s, n, len(scored), 100.0 * wins / len(scored), mr))


if __name__ == "__main__":
    main()


def counterfactual():
    """What an S/A/C gate would trade, read off the SAME committed book.

    Approximate by construction -- it cannot model the routing order changes --
    but it bounds the money question while the full arm re-runs. The book's
    `sgrade` column is `downgrade.score()` on the row's own bars and level, the
    same call `_sac_ladder_grade` makes, so the label is not re-derived here.
    """
    d = json.load(open(BOOK))
    rows = d["trades"]
    fired = [t for t in rows if t.get("status") == "fired"]      # traded + C alerts
    traded = [t for t in fired if t.get("traded")]
    alerts = [t for t in fired if not t.get("traded")]

    def stats(rs, lbl):
        n = len(rs)
        if not n:
            print("  %-34s n=0" % lbl)
            return
        w = sum(1 for t in rs if (t.get("r") or 0) > 0)
        mr = sum((t.get("r") or 0) for t in rs) / n
        mon = collections.defaultdict(float)
        for t in rs:
            mon[t.get("ym")] += (t.get("r") or 0)
        green = sum(1 for v in mon.values() if v > 0)
        print("  %-34s n=%4d win=%5.1f%% meanR=%+.4f totR=%+8.1f months %d/%d green"
              % (lbl, n, 100.0 * w / n, mr, mr * n, green, len(mon)))

    print("\n=== counterfactual gates on the committed book ===")
    stats(traded, "HEAD (grade != C)")
    stats([t for t in traded if t.get("sgrade") in ("S", "A")],
          "S/A gate, HEAD-traded pool only")
    stats([t for t in fired if t.get("sgrade") in ("S", "A")],
          "S/A gate, fired pool (incl C alerts)")
    stats([t for t in fired if t.get("sgrade") == "S"], "S-only gate, fired pool")
    stats([t for t in traded if t.get("sgrade") == "S"], "S-only gate, HEAD-traded pool")
    print("  C alerts promoted by an S/A gate: %d of %d"
          % (sum(1 for t in alerts if t.get("sgrade") in ("S", "A")), len(alerts)))


if __name__ == "__main__" and "--cf" in sys.argv:
    counterfactual()
