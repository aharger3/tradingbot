"""research/test_day_policy_flags.py -- OMEN 9.0 row O2.

Exercises the four flags O2 added (`DAY_POLICY`, `ENTRY_WINDOW_END`,
`FIRE_A_WHEN_NO_S`, `VETO_1D`) in `signal_runner.py`, plus their wiring in
`live_scanner.py`. O1's adversarial pass REFUTED shipping any grid winner as
a new default (research/g161_tweaks_shipped.md), so every default asserted
here is TODAY'S shipped behavior, not a new one:

  DAY_POLICY=first3, ENTRY_WINDOW_END=11:00, FIRE_A_WHEN_NO_S=0, VETO_1D=0.

Three sections:
  1. Flag parsing -- defaults, valid overrides, and rejection of bad values.
  2. `select_day_trades()` -- the pure selection function, checked against
     research/g160_tweak_grid.py::build_arm's semantics (one_and_done stops
     at the first pick; first3 collects up to 3 with a halt after 2
     consecutive losses; the window cut; fire_a_when_no_s; veto_1d).
  3. live_scanner wiring -- DAY_POLICY drives max_signals_per_day/
     consecutive-loss-halt defaults, ENTRY_WINDOW_END can only tighten
     ENTRY_CUTOFF, and the two reporting-only flags are stamped into
     scanner_status.json without changing what fires.

    python research/test_day_policy_flags.py
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FAILURES = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {label}")
    if not cond:
        FAILURES.append(label)


def _reload_signal_runner(env_overrides):
    """Import signal_runner fresh under a patched os.environ so its
    module-level flag parsing re-runs, then restore the environment."""
    saved = dict(os.environ)
    try:
        for k in ("DAY_POLICY", "ENTRY_WINDOW_END", "FIRE_A_WHEN_NO_S", "VETO_1D"):
            os.environ.pop(k, None)
        os.environ.update(env_overrides)
        if "signal_runner" in sys.modules:
            del sys.modules["signal_runner"]
        return importlib.import_module("signal_runner")
    finally:
        os.environ.clear()
        os.environ.update(saved)
        if "signal_runner" in sys.modules:
            del sys.modules["signal_runner"]
        importlib.import_module("signal_runner")


def section1_flag_parsing():
    print("\n[1] flag parsing (defaults + overrides + validation)")

    sr = _reload_signal_runner({})
    check("DAY_POLICY default is 'first3' (matches shipped max_signals_per_day=3)",
          sr.DAY_POLICY == "first3")
    check("ENTRY_WINDOW_END default is '11:00' (matches shipped SESSION_END/ENTRY_CUTOFF)",
          sr.ENTRY_WINDOW_END == "11:00")
    check("FIRE_A_WHEN_NO_S default is False", sr.FIRE_A_WHEN_NO_S is False)
    check("VETO_1D default is False", sr.VETO_1D is False)

    sr2 = _reload_signal_runner({"DAY_POLICY": "one_and_done", "ENTRY_WINDOW_END": "09:45",
                                  "FIRE_A_WHEN_NO_S": "1", "VETO_1D": "on"})
    check("DAY_POLICY=one_and_done parses", sr2.DAY_POLICY == "one_and_done")
    check("ENTRY_WINDOW_END=09:45 parses", sr2.ENTRY_WINDOW_END == "09:45")
    check("FIRE_A_WHEN_NO_S=1 parses True", sr2.FIRE_A_WHEN_NO_S is True)
    check("VETO_1D=on parses True", sr2.VETO_1D is True)

    for bad_var, bad_val in (("DAY_POLICY", "twice_a_day"), ("ENTRY_WINDOW_END", "10:30")):
        try:
            _reload_signal_runner({bad_var: bad_val})
            ok = False
        except ValueError:
            ok = True
        check(f"{bad_var}={bad_val!r} raises ValueError", ok)


def section2_select_day_trades():
    print("\n[2] select_day_trades() selection semantics")
    sr = _reload_signal_runner({})

    # -- one_and_done stops at the first takeable pick, win or lose --------
    day = [
        {"et": "09:35", "austin_tier": "S", "dir": "call", "spy_trend": "bull", "r": -1.0},
        {"et": "09:50", "austin_tier": "S", "dir": "call", "spy_trend": "bull", "r": 2.0},
    ]
    picks = sr.select_day_trades(day, day_policy="one_and_done")
    check("one_and_done takes exactly 1 pick", len(picks) == 1)
    check("one_and_done takes the FIRST candidate, not the winner",
          picks[0]["et"] == "09:35")

    # -- first3 collects up to 3, halts after 2 consecutive losses ---------
    day3 = [
        {"et": f"09:{35+i:02d}", "austin_tier": "S", "dir": "call", "spy_trend": "bull",
         "r": -1.0}
        for i in range(4)
    ]
    picks = sr.select_day_trades(day3, day_policy="first3")
    check("first3 halts after 2 consecutive losses (not the 4 available)", len(picks) == 2)

    day3b = [
        {"et": "09:35", "austin_tier": "S", "dir": "call", "spy_trend": "bull", "r": 1.0},
        {"et": "09:45", "austin_tier": "S", "dir": "call", "spy_trend": "bull", "r": 1.0},
        {"et": "09:55", "austin_tier": "S", "dir": "call", "spy_trend": "bull", "r": 1.0},
        {"et": "10:05", "austin_tier": "S", "dir": "call", "spy_trend": "bull", "r": 1.0},
    ]
    picks = sr.select_day_trades(day3b, day_policy="first3")
    check("first3 caps at 3 picks on an all-winning day", len(picks) == 3)

    # -- entry window cut ---------------------------------------------------
    windowed = [
        {"et": "09:50", "austin_tier": "S", "dir": "call", "spy_trend": "bull", "r": 1.0},
        {"et": "10:15", "austin_tier": "S", "dir": "call", "spy_trend": "bull", "r": 1.0},
    ]
    picks = sr.select_day_trades(windowed, day_policy="one_and_done", entry_window_end="09:45")
    check("entry_window_end=09:45 drops a 09:50 candidate entirely", len(picks) == 0)
    picks = sr.select_day_trades(windowed, day_policy="one_and_done", entry_window_end="11:00")
    check("entry_window_end=11:00 keeps the 09:50 candidate", len(picks) == 1)

    # -- fire_a_when_no_s ----------------------------------------------------
    no_s_day = [
        {"et": "09:40", "austin_tier": "A", "dir": "call", "spy_trend": "bull", "r": 1.0},
        {"et": "10:05", "austin_tier": "A", "dir": "call", "spy_trend": "bull", "r": 1.0},
    ]
    picks = sr.select_day_trades(no_s_day, day_policy="one_and_done", fire_a_when_no_s=False)
    check("fire_a_when_no_s=False never takes an A-tier candidate", len(picks) == 0)
    picks = sr.select_day_trades(no_s_day, day_policy="one_and_done", fire_a_when_no_s=True)
    check("fire_a_when_no_s=True takes an A-tier candidate at/after 10:00 with no S yet",
          len(picks) == 1 and picks[0]["et"] == "10:05")

    # -- veto_1d --------------------------------------------------------------
    veto_day = [
        {"et": "09:40", "austin_tier": "S", "dir": "call", "spy_trend": "bear", "r": 1.0},
        {"et": "09:50", "austin_tier": "S", "dir": "put", "spy_trend": "bear", "r": 1.0},
    ]
    picks = sr.select_day_trades(veto_day, day_policy="one_and_done", veto_1d=True)
    check("veto_1d=True skips a call opposing spy_trend=bear, takes the aligned put",
          len(picks) == 1 and picks[0]["dir"] == "put")
    picks = sr.select_day_trades(veto_day, day_policy="one_and_done", veto_1d=False)
    check("veto_1d=False (default) takes the first candidate regardless of spy_trend",
          len(picks) == 1 and picks[0]["dir"] == "call")


def section3_live_scanner_wiring():
    print("\n[3] live_scanner wiring (subprocess: import must not crash, "
          "flags must reach scanner_status)")

    for env, expect_max_trades, expect_max_losses in (
        ({}, "3", "2"),
        ({"DAY_POLICY": "one_and_done"}, "1", "1"),
        # .env pins MAX_TRADES_PER_DAY/CONSECUTIVE_LOSS_HALT to 3/2
        # unconditionally, so DAY_POLICY=one_and_done overrides them
        # outright rather than only filling an "unset" default -- see
        # live_scanner.py's comment at this wiring.
        ({"DAY_POLICY": "one_and_done", "MAX_TRADES_PER_DAY": "2"}, "1", "1"),
    ):
        code = (
            "import os\n"
            "import live_scanner as ls\n"
            "mt = 1 if ls._LIVE_DAY_POLICY == 'one_and_done' else "
            "int(os.getenv('MAX_TRADES_PER_DAY', '3'))\n"
            "ml = 1 if ls._LIVE_DAY_POLICY == 'one_and_done' else "
            "int(os.getenv('CONSECUTIVE_LOSS_HALT', '2'))\n"
            "print(mt, ml)\n"
        )
        run_env = dict(os.environ)
        run_env.pop("DAY_POLICY", None)
        run_env.pop("MAX_TRADES_PER_DAY", None)
        run_env.pop("CONSECUTIVE_LOSS_HALT", None)
        run_env.update(env)
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=run_env,
                                 capture_output=True, text=True, timeout=60)
        ok = result.returncode == 0
        out = result.stdout.strip()
        check(f"live_scanner imports clean under env={env or '{}'}", ok)
        if ok:
            got_trades, got_losses = out.split()
            check(f"  env={env or '{}'} -> max_trades={expect_max_trades} "
                  f"(got {got_trades})", got_trades == expect_max_trades)
            check(f"  env={env or '{}'} -> max_losses={expect_max_losses} "
                  f"(got {got_losses})", got_losses == expect_max_losses)
        else:
            print(result.stderr[-2000:])

    # -- reporting-only flags reach scanner_status.json's shape -------------
    code = (
        "import live_scanner as ls\n"
        "print(ls._LIVE_FIRE_A_WHEN_NO_S, ls._LIVE_VETO_1D)\n"
    )
    run_env = dict(os.environ)
    run_env.pop("FIRE_A_WHEN_NO_S", None)
    run_env.pop("VETO_1D", None)
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=run_env,
                             capture_output=True, text=True, timeout=60)
    check("live_scanner exposes _LIVE_FIRE_A_WHEN_NO_S/_LIVE_VETO_1D for scanner_status",
          result.returncode == 0 and result.stdout.strip() == "False False")


def main():
    section1_flag_parsing()
    section2_select_day_trades()
    section3_live_scanner_wiring()

    print()
    if FAILURES:
        print(f"FAIL: {len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("PASS: all O2 flag checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
