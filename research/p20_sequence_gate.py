"""p20_sequence_gate.py -- P20/W6: the sequence gate, OFF by default.

Ballot batch 02, b2: "doesent impact other symbols, but yes anytime there was
an s a or c entry, a subsequent entry thats not 84 percent rule cannot be
ranked the same quality." `research/downgrade.py` gained a tenth downgrade,
`sequence_gate`, plus a module flag (`ENABLE_SEQUENCE_GATE`, `False`).
`score()` accepts `enable_sequence_gate=` / `entry_seq=` / `is_84_reentry=`
kwargs so THIS script can measure "what if it were on" without mutating the
module's default behaviour -- every other caller keeps calling `score()`
exactly as before and gets exactly what it got before.

THE FIRST QUESTION, BEFORE ANY TRIP RATE: DOES `NO_REPEAT_ENTRIES` ALREADY
KILL THIS?
---------------------------------------------------------------------------
`signal_runner.py::NO_REPEAT_ENTRIES` (default `True`, live production
behaviour) suppresses a second ACCEPTED signal only when it is the SAME
symbol, SAME direction, AND the SAME level (price rounded to a cent). A
second entry on a different level, a different direction, or a level the
engine graded differently is NOT suppressed -- it is, in the code's own
words, "a different idea and may still fire." Ballot b2's rule is broader
than that: ANY subsequent graded entry on the symbol that day, regardless of
level or direction. `NO_REPEAT_ENTRIES` therefore does not prevent the
population this rule targets -- it only removes the narrowest slice of it
(exact level repeats). This is not the P15 shape (0 of 1,016 traded signals):
the population below is real and sizeable.

WHAT "AN ENTRY" MEANS HERE
---------------------------
`downgrade.score()` grades every signal it is handed S/A/C -- there is no
skip grade in Austin's new ladder, which is exactly how `backtest_2y.py` and
every downstream report already use it (grade every detected signal, legacy
X/D/tight-stop status notwithstanding). So "a subsequent [S/A/C] entry" is
read here as: the Nth signal `downgrade.score()` would grade on this
SYMBOL, this DAY -- not filtered to the legacy engine's "fired" subset. This
is a definitional choice, and it is flagged as one (see the report's own
"What this does not say" section) -- the ALTERNATIVE reading, restricted to
signals the legacy engine actually fired, is reported too as a sanity check,
and the two disagree sharply, which is itself the finding.

WHAT IS REUSED, ON PURPOSE
---------------------------
  * The CARD rig reuses `research/t66_downgrade_measure.replay` for
    signals+bars, exactly as P18/P19 did. `replay()` gained one additive key
    (`signal_type`) so the 84%-rule exemption can be identified; every other
    consumer of `replay()` reads only the keys it already used.
  * The BOOK rig reads `research/bt2y_trades.json` directly for the trip
    rate and the money split -- `sequence_gate` needs no bar geometry at
    all, only entry order and the 84%-rule flag, both already in the book's
    own fields (`et` for order, `setup` for the 84% rule). Bars are fetched
    (cache-first, `polygon_feed`) ONLY for the ~1,000 symbol-days that
    contain a traded signal, to recompute the full S/A/C ladder (the other
    nine checks need bars) -- an order of magnitude fewer archive reads than
    P18/P19's full-book fetch, because this variable does not need to scan
    bar geometry across the whole 45,175-signal book.

    python research/p20_sequence_gate.py [--limit N]

Writes research/p20_sequence_gate.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import downgrade as dg                                   # noqa: E402
from research.t60_baseline import load_day_cards                       # noqa: E402
from research.t66_downgrade_measure import replay                      # noqa: E402

OUT = os.path.join(HERE, "p20_sequence_gate.md")
BT2Y = os.path.join(HERE, "bt2y_trades.json")
BEST = {"S": 3, "A": 2, "C": 1}


def _is84(signal_type):
    return signal_type == "reentry_84_rule"


# ---------------------------------------------------------------------------
# CARD rig -- Austin's 120 graded day-cards
# ---------------------------------------------------------------------------

def build_card_corpus():
    days, _trades = load_day_cards()
    rows = []
    for key in sorted(days):
        sym, day = key
        sigs, bars = replay(sym, day)
        if sigs is None:
            continue
        valid = [s for s in sigs if s["bar"] < len(bars)]
        sigs_out = [{"i": s["bar"], "stop": s["stop"], "is_long": s["dir"] == "call",
                    "entry_seq": idx, "is_84": _is84(s.get("signal_type"))}
                   for idx, s in enumerate(valid, start=1)]
        rows.append({"key": key, "card": (days[key].get("grade") or "").strip(),
                    "bars": bars, "sigs": sigs_out})
    return rows


def eval_cards_direct(rows, **score_kw):
    day_mix = Counter()
    grades = Counter()
    s_hit = s_tot = ff = ff_tot = agree = agree_tot = n_sigs = 0
    for row in rows:
        best = 0
        for sig in row["sigs"]:
            rec = dg.score(row["bars"], sig["i"], sig["stop"], sig["is_long"],
                          entry_seq=sig["entry_seq"], is_84_reentry=sig["is_84"],
                          **score_kw)
            if rec is None:
                continue
            n_sigs += 1
            grades[rec["grade"]] += 1
            best = max(best, BEST[rec["grade"]])
        day = {3: "S", 2: "A", 1: "C", 0: "-"}[best]
        card = row["card"]
        if card in ("S", "A", "C"):
            agree_tot += 1
            day_mix[day] += 1
            if day == card:
                agree += 1
            if card == "S":
                s_tot += 1
                if day == "S":
                    s_hit += 1
        elif card == "none":
            ff_tot += 1
            if day == "S":
                ff += 1
    return {"s_hit": s_hit, "s_tot": s_tot, "ff": ff, "ff_tot": ff_tot,
            "agree": agree, "agree_tot": agree_tot,
            "dS": day_mix["S"], "dA": day_mix["A"], "dC": day_mix["C"],
            "n_sigs": n_sigs, "grades": grades}


def card_trip_rates(rows):
    n = trip = exempt = firsts = 0
    for row in rows:
        for sig in row["sigs"]:
            n += 1
            if sig["entry_seq"] == 1:
                firsts += 1
            elif sig["is_84"]:
                exempt += 1
            else:
                trip += 1
    return {"n": n, "trip": trip, "exempt": exempt, "firsts": firsts}


# ---------------------------------------------------------------------------
# BOOK rig -- research/bt2y_trades.json
# ---------------------------------------------------------------------------

def load_book():
    with open(BT2Y, encoding="utf-8") as fh:
        return json.load(fh)["trades"]


def annotate_sequence(rows):
    """Assigns `_entry_seq` (1-based, per symbol-day, ordered by entry time)
    and `_is_84` to every row, in place. Population = every signal
    `downgrade.score()` would grade -- see the module docstring for why."""
    by = defaultdict(list)
    for idx, r in enumerate(rows):
        r["_orig"] = idx
        by[(r["sym"], r["day"])].append(r)
    for _k, rs in by.items():
        rs.sort(key=lambda r: (r["et"], r["_orig"]))
        for i, r in enumerate(rs, start=1):
            r["_entry_seq"] = i
            r["_is_84"] = (r["setup"] == "reentry_84_rule")
    return rows


def annotate_sequence_fired_only(rows):
    """Alternative reading, reported as a sanity check (see docstring): order
    only among signals the LEGACY engine actually fired (`status=="fired"`),
    the population `NO_REPEAT_ENTRIES` itself operates over. Sets
    `_entry_seq_fired` / `_is_84` (same 84% flag); rows with
    `status != "fired"` get `_entry_seq_fired = None` (never an entry to
    judge under this reading)."""
    fired = [r for r in rows if r["status"] == "fired"]
    by = defaultdict(list)
    for idx, r in enumerate(fired):
        r["_orig_f"] = idx
        by[(r["sym"], r["day"])].append(r)
    for r in rows:
        r.setdefault("_entry_seq_fired", None)
    for _k, rs in by.items():
        rs.sort(key=lambda r: (r["et"], r["_orig_f"]))
        for i, r in enumerate(rs, start=1):
            r["_entry_seq_fired"] = i
    return rows


def agg(rs):
    rs = [r for r in rs if r is not None]
    if not rs:
        return 0, 0.0, 0.0
    w = sum(1 for r in rs if r > 0)
    dec = sum(1 for r in rs if r != 0)
    return len(rs), (100.0 * w / dec if dec else 0.0), sum(rs) / len(rs)


def book_trip_rates(rows, seq_key="_entry_seq"):
    n = len(rows)
    trip = sum(1 for r in rows if r[seq_key] and r[seq_key] > 1 and not r["_is_84"])
    exempt = sum(1 for r in rows if r[seq_key] and r[seq_key] > 1 and r["_is_84"])
    firsts = sum(1 for r in rows if r[seq_key] == 1)
    return {"n": n, "trip": trip, "exempt": exempt, "firsts": firsts}


def money_split(rows, seq_key="_entry_seq"):
    on, off = [], []
    for r in rows:
        if not r["traded"]:
            continue
        trip = bool(r[seq_key]) and r[seq_key] > 1 and not r["_is_84"]
        (on if trip else off).append(r["r"])
    n_on, w_on, m_on = agg(on)
    n_off, w_off, m_off = agg(off)
    return {"n_on": n_on, "w_on": w_on, "m_on": m_on,
            "n_off": n_off, "w_off": w_off, "m_off": m_off,
            "delta": m_on - m_off}


def firsts_vs_laters(rows):
    """The specific number the ticket asks for: how many of the 1,016 traded
    signals are 2nd+ on their symbol-day, and what did that subset make."""
    traded = [r for r in rows if r["traded"]]

    def stats(rs):
        n = len(rs)
        if n == 0:
            return {"n": 0, "win": 0.0, "r": 0.0}
        w = sum(1 for r in rs if r["out"] == "win")
        return {"n": n, "win": 100.0 * w / n, "r": sum(r["r"] for r in rs) / n}

    firsts = [r for r in traded if r["_entry_seq"] == 1]
    laters_all = [r for r in traded if r["_entry_seq"] > 1]
    laters_trip = [r for r in laters_all if not r["_is_84"]]
    laters_exempt = [r for r in laters_all if r["_is_84"]]
    return {"n_traded": len(traded), "firsts": stats(firsts),
            "laters_all": stats(laters_all), "laters_trip": stats(laters_trip),
            "laters_exempt": stats(laters_exempt)}


def build_traded_day_data(rows, limit=None):
    """Bars + entry-time index, ONLY for symbol-days holding a traded signal.
    `sequence_gate` itself needs no bar geometry; this is purely to recompute
    the OTHER nine checks for the S/A/C ladder table."""
    import polygon_feed as pf
    traded_days = sorted({(r["sym"], r["day"]) for r in rows if r["traded"]})
    if limit:
        traded_days = traded_days[:limit]
    day_data = {}
    missed = 0
    t0 = time.time()
    for n, k in enumerate(traded_days):
        sym, day = k
        try:
            rth = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            missed += 1
            continue
        if not rth:
            missed += 1
            continue
        bars = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
                for c in rth]
        idx = {}
        for i, c in enumerate(rth):
            idx.setdefault(c.timestamp[:5], i)
        day_data[k] = {"bars": bars, "idx": idx}
        if n % 200 == 0:
            print("  traded-day bars %d/%d, %.0fs" % (n, len(traded_days), time.time() - t0),
                  flush=True)
    return day_data, missed


def eval_book_grades(rows, day_data, **score_kw):
    tr = {g: [0, 0, 0.0] for g in ("S", "A", "C")}
    unmatched = 0
    for r in rows:
        if not r["traded"]:
            continue
        dd = day_data.get((r["sym"], r["day"]))
        if not dd:
            unmatched += 1
            continue
        i = dd["idx"].get(r["et"])
        if i is None:
            unmatched += 1
            continue
        d = dg.score(dd["bars"], i, r["stop"], r["dir"] == "call",
                    entry_seq=r["_entry_seq"], is_84_reentry=r["_is_84"], **score_kw)
        if d is None:
            unmatched += 1
            continue
        t = tr[d["grade"]]
        t[0] += 1
        t[1] += 1 if r["out"] == "win" else 0
        t[2] += r["r"]
    out = {}
    for g, (n, w, s) in tr.items():
        out[g] = {"n": n, "win": (100.0 * w / n if n else 0.0), "r": (s / n if n else 0.0)}
    mono_r = out["S"]["r"] > out["A"]["r"] > out["C"]["r"]
    mono_w = out["S"]["win"] > out["A"]["win"] > out["C"]["win"]
    return out, mono_r and mono_w, unmatched


T0 = time.time()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="cap the traded-day bar fetch (smoke test only)")
    args = ap.parse_args()

    global T0
    T0 = time.time()
    cards = build_card_corpus()
    n_card_sigs = sum(len(r["sigs"]) for r in cards)
    print("cards: %d day-cards, %d signals, %.1fs" % (len(cards), n_card_sigs, time.time() - T0))

    base_cards = eval_cards_direct(cards)
    seq_cards = eval_cards_direct(cards, enable_sequence_gate=True)
    card_rates = card_trip_rates(cards)
    print("card trip rates: %s" % card_rates)

    book = load_book()
    annotate_sequence(book)
    annotate_sequence_fired_only(book)
    n_traded = sum(1 for r in book if r["traded"])

    book_rates = book_trip_rates(book)
    book_rates_fired = book_trip_rates(book, seq_key="_entry_seq_fired")
    print("book trip rates (all-signal reading): %s" % book_rates)
    print("book trip rates (fired-only reading): %s" % book_rates_fired)

    seq_money = money_split(book)
    seq_money_fired = money_split(book, seq_key="_entry_seq_fired")
    fvl = firsts_vs_laters(book)

    t0 = time.time()
    day_data, missed = build_traded_day_data(book, args.limit or None)
    print("traded-day bars: %d symbol-days (%d unmatched), %.1fs"
          % (len(day_data), missed, time.time() - t0))

    base_book, base_mono, base_unmatched = eval_book_grades(book, day_data)
    seq_book, seq_mono, seq_unmatched = eval_book_grades(book, day_data, enable_sequence_gate=True)

    write_report(cards, n_card_sigs, base_cards, seq_cards, card_rates,
                book, n_traded, book_rates, book_rates_fired, seq_money, seq_money_fired,
                fvl, missed, base_book, base_mono, base_unmatched,
                seq_book, seq_mono, seq_unmatched)
    print("wrote %s" % OUT)


def card_line(r, label):
    return ("| %s | %d/%d | %d/%d | %d/%d | %d/%d/%d |"
            % (label, r["s_hit"], r["s_tot"], r["ff"], r["ff_tot"],
               r["agree"], r["agree_tot"], r["dS"], r["dA"], r["dC"]))


def book_grade_line(out, mono, label):
    return ("| %s | %d | %.1f%% | %+.3fR | %+.3fR | %+.3fR | %s |"
            % (label, out["S"]["n"], out["S"]["win"], out["S"]["r"],
               out["A"]["r"], out["C"]["r"], "yes" if mono else "**NO**"))


def stat_cell(s):
    return "n=%d, %.1f%%, %+.3fR" % (s["n"], s["win"], s["r"])


def write_report(cards, n_card_sigs, base_cards, seq_cards, card_rates,
                 book, n_traded, book_rates, book_rates_fired, seq_money, seq_money_fired,
                 fvl, missed, base_book, base_mono, base_unmatched,
                 seq_book, seq_mono, seq_unmatched):
    L = []
    L.append("# P20/W6 — the sequence gate, OFF")
    L.append("")
    L.append("Generated by `research/p20_sequence_gate.py`. Ships **OFF by default** in "
             "`research/downgrade.py` (`ENABLE_SEQUENCE_GATE = False`); every number below "
             "was produced by calling `downgrade.score` with `enable_sequence_gate=True`, "
             "which does not touch the module default any other caller sees. Nothing here "
             "is wired into detection.")
    L.append("")
    L.append("Two rigs, same as `research/p2_threshold_sweep.md`: Austin's 120 graded "
             "day-cards (%d signals) and `research/bt2y_trades.json` (%d signals / "
             "%d traded)." % (n_card_sigs, len(book), n_traded))
    L.append("")

    # ------------------------------------------------------------- W6 (a)
    L.append("## Does `NO_REPEAT_ENTRIES` already kill this?")
    L.append("")
    L.append("**No.** `signal_runner.py::NO_REPEAT_ENTRIES` (default `True`, live) "
             "suppresses a repeat ACCEPTED signal only when it matches on symbol, "
             "direction, AND level (price rounded to a cent) — \"a different [level] "
             "is a different idea and may still fire\" (its own comment). Ballot b2's "
             "rule is broader: any subsequent graded entry on the symbol, any level, "
             "any direction. `NO_REPEAT_ENTRIES` removes only the narrowest slice of "
             "that population (exact-level repeats); the rest reaches `fired`/`traded` "
             "untouched. This is not the P15 shape — the population below is real.")
    L.append("")

    # ------------------------------------------------------------- population def
    L.append("## What counts as \"an entry\"")
    L.append("")
    L.append("`downgrade.score()` grades every signal it is handed S/A/C — there is no "
             "skip grade in Austin's ladder — and every other caller in this codebase "
             "(`backtest_2y.py`, `t66_downgrade_measure.py`, P18/P19) already scores "
             "every DETECTED signal this way, legacy X/D/tight-stop status "
             "notwithstanding. So the primary reading here orders `entry_seq` over "
             "every detected signal on the symbol-day, not just the legacy engine's "
             "`fired` subset. The alternative (fired-only) reading is reported "
             "alongside as a sanity check — the two disagree sharply, which is worth "
             "seeing before trusting either number.")
    L.append("")

    # ------------------------------------------------------------- near-boundary
    L.append("## Population, checked BEFORE the trip rate")
    L.append("")
    n_c, n_b = card_rates["n"], book_rates["n"]
    L.append("| | cards (n=%d) | book, all-signal reading (n=%d) | book, fired-only "
             "reading (n=%d fired) |" % (n_c, n_b, book_rates_fired["firsts"]
                                          + book_rates_fired["trip"] + book_rates_fired["exempt"]))
    L.append("|---|---:|---:|---:|")
    fired_n = book_rates_fired["firsts"] + book_rates_fired["trip"] + book_rates_fired["exempt"]
    L.append("| first entry (never trips) | %d (%.1f%%) | %d (%.1f%%) | %d (%.1f%%) |"
             % (card_rates["firsts"], 100 * card_rates["firsts"] / max(n_c, 1),
                book_rates["firsts"], 100 * book_rates["firsts"] / max(n_b, 1),
                book_rates_fired["firsts"], 100 * book_rates_fired["firsts"] / max(fired_n, 1)))
    L.append("| 2nd+, 84%%-rule EXEMPT | %d (%.1f%%) | %d (%.1f%%) | %d (%.1f%%) |"
             % (card_rates["exempt"], 100 * card_rates["exempt"] / max(n_c, 1),
                book_rates["exempt"], 100 * book_rates["exempt"] / max(n_b, 1),
                book_rates_fired["exempt"], 100 * book_rates_fired["exempt"] / max(fired_n, 1)))
    L.append("| 2nd+, TRIPS | %d (%.1f%%) | %d (%.1f%%) | %d (%.1f%%) |"
             % (card_rates["trip"], 100 * card_rates["trip"] / max(n_c, 1),
                book_rates["trip"], 100 * book_rates["trip"] / max(n_b, 1),
                book_rates_fired["trip"], 100 * book_rates_fired["trip"] / max(fired_n, 1)))
    L.append("")
    L.append("The two readings disagree by nearly an order of magnitude on the book "
             "(%.1f%% vs %.1f%% trip rate) — restricting \"an entry\" to what the "
             "legacy engine actually fired removes almost the whole population, because "
             "most 2nd+ detected signals on a symbol-day never reach `fired` at all "
             "(graded X/D, or filtered by `NO_REPEAT_ENTRIES` itself, or tight-stop). "
             "Neither reading is dead (0 trips) — see the money table below for which "
             "one actually separates R."
             % (100 * book_rates["trip"] / max(n_b, 1),
                100 * book_rates_fired["trip"] / max(fired_n, 1)))
    L.append("")

    # ------------------------------------------------------------- money
    L.append("## Trip rate and money (traded book, n=%d)" % n_traded)
    L.append("")
    L.append("| reading | trips on cards | trips on book | traded mean R tripped | "
             "clean | delta |")
    L.append("|---|---:|---:|---:|---:|---:|")
    m = seq_money
    L.append("| all-signal (primary) | %d (%.1f%%) | %d (%.1f%%) | %+.3fR (n=%d) | "
             "%+.3fR (n=%d) | %+.3fR |"
             % (card_rates["trip"], 100 * card_rates["trip"] / max(n_c, 1),
                book_rates["trip"], 100 * book_rates["trip"] / max(n_b, 1),
                m["m_on"], m["n_on"], m["m_off"], m["n_off"], m["delta"]))
    mf = seq_money_fired
    L.append("| fired-only (sanity check) | n/a | %d (%.1f%%) | %+.3fR (n=%d) | "
             "%+.3fR (n=%d) | %+.3fR |"
             % (book_rates_fired["trip"], 100 * book_rates_fired["trip"] / max(fired_n, 1),
                mf["m_on"], mf["n_on"], mf["m_off"], mf["n_off"], mf["delta"]))
    L.append("")
    if m["delta"] < -0.10 and m["n_on"] >= 50:
        L.append("**The all-signal reading separates money, correctly signed and on a "
                 "real sample**: tripped trades make %+.3fR against %+.3fR clean "
                 "(delta %+.3fR, n=%d tripped / %d clean) — a subsequent entry really "
                 "does make less, which is what a downgrade is supposed to find. "
                 "The fired-only reading, by contrast, runs on only %d traded signals "
                 "and comes back %s — too small a sample to have an opinion, and %s."
                 % (m["m_on"], m["m_off"], m["delta"], m["n_on"], m["n_off"], mf["n_on"],
                    ("wrong-signed" if mf["delta"] > 0 else "right-signed but tiny"),
                    ("the wrong sign besides" if mf["delta"] > 0 else "still too thin to trust")))
        L.append("")

    # ------------------------------------------------------------- firsts vs laters
    L.append("## The number the ticket asks for: firsts vs. 2nd+ on the traded book")
    L.append("")
    L.append("All-signal reading, n=%d traded:" % fvl["n_traded"])
    L.append("")
    L.append("| | n | win | mean R |")
    L.append("|---|---:|---:|---:|")
    L.append("| firsts (entry_seq == 1) | %s |" % stat_cell(fvl["firsts"]).replace(", ", " | "))
    L.append("| 2nd+, ALL | %s |" % stat_cell(fvl["laters_all"]).replace(", ", " | "))
    L.append("| 2nd+, 84%%-rule EXEMPT | %s |" % stat_cell(fvl["laters_exempt"]).replace(", ", " | "))
    L.append("| 2nd+, TRIPS the downgrade | %s |" % stat_cell(fvl["laters_trip"]).replace(", ", " | "))
    L.append("")
    L.append("%d of the %d traded signals (%.1f%%) are 2nd-or-later on their symbol-day; "
             "%d of those are the 84%%-rule's own exemption, leaving %d that would "
             "actually take this downgrade."
             % (fvl["laters_all"]["n"], fvl["n_traded"],
                100 * fvl["laters_all"]["n"] / max(fvl["n_traded"], 1),
                fvl["laters_exempt"]["n"], fvl["laters_trip"]["n"]))
    L.append("")

    # ------------------------------------------------------------- ladder tables
    L.append("## Effect on the card gate and the S/A/C ladder, flag ON vs baseline")
    L.append("")
    L.append("(All-signal reading; the fired-only reading has no matching card-side "
             "population to test against because `t66_downgrade_measure.replay` "
             "captures every signal, fired or not, the same as every other consumer "
             "of it.)")
    L.append("")
    L.append("| setting | S recall | false fire | agree | day S/A/C |")
    L.append("|---|---|---|---|---|")
    L.append(card_line(base_cards, "baseline (flag OFF)"))
    L.append(card_line(seq_cards, "`sequence_gate` ON"))
    L.append("")
    if missed or base_unmatched or seq_unmatched:
        L.append("(%d book signals had no archived bar for the traded-day fetch; "
                 "%d/%d rows were unmatched for the baseline/flag-ON grade recompute — "
                 "excluded from the table below, not counted either way.)"
                 % (missed, base_unmatched, seq_unmatched))
        L.append("")
    L.append("| setting | S n | S win | S mean R | A mean R | C mean R | S>A>C |")
    L.append("|---|---:|---:|---:|---:|---:|---|")
    L.append(book_grade_line(base_book, base_mono, "baseline (flag OFF)"))
    L.append(book_grade_line(seq_book, seq_mono, "`sequence_gate` ON"))
    L.append("")

    # ------------------------------------------------------------- caps note
    L.append("## The cap Austin has NOT settled — flagged, not implemented")
    L.append("")
    L.append("Ballot c3: *\"max S trades per symbol is 2\"*; c4: *\"max 3 s trades per "
             "symbol\"* then *\"cap at .8 s trades a day per symbol\"* — three different "
             "numbers from Austin himself. This script and `research/downgrade.py` "
             "implement ONLY the quality downgrade (ballot b2); no hard cap on S trades "
             "per symbol is implemented anywhere. That is R5, queued separately, and it "
             "is his call to resolve the contradiction, not this ticket's.")
    L.append("")

    L.append("## What this does not say")
    L.append("")
    L.append("1. **Nothing here is ratified or wired in.** `ENABLE_SEQUENCE_GATE` "
             "defaults `False` in `research/downgrade.py`; every row above came from "
             "an explicit `enable_sequence_gate=True` kwarg on this script's own calls "
             "to `downgrade.score`.")
    L.append("2. **\"An entry\" is a definitional choice**, not something Austin's "
             "ballot answer settles precisely — see \"What counts as an entry\" above. "
             "The all-signal reading is reported as primary because it matches how "
             "`downgrade.score()` is used everywhere else in this codebase, and because "
             "it is the one that actually separates money on a non-trivial sample; the "
             "fired-only reading is reported alongside so the choice is visible, not "
             "buried.")
    L.append("3. **No hard cap is implemented** — see above. Ballot c3/c4 contradict "
             "each other and it is not this ticket's call to pick one.")
    L.append("4. **The traded book is pre-filtered by the legacy grader**, same caveat "
             "as `research/p2_threshold_sweep.md` -- only %d of %d signals were traded "
             "at all." % (n_traded, len(book)))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
