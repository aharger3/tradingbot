"""g77_wrongchart_counterfactual.py -- what the 30 cards would have been.

Re-picks each of the 30 graded symbol-days under g77_realtrade_pick.day_trade
(the engine's first booked trade on that chart) and reports how many cards change,
how they change, and what is left of the 70% precision figure.

Also the book-wide version, one pass over research/bt2y_trades.json: how often a
day the engine actually traded carries a first trade the g71 rule could not have
picked, because that trade is not S on Austin's ladder.

Read-only. Writes research/g77_wrongchart_counterfactual.json.
"""
from __future__ import annotations
import json
import math
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from g77_realtrade_pick import day_trade  # noqa: E402

CENSUS = os.path.join(HERE, "g77_wrongchart_census.json")
CACHE = os.path.join(HERE, "g77_wrongchart_signals.json")
BOOK = os.path.join(HERE, "bt2y_trades.json")
OUT = os.path.join(HERE, "g77_wrongchart_counterfactual.json")

SHORT = {"break_and_retest": "BR", "one_candle_rule": "OCR", "reentry_84_rule": "84"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def main():
    cen = json.load(open(CENSUS, encoding="utf-8"))
    raw = json.load(open(CACHE, encoding="utf-8"))
    sig, man = raw["signals"], raw["manifest"]

    rows_out, kinds = [], Counter()
    for p in cen["cards"]:
        rows = sig["%s|%s" % (p["symbol"], p["date"])]
        real = day_trade(rows)
        m = man[p["card_id"]]
        if real is None:
            kind = "day dropped -- engine refused this whole chart"
        elif real["et"] == m["et"] and real["setup"] == m["engine_setup"]:
            kind = "unchanged"
        else:
            kind = "same chart, different signal"
        kinds[kind] += 1
        rows_out.append({
            "card_id": p["card_id"], "he_said": "yes" if p["his_yes"] else "no",
            "his_minute": p["his_minute"],
            "card": "%s %s %s on %s" % (p["card_setup"], p["card_et"],
                                        p["card_dir"], p["card_level"]),
            "card_traded": p["card_traded"],
            "real": (None if real is None else
                     "%s %s %s on %s  %+.2fR" % (SHORT.get(real["setup"], real["setup"]),
                                                 real["et"], real["dir"],
                                                 real["level_name"], real["r"])),
            "verdict": kind,
            "minutes_card_vs_his": p["card_delta"],
            "minutes_real_vs_his": (None if real is None or p["his_minute"] is None
                                    else (int(real["et"][:2]) * 60 + int(real["et"][3:5]))
                                    - (int(p["his_minute"][:2]) * 60 + int(p["his_minute"][3:5]))),
        })

    # ---- how close each rule lands to the minute he wrote
    with_min = [r for r in rows_out if r["his_minute"] and r["minutes_real_vs_his"] is not None]
    card_abs = sorted(abs(r["minutes_card_vs_his"]) for r in with_min)
    real_abs = sorted(abs(r["minutes_real_vs_his"]) for r in with_min)

    def med(v):
        return v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2

    # ---- precision restated
    yes = sum(1 for p in cen["cards"] if p["his_yes"])
    real_cards = [p for p in cen["cards"] if p["card_traded"]]
    yes_real = sum(1 for p in real_cards if p["his_yes"])
    first_cards = [r for r in rows_out if r["verdict"] == "unchanged"]
    yes_first = sum(1 for r in first_cards if r["he_said"] == "yes")

    lo, hi = wilson(yes, 30)
    lo2, hi2 = wilson(yes_real, len(real_cards))
    prec = {
        "all_30_nominations": "%d/30 = %.0f%%  (95%% CI %.0f-%.0f%%)"
                              % (yes, 100 * yes / 30, 100 * lo, 100 * hi),
        "cards_that_were_a_booked_trade":
            "%d/%d = %.0f%%  (95%% CI %.0f-%.0f%%)"
            % (yes_real, len(real_cards), 100 * yes_real / len(real_cards),
               100 * lo2, 100 * hi2),
        "cards_that_were_the_day's_first_booked_trade":
            "%d/%d" % (yes_first, len(first_cards)),
        "arms_of_the_booked_cards": dict(Counter(p["bucket"] for p in real_cards)),
    }

    # ---- book-wide: could the g71 rule ever have picked the real trade?
    book = json.load(open(BOOK, encoding="utf-8"))["trades"]
    by_day = defaultdict(list)
    for r in book:
        if r.get("traded"):
            by_day[(r["sym"], r["day"])].append(r)
    firsts = [min(v, key=lambda r: r.get("et") or "99:99") for v in by_day.values()]
    n = len(firsts)
    not_s = sum(1 for r in firsts if r.get("sgrade") != "S")
    arm_mix = Counter(SHORT.get(r["setup"], r["setup"]) for r in firsts)
    # days that booked more than one kind of setup (g75 deck2 drops these)
    mixed = sum(1 for v in by_day.values()
                if len({r["setup"] for r in v}) > 1)
    bookwide = {
        "symbol_days_the_engine_traded": n,
        "first_trade_not_S_on_his_ladder": "%d of %d = %.0f%%"
                                           % (not_s, n, 100.0 * not_s / n),
        "meaning": ("the g71 rule only ever looked at sgrade=='S' rows "
                    "(g71_homework_build.py:276), so on those days it could not "
                    "have picked the engine's real trade even by accident"),
        "arm_of_the_real_first_trade": dict(arm_mix),
        "days_booking_more_than_one_setup": mixed,
        "sgrade_of_the_real_first_trade": dict(Counter(r.get("sgrade") for r in firsts)),
    }

    summary = {
        "counterfactual_on_the_30": dict(kinds),
        "closeness_to_his_minute_minutes": {
            "n_cards_with_a_minute_and_a_real_trade": len(with_min),
            "median_abs_gap_the_card": med(card_abs),
            "median_abs_gap_the_real_trade": med(real_abs),
            "real_trade_closer_on": sum(1 for r in with_min
                                        if abs(r["minutes_real_vs_his"])
                                        < abs(r["minutes_card_vs_his"])),
            "within_4_min_card": sum(1 for r in with_min if abs(r["minutes_card_vs_his"]) <= 4),
            "within_4_min_real": sum(1 for r in with_min if abs(r["minutes_real_vs_his"]) <= 4),
        },
        "precision": prec,
        "book_wide": bookwide,
    }

    json.dump({"summary": summary, "cards": rows_out}, open(OUT, "w", encoding="utf-8"),
              indent=1)
    print("%-18s %-4s %-6s %-26s %-34s %s"
          % ("card", "said", "his", "the card he was shown", "the trade the engine took",
             "verdict"))
    for r in rows_out:
        print("%-18s %-4s %-6s %-26s %-34s %s"
              % (r["card_id"], r["he_said"], r["his_minute"] or "-", r["card"],
                 r["real"] or "(none -- engine refused the chart)", r["verdict"]))
    print()
    print(json.dumps(summary, indent=1))
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
