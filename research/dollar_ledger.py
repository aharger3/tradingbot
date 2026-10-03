"""Dollar ledger for the eye-loop paper journal (read-only, paper only).

eye4 (research/agent_runs/v3-eye4-paper/eye_paper.py) journals one row per
S-confirmed paper trade to research/paper_journal/acks.jsonl with `r` and a
1-contract `usd`. That says nothing about account dollars. This maps each
trade to an integer MNQ size with the u07 L1 rule

    n = min(max_n, floor(budget / (stop_pt * usd_pt + size_cost)))

(defaults: $200 budget, $2/pt, $2.25 u07 modeled cost per contract), skips
and logs any trade where 1 lot already risks more than the budget (n == 0),
books n x (pts x $2 - rt_comm) with rt_comm from omen_data.SPEC["MNQ"], and
reports cumulative $ and max drawdown $. Never places or routes an order.

    python research/dollar_ledger.py [journal.jsonl]
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import median

REPO = Path(__file__).resolve().parents[1]
JOURNAL_PATH = REPO / "research" / "paper_journal" / "acks.jsonl"

try:  # same source eye_paper.py prices its 1-lot usd with (untracked on some checkouts)
    sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v2-s07-data"))
    from omen_data import SPEC  # noqa: E402
except ImportError:  # copy of omen_data.SPEC for the NQ family
    SPEC = {"MNQ": dict(usd_pt=2.0, rt_comm=1.24), "NQ": dict(usd_pt=20.0, rt_comm=4.50)}

BUDGET = 200.0                         # $ risk per trade (u07: 10% of a $2K trailing DD)
USD_PT = SPEC["MNQ"]["usd_pt"]         # $2/pt
RT_COMM = SPEC["MNQ"]["rt_comm"]       # $ round trip per MNQ, charged on P&L
SIZE_COST = 2.25                       # u07 modeled cost per MNQ (comm + 1 tick slip each side), sizing only
MAX_N = 50                             # u07 / Topstep 50K micro cap [unverified]


def contracts(stop_pt: float, budget: float = BUDGET, size_cost: float = SIZE_COST,
              usd_pt: float = USD_PT, max_n: int = MAX_N) -> int:
    """u07 L1 integer MNQ size; 0 means 1 lot risks more than the budget."""
    return min(max_n, int(math.floor(budget / (stop_pt * usd_pt + size_cost))))


def ledger(trades, sessions: int | None = None, budget: float = BUDGET, size_cost: float = SIZE_COST,
           rt_comm: float = RT_COMM, usd_pt: float = USD_PT, max_n: int = MAX_N) -> dict:
    """trades: dicts with date, stop_pt, pts (gross points per contract after fills), optional id.
    Order is kept (journal order). sessions: day count for $/day; default = distinct trade dates."""
    rows, skipped = [], []
    cum = peak = 0.0
    max_dd = 0.0
    for t in trades:
        n = contracts(t["stop_pt"], budget, size_cost, usd_pt, max_n)
        if n == 0:
            one = t["stop_pt"] * usd_pt + size_cost
            skipped.append(dict(id=t.get("id"), date=t["date"], reason=f"1 lot risks ${one:.2f} > ${budget:.0f}"))
            continue
        usd = n * (t["pts"] * usd_pt - rt_comm)
        cum += usd
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)
        rows.append(dict(id=t.get("id"), date=t["date"], stop_pt=t["stop_pt"], n=n, usd=round(usd, 2), cum=round(cum, 2)))
    days = sessions or len({t["date"] for t in trades}) or 1
    return dict(rows=rows, skipped=skipped, trades=len(rows), usd_total=round(cum, 2),
                usd_day=round(cum / days, 1), usd_trade=round(cum / len(rows), 1) if rows else 0.0,
                max_dd_usd=round(max_dd, 2), med_contracts=float(median(r["n"] for r in rows)) if rows else 0.0)


def journal_trades(path: Path = JOURNAL_PATH):
    """eye4 journal rows -> ledger trades. Returns (trades, skipped). Only confirmed rows with
    entry/stop/usd on an NQ-family symbol; the 1-lot usd is converted back to gross points."""
    trades, skipped = [], []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not row.get("confirmed", True) or "r" not in row:
            continue
        sym = row.get("symbol")
        if sym not in ("MNQ", "NQ") or not {"entry", "stop", "usd"} <= row.keys():
            skipped.append(dict(id=row.get("id"), date=row.get("date"), reason=f"unpriceable row (symbol {sym})"))
            continue
        spec = SPEC[sym]
        pts = (row["usd"] + spec["rt_comm"]) / spec["usd_pt"]
        trades.append(dict(id=row.get("id"), date=row["date"], stop_pt=abs(row["entry"] - row["stop"]), pts=pts))
    return trades, skipped


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0]) if argv else JOURNAL_PATH
    if not path.exists():
        print(f"no journal at {path}")
        return 1
    trades, bad = journal_trades(path)
    L = ledger(trades)
    print(f"dollar ledger  {path}  budget ${BUDGET:.0f}  MNQ ${USD_PT:g}/pt  rt_comm ${RT_COMM}  size_cost ${SIZE_COST}")
    for r in L["rows"]:
        print(f"  {r['date']}  {r['id']}  stop {r['stop_pt']:.2f}pt  n={r['n']}  ${r['usd']:+.2f}  cum ${r['cum']:+.2f}")
    for s in bad + L["skipped"]:
        print(f"  SKIP {s['date']}  {s['id']}  {s['reason']}")
    print(f"trades {L['trades']}  skipped {len(bad) + len(L['skipped'])}  total ${L['usd_total']:+.2f}  "
          f"$/day {L['usd_day']:+.1f}  max DD ${L['max_dd_usd']:.2f}  median n {L['med_contracts']:g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
