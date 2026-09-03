"""G7.2 (suppress) — which kind of rejected setup was eating the real trades?

Reads the two books research/g72_suppress_price.py builds and, for every entry
the fix UNLOCKS, looks one or two bars back on the same symbol / day / setup /
direction in the BEFORE book to name the row that had claimed the level. That
row is the culprit, and its `status` says what it was.

Approximate by construction — it matches on symbol+day+setup+direction inside the
two-bar window rather than re-deriving the dedupe key — so read the shares, not
the last digit.

Usage:  python research/g72_suppress_who_ate.py --workdir DIR
"""
import argparse, json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def mins(et):
    h, m = et.split(":")
    return int(h) * 60 + int(m)


def key(r):
    return (r["sym"], r["day"], r["setup"], r["dir"])


def idkey(r):
    return (r["sym"], r["day"], r["et"], round(r["entry"], 2), round(r["stop"], 2),
            r["dir"], r["setup"])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workdir", required=True)
    args = ap.parse_args()
    wd = Path(args.workdir)

    rb = json.load(open(wd / "g72_book_before.json", encoding="utf-8"))["trades"]
    ra = json.load(open(wd / "g72_book_after.json", encoding="utf-8"))["trades"]

    before_by = {}
    for r in rb:
        before_by.setdefault(key(r), []).append(r)
    for v in before_by.values():
        v.sort(key=lambda r: mins(r["et"]))

    old_ids = {idkey(r) for r in rb if r.get("traded")}
    new_traded = [r for r in ra if r.get("traded") and idkey(r) not in old_ids]

    culprit = Counter()
    money = Counter()
    for r in new_traded:
        t = mins(r["et"])
        cands = [x for x in before_by.get(key(r), []) if 0 < t - mins(x["et"]) <= 2]
        if not cands:
            culprit["(no row within 2 bars — window came from further back)"] += 1
            money["(none)"] += r["pnl"]
            continue
        c = max(cands, key=lambda x: mins(x["et"]))
        culprit[c["status"]] += 1
        money[c["status"]] += r["pnl"]

    print("entries the fix unlocks: %d" % len(new_traded))
    print("what had claimed the level, one or two bars earlier:")
    for k, n in culprit.most_common():
        print("  %-52s %5d  (%5.1f%%)  $%+.0f"
              % (k, n, 100.0 * n / max(1, len(new_traded)), money[k]))

    # --- is this just more of the same, or a different animal? ---
    kept = [r for r in ra if r.get("traded") and idkey(r) in old_ids]

    def facet(rows, f):
        c, m = Counter(), Counter()
        for r in rows:
            c[f(r)] += 1
            m[f(r)] += r["pnl"]
        return c, m

    for title, f in (("setup", lambda r: r["setup"]),
                     ("legacy grade", lambda r: r["grade"]),
                     ("Austin S/A/C", lambda r: r["sgrade"]),
                     ("outcome", lambda r: r["out"]),
                     ("stop width", lambda r: r["stopb"])):
        print("\n%s — unlocked vs kept (count, share, $/trade):" % title)
        cn, mn = facet(new_traded, f)
        ck, mk = facet(kept, f)
        for k in sorted(set(cn) | set(ck), key=lambda x: -cn.get(x, 0)):
            print("  %-22s new %5d (%5.1f%%) $%+6.0f   kept %5d (%5.1f%%) $%+6.0f"
                  % (k, cn.get(k, 0), 100.0 * cn.get(k, 0) / max(1, len(new_traded)),
                     mn.get(k, 0) / cn[k] if cn.get(k) else 0,
                     ck.get(k, 0), 100.0 * ck.get(k, 0) / max(1, len(kept)),
                     mk.get(k, 0) / ck[k] if ck.get(k) else 0))

    # a duplicate-idea audit: does the fix ever take the SAME level twice a day?
    seen = Counter()
    for r in sorted([r for r in ra if r.get("traded")], key=lambda r: (r["day"], r["et"])):
        seen[(r["sym"], r["day"], r["dir"], r["level"], round(r["stop"], 2))] += 1
    dups = sum(v - 1 for v in seen.values() if v > 1)
    print("\nsame symbol+day+direction+level traded more than once: %d extra rows "
          "of %d traded (%.2f%%)" % (dups, sum(seen.values()),
                                     100.0 * dups / max(1, sum(seen.values()))))


if __name__ == "__main__":
    main()
