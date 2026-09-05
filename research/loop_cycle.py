"""loop_cycle.py -- OMEN 10.0 row O4, the one program every Phase-L row runs.

WHAT THIS IS. Phase L ships rules one at a time behind a flag (SWARM.md's
"one change per row"). Every row needs the same four steps done the same
way: build the flag OFF, build the flag ON, price both on the SAME unit and
the SAME halves split, and apply the no-regression gate (green months may
not fall, $/day may not fall more than 5%, checked on BOTH halves). Six
L-rows re-implementing that arithmetic six times is how a project ends up
with six slightly different definitions of "green month" -- this script is
the one place it lives.

IMPORTS, NOT RETYPING. `research/book_stamp.py` owns the book's identity
(`book_id`, the flag stamp, `describe`) -- used here to prove a flag's OFF
arm is byte-identical to the baseline before trusting its ON arm at all.
`research/g72_suppress_price.py` owns the arithmetic every dollar figure in
this project already means: `stats()` ($/day, mean R, months/weeks green,
drawdown), `shipped_rows()` (every_signal unit) and `oneaday_rows()`
(first_of_day unit). Both are imported, never re-typed. `backtest_2y.py`
was read for its invocation contract (`--out PATH`, every behaviour flag
read from the environment at import time) -- it has no standalone metric
function to import, only a `main()` that builds a book; this script calls
it as a subprocess with the flag as an env var, exactly like every prior
A/B script in this repo already does. `avg_win`/`avg_loss` and the
`up_to_3_stop_win_or_2loss` unit are new -- no prior script computes them.

THE THREE UNITS (`--config`'s "unit" field picks one for a given L-row):
    every_signal                 every traded signal the engine fires
    first_of_day                 the day's first fired-and-traded candidate
    up_to_3_stop_win_or_2loss    his day policy: up to 3 fires a day, stop
                                  after the first win or the second loss

SESSION-COUNT CAVEAT. A book's `meta["sessions"]` is the true total session
count for the whole window (backtest_2y.py counts every day it opened a
symbol, even one with zero candidate setups). It does NOT carry a session
CALENDAR, so a half's session count here is approximated as the number of
distinct `day` values appearing anywhere in the book's rows (fired or
skipped) on that side of the boundary -- a day where literally no symbol
produced a single candidate setup is invisible to this approximation. That
undercount is systematic across both arms of an A/B (same replay engine,
same universe), so it does not change which arm wins; it can shift the
$/day of a given half slightly high. Flagged here rather than solved
because solving it is a second change (recording the session calendar in
`backtest_2y.py`) this row does not own.

INTERFACE.
    python research/loop_cycle.py --config research/tape/loop.json \\
        --flag SOME_ENV_FLAG --on 1 --label "the 1R first-target rule" \\
        --stage build|gate|all [--dry-run] [--smoke]

`--stage build` rebuilds the OFF arm (flag left at its current default --
env simply unset) into `research/tape/book_<flag>_off.json.gz` and asserts
its `book_stamp.book_id` equals the configured baseline book's -- proof the
code landing changed nothing when the flag is off. A mismatch is reported
as `{"decision": "blocked", ...}` with the row-count diff and the ON arm is
never built (there is no point pricing a flag against a baseline it can no
longer reproduce). It then builds the ON arm (flag set to `--on`'s value)
into `research/tape/book_<flag>_on.json.gz`. Both builds run as a
subprocess with output captured to `research/tape/logs/`; nothing here
blocks longer than one rebuild -- the CALLER is expected to run this
`--stage build` invocation itself in the background for a real (non-smoke)
build, per SWARM.md's bound-every-command rule.

`--stage gate` reads both books, computes $/day, total, mean R, avg
win/avg loss, green months, weeks green, trades and fires/day on the
config's unit, for the whole window and for each half (split at
`halves_boundary`). It applies the no-regression gate to both halves
independently, appends one row to `research/tape/cycles.md`, updates
`research/tape/loop_state.json` (cycle count, consecutive holds, whether
the loop's target is now met), pushes one plain-English ntfy line (unless
`--dry-run`), and prints the full decision as JSON on stdout.

`--smoke` runs both arms with `backtest_2y.py --days 15` to prove the
plumbing without ever building a full two-year book in this row; it also
skips the OFF-vs-baseline `book_id` assertion, since a 15-day smoke book
can never match a 730-day baseline's fingerprint.

STOP RULE (SWARM.md law: the gate is a normal outcome, holding is not a
failure). The loop stops when the config's target is met on the unit's
whole-window numbers, or after 5 consecutive holds. Both are written into
`loop_state.json` and the gate's stdout JSON; this script does not itself
decide to stop calling itself -- the dispatcher reads `stop` and acts.

1R = $1,000 (CLAUDE.md). Every dollar figure below names its fill (the
book's own `entry_fill` stamp), its unit (this file's three), and its
script (this one).
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import book_stamp                                    # noqa: E402
from research.g72_suppress_price import (                          # noqa: E402
    stats as g72_stats, shipped_rows, oneaday_rows,
)
import notify_ntfy                                                 # noqa: E402

TAPE = ROOT / "research" / "tape"
LOGS = TAPE / "logs"
CYCLES_MD = TAPE / "cycles.md"
STATE_JSON = TAPE / "loop_state.json"

MIN_TRADES = 30
MIN_MONTHS = 12
MAX_CONSECUTIVE_HOLDS = 5


# ------------------------------------------------------------------- the units

def up_to_3_rows(rows):
    """His day policy: up to 3 fired-and-traded signals a day, stop after the
    first win or after the second loss (spec: 'up to 3 S fires; stop after a
    win or after 2 losses'). Candidate pool matches g72_suppress_price's
    `oneaday_rows`: fired-and-traded, plus the account-wide two-loss halt's
    own rows (so a halt this unit's OWN stop-rule would not have reached yet
    does not silently erase the rest of that day)."""
    byday = {}
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday.setdefault(r["day"], []).append(r)
    out = []
    for day in sorted(byday):
        day_rows = sorted(byday[day], key=lambda r: (r.get("et") or "", r.get("sym") or ""))
        losses, taken = 0, 0
        for r in day_rows:
            if taken >= 3:
                break
            out.append(r)
            taken += 1
            pnl = r.get("pnl", 0.0)
            if pnl > 0:
                break
            if pnl < 0:
                losses += 1
                if losses >= 2:
                    break
    return out


UNIT_FUNCS = {
    "every_signal": shipped_rows,
    "first_of_day": oneaday_rows,
    "up_to_3_stop_win_or_2loss": up_to_3_rows,
}


# --------------------------------------------------------------------- loading

def load_book_any(path):
    """meta, rows -- from a plain .json book or a gzip .json.gz one."""
    path = str(path)
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            b = json.load(f)
    else:
        b = json.loads(Path(path).read_text(encoding="utf-8"))
    return b["meta"], b["trades"]


def session_days(rows):
    return sorted({r["day"] for r in rows if r.get("day")})


def split_halves(rows, boundary):
    h1 = [r for r in rows if r.get("day", "") < boundary]
    h2 = [r for r in rows if r.get("day", "") >= boundary]
    return h1, h2


def half_n_days(all_rows, boundary):
    """Approximate session count either side of the boundary -- see the
    SESSION-COUNT CAVEAT in the module docstring."""
    days = session_days(all_rows)
    return sum(1 for d in days if d < boundary), sum(1 for d in days if d >= boundary)


# ------------------------------------------------------------------- the figures

EMPTY_STATS = {"trades": 0, "win_pct": 0.0, "total_dollars": 0.0, "per_trade": 0.0,
               "mean_r": 0.0, "per_day": 0.0, "months_green": 0, "months": 0,
               "weeks_green": 0, "weeks": 0, "green_days_pct": 0.0, "days_traded": 0,
               "worst_drawdown": 0.0}


def avg_win_loss(rows):
    """(avg winning trade in dollars, avg LOSING trade in dollars, positive)."""
    wins = [r["pnl"] for r in rows if r.get("pnl", 0) > 0]
    losses = [r["pnl"] for r in rows if r.get("pnl", 0) < 0]
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    return round(avg_win, 0), round(avg_loss, 0)


def figures(rows, n_days, unit_name):
    """One unit's numbers for one slice of a book: g72's arithmetic, plus
    avg win/loss and fires/day, which g72 does not compute."""
    unit_rows = UNIT_FUNCS[unit_name](rows)
    base = dict(g72_stats(unit_rows, n_days)) if (unit_rows and n_days) else dict(EMPTY_STATS)
    aw, al = avg_win_loss(unit_rows)
    base["avg_win"] = aw
    base["avg_loss"] = al
    base["avg_win_over_avg_loss"] = round(aw / al, 3) if al else None
    base["fires_per_day"] = round(len(unit_rows) / n_days, 3) if n_days else 0.0
    return base


def compute_all(meta, rows, unit_name, boundary):
    """{'whole', 'h1', 'h2'} figures dicts for one book, on one unit."""
    n_days_all = meta.get("sessions") or len(session_days(rows))
    n1, n2 = half_n_days(rows, boundary)
    h1_rows, h2_rows = split_halves(rows, boundary)
    return {"whole": figures(rows, n_days_all, unit_name),
            "h1": figures(h1_rows, n1, unit_name),
            "h2": figures(h2_rows, n2, unit_name)}


# --------------------------------------------------------------------- the gate

def half_verdict(before: dict, after: dict, max_drop_pct: float) -> dict:
    """SWARM.md law 2, applied to one half: green months may not fall, $/day
    may not fall more than `max_drop_pct`. Under 30 trades or 12 months on
    the BEFORE side gets no verdict (law 3) -- `enough: False`, `pass: None`.
    A negative baseline's "$/day falls no more than N%" reads as "the LOSS
    may not get more than N% worse", not "any number above a negative floor
    passes"."""
    enough = before.get("trades", 0) >= MIN_TRADES and before.get("months", 0) >= MIN_MONTHS
    if not enough:
        return {"enough": False, "pass": None,
                "green_before": before.get("months_green"), "green_after": after.get("months_green"),
                "dollar_before": before.get("per_day"), "dollar_after": after.get("per_day")}
    green_ok = after.get("months_green", 0) >= before.get("months_green", 0)
    b, a = before.get("per_day", 0.0), after.get("per_day", 0.0)
    if b > 0:
        dollar_ok = a >= b * (1 - max_drop_pct / 100.0)
    elif b < 0:
        dollar_ok = a >= b * (1 + max_drop_pct / 100.0)
    else:
        dollar_ok = a >= 0
    return {"enough": True, "pass": bool(green_ok and dollar_ok),
            "green_before": before.get("months_green"), "green_after": after.get("months_green"),
            "dollar_before": before.get("per_day"), "dollar_after": after.get("per_day")}


def target_met(whole: dict, targets: dict) -> bool:
    if whole.get("months", 0) <= 0:
        return False
    return (whole.get("per_day", 0) >= targets["dollars_per_day"]
            and (whole.get("avg_win_over_avg_loss") or 0) >= targets["avg_win_over_avg_loss"]
            and whole.get("months_green", 0) == whole.get("months", 0))


# ---------------------------------------------------------------------- build

def build_book(env_overrides: dict, out_gz: Path, rebuild_cfg: dict, smoke: bool) -> Path:
    LOGS.mkdir(parents=True, exist_ok=True)
    tag = out_gz.name[:-len(".json.gz")] if out_gz.name.endswith(".json.gz") else out_gz.stem
    tmp_json = TAPE / (tag + "_tmp.json")
    cmd = [sys.executable, str(ROOT / rebuild_cfg["script"])]
    cmd += ["--days", "15"] if smoke else list(rebuild_cfg.get("args", []))
    cmd += ["--out", str(tmp_json)]
    env = dict(os.environ)
    env.update(rebuild_cfg.get("env", {}))
    env.update({str(k): str(v) for k, v in env_overrides.items()})
    env["PYTHONIOENCODING"] = "utf-8"
    log_path = LOGS / (tag + ".log")
    print("  $ %s -> %s (log: %s)" % (" ".join(cmd), out_gz.name, log_path))
    with open(log_path, "w", encoding="utf-8") as lf:
        proc = subprocess.run(cmd, cwd=str(ROOT), env=env, stdout=lf,
                              stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise SystemExit("build failed (exit %d) -- see %s" % (proc.returncode, log_path))
    payload = tmp_json.read_text(encoding="utf-8")
    with gzip.open(out_gz, "wt", encoding="utf-8") as gz:
        gz.write(payload)
    tmp_json.unlink(missing_ok=True)
    return out_gz


def stage_build(cfg: dict, flag: str, on_value: str, smoke: bool) -> dict:
    off_path = TAPE / ("book_%s_off.json.gz" % flag)
    on_path = TAPE / ("book_%s_on.json.gz" % flag)
    rebuild = cfg["rebuild"]

    print("building OFF arm (%s left at its default) -> %s" % (flag, off_path))
    build_book({}, off_path, rebuild, smoke)
    off_meta, off_rows = load_book_any(off_path)

    if smoke:
        print("(--smoke) skipping the OFF==baseline book_id check -- a 15-day "
              "smoke book cannot match a full-window baseline's fingerprint")
    else:
        baseline_meta, baseline_rows = load_book_any(cfg["baseline_book"])
        base_id = baseline_meta.get("stamp", {}).get("book_id") or book_stamp.book_id(baseline_rows)
        off_id = off_meta.get("stamp", {}).get("book_id") or book_stamp.book_id(off_rows)
        if base_id != off_id:
            decision = {
                "decision": "blocked", "flag": flag,
                "reason": ("the OFF arm's book_id does not match the configured baseline's -- "
                          "the code landing changed the book even with the flag at its default"),
                "baseline_book_id": base_id, "off_book_id": off_id,
                "baseline_rows": len(baseline_rows), "off_rows": len(off_rows),
                "row_count_diff": len(off_rows) - len(baseline_rows),
            }
            return decision

    print("building ON arm (%s=%s) -> %s" % (flag, on_value, on_path))
    build_book({flag: on_value}, on_path, rebuild, smoke)
    return {"decision": "built", "off_book": str(off_path), "on_book": str(on_path)}


# ----------------------------------------------------------------------- gate

def append_cycle_row(cycle_no, label, flag, decision, before, after, h1v, h2v,
                     off_path, on_path, script):
    header = ("| date | label | flag | decision | $/day a->b | green months a->b | "
             "H1 | H2 | trades | off book | on book | script |\n"
             "|---|---|---|---|---|---|---|---|---|---|---|---|\n")
    if not CYCLES_MD.exists():
        CYCLES_MD.write_text("# loop cycles\n\n" + header, encoding="utf-8")

    def half_cell(v):
        return "not enough" if not v["enough"] else ("pass" if v["pass"] else "fail")

    row = ("| %s | %s | %s | %s | %s -> %s | %s -> %s | %s | %s | %d | %s | %s | %s |\n" % (
        date.today().isoformat(), label, flag, decision,
        before["whole"].get("per_day"), after["whole"].get("per_day"),
        before["whole"].get("months_green"), after["whole"].get("months_green"),
        half_cell(h1v), half_cell(h2v), after["whole"].get("trades", 0),
        off_path.name, on_path.name, script))
    with open(CYCLES_MD, "a", encoding="utf-8") as f:
        f.write(row)


def load_state() -> dict:
    if STATE_JSON.exists():
        return json.loads(STATE_JSON.read_text(encoding="utf-8"))
    return {"cycle_count": 0, "consecutive_holds": 0, "target_met": False, "history": []}


def stage_gate(cfg: dict, flag: str, label: str, dry_run: bool) -> dict:
    off_path = TAPE / ("book_%s_off.json.gz" % flag)
    on_path = TAPE / ("book_%s_on.json.gz" % flag)
    if not off_path.exists() or not on_path.exists():
        missing = off_path if not off_path.exists() else on_path
        raise SystemExit("run --stage build first: missing %s" % missing)

    off_meta, off_rows = load_book_any(off_path)
    on_meta, on_rows = load_book_any(on_path)
    unit, boundary = cfg["unit"], cfg["halves_boundary"]

    before = compute_all(off_meta, off_rows, unit, boundary)
    after = compute_all(on_meta, on_rows, unit, boundary)

    max_drop = cfg["gate"]["max_dollar_drop_pct"]
    h1v = half_verdict(before["h1"], after["h1"], max_drop)
    h2v = half_verdict(before["h2"], after["h2"], max_drop)
    decision = "ship" if (h1v["enough"] and h1v["pass"] and h2v["enough"] and h2v["pass"]) else "hold"

    active_whole = after["whole"] if decision == "ship" else before["whole"]
    met = target_met(active_whole, cfg["targets"])

    state = load_state()
    state["cycle_count"] += 1
    state["consecutive_holds"] = 0 if decision == "ship" else state["consecutive_holds"] + 1
    state["target_met"] = met
    stop = bool(met or state["consecutive_holds"] >= MAX_CONSECUTIVE_HOLDS)
    state["stop"] = stop
    state["stop_reason"] = ("target met" if met else
                            ("5 consecutive holds" if state["consecutive_holds"] >= MAX_CONSECUTIVE_HOLDS
                             else None))
    state["history"].append({
        "cycle": state["cycle_count"], "flag": flag, "label": label, "decision": decision,
        "dollars_per_day_before": before["whole"].get("per_day"),
        "dollars_per_day_after": after["whole"].get("per_day"),
        "green_before": before["whole"].get("months_green"),
        "green_after": after["whole"].get("months_green"),
    })
    STATE_JSON.write_text(json.dumps(state, indent=2), encoding="utf-8")

    append_cycle_row(state["cycle_count"], label, flag, decision, before, after,
                     h1v, h2v, off_path, on_path, "research/loop_cycle.py")

    if not dry_run:
        line = ("[OMEN] cycle %d: %s -- %s. $/day %s -> %s, green months %s -> %s"
                % (state["cycle_count"], label, "shipped" if decision == "ship" else "held",
                   before["whole"].get("per_day"), after["whole"].get("per_day"),
                   before["whole"].get("months_green"), after["whole"].get("months_green")))
        notify_ntfy.push("OMEN loop", line)

    out = {"decision": decision, "flag": flag, "label": label, "unit": unit,
           "cycle": state["cycle_count"], "consecutive_holds": state["consecutive_holds"],
           "target_met": met, "stop": stop, "stop_reason": state["stop_reason"],
           "before_whole": before["whole"], "after_whole": after["whole"],
           "before_h1": before["h1"], "after_h1": after["h1"],
           "before_h2": before["h2"], "after_h2": after["h2"],
           "h1": h1v, "h2": h2v,
           "off_book": str(off_path), "on_book": str(on_path)}
    print(json.dumps(out, indent=2, default=str))
    return out


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--flag", required=True, help="env var name the L-row toggles")
    ap.add_argument("--on", required=True, help="value to set --flag to for the ON arm")
    ap.add_argument("--label", required=True, help="plain English name Austin reads")
    ap.add_argument("--stage", choices=["build", "gate", "all"], required=True)
    ap.add_argument("--dry-run", action="store_true", help="suppress the ntfy push")
    ap.add_argument("--smoke", action="store_true",
                    help="both arms at --days 15, never a full 2-year book")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    TAPE.mkdir(parents=True, exist_ok=True)

    if args.stage in ("build", "all"):
        result = stage_build(cfg, args.flag, args.on, args.smoke)
        if result.get("decision") == "blocked":
            print(json.dumps(result, indent=2))
            sys.exit(1)

    if args.stage in ("gate", "all"):
        stage_gate(cfg, args.flag, args.label, args.dry_run)


if __name__ == "__main__":
    main()
