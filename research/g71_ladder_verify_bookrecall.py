"""G7.1 / adversarial verify of track `ladder`.

Re-measures the two numbers the `ladder` blocker rests on, on the BOOK rather
than on `research/t4_engine_recall.CaptureRunner`:

  1. Held-out S recall of the 34 S cards in
     `research/marks/probe_s_sweep_2026-08-28.jsonl`, scored as "did the 2-year
     book take a trade on that symbol-day", for HEAD / sac_xlift / sac_all.
     `research/t0_heldout_recall.py` scores the same cards on CaptureRunner,
     whose `_route` is a hand-rolled copy that never calls `super()._route`
     (commit 145d564e; `signal_runner._apply_x_lift` docstring, :2465).

  2. Whether 25/25 -> 24/25 green months is separable from noise: per-month
     1-SE bands, and a within-month bootstrap of HEAD's OWN trades giving
     P(at least one red month).

Read-only. Marks are read, never written. No engine file is edited.
Usage: python research/g71_ladder_verify_bookrecall.py
"""
import json, os, collections, random, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
BOOKS = [("bt2y_trades.json", "HEAD"),
         ("g71_ladder_bt2y_sac_xlift.json", "sac_xlift"),
         ("g71_ladder_bt2y_sac_all.json", "sac_all")]


def s_cards():
    rs = [json.loads(l) for l in open(SWEEP, encoding="utf-8") if l.strip()]
    return [r for r in rs if r["answers"].get("s") == ["s"]]


def book(p):
    return json.load(open(os.path.join(HERE, p)))


def main():
    S = s_cards()
    meta = book("bt2y_trades.json")["meta"]
    syms, lo, hi = set(meta["symbols"]), meta["first"], meta["last"]
    reach = [r for r in S if r["symbol"] in syms and lo <= r["date"] <= hi]
    print("S cards %d; in book universe %d; reachable (universe x window) %d"
          % (len(S), sum(1 for r in S if r["symbol"] in syms), len(reach)))
    for p, lbl in BOOKS:
        d = book(p)
        idx = collections.defaultdict(list)
        for t in d["trades"]:
            idx[(t["sym"], t["day"])].append(t)
        hit = [(r["symbol"], r["date"]) for r in S
               if any(x.get("traded") for x in idx.get((r["symbol"], r["date"]), []))]
        fir = [(r["symbol"], r["date"]) for r in S
               if any(x.get("status") == "fired"
                      for x in idx.get((r["symbol"], r["date"]), []))]
        print("%-10s BOOK traded-recall %d/34  fired-recall %d/34  %s"
              % (lbl, len(hit), len(fir), sorted(hit)))

    for p, lbl in BOOKS[:2]:
        tr = [t for t in book(p)["trades"] if t.get("traded")]
        sd = st.pstdev([t.get("r") or 0 for t in tr])
        m = collections.defaultdict(list)
        for t in tr:
            m[t["ym"]].append(t.get("r") or 0)
        thin = [(k, round(sum(v), 2), len(v), round(sd * len(v) ** .5, 1))
                for k, v in sorted(m.items()) if sum(v) < sd * len(v) ** .5]
        print("%-10s per-trade sd=%.3f; months inside 1 SE of zero: %d/%d %s"
              % (lbl, sd, len(thin), len(m), thin))

    random.seed(7)
    tr = [t for t in book("bt2y_trades.json")["trades"] if t.get("traded")]
    m = collections.defaultdict(list)
    for t in tr:
        m[t["ym"]].append(t.get("r") or 0)
    n = 2000
    red = sum(1 for _ in range(n)
              if any(sum(random.choice(v) for _ in v) <= 0 for v in m.values()))
    print("HEAD within-month bootstrap: P(>=1 red month) = %.3f" % (red / n))


if __name__ == "__main__":
    main()
