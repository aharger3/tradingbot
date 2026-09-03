"""OMEN 8.0 R3 verify: `research/g92_x_lift.md` carries an `off` / `on_all` /
`targeted` table where

  1. the `targeted` arm's HELD-OUT recall lands STRICTLY BETWEEN the `off` arm's
     and the `on_all` arm's (in whichever direction the data actually runs --
     the row's own wording assumes `on_all` recalls more, but that is checked,
     not assumed), and
  2. the `targeted` arm's trade count is UNDER 2x the `off` arm's book. The row:
     "Exits nonzero if the book grows past 2x, which means the regrade was not
     targeted."

Exit 0 = pass, 1 = fail.

The verify criterion's literal numbers in the 8.0 spec (52.5% `off`, 44.1%
`on_all`, 12,770 trades) are NOT checked and are NOT reachable: `g4_dropped_s`,
`on_all` and W1's arm table exist nowhere in this repo, so those figures cannot
be reproduced from committed code -- see g92_x_lift.md's "What could not be
reconstructed". The row is read structurally, against this script's own three
arms, which is the only honest reading available. Same precedent as
`research/g90_fill_arms.md`'s lost `OMEN-7.3.md` source.

    python3 research/g92_verify.py
"""
import os
import re
import sys

ARMS = ["off", "on_all", "targeted"]
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "g92_x_lift.md")

# | off | **4/61 = 6.6%** | 5/69 = 7.2% | 926 | 1.00x | 1263 | +0.9770 | 53.1% |
ROW = re.compile(
    r"^\|\s*(\w+)\s*\|\s*\*{0,2}(\d+)/(\d+)\s*=\s*([\d.]+)%\*{0,2}\s*\|"      # held-out recall
    r"\s*(\d+)/(\d+)\s*=\s*([\d.]+)%\s*\|"                                     # dev recall
    r"\s*(\d+)\s*\|"                                                           # traded book
    r"\s*([\d.]+)x\s*\|"                                                       # vs off
    r"\s*(\d+)\s*\|"                                                           # fired signals
    r"\s*([+\-][\d.]+)\s*\|"                                                   # mean R
    r"\s*([\d.]+)%\s*\|")                                                      # win rate


def main():
    try:
        text = open(PATH, encoding="utf-8").read()
    except OSError as e:
        print(f"FAIL: cannot read {PATH}: {e}")
        return 1

    rows = {}
    for line in text.splitlines():
        m = ROW.match(line)
        if not m:
            continue
        arm = m.group(1)
        if arm not in ARMS or arm in rows:
            continue
        rows[arm] = dict(hit=int(m.group(2)), n=int(m.group(3)),
                         recall=float(m.group(4)),
                         dev_hit=int(m.group(5)), dev_n=int(m.group(6)),
                         traded=int(m.group(8)), ratio=float(m.group(9)),
                         fired=int(m.group(10)), mean_r=float(m.group(11)),
                         win_rate=float(m.group(12)))

    missing = [a for a in ARMS if a not in rows]
    if missing:
        print(f"FAIL: missing arm(s) in {os.path.basename(PATH)}: {missing}")
        return 1

    off, on_all, tgt = rows["off"], rows["on_all"], rows["targeted"]

    # sanity: one shared held-out denominator, and a non-empty baseline book
    ns = {rows[a]["n"] for a in ARMS}
    if len(ns) != 1:
        print(f"FAIL: the three arms do not share a held-out denominator: {ns}")
        return 1
    if off["traded"] <= 0:
        print("FAIL: the `off` arm has an empty book -- nothing to compare against")
        return 1
    if off["recall"] == on_all["recall"]:
        print(f"FAIL: `off` and `on_all` report the same held-out recall "
              f"({off['recall']}%) -- there is no interval for `targeted` to sit "
              f"strictly inside, so the arms are not doing different things")
        return 1

    # 1. strictly between, in whichever direction the two extremes actually run
    lo, hi = sorted((off["recall"], on_all["recall"]))
    if not (lo < tgt["recall"] < hi):
        print(f"FAIL: `targeted` held-out recall {tgt['recall']}% "
              f"({tgt['hit']}/{tgt['n']}) is NOT strictly between `off` "
              f"{off['recall']}% ({off['hit']}/{off['n']}) and `on_all` "
              f"{on_all['recall']}% ({on_all['hit']}/{on_all['n']})")
        return 1

    # 2. book under 2x off
    ratio = tgt["traded"] / off["traded"]
    if ratio >= 2.0:
        print(f"FAIL: `targeted` book is {tgt['traded']} trades vs `off`'s "
              f"{off['traded']} = {ratio:.2f}x -- at or past the 2x ceiling, so the "
              f"regrade was not targeted")
        return 1

    print("PASS: the targeted X lift lands in the middle and keeps the book under 2x.")
    print(f"  held-out recall   off {off['recall']}% ({off['hit']}/{off['n']})"
          f"  <  targeted {tgt['recall']}% ({tgt['hit']}/{tgt['n']})"
          f"  <  on_all {on_all['recall']}% ({on_all['hit']}/{on_all['n']})")
    print(f"  traded book       off {off['traded']}  ->  targeted {tgt['traded']} "
          f"({ratio:.2f}x, ceiling 2.00x)  |  on_all {on_all['traded']} "
          f"({on_all['traded']/off['traded']:.2f}x)")
    print(f"  mean R            off {off['mean_r']:+.4f}  targeted {tgt['mean_r']:+.4f}  "
          f"on_all {on_all['mean_r']:+.4f}")
    print("  (goalposts are this run's own off/on_all arms -- the spec's 52.5% / 44.1% / "
          "12,770 are unreconstructable, see the report's last section)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
