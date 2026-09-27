"""v3 eye4: paper execution for S-confirmed eye-loop candidates.

The eye loop (o2-eye-segments.md) sends Austin a phone card per candidate and
he taps S / not-S. This module is the execution stage: it takes candidates +
taps, keeps only candidates that got an "S" tap within a confirmation window
(default 120s per the ticket), simulates the trade on 1-min bars with honest
fills, and logs one row per confirmed trade to
`research/paper_journal/acks.jsonl` -- the exact file `daily_report.py` (v3
B3) already reads for its 4:30pm ET report. No change to daily_report.py is
needed: writing this schema IS "append to the existing report".

Card-send / tap-capture (eye1-3) do not exist in this repo yet -- this module
defines the contract they must produce and is testable against it today via
synthetic candidates/taps. See CONTRACT below.

Paper only. Never live orders. Two managements, chosen by `management=`:
  "flat_2r"      -- v3 ship-plan cell: flat exit at 2R, cutoff 10:30 (default,
                    matches the frozen orb1m.py signal engine's own run_trade)
  "ladder_4tier" -- s04's 30/30/30/10 ladder via levels_ladder.build_rungs,
                    stop -> breakeven once PT1 fills, flat (runner marked to
                    close) at cutoff.

CONTRACT
--------
Candidate (produced by the card-send stage, one per signal):
    {
      "id": str,                    # e.g. "S0941-1", must be unique per day
      "symbol": "MNQ" | "NQ",
      "date": "YYYY-MM-DD",
      "side": 1 | -1,                # 1 = long, -1 = short
      "signal_minute": int,          # bar index (0 = 09:30) of the SIGNAL bar;
                                      # entry is signal_minute + 1 (next open)
      "stop": float,                 # structural stop price at signal time
      "session_extreme": float|None, # HOD/LOD as-of entry, for PT1 (ladder only)
      "named_levels": dict,          # name -> price, causal, for PT2/PT3 (ladder only)
      "card_sent_ts": "2026-09-26T09:41:07-04:00",  # ISO 8601, when the phone card went out
      "cutoff_minute": int,          # default 60 (10:30 ET), last-entry/flat bar
    }

Tap (produced by the tap-capture stage, one per candidate Austin acts on):
    {
      "candidate_id": str,
      "grade": "S" | "not_s",
      "tap_ts": "2026-09-26T09:42:40-04:00",
    }

A candidate is CONFIRMED iff grade == "S" and
0 <= (tap_ts - card_sent_ts) <= confirm_window_s (default 120). Everything
else (not_s, late tap, no tap) is logged to `skipped` and never simulated or
traded -- this is the whole point of the eye loop (o2: "no mechanical rule
survives OOS; his eye is the edge" -- only tap-confirmed setups get capital,
even paper capital).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

REPO = Path(__file__).resolve().parents[3]  # .../tradingbot (research/agent_runs/v3-eye4-paper/this_file.py)
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v2-s07-data"))
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v2-t01-orb-1m"))
sys.path.insert(0, str(REPO))

from omen_data import load_fut, SPEC  # noqa: E402
from orb1m import day_arrays, run_trade as _flat_run_trade  # noqa: E402
from levels_ladder import build_rungs, Rung  # noqa: E402

TICK = 0.25
JOURNAL_PATH = REPO / "research" / "paper_journal" / "acks.jsonl"
DEFAULT_CONFIRM_WINDOW_S = 120
DEFAULT_CUTOFF_MINUTE = 60  # 10:30 ET, per OMEN-SHIP-PLAN-v3.md sec 2


# --------------------------------------------------------------------------- #
# confirmation
# --------------------------------------------------------------------------- #

def _parse_ts(ts) -> datetime:
    if isinstance(ts, datetime):
        return ts
    return datetime.fromisoformat(ts)


def confirm(candidate: dict, tap: dict, confirm_window_s: int = DEFAULT_CONFIRM_WINDOW_S):
    """Returns (ok: bool, reason: str, latency_s: float|None)."""
    if tap is None:
        return False, "no_tap", None
    if tap.get("candidate_id") != candidate["id"]:
        return False, "tap_id_mismatch", None
    if tap.get("grade") != "S":
        return False, f"grade_{tap.get('grade')}", None
    sent = _parse_ts(candidate["card_sent_ts"])
    tapped = _parse_ts(tap["tap_ts"])
    latency = (tapped - sent).total_seconds()
    if latency < 0:
        return False, "tap_before_send", latency
    if latency > confirm_window_s:
        return False, "late_tap", latency
    return True, "confirmed", latency


# --------------------------------------------------------------------------- #
# fills / simulation
# --------------------------------------------------------------------------- #

@dataclass
class TradeResult:
    id: str
    symbol: str
    date: str
    side: int
    management: str
    entry: float
    stop: float
    r: float
    usd: float
    legs: List[dict] = field(default_factory=list)
    tap_latency_s: Optional[float] = None


def _entry_price(A, i: int, side: int) -> Optional[float]:
    """Next-bar open + 1 tick against the trader (honest slippage). None if
    the entry bar doesn't exist (e.g. signal on the last bar of the window)."""
    if i >= len(A["open"]) or np.isnan(A["open"][i]):
        return None
    return A["open"][i] + TICK * side


def sim_flat_2r(A, i: int, side: int, entry: float, stop: float, cut: int, usd: float, comm: float):
    dist = (entry - stop) * side
    if dist < 2 * TICK:
        return None  # degenerate stop, no honest trade
    r, u = _flat_run_trade(A, i, side, dist, cut, usd, comm)
    return r, u, [{"name": "FLAT_2R", "weight": 1.0, "r": r}]


def sim_ladder_4tier(A, i: int, side: int, entry: float, stop: float, cut: int, usd: float, comm: float,
                      session_extreme: Optional[float], named_levels: Dict[str, float],
                      weights=(0.30, 0.30, 0.30, 0.10)):
    """s04's 30/30/30/10 ladder. Stop -> breakeven (touch-triggered, a
    documented simplification of the spec's close-trigger) once PT1 fills.
    Pessimistic same-bar rule: if a bar both hits the stop and touches a rung,
    the stop wins and no rung fills that bar (matches s04 sec 3 / PESSIMISTIC_FILL).
    Unfilled weight at the cutoff bar is marked to that bar's open (runner)."""
    risk = abs(entry - stop)
    if risk < 2 * TICK:
        return None
    rungs = build_rungs(entry, stop, side, session_extreme=session_extreme,
                         named_levels=named_levels or {}, weights=weights)
    if not rungs:
        return sim_flat_2r(A, i, side, entry, stop, cut, usd, comm)

    # NOTE: levels_ladder.Rung does not carry its PT1..PT4 label (build_rungs
    # drops it -- see levels_ladder.py tail, `Rung(price, weight, name)` where
    # `name` is the descriptive text like "session high (HOD as-of entry)").
    # By construction the nearest surviving candidate (index 0 after the
    # ascending-R sort) is whichever tier sits closest to entry -- PT1 when
    # the session extreme survives coalescing, otherwise PT2/PT3. s04's
    # `BE_TRIGGER=pt1` (the default) means "BE after the nearest tier fills",
    # so index 0 is the correct trigger regardless of which named tier it is.
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    remaining = [dict(tier=f"T{k + 1}", label=r.name, price=r.price, weight=r.weight, filled=False)
                 for k, r in enumerate(rungs)]
    cur_stop = stop
    be_armed = False
    legs: List[dict] = []
    total_pts = 0.0  # signed points contribution (side already applied via (px-entry)*side)
    stop_hit = False

    for j in range(i, cut):
        if np.isnan(O[j]):
            continue
        stop_hit = (L[j] <= cur_stop) if side > 0 else (H[j] >= cur_stop)
        if stop_hit:
            exit_px = (min(cur_stop, O[j]) - TICK) if side > 0 else (max(cur_stop, O[j]) + TICK)
            rem_w = sum(r["weight"] for r in remaining if not r["filled"])
            if rem_w > 0:
                total_pts += (exit_px - entry) * side * rem_w
                legs.append({"name": "STOP", "price": exit_px, "weight": rem_w})
            break
        for r in remaining:
            if r["filled"]:
                continue
            need = r["price"] + TICK * side  # 1 tick through, per s04 sec 6 "targets ... fill only if 1 tick through"
            touched = (H[j] >= need) if side > 0 else (L[j] <= need)
            if touched:
                r["filled"] = True
                total_pts += (r["price"] - entry) * side * r["weight"]
                legs.append({"name": r["tier"], "label": r["label"], "price": r["price"], "weight": r["weight"]})
                if r["tier"] == "T1" and not be_armed:
                    be_armed = True
                    cur_stop = entry  # BE, per s04 sec 3 default LADDER_TRAIL=be, BE_TRIGGER=pt1 (nearest tier)
        if all(r["filled"] for r in remaining):
            break
    else:
        j = cut - 1

    if not all(r["filled"] for r in remaining) and not stop_hit:
        rem_w = sum(r["weight"] for r in remaining if not r["filled"])
        if rem_w > 0:
            if cut < len(O) and not np.isnan(O[cut]):
                px = O[cut] - TICK * side
            else:
                v = C[:cut][~np.isnan(C[:cut])]
                px = (v[-1] if len(v) else entry) - TICK * side
            total_pts += (px - entry) * side * rem_w
            legs.append({"name": "RUNNER_FLAT", "price": px, "weight": rem_w})

    r_mult = total_pts / risk
    usd_pnl = total_pts * usd - comm
    return r_mult, usd_pnl, legs


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #

_bars_cache: Dict[str, list] = {}


def _bars_for(symbol: str) -> list:
    """[(date, day_array_dict), ...] for a symbol, cached per process."""
    if symbol not in _bars_cache:
        df = load_fut(symbol, "09:30", "11:01")
        _bars_cache[symbol] = [(str(d), day_arrays(g)) for d, g in df.groupby("date")]
    return _bars_cache[symbol]


def _day_array(symbol: str, date: str):
    for d, A in _bars_for(symbol):
        if d == date:
            return A
    return None


def run_confirmed(candidate: dict, tap: Optional[dict], management: str = "flat_2r",
                   confirm_window_s: int = DEFAULT_CONFIRM_WINDOW_S,
                   ladder_weights=(0.30, 0.30, 0.30, 0.10), day_array=None) -> dict:
    """Full pipeline for one candidate: confirm, then simulate if confirmed.
    `day_array` lets callers/tests inject synthetic bars instead of `load_fut`.
    Returns a dict ready to append to the journal (confirmed or not)."""
    ok, reason, latency = confirm(candidate, tap, confirm_window_s)
    row = {
        "id": candidate["id"],
        "symbol": candidate["symbol"],
        "date": candidate["date"],
        "side": candidate["side"],
        "confirmed": ok,
        "reason": reason,
        "tap_latency_s": latency,
        "management": management,
    }
    if not ok:
        return row

    A = day_array if day_array is not None else _day_array(candidate["symbol"], candidate["date"])
    if A is None:
        row.update(confirmed=False, reason="no_bars")
        return row

    i = candidate["signal_minute"] + 1
    side = candidate["side"]
    entry = _entry_price(A, i, side)
    if entry is None:
        row.update(confirmed=False, reason="no_entry_bar")
        return row
    stop = candidate["stop"]
    cut = candidate.get("cutoff_minute", DEFAULT_CUTOFF_MINUTE)
    spec = SPEC[candidate["symbol"]]
    usd, comm = spec["usd_pt"], spec["rt_comm"]

    if management == "flat_2r":
        sim = sim_flat_2r(A, i, side, entry, stop, cut, usd, comm)
    elif management == "ladder_4tier":
        sim = sim_ladder_4tier(A, i, side, entry, stop, cut, usd, comm,
                                candidate.get("session_extreme"), candidate.get("named_levels"),
                                weights=ladder_weights)
    else:
        raise ValueError(f"unknown management {management!r}")

    if sim is None:
        row.update(confirmed=False, reason="degenerate_stop")
        return row

    r, u, legs = sim
    row.update(entry=entry, stop=stop, r=round(float(r), 4), usd=round(float(u), 2), legs=legs)
    return row


def append_journal(rows: Sequence[dict], path: Path = JOURNAL_PATH, now=None) -> int:
    """Append confirmed+simulated rows to acks.jsonl in the schema
    daily_report.py already reads (needs "date"/"ts" and "r"). Skipped/
    unconfirmed rows are NOT written -- only S-confirmed, simulated trades
    count as paper trades. Returns the number of rows written."""
    now = now or datetime.now(timezone.utc)
    to_write = [row for row in rows if row.get("confirmed") and "r" in row]
    if not to_write:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for row in to_write:
            f.write(json.dumps({**row, "ts": now.isoformat()}) + "\n")
    return len(to_write)


def daily_summary(date: str, path: Path = JOURNAL_PATH) -> dict:
    """Stats for one date's confirmed paper trades, for the vault / manual
    checks. daily_report.py folds the same rows into its own 4:30pm report
    directly from acks.jsonl -- this is a read-only convenience, not a
    second writer."""
    if not path.exists():
        return {"date": date, "n": 0, "mean_r": None, "hit_rate": None, "usd": 0.0}
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    rows = [r for r in rows if r.get("date") == date and "r" in r]
    n = len(rows)
    if n == 0:
        return {"date": date, "n": 0, "mean_r": None, "hit_rate": None, "usd": 0.0}
    rs = [r["r"] for r in rows]
    return {
        "date": date,
        "n": n,
        "mean_r": round(sum(rs) / n, 4),
        "hit_rate": round(sum(1 for x in rs if x > 0) / n, 4),
        "usd": round(sum(r.get("usd", 0.0) for r in rows), 2),
    }


if __name__ == "__main__":
    print("eye_paper.py is a library; see tests in test_eye_paper.py")
