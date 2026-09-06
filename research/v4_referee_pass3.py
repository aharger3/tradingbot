"""V4 referee, pass 3 (OMEN 10.0 swarm).

Independent re-derivation of everything row V4 claims, written without reading
research/test_live_follows_loop.py's own parser: this file parses
research/tape/cycles.md with its own implementation, reads the five live flag
values out of a fresh live_scanner import, and then tries to BREAK the parity
test three different ways to prove it has teeth.

    python research/v4_referee_pass3.py

Exit 0 = every check I could run agrees with what the row claims.
Exit 1 = at least one check disagrees; the failing lines are printed.

Nothing here places an order, writes a book, or touches a mark file.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CYCLES = ROOT / "research" / "tape" / "cycles.md"
PARITY = ROOT / "research" / "test_live_follows_loop.py"
ALPACA = ROOT / "broker" / "alpaca.py"
SCANNER = ROOT / "live_scanner.py"
RUNNER = ROOT / "signal_runner.py"
MORNING = ROOT / "research" / "morning_report.py"

FAILS: list[str] = []
NOTES: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    tag = "ok  " if ok else "FAIL"
    print(f"[{tag}] {label}" + (f" -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(f"{label}{(' -- ' + detail) if detail else ''}")
    return ok


# ---------------------------------------------------------------- cycles.md
def my_parse_cycles(text: str) -> dict[str, str]:
    """My own parse, deliberately different from the parity test's: pull the
    header to find the flag/decision column indices instead of hardcoding 2/3,
    and keep the LAST row per flag."""
    header_idx = {}
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        low = [c.lower() for c in cells]
        if "flag" in low and "decision" in low:
            header_idx = {"flag": low.index("flag"), "decision": low.index("decision")}
            continue
        if not header_idx:
            continue
        try:
            flag = cells[header_idx["flag"]]
            decision = cells[header_idx["decision"]]
        except IndexError:
            continue
        if not flag or flag == "n/a":
            continue
        out[flag] = decision
    return out


def live_values(extra_env: dict | None = None, cwd: Path = ROOT) -> dict[str, str]:
    """Import live_scanner (which loads .env, then imports signal_runner) in a
    subprocess and read the five flag values back as JSON."""
    code = (
        "import sys, json; sys.path.insert(0, r'%s');"
        "import live_scanner as ls; import signal_runner as sr;"
        "flags=['MIN_PT1_R','RULE84_DECIDED','OCR_RETEST_DISPLACEMENT','TREND_DEF','DAY_POLICY'];"
        "print('@@'+json.dumps({f: str(getattr(ls,'_LIVE_'+f, getattr(sr,f))) for f in flags}))"
    ) % (str(ROOT),)
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    r = subprocess.run([sys.executable, "-c", code], cwd=str(cwd),
                       capture_output=True, text=True, timeout=180, env=env)
    if r.returncode != 0:
        raise RuntimeError("live import failed:\n" + r.stderr[-3000:])
    line = [l for l in r.stdout.splitlines() if l.startswith("@@")][-1]
    return json.loads(line[2:])


EXPECT_HOLD = {
    "MIN_PT1_R": {"0", "0.0", "False"},
    "RULE84_DECIDED": {"0", "False"},
    "OCR_RETEST_DISPLACEMENT": {"0", "False"},
    "TREND_DEF": {"off"},
    "DAY_POLICY": {"first3"},
}


def run_parity(env_extra: dict | None = None, cwd: Path = ROOT) -> tuple[int, str]:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    r = subprocess.run([sys.executable, str(PARITY)], cwd=str(cwd),
                       capture_output=True, text=True, timeout=300, env=env)
    return r.returncode, (r.stdout + r.stderr)[-1500:]


def main() -> int:
    print("=" * 74)
    print("V4 referee pass 3 -- independent re-derivation")
    print("=" * 74)

    text = CYCLES.read_text(encoding="utf-8")
    decisions = my_parse_cycles(text)
    print("\n1. cycles.md, parsed by my own implementation")
    for f, d in decisions.items():
        print(f"     {f:28s} {d}")
    check(len(decisions) == 5, "cycles.md carries exactly 5 gated flags",
          f"got {len(decisions)}: {sorted(decisions)}")
    check(all(d == "hold" for d in decisions.values()),
          "every cycles.md decision at HEAD reads 'hold'",
          f"{ {f: d for f, d in decisions.items() if d != 'hold'} }")

    print("\n2. live lane values (fresh live_scanner import)")
    live = live_values()
    for f, v in live.items():
        print(f"     {f:28s} {v!r}")
    for f, allowed in EXPECT_HOLD.items():
        check(live.get(f) in allowed, f"live {f} carries its held/off value",
              f"got {live.get(f)!r}, want one of {sorted(allowed)}")
    check(set(live) == set(decisions),
          "the live flag set is exactly the tape's flag set")

    print("\n3. the committed parity test, as shipped")
    rc, out = run_parity()
    check(rc == 0, "research/test_live_follows_loop.py exits 0 at HEAD", out.strip()[-200:])

    print("\n4. does it have teeth? (three injected drifts, each must turn it RED)")
    tmpdir = Path(tempfile.mkdtemp(prefix="v4ref3_"))
    try:
        # Teeth A: env drift -- someone exports the shipped DAY_POLICY string.
        rc_a, out_a = run_parity({"DAY_POLICY": "3fires_stop_win_or_2loss"})
        check(rc_a != 0, "teeth A: an exported DAY_POLICY drift turns the test RED",
              f"exit {rc_a}")

        # Teeth B/C need a mutated cycles.md. Copy the whole repo tree? No --
        # instead run the test with a patched CYCLES_MD constant in-process.
        def run_with_cycles(md_text: str, tag: str) -> tuple[int, str]:
            p = tmpdir / f"cycles_{tag}.md"
            p.write_text(md_text, encoding="utf-8")
            code = (
                "import sys, pathlib; sys.path.insert(0, r'%s');\n"
                "import importlib.util as iu\n"
                "spec = iu.spec_from_file_location('v4t', r'%s')\n"
                "m = iu.module_from_spec(spec); spec.loader.exec_module(m)\n"
                "m.CYCLES_MD = pathlib.Path(r'%s')\n"
                "m.test_live_flags_match_cycles_md_shipped_set()\n"
                "print('GREEN')\n"
            ) % (str(ROOT), str(PARITY), str(p))
            r = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT),
                               capture_output=True, text=True, timeout=300)
            return r.returncode, (r.stdout + r.stderr)[-800:]

        # sanity: unmutated text through the same harness must be GREEN
        rc_s, out_s = run_with_cycles(text, "sanity")
        check(rc_s == 0, "teeth harness sanity: unmutated cycles.md is GREEN via the harness",
              out_s.strip()[-200:])

        # Teeth B: flip DAY_POLICY's last row to ship.
        lines = text.splitlines()
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].startswith("|") and "DAY_POLICY" in lines[i]:
                lines[i] = lines[i].replace("| hold |", "| ship |", 1)
                break
        rc_b, out_b = run_with_cycles("\n".join(lines), "ship")
        check(rc_b != 0, "teeth B: flipping DAY_POLICY to 'ship' in the tape turns it RED",
              f"exit {rc_b}")

        # Teeth C: a brand-new sixth flag ships in the tape.
        newrow = ("| 2026-09-09 | a brand new gate | BRAND_NEW_FLAG | ship | 0 -> 1 | "
                  "11 -> 12 | pass | pass | 700 | a.gz | b.gz | research/loop_cycle.py |")
        rc_c, out_c = run_with_cycles(text.rstrip() + "\n" + newrow + "\n", "newflag")
        check(rc_c != 0, "teeth C: a newly shipped sixth flag turns it RED",
              f"exit {rc_c}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print("\n5. Alpaca: paper only")
    alp = ALPACA.read_text(encoding="utf-8")
    paper_args = re.findall(r"paper\s*=\s*([A-Za-z0-9_\.\"']+)", alp)
    check(paper_args and all(a == "True" for a in paper_args),
          "every paper= argument in broker/alpaca.py is the literal True",
          f"found {paper_args}")
    check("api.alpaca.markets" not in alp.replace("paper-api.alpaca.markets", ""),
          "no live Alpaca trading host literal in broker/alpaca.py")
    creds = sorted(set(re.findall(r"ALPACA_[A-Z_]+", alp)))
    check(all("PAPER" in c for c in creds),
          "broker/alpaca.py reads only *_PAPER_* credential names", f"{creds}")
    scan = SCANNER.read_text(encoding="utf-8")
    # _ALPACA_LEDGER is a Path constant, not a credential -- exclude it by name.
    live_key_names = [c for c in set(re.findall(r"ALPACA_[A-Z_]+", scan))
                      if "PAPER" not in c and c != "ALPACA_LEDGER"]
    check(not live_key_names, "live_scanner.py reads no non-paper Alpaca credential name",
          f"{live_key_names}")

    print("\n6. replay can never submit")
    n_asserts = scan.count('"Alpaca submit attempted with runner.replay=True')
    check(n_asserts >= 2,
          "both Alpaca submit paths assert not runner.replay", f"{n_asserts} asserts")
    m = re.search(r"def run_replay\(.*?(?=\ndef )", scan, re.S)
    body = m.group(0) if m else ""
    check(bool(body) and "runner.replay = True" in body,
          "run_replay sets runner.replay = True")
    check(bool(body) and "AlpacaBroker(" not in body and "broker=" not in body,
          "run_replay never constructs or passes a broker")

    print("\n7. morning report survives a missing ledger")
    missing = tempfile.gettempdir() + os.sep + "v4_referee_no_such_ledger.jsonl"
    if os.path.exists(missing):
        os.remove(missing)
    r = subprocess.run([sys.executable, str(MORNING), "--ledger", missing],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    check(r.returncode == 0, "morning_report.py --ledger <missing> exits 0",
          f"exit {r.returncode}")
    check("Nothing to report" in r.stdout,
          "and prints a plain-English 'nothing to report' line", r.stdout.strip()[:120])
    jargon = [w for w in ("DAY_POLICY", "MIN_PT1_R", "TREND_DEF", "R-multiple", "jsonl")
              if w in r.stdout]
    check(not jargon, "no flag names or jargon in what Austin reads", f"{jargon}")

    print("\n8. stale sentences in the committed V4 write-up and test")
    parity_src = PARITY.read_text(encoding="utf-8")
    flat = " ".join(parity_src.split())
    check("the one row that is `ship` (DAY_POLICY)" not in flat,
          "test docstring does not still call DAY_POLICY the shipped row")
    # the helper claims a clean env but passes no env= to subprocess.run
    m2 = re.search(r"def read_live_value.*?(?=\ndef )", parity_src, re.S)
    rlv = m2.group(0) if m2 else ""
    check(not ("clean env" in rlv and "env=" not in rlv),
          "read_live_value's 'clean env' docstring matches what it does")
    # is the guard wired into anything that actually runs?
    gate = (ROOT / "research" / "regression_gate.py").read_text(encoding="utf-8")
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    wired = ("test_live_follows_loop" in gate) or ("test_live_follows_loop" in claude)
    check(wired, "the parity guard is run by the verify gate or named in CLAUDE.md's verify line")
    md = (ROOT / "research" / "v4_referee.md")
    if md.exists():
        mdt = md.read_text(encoding="utf-8")
        check("DAY_POLICY=3fires_stop_win_or_2loss`" not in mdt
              and "| DAY_POLICY | ship |" not in mdt,
              "research/v4_referee.md does not still publish DAY_POLICY as shipped")

    print("\n" + "=" * 74)
    if FAILS:
        print("FAILED CHECKS (%d):" % len(FAILS))
        for f in FAILS:
            print("  - " + f)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
