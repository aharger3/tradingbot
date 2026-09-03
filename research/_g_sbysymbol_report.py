"""_g_sbysymbol_report.py -- AREA s_by_symbol, one-off, read-only.

S-rate and engine EV/R by symbol, pool (index/equity/other), and tier
(core/experimental/other). Marks come from marks_pool.canonical_pool()
(1,263 judged symbol-days). Engine EV/R comes from the committed book
research/bt2y_trades_retest_on.json, size-gated via omen_metrics.ev_r_scoreboard.

CONFOUND, stated once here and repeated in the printed report: deck cards are
SELECTED by build_deck.py (mixed fire/silent, T21-prefiltered, never-repeat),
not a random sample of trading days. S-rate by symbol is therefore "S-rate
among days he was SHOWN for that symbol", not "S-rate among all days that
symbol traded". A symbol shown more often, or shown a harder/easier mix of
days, moves its S-rate independent of anything about the symbol itself.
"""
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import marks_pool as mp
import omen_metrics as om
import universe as U

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")


def load_book():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    return blob["meta"], blob["trades"]


def traded_rows(rows):
    """Every row the engine actually put a trade on -- fired&traded, plus
    halted (blocked by the account-wide loss halt, a policy choice, not a
    'no setup' day) -- same definition omen_metrics.first_of_day_arm uses
    for status, but here EVERY such row counts, not just the day's first."""
    return [r for r in rows if (r["status"] == "fired" and r.get("traded"))
            or r["status"] == "halted"]


def sym_pool_tier(rows):
    """symbol -> (pool, tier) straight off the book (deterministic per symbol)."""
    out = {}
    for r in rows:
        out[r["sym"]] = (r.get("pool"), r.get("tier"))
    return out


def main():
    pool = mp.canonical_pool()
    meta, rows = load_book()
    trows = traded_rows(rows)
    sym_meta = sym_pool_tier(rows)

    # ---- per-symbol marks: n judged, n S, S-rate -----------------------
    by_sym_marks = defaultdict(Counter)
    for e in pool.values():
        by_sym_marks[e.symbol]["n"] += 1
        if e.grade == "S":
            by_sym_marks[e.symbol]["S"] += 1

    # ---- per-symbol engine trades, EV/R scoreboard ----------------------
    by_sym_trades = defaultdict(list)
    for r in trows:
        by_sym_trades[r["sym"]].append(r)

    all_syms = sorted(set(by_sym_marks) | set(by_sym_trades))

    print("=" * 100)
    print("AREA s_by_symbol -- S-rate and engine EV/R, per symbol")
    print("marks: marks_pool.canonical_pool() n=%d judged symbol-days (%d S)"
          % (len(pool), sum(1 for e in pool.values() if e.grade == "S")))
    print("book: %s -- %d sessions, %d fired-and-traded/halted rows"
          % (os.path.basename(BOOK_PATH), meta.get("sessions"), len(trows)))
    print("CONFOUND: deck cards are SELECTED (build_deck.py: mixed fire/silent,")
    print("T21-prefiltered, never-repeat), not a random sample of trading days.")
    print("S-rate below is S-rate AMONG DAYS HE WAS SHOWN for that symbol, not")
    print("among all days that symbol traded. Denominators are printed so this")
    print("cannot be silently read as the second thing.")
    print("=" * 100)

    hdr = ("%-6s %6s %6s %8s | %6s %6s %6s %8s %8s %6s %5s | %-6s %-12s"
           % ("SYM", "n_jdg", "n_S", "S_rate", "n_trd", "ndrop", "n_scr",
              "ev_r", "win%", "avgW", "avgL", "pool", "tier"))
    print(hdr)
    print("-" * len(hdr))

    sym_rows_out = []
    for sym in all_syms:
        mc = by_sym_marks.get(sym, Counter())
        n_j, n_s = mc.get("n", 0), mc.get("S", 0)
        s_rate = (n_s / n_j) if n_j else None
        tr = by_sym_trades.get(sym, [])
        p, t = sym_meta.get(sym, (None, None))
        if tr:
            sb = om.ev_r_scoreboard(tr, risk_dollars=1000.0)
            n_trd, ndrop, n_scr = sb["n_input"], sb["n_dropped_size_gate"], sb["n"]
            ev_r, win, aw, al = sb["ev_r"], sb["win_rate"], sb["avg_win_R"], sb["avg_loss_R"]
        else:
            n_trd = ndrop = n_scr = 0
            ev_r = win = aw = al = None
        print("%-6s %6d %6d %8s | %6d %6d %6d %8s %8s %6s %5s | %-6s %-12s" % (
            sym, n_j, n_s,
            ("%.3f" % s_rate) if s_rate is not None else "n/a",
            n_trd, ndrop, n_scr,
            ("%.4f" % ev_r) if ev_r is not None else "n/a",
            ("%.1f" % (win * 100)) if win is not None else "n/a",
            ("%.3f" % aw) if aw is not None else "n/a",
            ("%.3f" % al) if al is not None else "n/a",
            p or "-", t or "-",
        ))
        sym_rows_out.append(dict(sym=sym, n_judged=n_j, n_S=n_s, s_rate=s_rate,
                                  n_traded=n_trd, n_dropped_size_gate=ndrop,
                                  n_scored=n_scr, ev_r=ev_r, win_rate=win,
                                  avg_win_R=aw, avg_loss_R=al, pool=p, tier=t))

    # symbols judged but absent from the current 28-symbol book universe
    off_universe = sorted(s for s in by_sym_marks if s not in U.ALL_SYMS)
    print()
    print("Judged symbols with NO engine book to price against (not in the")
    print("current 28-symbol universe.ALL_SYMS -- retired or never added):")
    for s in off_universe:
        mc = by_sym_marks[s]
        print("  %-6s n_judged=%d  n_S=%d" % (s, mc.get("n", 0), mc.get("S", 0)))

    # ---------------------------------------------------------------- pool
    print()
    print("=" * 100)
    print("BY POOL (index / equity / other -- universe.py pool_for; book field")
    print("'pool' agrees with it for every symbol in the book)")
    print("=" * 100)
    by_pool_marks = defaultdict(Counter)
    for e in pool.values():
        p = U.pool_for(e.symbol) if e.symbol in U.ALL_SYMS else "off_universe"
        by_pool_marks[p]["n"] += 1
        if e.grade == "S":
            by_pool_marks[p]["S"] += 1
    by_pool_trades = defaultdict(list)
    for r in trows:
        by_pool_trades[r.get("pool")].append(r)

    print("%-12s %8s %8s %8s | %8s %8s %8s %8s %8s"
          % ("pool", "n_jdg", "n_S", "S_rate", "n_scr", "ndrop", "ev_r", "win%", "yrR"))
    for p in ("index", "equity", "other", "off_universe"):
        mc = by_pool_marks.get(p, Counter())
        n_j, n_s = mc.get("n", 0), mc.get("S", 0)
        s_rate = (n_s / n_j) if n_j else None
        tr = by_pool_trades.get(p, [])
        if tr:
            sb = om.ev_r_scoreboard(tr, risk_dollars=1000.0, sessions=meta.get("sessions"))
            ev_r, win, ndrop, n_scr, yr = sb["ev_r"], sb["win_rate"], sb["n_dropped_size_gate"], sb["n"], sb["yearly_R"]
        else:
            ev_r = win = yr = None
            ndrop = n_scr = 0
        print("%-12s %8d %8d %8s | %8d %8d %8s %8s %8s" % (
            p, n_j, n_s, ("%.3f" % s_rate) if s_rate is not None else "n/a",
            n_scr, ndrop,
            ("%.4f" % ev_r) if ev_r is not None else "n/a",
            ("%.1f" % (win * 100)) if win is not None else "n/a",
            ("%.2f" % yr) if yr is not None else "n/a",
        ))

    # ---------------------------------------------------------------- tier
    print()
    print("=" * 100)
    print("BY TIER (core / experimental / other -- universe.py CORE_SYMBOLS /")
    print("EXPERIMENTAL_SYMBOLS; 'other' = untiered, e.g. index symbols + SPCX/ACHR)")
    print("=" * 100)

    def tier_for(sym):
        if sym in U.CORE_SYMBOLS:
            return "core"
        if sym in U.EXPERIMENTAL_SYMBOLS:
            return "experimental"
        if sym in U.ALL_SYMS:
            return "other"
        return "off_universe"

    by_tier_marks = defaultdict(Counter)
    for e in pool.values():
        t = tier_for(e.symbol)
        by_tier_marks[t]["n"] += 1
        if e.grade == "S":
            by_tier_marks[t]["S"] += 1
    by_tier_trades = defaultdict(list)
    for r in trows:
        by_tier_trades[r.get("tier")].append(r)

    print("%-14s %8s %8s %8s | %8s %8s %8s %8s %8s"
          % ("tier", "n_jdg", "n_S", "S_rate", "n_scr", "ndrop", "ev_r", "win%", "yrR"))
    for t in ("core", "experimental", "other", "off_universe"):
        mc = by_tier_marks.get(t, Counter())
        n_j, n_s = mc.get("n", 0), mc.get("S", 0)
        s_rate = (n_s / n_j) if n_j else None
        tr = by_tier_trades.get(t, [])
        if tr:
            sb = om.ev_r_scoreboard(tr, risk_dollars=1000.0, sessions=meta.get("sessions"))
            ev_r, win, ndrop, n_scr, yr = sb["ev_r"], sb["win_rate"], sb["n_dropped_size_gate"], sb["n"], sb["yearly_R"]
        else:
            ev_r = win = yr = None
            ndrop = n_scr = 0
        print("%-14s %8d %8d %8s | %8d %8d %8s %8s %8s" % (
            t, n_j, n_s, ("%.3f" % s_rate) if s_rate is not None else "n/a",
            n_scr, ndrop,
            ("%.4f" % ev_r) if ev_r is not None else "n/a",
            ("%.1f" % (win * 100)) if win is not None else "n/a",
            ("%.2f" % yr) if yr is not None else "n/a",
        ))

    # dump machine-readable copy alongside
    out_path = os.path.join(HERE, "_g_sbysymbol_out.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"symbols": sym_rows_out, "off_universe": off_universe}, f, indent=2)
    print("\nwrote %s" % out_path)


if __name__ == "__main__":
    main()
