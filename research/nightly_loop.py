"""nightly_loop.py -- the schedule research/loop_cycle.py never had.

WHY. research/loop_cycle.py (O4) does one cycle when invoked -- build both
arms, gate them, append a row to research/tape/cycles.md. All 9 rows there
were fired by hand; nothing ever called it on its own. This is the part
that calls it: pop the top real candidate off research/tape/loop_queue.json,
run it through `loop_cycle.py --stage all`, and append exactly one receipt
line to research/tape/nightly.md. research/nightly_loop.cmd (scheduled task
OmenNightlyLoop) is the thin trigger that runs this every night; all the
logic lives here, matching this repo's own daily_run.cmd / daily_fetch.py
split.

NEVER --allow-drift, never a live order, never touches signal_runner.py --
this only ever calls loop_cycle.py, which only ever builds backtest books.

MUST NOT FAIL THE TASK. An empty queue, a held cycle, a blocked cycle
(loop_cycle.py's OFF-arm-vs-baseline check) or an unexpected crash all still
produce exactly one valid receipt row and a zero exit code -- a bad night
must never stop Task Scheduler's next run.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TAPE = ROOT / "research" / "tape"
QUEUE = TAPE / "loop_queue.json"
NIGHTLY = TAPE / "nightly.md"
LOOP_CONFIG = TAPE / "loop.json"
CYCLES_MD = TAPE / "cycles.md"

RESEARCH = ROOT / "research"
LOGS = ROOT / "logs"

# omen-nightly-robustness-recheck (2026-09-26): both scripts are grid
# searches with their own multiprocessing.Pool + day-shuffle permutation
# checks -- PR #27's and #28's own test plans clocked them at ~100s and ~80s
# with 8 procs on the committed book. Cheap once, not cheap every night
# forever, so they only run on ROBUSTNESS_RECHECK_WEEKDAY (default Sunday)
# and are a no-op skip every other night. ROBUSTNESS_RECHECK_TIMEOUT_SEC is
# a hard subprocess wall-clock cap, generous headroom over the ~100s
# observed so a slower box still finishes, but never lets a hung search
# block the rest of the nightly loop.
ROBUSTNESS_RECHECK_WEEKDAY = 6  # Monday=0 .. Sunday=6
ROBUSTNESS_RECHECK_TIMEOUT_SEC = 900

HEADER = ("| date | flag | decision | $/day a->b | green a->b | off_book_id -> on_book_id |\n"
          "|---|---|---|---|---|---|\n")

EMPTY_ROW = "| %s | - | empty | - | - | - |\n"


def load_queue() -> list:
    if not QUEUE.exists():
        return []
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def is_real(candidate) -> bool:
    """loop_queue.json ships one commented-out shape example (an '_example'
    marker instead of real work) -- only a dict with a real flag/on/label and
    no '_example' key counts as queued work."""
    return (isinstance(candidate, dict) and not candidate.get("_example")
            and bool(candidate.get("flag")) and "on" in candidate and bool(candidate.get("label")))


def pop_top(queue: list):
    """(candidate, remaining_queue) -- the first real entry, everything else
    (including any example rows) left in place."""
    for i, c in enumerate(queue):
        if is_real(c):
            return c, queue[:i] + queue[i + 1:]
    return None, queue


def book_id_for(path_str: str | None) -> str:
    if not path_str:
        return "-"
    path = Path(path_str)
    if not path.exists():
        return "-"
    from research import book_stamp
    if path.name.endswith(".gz"):
        import gzip
        with gzip.open(path, "rt", encoding="utf-8") as f:
            b = json.load(f)
    else:
        b = json.loads(path.read_text(encoding="utf-8"))
    return b.get("meta", {}).get("stamp", {}).get("book_id") or book_stamp.book_id(b.get("trades", []))


def parse_result(stdout: str) -> dict:
    """loop_cycle.py prints exactly one pretty-printed json.dumps(..., indent=2)
    block as its last output (the blocked dict on a build-stage block, the
    full gate dict otherwise). Pretty-printing means every nested dict inside
    it (before_whole, after_whole, h1, h2, ...) opens with its own '{', so
    anchoring on `stdout.rfind("{")` (the previous approach) lands on the
    LAST nested brace instead of the block's own -- slicing from there yields
    a truncated fragment (e.g. just the "h2" sub-dict) that either fails to
    parse or parses "successfully" without "decision"/"before_whole"/
    "after_whole", silently producing an empty-looking result. Anchor on the
    FIRST '{' instead and let raw_decode stop at that object's own matching
    close brace, ignoring whatever text (if any) follows it."""
    start = stdout.find("{")
    if start == -1:
        return {}
    try:
        obj, _ = json.JSONDecoder().raw_decode(stdout, start)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


def cycles_md_row(flag: str, today: str) -> dict | None:
    """Fallback source of truth for run_candidate(). research/tape/cycles.md
    is the file research/loop_cycle.py's append_cycle_row() writes the real
    verdict to -- unconditionally, and before it ever prints the summary JSON
    parse_result() above reads. If that JSON still comes back unusable (a
    future loop_cycle.py change breaks its stdout contract, a crash between
    the two writes, whatever), re-derive tonight's line from the newest
    cycles.md row for this flag+date instead of falling back to an empty
    receipt while the real numbers sit one file over."""
    if not CYCLES_MD.exists():
        return None
    match = None
    for line in CYCLES_MD.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) != 12:
            continue
        row_date, _label, row_flag, decision = parts[0], parts[1], parts[2], parts[3]
        if row_flag == flag and row_date == today and decision in ("ship", "hold"):
            match = {"decision": decision, "per_day": parts[4], "green": parts[5],
                     "off_book": parts[9], "on_book": parts[10]}
    return match


def run_candidate(candidate: dict) -> str:
    flag, on, label = candidate["flag"], str(candidate["on"]), candidate["label"]
    today = date.today().isoformat()
    # Optional per-entry "env": extra env vars applied to the ON arm's build
    # ONLY (research/loop_cycle.py's --on-env) -- the OFF arm keeps whatever
    # the flag's code default is. Needed for combos like g88 option A
    # (ENTRY_FLOOR_STOP=1 alone is a no-op with the shipped ENTRY_FILL=close
    # default; it has to ride alongside ENTRY_FILL=limit_level -- see
    # backtest_week.py's ENTRY_FLOOR_STOP docstring). Stamped into the label
    # that flows into cycles.md/nightly.md so the referee sees the real combo
    # a flag+on alone would hide, not just whatever prose the label happens
    # to say.
    env = candidate.get("env") or {}
    label_for_run = label
    if env:
        combo = ", ".join("%s=%s" % (k, v) for k, v in sorted(env.items()))
        label_for_run = "%s [env: %s]" % (label, combo)
    cmd = [sys.executable, str(ROOT / "research" / "loop_cycle.py"),
           "--config", str(LOOP_CONFIG), "--flag", flag, "--on", on,
           "--label", label_for_run, "--stage", "all"]
    if env:
        cmd += ["--on-env", json.dumps(env)]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    result = parse_result(proc.stdout)

    if result.get("decision") == "blocked":
        # the ON arm is never built when blocked -- no on_book_id to report.
        return "| %s | %s | hold | - | - | %s -> - |\n" % (
            today, flag, result.get("off_book_id", "-"))

    decision = result.get("decision")
    if decision not in ("ship", "hold"):
        row = cycles_md_row(flag, today)
        if row is None:
            return "| %s | %s | hold | - | - | - -> - |\n" % (today, flag)
        off_id = book_id_for(str(TAPE / row["off_book"])) if row["off_book"] not in ("-", "") else "-"
        on_id = book_id_for(str(TAPE / row["on_book"])) if row["on_book"] not in ("-", "") else "-"
        return "| %s | %s | %s | %s | %s | %s -> %s |\n" % (
            today, flag, row["decision"], row["per_day"], row["green"], off_id, on_id)

    before, after = result.get("before_whole", {}), result.get("after_whole", {})
    off_id = book_id_for(result.get("off_book"))
    on_id = book_id_for(result.get("on_book"))
    return "| %s | %s | %s | %s -> %s | %s -> %s | %s -> %s |\n" % (
        today, flag, decision,
        before.get("per_day", "-"), after.get("per_day", "-"),
        before.get("months_green", "-"), after.get("months_green", "-"),
        off_id, on_id)


def main() -> int:
    queue = load_queue()
    candidate, remaining = pop_top(queue)

    if candidate is None:
        line = EMPTY_ROW % date.today().isoformat()
    else:
        QUEUE.write_text(json.dumps(remaining, indent=2) + "\n", encoding="utf-8")
        try:
            line = run_candidate(candidate)
        except Exception as exc:  # a bad night must still produce a row and exit 0
            print("nightly_loop.py: %s: %r" % (candidate.get("flag", "?"), exc), file=sys.stderr)
            line = "| %s | %s | hold | - | - | - -> - |\n" % (
                date.today().isoformat(), candidate.get("flag", "-"))

    if not NIGHTLY.exists():
        NIGHTLY.write_text("# nightly loop receipts\n\n" + HEADER, encoding="utf-8")
    with open(NIGHTLY, "a", encoding="utf-8") as f:
        f.write(line)

    print(line.strip())
    rebuild_tape_page()
    rebuild_status_page()
    run_v5_session_counter()
    run_propfirm_gate(candidate)
    run_propfirm_overlay_search()
    run_edge_slices()
    return 0


def rebuild_tape_page() -> None:
    """Regenerate research/tape/omen-tape.html so its Nightly receipts
    section shows tonight's row without waiting for someone to run
    build_tape.py by hand. MUST NOT FAIL THE TASK -- same rule as the rest
    of this file: a broken/slow tape-page rebuild is logged and swallowed,
    never allowed to turn a good night's receipt into a bad exit code."""
    try:
        from research import build_tape
        build_tape.build()
    except Exception as exc:
        print("nightly_loop.py: tape page rebuild failed: %r" % exc, file=sys.stderr)


def rebuild_status_page() -> None:
    """Regenerate the small phone status page (research/build_status.py) so
    tonight's receipt, queue and V5/bar-deck numbers are on it without
    waiting for someone to run it by hand. Same MUST NOT FAIL THE TASK rule
    as rebuild_tape_page() above."""
    try:
        from research import build_status
        build_status.build()
    except Exception as exc:
        print("nightly_loop.py: status page rebuild failed: %r" % exc, file=sys.stderr)


def run_v5_session_counter() -> None:
    """omen-session-count-check (2026-09-20): run v5_session_counter.run()
    as part of OmenNightlyLoop's own nightly run, instead of the separate
    OmenV5SessionCounter scheduled task (retired same day this was wired
    in). Read-only against journal files, idempotent per calendar day --
    same MUST NOT FAIL THE TASK rule as the rebuild_*_page() calls above."""
    try:
        from research import v5_session_counter
        result = v5_session_counter.run()
        print("nightly_loop.py: v5 session count: %r" % result)
    except Exception as exc:
        print("nightly_loop.py: v5 session counter failed: %r" % exc, file=sys.stderr)


def run_propfirm_gate(candidate) -> None:
    """OMEN funding-ladder card, 2026-09-26: "Agents hunt a strategy that
    passes" -- every candidate strategy this loop tests must ALSO report
    whether it would pass specific prop-firm rules, on paper, before
    anything is bought (known fact, 2026-09-05: 16/16 futures firms tested
    failed OMEN's trailing drawdown -- research/g174_funding_ladder.py,
    Projects/open-loops.md::omen-funding-ladder). Runs
    research/propfirm_gate.py (which reuses omen_metrics.evaluate_prop_
    challenge, the same simulator g174 already trusts) against tonight's
    ON book -- the one this cycle just gated above -- so the gate always
    grades the candidate this run actually measured, not a stale one. On an
    empty-queue night (no candidate ran) it falls back to the committed
    bt2y_trades_retest_on book (propfirm_gate.DEFAULT_BOOK) so the gate
    still reports something every night. Writes
    logs/propfirm_gate_latest.json at the repo root. Same MUST NOT FAIL THE
    TASK rule as the rebuild_*_page() calls above -- a bad prop-firm read
    must never turn a good night's receipt into a bad exit code."""
    try:
        from research import propfirm_gate
        book = None
        if candidate is not None:
            on_path = TAPE / ("book_%s_on.json.gz" % candidate["flag"])
            if on_path.exists():
                book = on_path
        report = propfirm_gate.write_gate_report(book)  # None -> DEFAULT_BOOK
        print("nightly_loop.py: propfirm gate -> %s" % report["headline"])
    except Exception as exc:
        print("nightly_loop.py: propfirm gate failed: %r" % exc, file=sys.stderr)


def _run_research_script(script_name: str, raw_out_path: Path, timeout_sec: int) -> dict:
    """Shared plumbing for run_propfirm_overlay_search()/run_edge_slices()
    below. Runs research/<script_name> as a SUBPROCESS, not an in-process
    import + call -- both scripts parse sys.argv in their own main() and
    spin up their own multiprocessing.Pool, neither of which should touch
    this process's argv or fork from inside an already-running loop. Raises
    on a non-zero exit, a timeout, or unparsable output; the caller (which
    has the MUST NOT FAIL THE TASK contract) is what turns that into a
    report-only, never-raise result."""
    proc = subprocess.run(
        [sys.executable, str(RESEARCH / script_name)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise RuntimeError("%s exited %d: %s" % (
            script_name, proc.returncode, proc.stderr[-2000:]))
    return json.loads(raw_out_path.read_text(encoding="utf-8"))


def run_propfirm_overlay_search() -> None:
    """omen-nightly-robustness-recheck (2026-09-26): PR #27's own body says
    "Re-run the script on any new book" -- that re-run was manual until now.
    Runs research/propfirm_overlay_search.py once a week
    (ROBUSTNESS_RECHECK_WEEKDAY) against the committed book, bounded by
    ROBUSTNESS_RECHECK_TIMEOUT_SEC, and writes a COMPACT summary (not the
    full 23,976-config grid PR #27 already writes to
    research/propfirm_overlay_search.json) to
    logs/propfirm_overlay_search_latest.json, next to
    logs/propfirm_gate_latest.json. Report-only: never touches live keys or
    trading logic, only reads the committed book and writes a log. Same MUST
    NOT FAIL THE TASK rule as run_propfirm_gate() above -- a weekday skip, a
    timeout, a non-zero exit, or a malformed result all land as a
    ok:false/skipped row in the log, never a bad exit code for the loop."""
    out_path = LOGS / "propfirm_overlay_search_latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    today = date.today()
    if today.weekday() != ROBUSTNESS_RECHECK_WEEKDAY:
        out_path.write_text(json.dumps(
            {"generated": today.isoformat(), "ok": True, "skipped": "weekly cadence",
             "weekday": ROBUSTNESS_RECHECK_WEEKDAY}, indent=2), encoding="utf-8")
        return
    try:
        raw = _run_research_script(
            "propfirm_overlay_search.py", RESEARCH / "propfirm_overlay_search.json",
            ROBUSTNESS_RECHECK_TIMEOUT_SEC)
        firms = {firm: {"overlay": v["best"]["overlay"],
                        "min_pass": v["best"]["min_pass"],
                        "robust": v["best"]["robust"]}
                for firm, v in raw.get("firms", {}).items()}
        summary = {"generated": today.isoformat(), "ok": True,
                   "book": raw.get("book"), "book_sessions": raw.get("book_sessions"),
                   "n_configs": raw.get("n_configs"),
                   "n_robust": sum(1 for v in firms.values() if v["robust"]),
                   "n_firms": len(firms), "firms": firms}
        out_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print("nightly_loop.py: propfirm overlay search -> %d/%d firms robust"
              % (summary["n_robust"], summary["n_firms"]))
    except Exception as exc:
        print("nightly_loop.py: propfirm overlay search failed: %r" % exc, file=sys.stderr)
        out_path.write_text(json.dumps(
            {"generated": today.isoformat(), "ok": False, "error": repr(exc)},
            indent=2), encoding="utf-8")


def run_edge_slices() -> None:
    """omen-nightly-robustness-recheck (2026-09-26): companion to
    run_propfirm_overlay_search() above -- same weekly cadence
    (ROBUSTNESS_RECHECK_WEEKDAY), same subprocess + timeout
    (ROBUSTNESS_RECHECK_TIMEOUT_SEC) shape, same MUST NOT FAIL THE TASK
    contract. Runs research/edge_slices.py (PR #28, "no subset of the book
    survives correction") against the committed book and writes a COMPACT
    summary -- counts and the top slice, not all 1,105 tested slices -- to
    logs/edge_slices_latest.json, next to logs/propfirm_gate_latest.json.
    Report-only, reads the committed book only, never trading logic."""
    out_path = LOGS / "edge_slices_latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    today = date.today()
    if today.weekday() != ROBUSTNESS_RECHECK_WEEKDAY:
        out_path.write_text(json.dumps(
            {"generated": today.isoformat(), "ok": True, "skipped": "weekly cadence",
             "weekday": ROBUSTNESS_RECHECK_WEEKDAY}, indent=2), encoding="utf-8")
        return
    try:
        raw = _run_research_script(
            "edge_slices.py", RESEARCH / "edge_slices.json",
            ROBUSTNESS_RECHECK_TIMEOUT_SEC)
        top = raw.get("slices", [{}])[0] if raw.get("slices") else {}
        summary = {"generated": today.isoformat(), "ok": True,
                   "book": raw.get("book"), "n_trades": raw.get("n_trades"),
                   "n_slices": raw.get("n_slices"), "n_bh_q05": raw.get("n_bh_q05"),
                   "n_bh_q10": raw.get("n_bh_q10"), "n_survivors": raw.get("n_survivors"),
                   "top_slice": {"slice": top.get("slice"), "bh_q": top.get("bh_q"),
                                "avg_r": top.get("avg_r"), "survives": top.get("survives")}}
        out_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print("nightly_loop.py: edge slices -> %d/%d slices survive BH q<=.05"
              % (summary["n_survivors"] or 0, summary["n_slices"] or 0))
    except Exception as exc:
        print("nightly_loop.py: edge slices failed: %r" % exc, file=sys.stderr)
        out_path.write_text(json.dumps(
            {"generated": today.isoformat(), "ok": False, "error": repr(exc)},
            indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
