"""Print the filled manual-execution ticket checklist for one eye card.

PAPER / MANUAL ONLY: this prints text for Austin to type into the eval
platform (Tradovate assumed for Lucid, unverified). It never places an order.

Card JSON = the eye_card.chart.Candidate fields (candidate_id, symbol,
direction, trigger_time, entry, stop, targets, level, ...). Optional keys:
  date      "YYYY-MM-DD" (else parsed from candidate_id YYYYMMDD, else today)
  qty       contracts from the card size line (else u07 formula, below)
  risk_usd  per-trade risk for the u07 formula (default 200)
  atr       1-min ATR in points, for the 4-ATR chase guard (a3-pro-calls)

Run:  python scripts\\print_ticket.py eye_card\\tests\\fixtures\\replay_card.json
"""
import datetime as dt
import json
import math
import re
import sys

TICK = 0.25
MICRO = {"NQ": "MNQ", "MNQ": "MNQ", "ES": "MES", "MES": "MES"}
USD_PER_PT = {"MNQ": 2.0, "MES": 5.0}      # u07 contract specs
RT_COST = {"MNQ": 2.25, "MES": 3.75}       # u07 modeled cost / contract / round trip
QTY_CAP = 12                               # t08: Lucid 50K tier-1 cap, 12 MNQ
MONTH_CODE = {3: "H", 6: "M", 9: "U", 12: "Z"}


def _third_friday(year, month):
    d = dt.date(year, month, 15)
    return d + dt.timedelta(days=(4 - d.weekday()) % 7)


def front_month(root, day):
    """Quarterly front month; rolls 8 days before 3rd-Friday expiry (CME equity index)."""
    for year in (day.year, day.year + 1):
        for month in (3, 6, 9, 12):
            if day < _third_friday(year, month) - dt.timedelta(days=8):
                return f"{root}{MONTH_CODE[month]}{year % 10}"
    raise ValueError(day)


def card_date(card):
    if card.get("date"):
        return dt.date.fromisoformat(card["date"])
    m = re.search(r"(20\d{6})", card.get("candidate_id", ""))
    if m:
        return dt.datetime.strptime(m.group(1), "%Y%m%d").date()
    return dt.date.today()


def _tick(x):
    return round(round(x / TICK) * TICK, 2)


def build_ticket(card):
    root = MICRO[card["symbol"].upper()]
    short = card["direction"].upper() == "SHORT"
    sign = -1 if short else 1
    entry, stop = float(card["entry"]), float(card["stop"])
    risk_pts = abs(entry - stop)
    if risk_pts <= 0 or (stop > entry) != short:
        raise ValueError("stop must be on the losing side of entry")
    risk_usd = float(card.get("risk_usd", 200))
    qty = int(card.get("qty") or min(QTY_CAP, math.floor(risk_usd / (risk_pts * USD_PER_PT[root] + RT_COST[root]))))
    if qty < 1:
        raise ValueError("stop too wide for risk_usd: qty would be 0 -> skip the trade")
    q2 = qty if qty == 1 else qty // 2
    q3 = qty - q2
    t2, t3 = _tick(entry + sign * 2 * risk_pts), _tick(entry + sign * 3 * risk_pts)
    hh, mm, _ = (int(x) for x in card["trigger_time"].split(":"))
    next_bar = (dt.datetime(2000, 1, 1, hh, mm) + dt.timedelta(minutes=1)).strftime("%H:%M")
    side, exit_side = ("SELL", "BUY") if short else ("BUY", "SELL")
    atr = card.get("atr") or card.get("extra", {}).get("atr")
    level = float(card["level"])
    chase = (f"{_tick(level + sign * 4 * float(atr))} (level {level} {'-' if short else '+'} 4 ATR)"
             if atr else f"4 ATR past level {level} (ATR not on card: read it off the chart)")
    target_line = f"LIMIT {exit_side} {q2} @ {t2} (2R)" + (f" + {q3} @ {t3} (3R)" if q3 else "")
    return [
        ("card", f"{card['candidate_id']} {card.get('setup', '')} {card['direction'].upper()}".strip()),
        ("1 contract", f"{front_month(root, card_date(card))} (front month for {card_date(card)}; never the mini {root[1:]})"),
        ("2 qty", f"{qty} {root} (= card size line; {qty} micros, NOT {qty} minis)"),
        ("3 entry", f"MARKET {side} at {next_bar} bar open, or STOP {side} @ {_tick(entry + sign * TICK)} (1 tick past confirm close {entry})"),
        ("4 stop", f"STOP-MARKET {exit_side} @ {stop} ({risk_pts:g} pt; never stop-limit)"),
        ("5 targets", target_line),
        ("6 OCO", "ON (stop + targets one bracket; check both legs show working)"),
        ("7 TIF", "DAY"),
        ("8 flatten", "Flatten-all at 10:30 ET (hard 11:00)"),
        ("9 chase guard", f"skip if price already beyond {chase}"),
        ("10 one trade", "no second entry today after this one closes (re-entries lose)"),
        ("11 ack", "tap TOOK on the phone card"),
    ]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python scripts/print_ticket.py <card.json>")
        return 2
    with open(argv[0], encoding="utf-8") as fh:
        card = json.load(fh)
    print("OMEN TICKET  (manual, PAPER/eval; Tradovate [unverified])")
    for key, val in build_ticket(card):
        print(f"[ ] {key:<14} {val}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
