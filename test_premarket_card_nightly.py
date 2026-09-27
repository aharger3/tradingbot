"""test_premarket_card_nightly.py -- premarket_card.py's _nightly_recap()
must surface OmenNightlyLoop's last real result on the 9am card.

R33: the nightly loop (research/nightly_loop.py, OmenNightlyLoop 20:00
weekdays) already writes one row per cycle to research/tape/nightly.md, but
premarket_card.py (the 9:00 ET pre-market brief) never read it -- the loop's
overnight work never reached the morning card. This locks down that
_nightly_recap() pulls the last row (reusing research/build_status.py's own
last_night_row(), not a second parser) and that build_card() wires it into
a "Nightly Recap" field.

    python test_premarket_card_nightly.py
"""
from __future__ import annotations

import sys

import premarket_card as pc

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    assert cond, f"{name}: {detail}"


def _run(fn, *args) -> None:
    try:
        fn(*args)
    except AssertionError as exc:
        FAILURES.append(str(exc))


NIGHTLY_FIXTURE = """# nightly loop receipts

| date | flag | decision | $/day a->b | green a->b | off_book_id -> on_book_id |
|---|---|---|---|---|---|
| 2026-09-19 | BNR_DISPLACEMENT_GATE | ship | -52.0 -> -54.0 | 11 -> 11 | d5ba41a -> baafa44 |
| 2026-09-26 | HTF_BIAS_GATE | hold | -21.0 -> -21.0 | 12 -> 12 | f479f81 -> f479f81 |
"""


def test_nightly_recap_reads_last_row(tmp_path) -> None:
    nightly = tmp_path / "nightly.md"
    nightly.write_text(NIGHTLY_FIXTURE, encoding="utf-8")

    line = pc._nightly_recap(nightly)

    check("recap has last row's date, not the first", "2026-09-26" in line, line)
    check("recap has last row's flag", "HTF_BIAS_GATE" in line, line)
    check("recap has last row's decision", "**hold**" in line, line)
    check("recap has last row's $/day pair", "-21.0 -> -21.0" in line, line)
    check("recap has last row's green pair", "12 -> 12" in line, line)
    check("recap does NOT surface an earlier row's flag",
          "BNR_DISPLACEMENT_GATE" not in line, line)


def test_nightly_recap_missing_file(tmp_path) -> None:
    line = pc._nightly_recap(tmp_path / "does-not-exist.md")
    check("missing nightly.md degrades to a placeholder, never raises",
          line == "no nightly run logged", line)


def test_build_card_wires_recap_into_a_field(tmp_path, monkeypatch=None) -> None:
    """build_card() must carry _nightly_recap()'s line into its own
    'Nightly Recap' field -- stub out the network-dependent pieces
    (yfinance calls, QQQ bias) so this stays a pure fixture test."""
    nightly = tmp_path / "nightly.md"
    nightly.write_text(NIGHTLY_FIXTURE, encoding="utf-8")

    mp = monkeypatch if monkeypatch is not None else _Monkeypatch()
    mp.setattr(pc, "_qqq_bias", lambda: "**NEUTRAL** gap +0.00%")
    mp.setattr(pc, "_yf_daily_context", lambda sym: (None, None, None, None, None, None, None))
    mp.setattr(pc, "_premarket_last", lambda sym: None)
    mp.setattr(pc, "NIGHTLY_MD", nightly)

    try:
        payload = pc.build_card(["TSLA"])
        fields = payload["embeds"][0]["fields"]
        recap_fields = [f for f in fields if f["name"] == "Nightly Recap"]
        check("build_card has exactly one Nightly Recap field", len(recap_fields) == 1,
              [f["name"] for f in fields])
        check("its value is this fixture's last row", "HTF_BIAS_GATE" in recap_fields[0]["value"],
              recap_fields[0]["value"])
    finally:
        if monkeypatch is None:
            mp.undo()


class _Monkeypatch:
    """Stand-in for pytest's monkeypatch fixture when this file is run as a
    plain script (see research/test_nightly_receipt.py, same pattern)."""

    def __init__(self):
        self._restore = []

    def setattr(self, obj, name, value):
        self._restore.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def undo(self):
        for obj, name, old in reversed(self._restore):
            setattr(obj, name, old)


def main() -> None:
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _run(test_nightly_recap_reads_last_row, tmp)
        _run(test_nightly_recap_missing_file, tmp)
        _run(test_build_card_wires_recap_into_a_field, tmp)

    if FAILURES:
        print("PREMARKET CARD NIGHTLY TEST FAILED: %d check(s)" % len(FAILURES))
        for f in FAILURES:
            print("  " + f)
        sys.exit(1)

    print("premarket_card nightly recap test ok: _nightly_recap() reads the "
          "last nightly.md row (not an earlier one), degrades cleanly when "
          "the file is missing, and build_card() wires it into a Nightly "
          "Recap field.")


if __name__ == "__main__":
    main()
