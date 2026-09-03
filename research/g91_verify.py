"""OMEN 8.0 R2 verify: research/g90_fill_arms.md carries a fifth row `mid_candle`
with the same columns as R1's table, and a one-line verdict naming which of
close vs mid pays more and by how much, with an error bar. Exit 0 = pass."""
import re
import sys

PATH = "g90_fill_arms.md"


def main():
    try:
        text = open(PATH).read()
    except OSError as e:
        print(f"FAIL: cannot read {PATH}: {e}")
        return 1

    row_re = re.compile(
        r"\|\s*(\w+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)%\s*\|\s*([+\-][\d.]+)\s*\|"
        r"\s*(\d+)\s*\|\s*(\d+)/(\d+)\s*\|\s*\$([\d,]+)\s*\|")
    rows = {}
    for line in text.splitlines():
        m = row_re.match(line)
        if m:
            rows[m.group(1)] = dict(trades=int(m.group(2)), mean_r=float(m.group(5)))

    if "mid_candle" not in rows:
        print("FAIL: no `mid_candle` row found with the same columns as the other arms")
        return 1
    if "close" not in rows:
        print("FAIL: no `close` comparator row found")
        return 1
    if rows["mid_candle"]["trades"] <= 0:
        print("FAIL: mid_candle has zero trades")
        return 1

    # a one-line verdict naming which of close vs mid pays more, with an error
    # bar (a numeric CI in brackets) somewhere in the document
    verdict_line = re.search(
        r"^.*\bclose\b.*\bmid[_ ]?candle\b.*\bpays\b.*\[[+\-]?[\d.]+.*,\s*[+\-]?[\d.]+\].*$",
        text, re.IGNORECASE | re.MULTILINE)
    if not verdict_line:
        print("FAIL: no line found naming which of close vs mid pays more, with a "
              "bracketed error bar")
        return 1

    print(f"PASS: mid_candle row present ({rows['mid_candle']['trades']} trades, "
          f"mean R {rows['mid_candle']['mean_r']:+.4f}), close comparator present "
          f"({rows['close']['trades']} trades, mean R {rows['close']['mean_r']:+.4f}), "
          f"verdict line with error bar found:")
    print(f"  {verdict_line.group(0).strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
