"""OMEN 8.0 R5 verify: the live promotion rule is expressed in S/A/C terms, a
test asserts it, and the promotion count over the sample is reported.

    python3 research/g94_verify.py

Exit 0 = pass, 1 = fail. Checks, mechanically:

 1. `live_scanner._tier` -- the live TRADE/WATCH gate -- reads
    `sig["austin_tier"]` and does NOT read the retired A+/A/B/C/D engine grade.
    Checked against the parsed AST of the function's executable body (the
    docstring and the comment block above it are allowed to discuss the old
    ladder; the CODE may not use it), and against its signature, which no longer
    carries a `grade` argument.
 2. `_emit_signal` calls that gate with the new signature, so the rule under
    test is the one the live path runs.
 3. `python3 test_live_tier_s_gate.py` exits 0 -- the promotion rule asserted
    case by case, including the case that changed behaviour (austin_tier A or C
    at engine grade A+ no longer promotes).
 4. `research/g94_live_tier.md` reports a promotion count for the OLD gate and
    the NEW gate over a named sample size, and the numbers in its headline table
    agree with `research/g94_live_tier_summary.json`, the artifact
    `research/g94_live_tier.py` actually wrote.
"""
import ast
import inspect
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

REPORT = os.path.join(HERE, "g94_live_tier.md")
SUMMARY = os.path.join(HERE, "g94_live_tier_summary.json")
TEST = os.path.join(ROOT, "test_live_tier_s_gate.py")


def check_gate():
    import live_scanner as ls

    params = list(inspect.signature(ls._tier).parameters)
    if "grade" in params:
        print(f"FAIL: live_scanner._tier still takes a `grade` argument: {params}")
        return 1

    fn = ast.parse(inspect.getsource(ls._tier).lstrip()).body[0]
    body = list(fn.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(getattr(body[0], "value", None), ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]                     # prose may name the retired ladder
    names, consts = set(), set()
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                consts.add(node.value)

    if "grade" in names or "grade" in consts:
        print("FAIL: live_scanner._tier's body still reads the engine grade")
        return 1
    if "austin_tier" not in consts:
        print("FAIL: live_scanner._tier's body does not read sig['austin_tier']")
        return 1
    ladder = {"A+", "B", "D", "X"} & consts
    if ladder:
        print(f"FAIL: A+/A/B/C/D ladder letters still in _tier's body: {sorted(ladder)}")
        return 1
    print(f"  ok   live_scanner._tier{tuple(params)} gates on sig['austin_tier'], "
          f"not on the retired engine grade")

    emit = inspect.getsource(ls._emit_signal)
    if "_tier(runner, sig, candle.timestamp)" not in emit:
        print("FAIL: _emit_signal does not call _tier(runner, sig, candle.timestamp) "
              "-- the gate under test is not the one the live path uses")
        return 1
    print("  ok   _emit_signal calls that gate (grade dropped from the call site)")
    return 0


def check_test():
    proc = subprocess.run([sys.executable, TEST], cwd=ROOT,
                          capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stdout.write(proc.stderr)
        print(f"FAIL: {os.path.basename(TEST)} exited {proc.returncode}")
        return 1
    print(f"  ok   {os.path.basename(TEST)} exits 0")
    return 0


def check_report():
    if not os.path.exists(REPORT):
        print(f"FAIL: {REPORT} does not exist")
        return 1
    if not os.path.exists(SUMMARY):
        print(f"FAIL: {SUMMARY} does not exist -- run research/g94_live_tier.py")
        return 1
    text = open(REPORT, encoding="utf-8").read()
    summary = json.load(open(SUMMARY, encoding="utf-8"))

    sample = summary.get("sample", {})
    for key, label in (("fired", "the signal sample size"),
                       ("captured", "the captured-signal count")):
        n = sample.get(key)
        if n is None:
            print(f"FAIL: {SUMMARY} carries no sample['{key}']")
            return 1
        if f"{n:,}" not in text and str(n) not in text:
            print(f"FAIL: {REPORT} never states {label} ({n})")
            return 1
    print(f"  ok   report states the sample: {sample['captured']:,} signals routed, "
          f"{sample['fired']:,} accepted, over {sample['days_run']:,} symbol-days")

    for arm in ("old", "new"):
        n = summary[arm]["promotions"]
        if not re.search(rf"(?<![\d,]){n}(?![\d])", text):
            print(f"FAIL: {REPORT} never states the {arm}-gate promotion count ({n})")
            return 1
    print(f"  ok   report states both promotion counts: "
          f"old {summary['old']['promotions']}, new {summary['new']['promotions']} "
          f"over the same sample")

    if summary["new"]["promotions"] == summary["old"]["promotions"]:
        print("FAIL: the two gates promote an identical number of signals, which "
              "would mean the rule did not actually change")
        return 1
    print(f"  ok   the gates differ: {summary['old']['promotions']} -> "
          f"{summary['new']['promotions']} promotions "
          f"({summary['old']['s_symday_recall']} -> "
          f"{summary['new']['s_symday_recall']} of Austin's "
          f"{sample['s_symdays']} S-marked symbol-days)")
    return 0


def main():
    rc = 0
    rc |= check_gate()
    rc |= check_test()
    rc |= check_report()
    if rc:
        return 1
    print("\nPASS: the live promotion rule is expressed in S/A/C terms, asserted by "
          "test_live_tier_s_gate.py, and the promotion count over the sample is "
          "reported in research/g94_live_tier.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
