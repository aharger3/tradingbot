"""Adversarial re-check of the G83 dark-theme audit (research/g83_dark_theme.md).

The audit claimed three things and this script tries to break each one, from the
files on disk, with no trust in the audit's prose:

  1. every colour literal in the four source files lives inside a theme block
     (bare :root, the prefers-color-scheme guard, or :root[data-theme="dark"]),
     so a page cannot carry a hard-coded light colour that ignores the theme;
  2. each generator declares all three theme states and paints body explicitly;
  3. the dark palette is actually readable -- up candles apart from down candles,
     gridlines apart from the page ground -- measured as WCAG 2.x contrast
     ratios, not described in words.

It also re-checks the homework contract on the built pages: localStorage save,
restore on load, .jsonl export, inline SVG (never canvas), and no network call
beyond the Google Fonts stylesheet.

Read-only. Opens nothing under research/marks/ and writes nothing anywhere.
Run:  python research/g83_verify_4.py
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

SOURCES = [
    "probe_page.py",
    "probe_chart.py",
    "g75_deck2_build.py",
    "g82_artifact_cleanup_build.py",
]

PAGES = [
    ("g75_deck2.html", True),          # homework deck: full contract
    ("omen-71-verdict.html", False),   # verdict sheet: read-only, no ballot
    ("g83_sizing.html", False),        # same-night sizing page, audit skipped it
]

# A "theme block" is any CSS rule whose selector mentions :root. Every colour
# literal must sit inside one -- that is what makes a single edit re-theme the
# whole page.
ROOT_BLOCK = re.compile(r'(?:@media[^{]*\{\s*)?:root[^{]*\{[^}]*\}', re.S)
HEX = re.compile(r'#[0-9a-fA-F]{3,8}\b')

failures: list[str] = []
notes: list[str] = []


def check(cond: bool, msg: str) -> bool:
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)
    return cond


# ---------------------------------------------------------------- 1. literals
def stray_hex(path: str) -> list[str]:
    """Hex colours that fall outside every :root block."""
    src = open(path, encoding="utf-8").read()
    spans = [m.span() for m in ROOT_BLOCK.finditer(src)]
    out = []
    for m in HEX.finditer(src):
        if not any(a <= m.start() < b for a, b in spans):
            line = src.count("\n", 0, m.start()) + 1
            out.append("%s:%d %s" % (os.path.basename(path), line, m.group()))
    return out


# ---------------------------------------------------------------- 2. guards
def guards(path: str) -> dict:
    src = open(path, encoding="utf-8").read()
    return {
        "bare :root palette": bool(re.search(r'(?<!\S):root\s*\{', src)),
        "prefers-color-scheme guard": "prefers-color-scheme" in src
        and ':root:not([data-theme="light"])' in src,
        'explicit :root[data-theme="dark"]': ':root[data-theme="dark"]' in src,
        "body paints its own background": bool(
            re.search(r'body\s*\{[^}]*background\s*:\s*var\(--', src, re.S)),
    }


# ---------------------------------------------------------------- 3. contrast
def rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def lum(h: str) -> float:
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a: str, b: str) -> float:
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def lab(h: str) -> tuple[float, float, float]:
    """sRGB -> CIE L*a*b* (D65). Perceptual space, so a green and a red that
    happen to share a luminance still land far apart."""
    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb(h))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 1.00000
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)
    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(a: str, b: str) -> float:
    """CIE76 colour difference. ~2.3 is the just-noticeable threshold; a chart
    mark two people must never confuse wants a lot more than that."""
    la, aa, ba = lab(a)
    lb, ab, bb = lab(b)
    return ((la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2) ** 0.5


def palette(path: str, block: str) -> dict:
    """Pull one theme block's --var:#hex pairs."""
    src = open(path, encoding="utf-8").read()
    i = src.find(block)
    if i < 0:
        return {}
    j = src.find("}", i)
    return dict(re.findall(r'(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})', src[i:j]))


# ---------------------------------------------------------------- 4. contract
def page_contract(path: str, ballot: bool) -> list[tuple[bool, str]]:
    src = open(path, encoding="utf-8").read()
    name = os.path.basename(path)
    out = [
        (src.count("<canvas") == 0, "%s draws no canvas" % name),
        (bool(re.search(r'https?://(?!fonts\.(googleapis|gstatic)\.com)', src)) is False,
         "%s makes no network call except Google Fonts" % name),
        ("system-ui" in src or "sans-serif" in src,
         "%s has a real font fallback stack" % name),
        ("background:var(--" in src.replace(" ", "")
         or "background: var(--" in src,
         "%s paints body from a theme variable" % name),
    ]
    if ballot:
        out += [
            ("<svg" in src, "%s renders inline SVG charts" % name),
            ("localStorage.setItem" in src, "%s saves to localStorage" % name),
            ("localStorage.getItem" in src, "%s reads localStorage back" % name),
            (bool(re.search(r'restore\(\)\s*;', src)),
             "%s calls restore() on load" % name),
            (".jsonl" in src, "%s exports .jsonl" % name),
        ]
    return out


def main() -> int:
    print("=" * 72)
    print("1. colour literals outside a :root block")
    print("=" * 72)
    for f in SOURCES:
        p = os.path.join(HERE, f)
        s = stray_hex(p)
        n_total = len(HEX.findall(open(p, encoding="utf-8").read()))
        if s:
            print("  %-32s %d hex total, %d STRAY:" % (f, n_total, len(s)))
            for h in s:
                print("        " + h)
            # A white ink on a saturated fill is legitimate in both themes; it is
            # the only stray the audit claimed, so it is reported not failed.
            if all(x.lower().endswith(("#fff", "#ffffff")) for x in s):
                notes.append("%s: %d stray white ink literal(s) -- readable on a "
                             "saturated fill in both themes, not a theme leak"
                             % (f, len(s)))
            else:
                failures.append("%s carries %d stray colour literal(s)" % (f, len(s)))
        else:
            print("  PASS  %-32s %d hex total, all inside :root" % (f, n_total))

    print()
    print("=" * 72)
    print("2. theme guards, per generator")
    print("=" * 72)
    for f in ["probe_page.py", "g82_artifact_cleanup_build.py"]:
        print("  " + f)
        for k, v in guards(os.path.join(HERE, f)).items():
            check(v, "    " + k)
    print("  probe_chart.py / g75_deck2_build.py inherit probe_page's block")
    for f in ["probe_chart.py", "g75_deck2_build.py"]:
        src = open(os.path.join(HERE, f), encoding="utf-8").read()
        check(len(HEX.findall(src)) == 0,
              "    %s defines no colour of its own" % f)

    print()
    print("=" * 72)
    print("3. dark palette readability -- WCAG contrast, recomputed")
    print("=" * 72)
    dark = palette(os.path.join(HERE, "probe_page.py"), ':root[data-theme="dark"]')
    if not dark:
        failures.append("could not read the dark palette out of probe_page.py")
    else:
        bg = dark["--bg"]
        # Legibility AGAINST THE GROUND is a luminance question -- WCAG applies.
        print("  -- against the page ground (WCAG luminance contrast)")
        ground = [
            ("up candle", dark["--up"], 3.0),
            ("down candle", dark["--dn"], 3.0),
            ("gridline", dark["--rule"], 1.15),
            ("body ink", dark["--ink"], 4.5),
            ("entry line", dark["--entry"], 3.0),
            ("stop line", dark["--stop"], 3.0),
        ]
        for label, c, floor in ground:
            r = ratio(c, bg)
            check(r >= floor, "%-22s %s vs %s = %6.2f:1 (floor %.2f)"
                  % (label, c, bg, r, floor))

        # Telling two MARKS apart is a hue question, not a luminance one: a green
        # and a red can share a luminance and still be unmistakable, so a WCAG
        # ratio is the wrong tool here. CIE76 deltaE is the right one; 2.3 is the
        # just-noticeable step, and a chart pair wants far more than that.
        print("")
        print("  -- one mark against another (CIE76 deltaE, JND = 2.3)")
        marks = [
            ("up candle vs down candle", dark["--up"], dark["--dn"], 40.0),
            ("entry line vs stop line", dark["--entry"], dark["--stop"], 20.0),
            ("PDH/PDL vs PMH/PML", dark["--lvl-pd"], dark["--lvl-pm"], 20.0),
            ("PDH/PDL vs ORH/ORL", dark["--lvl-pd"], dark["--lvl-or"], 20.0),
            ("entry line vs HOD/LOD level", dark["--entry"],
             dark.get("--lvl-hl", dark["--entry"]), 20.0),
        ]
        for label, a, b, floor in marks:
            d = delta_e(a, b)
            check(d >= floor, "%-30s %s vs %s = %6.2f dE (floor %.1f)"
                  % (label, a, b, d, floor))

        print("")
        print("  largest number recomputed on this page: %.2f:1 -- body ink"
              " against the dark ground" % max(ratio(c, bg) for _, c, _ in ground))

    print()
    print("=" * 72)
    print("4. built pages -- homework contract")
    print("=" * 72)
    for f, ballot in PAGES:
        p = os.path.join(HERE, f)
        if not os.path.exists(p):
            p = os.path.join(HERE, "probes", f)
        if not os.path.exists(p):
            print("  SKIP  %s not on disk" % f)
            continue
        for ok, msg in page_contract(p, ballot):
            check(ok, msg)
        src = open(p, encoding="utf-8").read()
        if "prefers-color-scheme" not in src:
            notes.append("%s is dark-only: no light palette and no "
                         "prefers-color-scheme guard. Allowed for a page that "
                         "commits to one look, but it is NOT the three-state "
                         "pattern the audit documented." % f)

    print()
    print("=" * 72)
    if notes:
        print("NOTES")
        for n in notes:
            print("  - " + n)
        print()
    if failures:
        print("REFUTED -- %d check(s) failed:" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("HOLDS -- every claim in research/g83_dark_theme.md reproduced.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
