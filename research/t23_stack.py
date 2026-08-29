"""T23 — the stack, and each lever's MARGINAL contribution inside it.

Nobody has ever done this here. Twelve lanes ran single-lever A/Bs against T0 in
isolated worktrees and ZERO combinations, and `research/p23_combined_arms.md` is
the standing precedent that a stack can underperform its parts (P19 alone scored
+0.033 on TUNE; P19+P20+P18 fell to +0.007 while S recall collapsed 5/14 -> 1/14).

WHAT THIS MEASURES
------------------
Three levers change the two-year book. Each gets a LEAVE-ONE-OUT arm: the full
stack with exactly that lever switched off, so the number reported is its
marginal contribution INSIDE the stack, not its solo number against T0.

  stack          X_LIFT=clean  MIN_STOP_PCT=0.08  LOSS_HALT=1
  -T10           X_LIFT=off    MIN_STOP_PCT=0.08  LOSS_HALT=1
  -T9            X_LIFT=clean  MIN_STOP_PCT=0     LOSS_HALT=1
  -T20           X_LIFT=clean  MIN_STOP_PCT=0.08  LOSS_HALT=0
  t0_base        X_LIFT=off    MIN_STOP_PCT=0     LOSS_HALT=0   <- T0's shipped book

The halt arms cost nothing to produce: the halt is a book-level post-pass
(loss_halt.apply_to_book), so un-halting a book is exact, not a re-run. Every
other arm is its own 500-session replay.

A lever whose marginal sign FLIPS against its solo sign is unshipped until
re-measured. That test is printed explicitly.

ERROR BARS
----------
1.96 x the standard error of the difference of two means, the same construction
`research/t0_rebaseline.py` used for the +/-0.1725R bar the whole wave quotes.
The two books share most of their days but not their rows, so they are treated
as independent samples of trade outcomes. A move inside its own bar is a NULL
and is printed as one.

HELD-OUT RECALL
---------------
Method rule 2: recall governs, not mean R. It is scored twice on purpose.

  ENGINE-LEVEL, via research/t0_heldout_recall.py -- replays each marked
  symbol-day through research/t4_engine_recall.run_day. This is the number the
  whole wave quotes, and it CANNOT see the loss halt, because the halt is a
  statement about a whole trading day across every symbol and a single-day
  replay has no book to count losses in.

  BOOK-LEVEL, here -- did a row for that symbol-day survive into the traded
  book. This one DOES see the halt, and the gap between the two is exactly what
  R31 costs in recall. Nobody had measured that before either.

Usage:
  python research/t23_stack.py --out research/t23_stack.json
"""
from __future__ import annotations

import argparse, json, math, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from research.t0_rebaseline import stats, load          # noqa: E402
import loss_halt                                        # noqa: E402

SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
MASTER = os.path.join(HERE, "marks", "probe_master_2026-08-29.jsonl")

# The arms. `book` is the file the replay wrote; `halt` says whether to keep the
# halt that book was written with. Un-halting is exact and free.
ARMS = [
    ("stack",   "bt2y_trades.json",            True,
     "X_LIFT=clean  MIN_STOP_PCT=0.08  LOSS_HALT=1   -- SHIPPED"),
    ("-T10",    "_t23_arm_noxlift.json",       True,
     "X_LIFT=off    MIN_STOP_PCT=0.08  LOSS_HALT=1   -- leave out the recall lever"),
    ("-T9",     "_t23_arm_nostopfloor.json",   True,
     "X_LIFT=clean  MIN_STOP_PCT=0     LOSS_HALT=1   -- leave out the stop-width floor"),
    ("-T20",    "bt2y_trades.json",            False,
     "X_LIFT=clean  MIN_STOP_PCT=0.08  LOSS_HALT=0   -- leave out the loss halt"),
    ("t0_base", "_t23_arm_t0base.json",        False,
     "X_LIFT=off    MIN_STOP_PCT=0     LOSS_HALT=0   -- T0's shipped book"),
]


# --------------------------------------------------------------------------
def unhalt(rows):
    """Undo loss_halt.apply_to_book. Exact: the halt only ever flips flags."""
    out = []
    for r in rows:
        if r.get("halted") or r.get("status") == "halted":
            r = dict(r)
            r["traded"] = True
            r["status"] = "fired"
            r.pop("halted", None)
            r["reason"] = r.get("reason", "").replace(
                " [halt: %d consecutive losses]" % loss_halt.HALT_AFTER_CONSECUTIVE_LOSSES, "")
        out.append(r)
    return out


def bar_and_move(A, B):
    """B is the reference arm. Returns (move, 95% bar, is_null)."""
    move = A["mean_r"] - B["mean_r"]
    bar = 1.96 * math.sqrt(A["se_r"] ** 2 + B["se_r"] ** 2)
    return move, bar, abs(move) <= bar


# --------------------------------------------------------------------------
def read_marks(path, lane=None):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if lane and r.get("lane") != lane:
                continue
            rows.append(r)
    return rows


def card_sym_day(r):
    """(SYMBOL, YYYY-MM-DD) out of whichever id field this corpus uses."""
    for k in ("card_id", "id", "sym_day_ET", "sym_day"):
        v = r.get(k)
        if isinstance(v, str) and "_" in v:
            sym, _, rest = v.partition("_")
            day = rest[:10]
            if len(day) == 10 and day[4] == "-":
                return sym.upper(), day
    sym, day = r.get("symbol"), r.get("date") or r.get("day")
    if sym and day:
        return str(sym).upper(), str(day)[:10]
    return None


def grade_of(r, key):
    """His answer, out of `answers` -- NOT the top-level `grade`, which is the
    page's default and reads "none" on every card. Same read as
    research/t0_heldout_recall.py, so the two scorers cannot disagree."""
    v = (r.get("answers") or {}).get(key) or []
    return v[0].strip().lower() if v else ""


def book_recall(rows, cards):
    """Day-level: did a TRADED row land on that symbol-day."""
    fired = set()
    for r in rows:
        if r.get("traded"):
            fired.add((r["sym"].upper(), r["day"]))
    hit = [c for c in set(cards) if c in fired]
    return len(hit), sorted(set(cards)), sorted(fired & set(cards))


def book_funnel(rows, cards):
    """Where a marked symbol-day dies in the BOOK, as opposed to in the recall
    harness. Four nested populations:

      in_universe  the symbol is one the book trades at all
      any_row      the engine produced at least one signal on that day
      fired_row    at least one of them cleared _route and was taken
      traded_row   it survived to traded=True (fills, day caps, the halt)

    The published recall figure is none of these: it comes from
    research/t4_engine_recall.CaptureRunner, whose _route is a HAND-ROLLED COPY
    of the base router that never calls super(). backtest_week.BacktestRunner
    had the identical bug and it was fixed in omen-5.0 (2026-08-12) with the
    comment "every gate the base grew after it was written was therefore INERT
    in every backtest ever run". The recall harness was never given the same
    fix, so every gate the base has grown since -- the session-extreme veto,
    no-repeat, level retirement, and as of T23 MIN_STOP_PCT -- is inert in the
    one rig that scores the governing metric."""
    cards = set(cards)
    syms = {r["sym"].upper() for r in rows}
    any_row, fired_row, traded_row = set(), set(), set()
    for r in rows:
        k = (r["sym"].upper(), r["day"])
        if k not in cards:
            continue
        any_row.add(k)
        if r.get("status") == "fired" or r.get("traded"):
            fired_row.add(k)
        if r.get("traded"):
            traded_row.add(k)
    return {
        "cards": len(cards),
        "in_universe": sum(1 for s, _d in cards if s in syms),
        "any_row": len(any_row),
        "fired_row": len(fired_row),
        "traded_row": len(traded_row),
        "symbols_not_in_book": sorted({s for s, _d in cards if s not in syms}),
    }


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(HERE, "t23_stack.json"))
    a = ap.parse_args()

    # ---- the marks. READ ONLY. Never written, never moved. ----------------
    sweep = read_marks(SWEEP)
    s_cards, refused_cards = [], []
    for r in sweep:
        sd = card_sym_day(r)
        if not sd:
            continue
        g = grade_of(r, "s")
        if not g:
            continue
        (s_cards if g == "s" else refused_cards).append(sd)
    vetoes = read_marks(MASTER, lane="vetoes")
    v_yes, v_no = [], []
    for r in vetoes:
        sd = card_sym_day(r)
        if not sd:
            continue
        g = grade_of(r, "grade")
        if not g:
            continue
        (v_yes if g in ("s", "a", "c") else v_no).append(sd)

    print("held-out corpora (read only):")
    print("  probe_s_sweep_2026-08-28: %d S cards, %d refused cards"
          % (len(set(s_cards)), len(set(refused_cards))))
    print("  probe_master_2026-08-29 vetoes: %d graded yes, %d explicit no"
          % (len(set(v_yes)), len(set(v_no))))

    # ---- the arms ---------------------------------------------------------
    out = {"arms": {}, "marginals": [], "corpora": {
        "s_sweep_S": len(set(s_cards)), "s_sweep_refused": len(set(refused_cards)),
        "veto_yes": len(set(v_yes)), "veto_no": len(set(v_no))}}

    books = {}
    for name, fn, keep_halt, desc in ARMS:
        path = os.path.join(HERE, fn)
        if not os.path.exists(path):
            print("MISSING %s (%s) -- arm skipped, not guessed" % (name, path))
            continue
        meta, rows = load(path)
        if not keep_halt:
            rows = unhalt(rows)
        S = stats(rows)
        hit_s, _all_s, _ = book_recall(rows, s_cards)
        hit_ff, _, _ = book_recall(rows, refused_cards)
        hit_vy, _, _ = book_recall(rows, v_yes)
        hit_vn, _, _ = book_recall(rows, v_no)
        books[name] = (S, rows)
        funnel_s = book_funnel(rows, s_cards)
        funnel_no = book_funnel(rows, refused_cards)
        out["arms"][name] = {
            "config": desc, "book": fn, "halt_applied": keep_halt,
            "window": [meta.get("first"), meta.get("last")],
            "sessions": meta.get("sessions"), "signals": S["signals"],
            "traded": S["traded"], "mean_r": round(S["mean_r"], 4),
            "se_r": round(S["se_r"], 4), "total_r": round(S["total_r"], 2),
            "win_rate": round(S["win_rate"], 2), "pf": round(S["pf"], 4),
            "max_dd_r": round(S["max_dd_r"], 2),
            "months_green": "%d/%d" % (S["months_green"], S["months"]),
            "setups": dict(S["setups"]), "sgrade": dict(S["sgrade"]),
            "index_trades": S["index"],
            "book_s_recall": "%d/%d" % (hit_s, len(set(s_cards))),
            "book_false_fire": "%d/%d" % (hit_ff, len(set(refused_cards))),
            "book_veto_yes": "%d/%d" % (hit_vy, len(set(v_yes))),
            "book_veto_no": "%d/%d" % (hit_vn, len(set(v_no))),
            "book_funnel_S": funnel_s,
            "book_funnel_refused": funnel_no,
        }
        print("\n== %-8s %s" % (name, desc))
        print("   %d traded  mean R %+.4f  win %.2f%%  total %+.1fR  "
              "%s green  maxDD %.2fR"
              % (S["traded"], S["mean_r"], S["win_rate"], S["total_r"],
                 out["arms"][name]["months_green"], S["max_dd_r"]))
        print("   book-level held-out S recall %s   false fire %s"
              % (out["arms"][name]["book_s_recall"],
                 out["arms"][name]["book_false_fire"]))
        print("   S-card funnel in the BOOK: %d cards -> %d in universe -> "
              "%d with a signal -> %d fired -> %d traded"
              % (funnel_s["cards"], funnel_s["in_universe"], funnel_s["any_row"],
                 funnel_s["fired_row"], funnel_s["traded_row"]))

    # ---- marginals --------------------------------------------------------
    if "stack" in books:
        SS = books["stack"][0]
        print("\n" + "=" * 72)
        print("MARGINAL CONTRIBUTION INSIDE THE STACK")
        print("  read as: stack minus the arm without this lever")
        print("=" * 72)
        for lever, arm, solo in (("T10 X_LIFT=clean", "-T10", -0.0426),
                                 ("T9  MIN_STOP_PCT", "-T9", -0.0462),
                                 ("T20 loss halt", "-T20", +0.0493)):
            if arm not in books:
                continue
            SA = books[arm][0]
            move, bar, null = bar_and_move(SS, SA)
            flip = (move > 0) != (solo > 0)
            rec = {
                "lever": lever, "arm": arm,
                "marginal_mean_r": round(move, 4),
                "error_bar_95": round(bar, 4),
                "null": bool(null),
                "solo_mean_r": solo,
                "sign_flip_vs_solo": bool(flip),
                "traded_move": SS["traded"] - SA["traded"],
                "win_rate_move": round(SS["win_rate"] - SA["win_rate"], 2),
                "months_green": "%d/%d -> %d/%d" % (SA["months_green"], SA["months"],
                                                    SS["months_green"], SS["months"]),
                "book_s_recall": "%s -> %s" % (out["arms"][arm]["book_s_recall"],
                                               out["arms"]["stack"]["book_s_recall"]),
            }
            out["marginals"].append(rec)
            print("\n  %s" % lever)
            print("    marginal mean R %+.4f against a +/-%.4f bar  -> %s"
                  % (move, bar, "NULL" if null else "REAL"))
            print("    solo (vs T0) was %+.4f   sign flip: %s"
                  % (solo, "YES -- UNSHIPPED UNTIL RE-MEASURED" if flip else "no"))
            print("    trades %+d   win rate %+.2f pts   months green %s"
                  % (rec["traded_move"], rec["win_rate_move"], rec["months_green"]))
            print("    book-level held-out S recall %s" % rec["book_s_recall"])

        if "t0_base" in books:
            SB = books["t0_base"][0]
            move, bar, null = bar_and_move(SS, SB)
            out["whole_stack_vs_t0"] = {
                "mean_r": "%+.4f -> %+.4f" % (SB["mean_r"], SS["mean_r"]),
                "move": round(move, 4), "error_bar_95": round(bar, 4),
                "null": bool(null),
                "traded": "%d -> %d" % (SB["traded"], SS["traded"]),
                "win_rate": "%.2f -> %.2f" % (SB["win_rate"], SS["win_rate"]),
                "months_green": "%d/%d -> %d/%d" % (SB["months_green"], SB["months"],
                                                    SS["months_green"], SS["months"]),
                "book_s_recall": "%s -> %s" % (out["arms"]["t0_base"]["book_s_recall"],
                                               out["arms"]["stack"]["book_s_recall"]),
                "sum_of_marginals": round(sum(m["marginal_mean_r"] for m in out["marginals"]), 4),
            }
            print("\n" + "=" * 72)
            print("WHOLE STACK vs T0's BOOK")
            print("=" * 72)
            for k, v in out["whole_stack_vs_t0"].items():
                print("  %-18s %s" % (k, v))
            print("\n  the sum of the marginals is NOT the whole-stack move when the")
            print("  levers interact; the gap between them IS the interaction.")

        # money gate, stated plainly
        gate = (SS["mean_r"] >= 2.0 and SS["months_green"] == SS["months"])
        out["money_gate"] = {
            "reached": bool(gate),
            "mean_r": round(SS["mean_r"], 4), "target_mean_r": 2.0,
            "shortfall_r": round(2.0 - SS["mean_r"], 4),
            "win_rate": round(SS["win_rate"], 2), "target_win_rate": 55.0,
            "months_green": "%d/%d" % (SS["months_green"], SS["months"]),
            "durability_met": SS["months_green"] == SS["months"],
        }
        print("\nMONEY GATE (mean R >= 2.0 AND every month green): %s"
              % ("REACHED" if gate else "NOT REACHED"))
        print("  mean R %+.4f (needs %+.4f more)  win rate %.2f%%  months green %d/%d"
              % (SS["mean_r"], 2.0 - SS["mean_r"], SS["win_rate"],
                 SS["months_green"], SS["months"]))

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("\nwrote %s" % a.out)


if __name__ == "__main__":
    main()
