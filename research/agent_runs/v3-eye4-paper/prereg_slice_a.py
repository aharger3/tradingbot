"""
Frozen pre-registration config for OMEN forward paper-trade, slice A.

Source of truth (do not restate the reasoning here, only the frozen rules):
    life-plan/07-money/omen-paper-trade-prereg.md, decision A5, section 1 & 2.

Slice A: S+A grades only, one trade at a time, max 5 trades/day, stop the
day at -1R or +1R.

FROZEN at tradingbot commit a9fc9eec (2026-09-27, R06). Per the prereg doc
section 2: "Any rule change = the count restarts at zero under a new
pre-registration. Bug fixes that change trade decisions count as rule
changes." Do not edit the fields on PREREG_SLICE_A in place -- if a value
must change, bump `slice_id` (e.g. "A2") and record why in the prereg doc.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PreregConfig:
    slice_id: str = "A"
    allowed_grades: tuple = ("S", "A")
    max_concurrent_trades: int = 1
    max_trades_per_day: int = 5
    day_stop_r: float = 1.0
    losing_streak_sit_out_days: int = 2
    frozen_commit: str = "a9fc9eec"

    def config_hash(self) -> str:
        """Short, deterministic hash of the frozen rules -- logged on every
        fill so a forward-test row can always be traced back to the exact
        pre-registered slice that produced it."""
        payload = json.dumps(asdict(self), sort_keys=True, default=list).encode()
        return hashlib.sha256(payload).hexdigest()[:12]


PREREG_SLICE_A = PreregConfig()


def allowed(grade_hint: str, config: PreregConfig = PREREG_SLICE_A) -> bool:
    """Grade filter: only S+A candidates are ever sent as cards."""
    return grade_hint in config.allowed_grades


def concurrent_slot_free(pending_count: int, config: PreregConfig = PREREG_SLICE_A) -> bool:
    """One trade at a time: no new card while `pending_count` trades are
    still waiting on a confirmation tap or open in the sim."""
    return pending_count < config.max_concurrent_trades


def day_cap_hit(trades_taken_today: int, config: PreregConfig = PREREG_SLICE_A) -> bool:
    """Max 5 trades/day."""
    return trades_taken_today >= config.max_trades_per_day


def day_stop_hit(daily_r: float, config: PreregConfig = PREREG_SLICE_A) -> bool:
    """+-1R day stop."""
    return abs(daily_r) >= config.day_stop_r


def should_halt_day(trades_taken_today: int, daily_r: float, config: PreregConfig = PREREG_SLICE_A) -> bool:
    """True once either the daily trade cap or the R day-stop has fired --
    no more candidates should be sent as cards for the rest of the session."""
    return day_cap_hit(trades_taken_today, config) or day_stop_hit(daily_r, config)
