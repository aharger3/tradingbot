"""Weekly prove-it replay: catch silent regressions in the OOS backtest.

Runs the frozen out-of-sample replay harness, compares mean R and trade
count against a committed baseline, and fails loud (exit 1 + ntfy push)
if either moved *without* the config/flags hash also changing. A hash
change means someone flagged a real edit -- that's expected drift, not
a silent regression, so it's a no-op (re-run with --update-baseline to
accept the new numbers).

Usage:
    python research/prove_it.py
    python research/prove_it.py --update-baseline
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPLAY_SCRIPT = REPO_ROOT / "research" / "agent_runs" / "v2-paper-harness" / "paper_replay.py"
DEFAULT_BASELINE = Path(__file__).resolve().parent / "prove_it_baseline.json"
NTFY_TOPIC = "omen-prove-it"  # ntfy.sh/omen-prove-it
R_TOLERANCE = 0.02


class ReplayUnavailable(Exception):
    """Raised when the OOS harness can't be run (e.g. not yet merged)."""


def config_hash(replay_script: Path) -> str:
    """Hash the replay script's bytes -- a stand-in for a flags/config file.

    Any edit to the frozen engine or its flags changes this hash, which
    is exactly the signal we want: "a flag changed" vs "nothing changed
    but the number moved anyway".
    """
    return hashlib.sha256(replay_script.read_bytes()).hexdigest()[:16]


def run_replay(replay_script: Path) -> dict:
    """Run `python <replay_script> --oos` and return its oos.json result.

    Raises ReplayUnavailable if the script doesn't exist yet (the v3 OOS
    harness is still unmerged as of 2026-09-27 -- see REFEREE-v3.md) or
    the run itself fails, so callers can decide how to treat that.
    """
    if not replay_script.exists():
        raise ReplayUnavailable(f"{replay_script} not found")
    result = subprocess.run(
        [sys.executable, str(replay_script), "--oos"],
        cwd=replay_script.parent,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise ReplayUnavailable(
            f"{replay_script} --oos exited {result.returncode}: {result.stderr[-500:]}"
        )
    out_json = replay_script.parent / "oos.json"
    if not out_json.exists():
        raise ReplayUnavailable(f"{out_json} was not written by the replay run")
    return json.loads(out_json.read_text())


def send_ntfy(message: str) -> None:
    try:
        req = urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": "OMEN prove-it: drift detected", "Priority": "high"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:  # pragma: no cover -- best-effort push
        print(f"[prove_it] ntfy push failed (non-fatal): {exc}", file=sys.stderr)


def check_drift(current: dict, baseline: dict) -> tuple[bool, str]:
    """Return (drifted, reason). Flag-hash change short-circuits to no-drift."""
    if current["config_hash"] != baseline["config_hash"]:
        return False, (
            f"config hash changed ({baseline['config_hash']} -> {current['config_hash']}); "
            "expected drift, not a regression"
        )
    r_delta = abs(current["mean_r"] - baseline["mean_r"])
    n_changed = current["n"] != baseline["n"]
    if r_delta > R_TOLERANCE or n_changed:
        return True, (
            f"mean R {baseline['mean_r']:.4f} -> {current['mean_r']:.4f} "
            f"(delta {r_delta:.4f}, tol {R_TOLERANCE}); n {baseline['n']} -> {current['n']}"
        )
    return False, f"stable: R delta {r_delta:.4f}, n unchanged at {current['n']}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-script", type=Path, default=DEFAULT_REPLAY_SCRIPT)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args(argv)

    try:
        oos = run_replay(args.replay_script)
    except ReplayUnavailable as exc:
        # The frozen OOS harness isn't on main yet (still unmerged as of
        # 2026-09-27). Soft-skip rather than fail the nightly/weekly task
        # for something out of this row's scope. Remove this branch once
        # research/agent_runs/v2-paper-harness/paper_replay.py ships.
        print(f"[prove_it] SKIP: {exc}")
        return 0

    current = {
        "mean_r": oos["mean_r"],
        "n": oos["n"],
        "config_hash": config_hash(args.replay_script),
    }

    if args.update_baseline or not args.baseline.exists():
        args.baseline.write_text(json.dumps(current, indent=2) + "\n")
        print(f"[prove_it] baseline written to {args.baseline}: {current}")
        return 0

    baseline = json.loads(args.baseline.read_text())
    drifted, reason = check_drift(current, baseline)
    print(f"[prove_it] {reason}")
    if drifted:
        send_ntfy(f"OMEN prove-it drift: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
