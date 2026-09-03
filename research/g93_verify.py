"""OMEN 8.0 R4 verify: `grep -c 'HTF_BIAS_VETO' omen_bot.py` and the rulebook's
claim agree, and a test asserts the shipped default explicitly.

    python3 research/g93_verify.py

Exit 0 = pass, 1 = fail.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OMEN_BOT = os.path.join(ROOT, "omen_bot.py")
TEST = os.path.join(ROOT, "test_htf_grade_veto_default.py")

# The vault repo isn't a tradingbot artifact, so its clone location varies by
# session -- try the common candidates rather than hardcoding one path.
VAULT_CANDIDATES = [
    "/home/user/obsidian-vault",
    os.path.join(os.path.dirname(ROOT), "obsidian-vault"),
    os.path.expanduser("~/obsidian-vault"),
]


def find_rulebook():
    for base in VAULT_CANDIDATES:
        path = os.path.join(base, "Projects", "omen-rulebook.md")
        if os.path.exists(path):
            return path
    return None


def main():
    try:
        code_text = open(OMEN_BOT, encoding="utf-8").read()
    except OSError as e:
        print(f"FAIL: cannot read {OMEN_BOT}: {e}")
        return 1
    actual_count = code_text.count("HTF_BIAS_VETO")

    rulebook_path = find_rulebook()
    if rulebook_path is None:
        print(f"FAIL: could not find omen-rulebook.md in any of {VAULT_CANDIDATES} "
              f"-- clone aharger3/obsidian-vault first")
        return 1
    rulebook_text = open(rulebook_path, encoding="utf-8").read()

    m = re.search(
        r"HTF_BIAS_VETO.{0,200}?\bappears exactly\s+(\d+)\s+time", rulebook_text, re.DOTALL)
    if not m:
        print(f"FAIL: {rulebook_path} does not state an explicit count for "
              f"HTF_BIAS_VETO's appearances in omen_bot.py (looked for "
              f"'appears exactly N time...')")
        return 1
    claimed_count = int(m.group(1))

    if actual_count != claimed_count:
        print(f"FAIL: omen_bot.py contains 'HTF_BIAS_VETO' {actual_count} time(s), "
              f"but {rulebook_path} claims {claimed_count}")
        return 1
    print(f"  ok   grep -c 'HTF_BIAS_VETO' omen_bot.py = {actual_count}, "
          f"matches the rulebook's claim ({rulebook_path})")

    proc = subprocess.run([sys.executable, TEST], cwd=ROOT,
                          capture_output=True, text=True)
    print(proc.stdout, end="")
    if proc.returncode != 0:
        print(proc.stderr, end="")
        print(f"FAIL: {TEST} exited {proc.returncode}")
        return 1
    print(f"  ok   {os.path.basename(TEST)} exits 0 -- shipped default asserted")

    print("\nPASS: the rulebook's claim about HTF_BIAS_VETO's presence in omen_bot.py "
          "is accurate, and the shipped default (HTF_GRADE_VETO off) is test-asserted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
