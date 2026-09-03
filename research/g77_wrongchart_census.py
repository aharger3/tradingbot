"""g77_wrongchart_census.py -- was the homework card the trade the engine takes?

For each of the 30 graded cards: every signal the engine had on that symbol-day,
which one the card was built from, which one (if any) the engine actually traded,
and which one sits closest to the minute Austin wrote.

Reads only research/g77_wrongchart_signals.json (built by g77_wrongchart_extract.py)
and the read-only mark file. Writes research/g77_wrongchart_census.json.
"""
from __future__ import annotations
import json
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "g77_wrongchart_signals.json")
OUT = os.path.join(HERE, "g77_wrongchart_census.json")

SETUP_SHORT = {"break_and_retest": "BR", "one_candle_rule": "OCR",
               "reentry_84_rule": "84"}

# Austin's minute, when he wrote one. "9:%5" is a typo -- unparseable, never guessed.
MIN_RE = re.compile(r"\b(\d{1,2}):([0-5]\d)\b")


def his_minute(card):
    notes = card.get("notes") or {}
    blob = " ".join(v for v in notes.values() if v)
    m = MIN_RE.search(blob)
    if not m:
        return None, blob
    h, mi = int(m.group(1)), int(m.group(2))
    if h < 9:
        h += 12
    return "%02d:%02d" % (h, mi), blob


def mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def main():
    d = json.load(open(CACHE, encoding="utf-8"))
    cards, manifest, signals = d["cards"], d["manifest"], d["signals"]

    per_card = []
    for c in cards:
        cid = c["card_id"]
        man = manifest[cid]
        key = "%s|%s" % (c["symbol"], c["date"])
        rows = signals.get(key, [])
        hm, blob = his_minute(c)

        # which row is the card? manifest carries engine_setup + et + level_px
        card_row = None
        for r in rows:
            if (r["setup"] == man["engine_setup"] and r["et"] == man["et"]
                    and abs((r.get("level_px") or 0) - (man.get("level_px") or 0)) < 0.011):
                card_row = r
                break
        if card_row is None:
            for r in rows:
                if r["setup"] == man["engine_setup"] and r["et"] == man["et"]:
                    card_row = r
                    break

        traded = [r for r in rows if r["traded"]]
        yes = c["answers"].get("is_s", ["?"])[0] == "yes"

        def closest(pool):
            if not pool or hm is None:
                return None
            return min(pool, key=lambda r: abs(mins(r["et"]) - mins(hm)))

        cl_any = closest(rows)
        cl_traded = closest(traded)

        per_card.append({
            "card_id": cid, "symbol": c["symbol"], "date": c["date"],
            "bucket": c["bucket"], "his_yes": yes,
            "his_minute": hm, "his_note": blob,
            "card_setup": SETUP_SHORT.get(man["engine_setup"], man["engine_setup"]),
            "card_et": man["et"], "card_dir": man.get("dir"),
            "card_level": man.get("claimed_level"),
            "card_level_src": man.get("claimed_level_source"),
            "card_legacy": man.get("legacy_grade"), "card_sgrade": man.get("sgrade"),
            "card_traded": bool(man.get("traded")),
            "card_r": man.get("r"), "card_out": man.get("outcome"),
            "card_status": (card_row or {}).get("status"),
            "n_signals": len(rows),
            "n_traded": len(traded),
            "traded_rows": [{"setup": SETUP_SHORT.get(r["setup"], r["setup"]),
                             "et": r["et"], "dir": r["dir"], "grade": r["grade"],
                             "sgrade": r["sgrade"], "level": r["level_name"],
                             "level_px": r["level_px"], "entry": r["entry"],
                             "r": r["r"], "pnl": r["pnl"], "out": r["out"]}
                            for r in traded],
            "closest_any": (None if cl_any is None else
                            {"setup": SETUP_SHORT.get(cl_any["setup"], cl_any["setup"]),
                             "et": cl_any["et"], "traded": cl_any["traded"],
                             "sgrade": cl_any["sgrade"], "grade": cl_any["grade"],
                             "delta": mins(cl_any["et"]) - mins(hm)}),
            "closest_traded": (None if cl_traded is None else
                               {"setup": SETUP_SHORT.get(cl_traded["setup"], cl_traded["setup"]),
                                "et": cl_traded["et"], "dir": cl_traded["dir"],
                                "level": cl_traded["level_name"], "r": cl_traded["r"],
                                "pnl": cl_traded["pnl"],
                                "delta": mins(cl_traded["et"]) - mins(hm)}),
            "card_delta": (None if hm is None or card_row is None else
                           mins(card_row["et"]) - mins(hm)),
            "all_signals": [{"setup": SETUP_SHORT.get(r["setup"], r["setup"]),
                             "et": r["et"], "dir": r["dir"], "grade": r["grade"],
                             "sgrade": r["sgrade"], "traded": r["traded"],
                             "status": r["status"], "level": r["level_name"],
                             "level_px": r["level_px"], "entry": r["entry"],
                             "stop": r["stop"], "r": r["r"], "pnl": r["pnl"],
                             "out": r["out"], "tripped": r["tripped"],
                             "is_card": r is card_row}
                            for r in rows],
        })

    # ---------------------------------------------------------------- summary
    n = len(per_card)
    card_traded = sum(1 for p in per_card if p["card_traded"])
    day_had_trade = sum(1 for p in per_card if p["n_traded"] > 0)
    wrong_chart = [p for p in per_card if not p["card_traded"] and p["n_traded"] > 0]
    silent_day = [p for p in per_card if p["n_traded"] == 0]

    with_min = [p for p in per_card if p["his_minute"]]
    closer_other = [p for p in with_min
                    if p["card_delta"] is not None and p["closest_any"]
                    and abs(p["closest_any"]["delta"]) < abs(p["card_delta"])]
    closer_traded = [p for p in with_min
                     if p["card_delta"] is not None and p["closest_traded"]
                     and abs(p["closest_traded"]["delta"]) < abs(p["card_delta"])]

    yes_all = sum(1 for p in per_card if p["his_yes"])
    real = [p for p in per_card if p["card_traded"]]

    summary = {
        "n_cards": n,
        "cards_the_engine_traded": card_traded,
        "cards_the_engine_refused": n - card_traded,
        "days_where_engine_traded_something": day_had_trade,
        "wrong_chart_days": len(wrong_chart),
        "wrong_chart_ids": [p["card_id"] for p in wrong_chart],
        "silent_days": len(silent_day),
        "cards_with_a_minute": len(with_min),
        "some_signal_closer_than_the_card": len(closer_other),
        "closer_any_ids": [p["card_id"] for p in closer_other],
        "a_TRADED_signal_closer_than_the_card": len(closer_traded),
        "closer_traded_ids": [p["card_id"] for p in closer_traded],
        "money_the_engine_made_on_wrong_chart_days":
            round(sum(t["pnl"] for p in wrong_chart for t in p["traded_rows"]), 2),
        "signals_per_card_day": dict(sorted(Counter(p["n_signals"] for p in per_card).items())),
        "precision_all_30": "%d/%d = %.0f%%" % (yes_all, n, 100.0 * yes_all / n),
        "precision_on_real_trades": (
            "%d/%d = %.0f%%" % (sum(1 for p in real if p["his_yes"]), len(real),
                                100.0 * sum(1 for p in real if p["his_yes"]) / len(real))
            if real else "n/a"),
    }

    json.dump({"summary": summary, "cards": per_card}, open(OUT, "w", encoding="utf-8"),
              indent=1)
    print(json.dumps(summary, indent=1))
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
