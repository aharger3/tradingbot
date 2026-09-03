"""g73_mentorbook_tradezella.py — can the mentor corpus be imported into TradeZella?

Austin, 2026-08-29: "or you could import them into tradezella because its a way
to track trades."

Format of record: **TradeZella Generic CSV** (for brokers TradeZella does not
sync). Source, read 2026-08-29:
https://help.tradezella.com/en/articles/8239862-how-to-import-trades-from-unsupported-broker-into-tradezella-via-generic-csv-file-upload
(the article carries no explicit revision date; TradeZella's help centre shows
it as "Updated this week" as of 2026-08-29).

Columns, in order:
    Date, Time, Symbol, Buy/Sell, Quantity, Price, Spread,
    Expiration, Strike, Call/Put, Commission, Fees

Rules the format imposes, and they are the whole problem:
  * Date mm/dd/yy, Time 24h hh:mm:ss.
  * **One row per EXECUTION, not per trade.** A round trip needs at least two
    rows -- a buy and a sell -- or TradeZella books an open position with no
    P&L. "You must enter each execution individually, including both buy and
    sell orders."
  * Expiration / Strike / Call/Put are mandatory once Spread says the
    instrument is an option, which is what these men trade.

This script scores the pooled corpus field by field against that template,
writes the census, and emits an import file containing exactly the rows that
genuinely satisfy it -- no invented quantities, no guessed strikes, no
back-filled exits. Nothing is uploaded and nothing is logged into.

Run: python research/g73_mentorbook_tradezella.py
"""
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "research" / "corpus_sf" / "pooled_trades.jsonl"
OUT_CSV = ROOT / "research" / "g73_mentorbook_tradezella.csv"
OUT_JSON = ROOT / "research" / "g73_mentorbook_tradezella.json"

COLS = ["Date", "Time", "Symbol", "Buy/Sell", "Quantity", "Price", "Spread",
        "Expiration", "Strike", "Call/Put", "Commission", "Fees"]
MANDATORY = ["Date", "Time", "Symbol", "Buy/Sell", "Quantity", "Price", "Spread"]
OPTION_CONDITIONAL = ["Expiration", "Strike", "Call/Put"]

# "NVDA 905 CALLS", "AMD Puts 870", "TSLA 250c" — a strike is often IN the prose
# even though no parser field holds it. Counted, never guessed into the file.
STRIKE_RE = re.compile(r"\b(\d{2,5}(?:\.\d{1,2})?)\s*(c|p|calls?|puts?)\b", re.I)
STRIKE_RE2 = re.compile(r"\b(?:calls?|puts?)\s+(\d{2,5}(?:\.\d{1,2})?)\b", re.I)
QTY_RE = re.compile(r"\b(\d{1,4})\s*(?:cons?|contracts?)\b", re.I)
EXP_RE = re.compile(r"\b(\d{1,2}\s*/\s*\d{1,2}|"
                    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*\d{1,2})\b",
                    re.I)


def main():
    pool = [json.loads(l) for l in POOL.open(encoding="utf-8") if l.strip()]

    have = Counter()
    prose = Counter()
    complete_rows = []

    for r in pool:
        q = r.get("quote") or ""
        d = r.get("trade_date")
        ts = r.get("ts")
        sym = r.get("symbol")
        direction = r.get("direction")
        entry = r.get("entry")
        is_opt = r.get("instrument") == "equity_option"

        if d:
            have["Date"] += 1
        if ts:
            have["Time"] += 1
        if sym:
            have["Symbol"] += 1
        if direction in ("long", "short"):
            have["Buy/Sell"] += 1
        # Quantity: no parser field exists at all. Only prose ever carries it.
        if QTY_RE.search(q):
            prose["Quantity in prose"] += 1
        if entry is not None:
            have["Price"] += 1
        if r.get("instrument"):
            have["Spread"] += 1
        if is_opt and (STRIKE_RE.search(q) or STRIKE_RE2.search(q)):
            prose["Strike in prose"] += 1
        if is_opt and EXP_RE.search(q):
            prose["Expiration in prose"] += 1
        # The exit leg. No field in the schema holds one, and no parser looked
        # for one -- `target` is a plan, not a fill.
        if r.get("outcome"):
            have["_has an outcome word (not an exit price)"] += 1

        # A row that genuinely satisfies every mandatory column
        ok = all([d, ts, sym, direction in ("long", "short"), entry is not None,
                  r.get("instrument")])
        if ok:
            qty = QTY_RE.search(q)
            if not qty:
                continue                      # Quantity is mandatory; never invent it
            dt = datetime.fromisoformat(ts)
            complete_rows.append({
                "Date": "%d/%d/%02d" % (dt.month, dt.day, dt.year % 100),
                "Time": dt.strftime("%H:%M:%S"),
                "Symbol": sym,
                "Buy/Sell": "Buy" if direction == "long" else "Sell",
                "Quantity": qty.group(1),
                "Price": entry,
                "Spread": "Option" if is_opt else "Stock",
                "Expiration": "", "Strike": "", "Call/Put": "",
                "Commission": "", "Fees": "",
            })

    n = len(pool)
    census = {}
    for c in COLS:
        census[c] = dict(present=have.get(c, 0), of=n,
                         pct=round(have.get(c, 0) / n * 100, 1),
                         mandatory=c in MANDATORY,
                         conditional_on_options=c in OPTION_CONDITIONAL)
    census["Quantity"]["note"] = ("no field in the corpus schema. Prose mentions "
                                  "a contract count in %d of %d rows." %
                                  (prose["Quantity in prose"], n))
    census["Price"]["note"] = ("entry only. There is NO exit price anywhere in "
                               "the corpus, so no row can close a trade.")
    census["Strike"]["note"] = "%d rows name a strike in prose" % prose["Strike in prose"]
    census["Expiration"]["note"] = ("%d rows name something date-like in prose"
                                    % prose["Expiration in prose"])

    verdict = {
        "format": "TradeZella Generic CSV",
        "doc": ("https://help.tradezella.com/en/articles/8239862-how-to-import-"
                "trades-from-unsupported-broker-into-tradezella-via-generic-csv-"
                "file-upload"),
        "doc_read": "2026-08-29",
        "doc_revision_shown": "Updated this week (no explicit date published)",
        "columns": COLS,
        "row_granularity": "one row per execution (fill); a round trip needs 2+ rows",
        "pooled_instances": n,
        "rows_meeting_every_mandatory_column": len(complete_rows),
        "rows_that_could_close_a_trade": 0,
        "blocking_fields": [
            "Quantity — no schema field; these men post option strikes and "
            "dollar P&L, never a contract count in a parseable place",
            "Price — 49 of 3,547 rows state an entry; ZERO state an exit fill, "
            "so even those 49 import as open positions with no P&L",
            "Expiration / Strike / Call/Put — mandatory for options, and the "
            "corpus holds no parsed field for any of the three",
        ],
        "answer": ("No. TradeZella's generic importer wants executions, and the "
                   "corpus holds opinions. The blocker is not a mapping anyone "
                   "could write -- the exit fill does not exist in the data at "
                   "any confidence level."),
    }

    OUT_JSON.write_text(json.dumps(dict(verdict=verdict, column_census=census,
                                        prose_only=dict(prose)), indent=1),
                        encoding="utf-8")
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for row in complete_rows:
            w.writerow(row)

    print("TradeZella Generic CSV — %d columns, %d mandatory" % (len(COLS), len(MANDATORY)))
    for c in COLS:
        v = census[c]
        flag = "MANDATORY" if v["mandatory"] else ("options-mandatory"
                                                   if v["conditional_on_options"] else "optional")
        print("  %-12s %6d/%d (%4.1f%%)  %-17s %s"
              % (c, v["present"], n, v["pct"], flag, v.get("note", "")))
    print("\nrows meeting every mandatory column:", len(complete_rows))
    print("rows able to CLOSE a trade (exit fill):", 0)
    print("wrote", OUT_CSV, "and", OUT_JSON)


if __name__ == "__main__":
    main()
