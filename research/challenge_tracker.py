"""challenge_tracker.py -- prop-firm challenge tracker (code, not the P3 ledger).

One row per account per session in `journal/challenge.jsonl` (gitignored runtime
state). Each row carries the account's cumulative state after that session, so
the last row per account IS its current state.

Rules (vault 07-money/omen/u06 + g/sizing-mc, aggregator-sourced, not live-checked):
  LucidFlex 50K: $146 one-time, $3K target, $2K EOD trailing drawdown that
  LOCKS at start + $100, no daily loss limit.
    floor = min(EOD high-water - 2000, start + 100)       (never decreases)
    a session FAILS if its balance (or intraday min equity, when given) <= the
    floor set at the prior EOD; PASSES when balance >= start + 3000.
  Payout clock: profitable days >= $150 (u06 funded rule, 5 needed).
  Pace yardstick: g/sizing-mc median 43 sessions (LucidFlex, 12/10/6, edge C).
  Kill budget (topics/prop-firms Q2): 3 failed evals = $438 (3 x $146) -> stop.

Sizing for --seed-paper: g/sizing-mc ladder 12/10/6 MNQ by eval profit
(<$1K / $1K-2K / >=$2K), applied to the paper journal's per-1-MNQ `usd`.

Paper only. Never places an order.

Usage:
  python research/challenge_tracker.py --status
  python research/challenge_tracker.py --seed-paper [--paper PATH ...]
  python research/challenge_tracker.py --record ACCOUNT DATE PNL [--firm lucid_flex_50k] [--min-equity X]
"""
from __future__ import annotations

import argparse
import json
from datetime import date as _date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
JOURNAL = REPO / "journal" / "challenge.jsonl"
PAPER_JOURNALS = (REPO / "research" / "paper_journal" / "acks_replay.jsonl",
                  REPO / "research" / "paper_journal" / "acks.jsonl")

FIRMS = {
    "lucid_flex_50k": {"firm": "Lucid", "plan": "LucidFlex 50K", "start": 50000.0,
                       "trail": 2000.0, "lock_over_start": 100.0, "target": 3000.0, "fee": 146.0},
}
PROFIT_DAY_USD = 150.0
MEDIAN_SESSIONS = 43
KILL_FAILS = 3
KILL_BUDGET = 438.0
PAPER_ACCOUNT = "PAPER-LUCID-1"


def c(x: float) -> float:
    """Round to the cent."""
    return round(float(x) + 0.0, 2)


def lucid_floor(high_water: float, rules: dict) -> float:
    return c(min(high_water - rules["trail"], rules["start"] + rules["lock_over_start"]))


def contracts_for(profit: float) -> int:
    """g/sizing-mc ladder 12/10/6 MNQ by eval profit."""
    return 12 if profit < 1000 else 10 if profit < 2000 else 6


def step(prev: dict | None, account: str, day: str, pnl: float, firm_key: str = "lucid_flex_50k",
         tag: str = "REAL", min_equity: float | None = None) -> dict:
    """Pure: prior row (or None for a new account) + one session -> next row."""
    rules = FIRMS[firm_key]
    if prev is None:
        prev = {"balance": rules["start"], "high_water": rules["start"],
                "floor": lucid_floor(rules["start"], rules), "session_n": 0,
                "profit_days_150": 0, "start_date": day, "status": "active"}
    if prev["status"] != "active":
        raise ValueError(f"{account} is {prev['status']}; start a new account id")
    balance = c(prev["balance"] + pnl)
    prior_floor = prev["floor"]
    low = balance if min_equity is None else min(balance, c(min_equity))
    high_water = c(max(prev["high_water"], balance))
    floor = lucid_floor(high_water, rules)
    target_bal = rules["start"] + rules["target"]
    status = "failed" if low <= prior_floor else "passed" if balance >= target_bal else "active"
    return {
        "account": account, "tag": tag, "firm": rules["firm"], "plan": rules["plan"],
        "firm_key": firm_key, "start_date": prev["start_date"], "date": day,
        "session_n": prev["session_n"] + 1, "pnl": c(pnl), "balance": balance,
        "high_water": high_water, "floor": floor,
        "locked": floor >= c(rules["start"] + rules["lock_over_start"]),
        "profit_days_150": prev["profit_days_150"] + (1 if pnl >= PROFIT_DAY_USD else 0),
        "to_target": c(max(0.0, target_bal - balance)),
        "sessions_median": MEDIAN_SESSIONS, "status": status, "fee": rules["fee"],
    }


# --------------------------------------------------------------------------- #
# journal I/O
# --------------------------------------------------------------------------- #

def load_rows(path: Path = JOURNAL) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def latest_by_account(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in rows:
        out[r["account"]] = r
    return out


def budget(latest: dict[str, dict], tag: str) -> dict:
    accts = [r for r in latest.values() if r["tag"] == tag]
    fails = sum(1 for r in accts if r["status"] == "failed")
    spent = c(sum(r["fee"] for r in accts))
    return {"tag": tag, "failed_evals": fails, "spent": spent,
            "kill": fails >= KILL_FAILS or spent >= KILL_BUDGET}


def _stamp(row: dict, rows: list[dict]) -> dict:
    """Attach firm-level failed-eval count + $ spent (same tag) to a new row."""
    latest = latest_by_account(rows + [row])
    b = budget(latest, row["tag"])
    return {**row, "failed_evals": b["failed_evals"], "spent": b["spent"],
            "kill_fails": KILL_FAILS, "kill_budget": KILL_BUDGET}


def record(account: str, day: str, pnl: float, firm_key: str = "lucid_flex_50k", tag: str = "REAL",
           min_equity: float | None = None, path: Path = JOURNAL) -> dict:
    rows = load_rows(path)
    prev = latest_by_account(rows).get(account)
    row = _stamp(step(prev, account, day, pnl, firm_key, tag, min_equity), rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def _mon_thu(d0: str, d1: str) -> list[str]:
    a, b = _date.fromisoformat(d0), _date.fromisoformat(d1)
    out = []
    while a <= b:
        if a.weekday() <= 3:
            out.append(a.isoformat())
        a += timedelta(days=1)
    return out


def seed_paper(paper_paths=PAPER_JOURNALS, path: Path = JOURNAL, account: str = PAPER_ACCOUNT) -> list[dict]:
    """Rebuild the PAPER Lucid account from the paper journal(s): per-date sum
    of per-1-MNQ `usd` x ladder contracts, Mon-Thu gaps filled with $0
    sessions. Replaces prior PAPER rows; REAL rows are left untouched."""
    by_date: dict[str, float] = {}
    for p in paper_paths:
        for r in load_rows(Path(p)):
            if r.get("confirmed") and "usd" in r and r.get("date"):
                by_date[r["date"]] = by_date.get(r["date"], 0.0) + float(r["usd"])
    keep = [r for r in load_rows(path) if r["tag"] != "PAPER"]
    new: list[dict] = []
    if by_date:
        days = _mon_thu(min(by_date), max(by_date))
        days = sorted(set(days) | set(by_date))
        prev = None
        rules = FIRMS["lucid_flex_50k"]
        for d in days:
            if prev is not None and prev["status"] != "active":
                break
            profit = (prev["balance"] if prev else rules["start"]) - rules["start"]
            pnl = by_date.get(d, 0.0) * contracts_for(profit)
            prev = _stamp(step(prev, account, d, pnl, tag="PAPER"), keep + new)
            new.append(prev)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in keep + new))
    return new


# --------------------------------------------------------------------------- #
# output
# --------------------------------------------------------------------------- #

COLS = ("account", "tag", "plan", "start", "sess", "balance", "HWM", "floor", "lock",
        "d>=150", "to $3K", "status")


def status_table(path: Path = JOURNAL) -> str:
    latest = latest_by_account(load_rows(path))
    if not latest:
        return f"no challenge rows in {path} (run --seed-paper or --record)"
    lines = [COLS]
    for r in latest.values():
        lines.append((r["account"], r["tag"], r["plan"], r["start_date"],
                      f"{r['session_n']}/{r['sessions_median']}", f"{r['balance']:,.2f}",
                      f"{r['high_water']:,.2f}", f"{r['floor']:,.2f}", "Y" if r["locked"] else "-",
                      str(r["profit_days_150"]), f"{r['to_target']:,.2f}", r["status"]))
    w = [max(len(str(row[i])) for row in lines) for i in range(len(COLS))]
    out = ["  ".join(str(v).ljust(w[i]) for i, v in enumerate(row)) for row in lines]
    for tag in sorted({r["tag"] for r in latest.values()}):
        b = budget(latest, tag)
        out.append(f"{tag}: failed evals {b['failed_evals']}/{KILL_FAILS}  spent ${b['spent']:,.2f}"
                   f"/${KILL_BUDGET:,.0f}" + ("  ** KILL BUDGET HIT **" if b["kill"] else ""))
    return "\n".join(out)


def status_line(path: Path = JOURNAL) -> str:
    """One line for the 16:30 ntfy report. Never raises."""
    try:
        latest = latest_by_account(load_rows(path))
        if not latest:
            return "Challenge: no rows"
        parts = [f"{r['account']} bal {r['balance']:,.2f} floor {r['floor']:,.2f}"
                 f"{' LOCK' if r['locked'] else ''} to-target {r['to_target']:,.2f} "
                 f"sess {r['session_n']}/{r['sessions_median']} {r['status']}" for r in latest.values()]
        budgets = [budget(latest, t) for t in sorted({r["tag"] for r in latest.values()})]
        parts += [f"{b['tag']} fails {b['failed_evals']}/{KILL_FAILS} ${b['spent']:,.0f}/${KILL_BUDGET:,.0f}"
                  + (" KILL" if b["kill"] else "") for b in budgets]
        return "Challenge: " + " | ".join(parts)
    except Exception as e:  # the report must still go out
        return f"Challenge: n/a ({type(e).__name__})"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--seed-paper", action="store_true")
    ap.add_argument("--record", nargs=3, metavar=("ACCOUNT", "DATE", "PNL"))
    ap.add_argument("--firm", default="lucid_flex_50k", choices=sorted(FIRMS))
    ap.add_argument("--min-equity", type=float, default=None)
    ap.add_argument("--journal", default=str(JOURNAL))
    ap.add_argument("--paper", nargs="+", default=[str(x) for x in PAPER_JOURNALS],
                    help="paper journal(s) for --seed-paper")
    a = ap.parse_args(argv)
    path = Path(a.journal)
    if a.seed_paper:
        rows = seed_paper(a.paper, path=path)
        print(f"seeded {len(rows)} PAPER sessions -> {path}")
    if a.record:
        acct, day, pnl = a.record
        r = record(acct, day, float(pnl), a.firm, "REAL", a.min_equity, path)
        print(f"recorded {acct} {day} pnl {r['pnl']:,.2f} -> {r['status']}")
    if a.status or not (a.seed_paper or a.record):
        print(status_table(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
