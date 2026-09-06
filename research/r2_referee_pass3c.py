"""R2 referee pass 3, part C -- provenance of the committed report.

R1's pass-4 referee found that a repaired report and the generator that is
documented to rebuild it had drifted apart: re-running the documented reproduce
command would have overwritten the corrected page with refuted text.  Same
check here, without re-running the (multi-minute, tree-dirtying) simulation:
every prose line of research/g211_reconcile_ladder.md must be traceable to a
string literal in research/g211_reconcile_ladder.py, and every hard-coded
number inside those literals is listed so a stale one is visible.

Usage: python research/r2_referee_pass3c.py
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(HERE, "g211_reconcile_ladder.md")
PY = os.path.join(HERE, "g211_reconcile_ladder.py")


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def main():
    md = open(MD, encoding="utf-8").read()
    py = open(PY, encoding="utf-8").read()
    # join Python's implicit string concatenation ("a" \n "b") so a report
    # sentence split across source lines still matches as one fragment, and
    # drop the f-string braces so an interpolated value is a wildcard.
    py_j = re.sub(r'"\s*\n\s*f?"', "", py)
    py_j = re.sub(r"\{[^{}]*\}", "\x00", py_j)
    py_n = norm(py_j)

    lines = [l for l in md.split("\n") if l.strip()]
    table = [l for l in lines if l.lstrip().startswith("|")]
    prose = [l for l in lines if not l.lstrip().startswith("|")
             and not l.strip().startswith("```")
             and l.strip() != "python research/g211_reconcile_ladder.py --procs 8"]

    print(f"report lines: {len(lines)}  table rows: {len(table)}  prose lines: {len(prose)}")
    print()
    print("A. PROSE PROVENANCE -- each prose line's longest literal fragment must appear in the .py")
    missing = []
    for l in prose:
        n = norm(l)
        # split the line on the places the generator interpolates a value, and
        # require the longest static fragment to be present verbatim in the .py
        frags = [f for f in re.split(r"[\$\d][\d,\.\%\-\>\/ ]*", n) if len(f) > 28]
        if not frags:
            frags = [n] if len(n) > 28 else []
        if not frags:
            continue
        best = max(frags, key=len)
        if norm(best) not in py_n:
            missing.append((l, best))
    print(f"   prose lines checked: {len(prose)}   NOT found in the generator: {len(missing)}")
    for l, frag in missing:
        print("   ORPHAN LINE:", l[:150])
        print("      fragment:", frag[:120])

    print()
    print("B. HARD-CODED NUMBERS inside the generator's report literals")
    # every numeric literal that sits inside an L.append(...) string, i.e. is
    # printed verbatim rather than computed
    hard = []
    for m in re.finditer(r'L\.append\((.*?)\)\n', py, re.S):
        blob = m.group(1)
        for sm in re.finditer(r'"([^"]*)"', blob):
            s = sm.group(1)
            for num in re.finditer(r'(?<![\{\.\w])(\d[\d,]*\.?\d*)\s*(%|x|/day|R\b)?', s):
                tok = num.group(0).strip()
                if tok in ("1", "2", "3", "4", "5", "6", "7", "8", "0", "11", "29"):
                    continue
                hard.append((tok, s[:90]))
    seen = set()
    for tok, ctx in hard:
        if (tok, ctx) in seen:
            continue
        seen.add((tok, ctx))
        print(f"   {tok:<12} in: {ctx}")

    print()
    print("C. SECTION HEADINGS in the report, and whether the generator emits them")
    for l in lines:
        if l.startswith("#"):
            body = norm(l.lstrip("# ").strip())
            print(f"   {'OK ' if body in py_n else 'ORPHAN'}  {l}")


if __name__ == "__main__":
    main()
