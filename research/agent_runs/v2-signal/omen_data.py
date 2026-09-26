"""Stub for orb1m.py's `from omen_data import load_fut, SPEC` import.

The real omen_data.py (research/agent_runs/v2-s07-data/) that t01's backtest
ran against lived only in that agent's now-deleted worktree -- it is not part
of the committed tree. orb1m.py itself is FROZEN (do not edit it), and it
imports `load_fut`/`SPEC` at module scope even though the streaming signal
engine here only ever calls `signal()`, `pin()`, `strong()` -- never
`load_fut`. This stub satisfies that import so the frozen module can be
imported for its detection logic; `load_fut` deliberately raises if anything
ever calls it, so a silent switch to fabricated backtest data is impossible.

SPEC values match the constants already used throughout OMEN v2 (s06, this
package's discord_format.py): $/point and round-trip commission per micro.
"""

SPEC = {
    "MNQ": {"usd_pt": 2.0, "rt_comm": 1.24},
    "MES": {"usd_pt": 5.0, "rt_comm": 1.24},
}


def load_fut(*args, **kwargs):
    raise NotImplementedError(
        "omen_data.load_fut is a stub (see this file's docstring) -- the "
        "live signal engine never calls it. If something just tried to, "
        "that's a real bug, not a missing data file."
    )
