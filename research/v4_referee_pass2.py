"""V4 referee (pass 2) -- independent re-derivation of every claim in row V4.

Builder commit under review: 76d6e4ad (repair of 79d6f57f).
Nothing here trusts the builder's report: each check re-derives the fact from
the file, the tape, or a subprocess import.

    python research/v4_referee.py

Prints one PASS/FAIL line per check and exits nonzero if any check FAILS.
Never prints an environment value that could be a credential.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).parent.parent
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))


def _load(modpath: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, modpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = _load(ROOT / "research" / "test_live_follows_loop.py", "v4_t")
CYCLES = (ROOT / "research" / "tape" / "cycles.md").read_text(encoding="utf-8")

# ---------------------------------------------------------------- check 1
# Fix 1: parse_cycles_md must return EVERY flag row, not just FLAG_ENV keys.
synthetic = CYCLES + (
    "| 2026-09-06 | a brand new gate | BRAND_NEW_FLAG | ship | 0 -> 1 | 11 -> 12 "
    "| pass | pass | 700 | a.gz | b.gz | research/loop_cycle.py |\n"
)
parsed_syn = T.parse_cycles_md(synthetic)
check(
    "1 parse_cycles_md returns a flag outside FLAG_ENV (fix 1)",
    "BRAND_NEW_FLAG" in parsed_syn and parsed_syn["BRAND_NEW_FLAG"] == "ship",
    "parsed keys=%r" % sorted(parsed_syn),
)

# ---------------------------------------------------------------- check 2
# and the test body must FAIL LOUDLY on that unknown flag, not pass silently.
tmp = Path(tempfile.mkdtemp()) / "cycles.md"
tmp.write_text(synthetic, encoding="utf-8")
orig_cycles = T.CYCLES_MD
T.CYCLES_MD = tmp
try:
    T.test_live_flags_match_cycles_md_shipped_set()
    fired, msg = False, "test PASSED with an unknown shipped flag present"
except AssertionError as e:
    fired, msg = "BRAND_NEW_FLAG" in str(e), str(e).splitlines()[0][:120]
finally:
    T.CYCLES_MD = orig_cycles
check("2 test fails loudly naming the unknown flag (fix 1)", fired, msg)

# ---------------------------------------------------------------- check 3
# Fix 2: expected_env_value branches on decision for DAY_POLICY.
ev = T.expected_env_value
check(
    "3 expected_env_value DAY_POLICY branches on decision (fix 2)",
    ev("DAY_POLICY", "hold") == "first3"
    and ev("DAY_POLICY", "ship") == "3fires_stop_win_or_2loss",
    "hold=%r ship=%r" % (ev("DAY_POLICY", "hold"), ev("DAY_POLICY", "ship")),
)

# and a synthetic "hold" DAY_POLICY tape must make the test fail against the
# live lane, which currently carries the shipped string.
tmp2 = Path(tempfile.mkdtemp()) / "cycles.md"
tmp2.write_text(CYCLES.replace("| DAY_POLICY | ship |", "| DAY_POLICY | hold |"),
                encoding="utf-8")
T.CYCLES_MD = tmp2
try:
    T.test_live_flags_match_cycles_md_shipped_set()
    held_fail, hmsg = False, "test PASSED with tape saying hold and live saying ship"
except AssertionError as e:
    held_fail, hmsg = "DAY_POLICY" in str(e), "raised on DAY_POLICY"
finally:
    T.CYCLES_MD = orig_cycles
check("4 tape 'hold' for DAY_POLICY now fails the test (fix 2)", held_fail, hmsg)

# ---------------------------------------------------------------- check 5
# Independent parity diff: cycles.md decisions vs live runtime values.
decisions = T.parse_cycles_md(CYCLES)
rows = []
parity_ok = True
for flag, decision in sorted(decisions.items()):
    want = ev(flag, decision)
    got = T.read_live_value(flag)
    same = str(got) == str(want)
    if not same:
        try:
            same = float(got) == float(want)
        except ValueError:
            same = {"True": "1", "False": "0"}.get(got, got) == want
    parity_ok &= same
    rows.append((flag, decision, want, got, same))
check("5 live runtime values match cycles.md (%d flags)" % len(rows), parity_ok,
      "; ".join("%s:%s want=%s got=%s" % (f, d, w, g) for f, d, w, g, _ in rows))

# ---------------------------------------------------------------- check 6
# Alpaca: paper endpoint only, no live key read, no live host literal.
alp = (ROOT / "broker" / "alpaca.py").read_text(encoding="utf-8")
env_names = sorted(set(re.findall(r"ALPACA_[A-Z_]+", alp)))
check("6 broker/alpaca.py constructs TradingClient(paper=True) literal",
      "paper=True" in alp and "paper=" not in alp.replace("paper=True", ""),
      "env names read: %r" % env_names)
check("7 broker/alpaca.py reads paper credentials only",
      env_names == ["ALPACA_PAPER_KEY", "ALPACA_PAPER_SECRET"],
      "env names: %r" % env_names)
check("8 no live-trading host literal in broker/alpaca.py",
      "api.alpaca.markets" not in alp.replace("paper-api.alpaca.markets", ""),
      "")

ls_src = (ROOT / "live_scanner.py").read_text(encoding="utf-8")
n_asserts = ls_src.count(
    'assert not getattr(runner, "replay", False)')
check("9 replay can never submit (assert in both alpaca submit paths)",
      n_asserts >= 2, "%d guarded submit functions" % n_asserts)

# ---------------------------------------------------------------- check 10
# Morning report survives an absent ledger.
MR = _load(ROOT / "research" / "morning_report.py", "v4_mr")
missing = ROOT / "journal" / "definitely-not-here-v4referee.jsonl"
buf = io.StringIO()
try:
    sys.argv = ["morning_report.py", "--ledger", str(missing)]
    with redirect_stdout(buf):
        MR.main()
    mr_ok, mr_msg = True, buf.getvalue().strip().splitlines()[0][:90]
except Exception as e:  # noqa: BLE001
    mr_ok, mr_msg = False, "%s: %s" % (type(e).__name__, e)
check("10 morning_report.py runs with journal/alpaca-paper.jsonl absent",
      mr_ok, mr_msg)
check("11 journal/alpaca-paper.jsonl absent today (nothing has traded yet)",
      not (ROOT / "journal" / "alpaca-paper.jsonl").exists(), "")

# ---------------------------------------------------------------- check 12
# The behaviour question the test does NOT ask: does the live session actually
# enforce the shipped day policy, or only carry its label?
stop_after_win_default = re.search(
    r'STOP_AFTER_WIN\s*=\s*os\.getenv\("STOP_AFTER_WIN",\s*"(\d)"\)', ls_src)
swd = stop_after_win_default.group(1) if stop_after_win_default else "?"
env_has_saw = False
env_path = ROOT / ".env"
if env_path.exists():
    env_has_saw = any(l.strip().startswith("STOP_AFTER_WIN=")
                      for l in env_path.read_text(encoding="utf-8").splitlines())
check("12 live enforces 'stop after a win' (the shipped policy's other half)",
      swd == "1" or env_has_saw,
      "STOP_AFTER_WIN live default=%r, pinned in .env=%s -- shipped DAY_POLICY "
      "is '3fires_stop_win_or_2loss' (3 fires, day ends on a closed WIN or the "
      "2nd closed loss); live_scanner sets max_trades/max_losses from "
      "MAX_TRADES_PER_DAY/CONSECUTIVE_LOSS_HALT (3/2) and only special-cases "
      "one_and_done, so the win-stop half is not carried"
      % (swd, env_has_saw))

# ---------------------------------------------------------------- report
print("V4 referee (pass 2) -- builder commit 76d6e4ad")
print("=" * 72)
fails = 0
for name, ok, detail in results:
    print("%-4s %s" % ("PASS" if ok else "FAIL", name))
    if detail:
        print("       %s" % detail)
    fails += 0 if ok else 1
print("=" * 72)
print("%d checks, %d FAIL" % (len(results), fails))
sys.exit(1 if fails else 0)
