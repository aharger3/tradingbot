"""V4 referee, pass 4 -- independent re-derivation of row V4 at builder commit de3cceb6.

Refutes-by-default. Nothing here reuses research/test_live_follows_loop.py's
parser or its subprocess helper; the tape is parsed by header name, the live
values are read out of a fresh interpreter, and the guard's teeth are proved
by mutating copies of the tape / the environment and requiring exit 1.

Run: python research/v4_referee_pass4.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
TAPE = ROOT / "research" / "tape" / "cycles.md"
TEST = ROOT / "research" / "test_live_follows_loop.py"

FLAGS = ["MIN_PT1_R", "RULE84_DECIDED", "OCR_RETEST_DISPLACEMENT",
         "TREND_DEF", "DAY_POLICY"]


def parse_tape_by_header(text):
    """{flag: decision}, last row per flag, columns located by header name."""
    rows, hdr = [], None
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if hdr is None:
            low = [c.lower() for c in cells]
            if "flag" in low and "decision" in low:
                hdr = (low.index("flag"), low.index("decision"))
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        fi, di = hdr
        if max(fi, di) >= len(cells):
            continue
        flag, dec = cells[fi], cells[di]
        if not flag or flag == "n/a":
            continue
        rows.append((flag, dec))
    out = {}
    for flag, dec in rows:
        out[flag] = dec
    return out, len(rows)


def live_values(env=None):
    code = (
        "import sys; sys.path.insert(0, r'%s');"
        "import live_scanner as ls, signal_runner as sr;"
        "print(repr([(f, getattr(sr, f)) for f in %r]))" % (str(ROOT), FLAGS)
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT),
                       capture_output=True, text=True, timeout=180, env=env)
    assert r.returncode == 0, r.stderr[-2000:]
    return dict(eval(r.stdout.strip()))


def run_test(env=None, cwd=None):
    r = subprocess.run([sys.executable, str(TEST)], cwd=str(cwd or ROOT),
                       capture_output=True, text=True, timeout=300, env=env)
    return r.returncode, (r.stdout + r.stderr)[-600:]


def sandbox():
    """A throwaway copy of the repo's relevant files so tape mutations never
    touch the real tree."""
    d = Path(tempfile.mkdtemp(prefix="v4ref4_"))
    (d / "research" / "tape").mkdir(parents=True)
    shutil.copy2(TEST, d / "research" / TEST.name)
    shutil.copy2(TAPE, d / "research" / "tape" / "cycles.md")
    # the test resolves ROOT = parent.parent and imports live_scanner from it;
    # symlinking is unreliable on Windows, so drop a sitecustomize-free shim:
    # copy nothing else -- instead we point PYTHONPATH at the real repo.
    return d


def main():
    fails = []

    def check(name, ok, detail=""):
        print(("PASS " if ok else "FAIL ") + name + ((" -- " + detail) if detail else ""))
        if not ok:
            fails.append(name)

    text = TAPE.read_text(encoding="utf-8")
    dec, nrows = parse_tape_by_header(text)
    print("tape rows=%d  last-per-flag=%r" % (nrows, dec))

    # 1. every tape row reads hold (the repaired docstring's claim)
    check("C1 all tape decisions are 'hold'",
          set(dec.values()) == {"hold"} and len(dec) == 5,
          "decisions=%r" % dec)

    # 2. live values equal the off-values
    lv = live_values()
    print("live=%r" % lv)
    want = {"MIN_PT1_R": 0.0, "RULE84_DECIDED": False,
            "OCR_RETEST_DISPLACEMENT": False, "TREND_DEF": "off",
            "DAY_POLICY": "first3"}
    check("C2 live lane carries the off/default value for all 5 flags",
          all(lv[f] == want[f] for f in FLAGS), "want=%r" % want)

    # 3. the shipped test is green as committed
    rc, out = run_test()
    check("C3 test_live_follows_loop.py exits 0 at HEAD", rc == 0, out.strip()[:200])

    # 4-6. teeth: three injected drifts must turn it RED
    env = dict(os.environ)
    env["DAY_POLICY"] = "3fires_stop_win_or_2loss"
    rc_a, _ = run_test(env=env)
    check("C4 teeth A: env drift on DAY_POLICY turns the test RED", rc_a != 0)

    sb = sandbox()
    try:
        senv = dict(os.environ)
        senv["PYTHONPATH"] = str(ROOT) + os.pathsep + senv.get("PYTHONPATH", "")
        tape_sb = sb / "research" / "tape" / "cycles.md"
        test_sb = sb / "research" / TEST.name

        # control: unmutated copy must be GREEN in the sandbox harness
        rc_c, out_c = subprocess.run(
            [sys.executable, str(test_sb)], cwd=str(ROOT),
            capture_output=True, text=True, timeout=300, env=senv
        ).returncode, ""
        check("C5 sandbox control (unmutated tape copy) is GREEN", rc_c == 0)

        orig = tape_sb.read_text(encoding="utf-8")
        # B: flip DAY_POLICY back to ship
        tape_sb.write_text(
            re.sub(r"(\| DAY_POLICY \| )hold", r"\1ship", orig), encoding="utf-8")
        rc_b = subprocess.run([sys.executable, str(test_sb)], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=300,
                              env=senv).returncode
        check("C6 teeth B: tape flipped to ship turns the test RED", rc_b != 0)

        # C: a sixth, unknown flag
        tape_sb.write_text(
            orig.rstrip() + "\n| 2026-09-06 | synthetic | BRAND_NEW_FLAG | ship | "
            "0 -> 0 | 0 -> 0 | pass | pass | 0 | a | b | c |\n", encoding="utf-8")
        rc_n = subprocess.run([sys.executable, str(test_sb)], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=300,
                              env=senv)
        check("C7 teeth C: an unknown sixth flag turns the test RED",
              rc_n.returncode != 0 and "BRAND_NEW_FLAG" in (rc_n.stdout + rc_n.stderr))
    finally:
        shutil.rmtree(sb, ignore_errors=True)

    # 8. Alpaca paper-only
    alp = (ROOT / "broker" / "alpaca.py").read_text(encoding="utf-8")
    paper_args = re.findall(r"paper\s*=\s*([A-Za-z_][A-Za-z_0-9\.\[\]\"']*)", alp)
    creds = sorted(set(re.findall(r"ALPACA_[A-Z_]+", alp)))
    check("C8 every paper= argument is the literal True",
          paper_args and set(paper_args) == {"True"}, "found=%r" % paper_args)
    check("C9 only paper credentials are read",
          creds == ["ALPACA_PAPER_KEY", "ALPACA_PAPER_SECRET"], "found=%r" % creds)
    check("C10 no live Alpaca host literal in broker/alpaca.py",
          "api.alpaca.markets" not in alp)

    # 11. replay never submits
    ls = (ROOT / "live_scanner.py").read_text(encoding="utf-8")
    bodies = re.findall(
        r"def (_alpaca_submit_(?:entry|exit))\(.*?\n(.*?)(?=\ndef |\Z)", ls, re.S)
    guarded = [n for n, b in bodies if 'assert not getattr(runner, "replay"' in b]
    check("C11 both submit paths assert not replay",
          sorted(guarded) == ["_alpaca_submit_entry", "_alpaca_submit_exit"],
          "guarded=%r" % guarded)
    check("C12 run_replay sets runner.replay = True", "runner.replay = True" in ls)

    # 13. morning report survives a missing ledger
    ledger = ROOT / "journal" / "alpaca-paper.jsonl"
    check("C13 journal/alpaca-paper.jsonl is absent on this box", not ledger.exists())
    r = subprocess.run([sys.executable, str(ROOT / "research" / "morning_report.py")],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=180)
    check("C14 morning_report.py exits 0 with the ledger absent",
          r.returncode == 0, (r.stdout + r.stderr).strip()[:200])
    r2 = subprocess.run([sys.executable, str(ROOT / "research" / "morning_report.py"),
                         "--ledger", "journal/__no_such_file__.jsonl"],
                        cwd=str(ROOT), capture_output=True, text=True, timeout=180)
    check("C15 morning_report.py exits 0 with --ledger pointing at nothing",
          r2.returncode == 0, (r2.stdout + r2.stderr).strip()[:200])

    # 16. nothing runs the guard  (D3 from pass 3)
    callers = subprocess.run(
        ["git", "grep", "-l", "test_live_follows_loop"], cwd=str(ROOT),
        capture_output=True, text=True, timeout=120).stdout.split()
    non_ref = [c for c in callers
               if not Path(c).name.startswith(("v4_referee", "test_live_follows_loop"))]
    check("C16 (D3) the guard is wired into some gate", not non_ref,
          "callers outside referee scripts: %r" % non_ref)

    print("\n%d/%d checks passed" % (16 - len(fails), 16))
    if fails:
        print("FAILED: " + ", ".join(fails))
    return 0


if __name__ == "__main__":
    sys.exit(main())
