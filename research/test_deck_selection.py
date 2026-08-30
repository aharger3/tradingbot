"""test_deck_selection.py -- the G8.2 self-check (research/g82_deck_fix.md).

research/g77_wrongchart.md found the g71 homework builder picked its
representative signal by BELIEF alone and never asked whether the engine TOOK
it: 25 of 30 served cards were signals the engine refused outright or traded
something else on the same chart. The fix (research/g82_deck_fix.md) makes
every card one of exactly two honest roles -- "traded" (the engine's own
booked trade) or "silent" (the engine refused the whole chart) -- picked to a
STATED quota, and keeps that role out of the rendered page the way the
`traded` field always was.

This is the thing that must never silently break again:

    1. a stated quota exists and is actually used to shape the pick, not just
       "prefer traded, fill the rest with whatever" (a regression could pick
       0% or 100% traded and nothing would say so);
    2. every served card's role is TRUE about what the engine did that
       session -- independently re-derived here from the book, not just
       trusted from the label the builder attached;
    3. the role/traded distinction -- the answer key -- never reaches the
       rendered HTML, in either role.

Does NOT build or serve a deck: calls `pick()` directly (read-only: it reads
the two-year book and the two-year price archive, both static files) and never
calls `main()`, `build_deck.py`'s HTML writer, or writes to the real
`OUT_HTML/OUT_MANIFEST` paths. `write_manifest` is exercised against a
tempfile.

    python research/test_deck_selection.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import g71_homework_build as hb  # noqa: E402
import g77_realtrade_pick as realtrade  # noqa: E402

SEED = 71
N_SLATES = 3   # small: enough to exercise every bucket without a slow probe


def main():
    ok = True

    # ---- 1. a stated quota exists, is a real fraction, and pick() uses it
    assert 0.0 < hb.TRADED_QUOTA_FRAC <= 1.0, \
        "TRADED_QUOTA_FRAC must be a stated fraction in (0, 1]"
    print("PASS  TRADED_QUOTA_FRAC is stated: %.2f" % hb.TRADED_QUOTA_FRAC)

    slates, seen, stats, census, level_census = hb.pick(N_SLATES, SEED)
    cards = [c for row in slates for c in row]
    assert cards, "pick() returned no cards -- cannot self-check an empty deck"

    for b in hb.BUCKETS:
        s = stats[b]
        assert "target_traded" in s and "role_counts" in s, \
            "bucket %s stats missing the quota fields -- the quota is not " \
            "being recorded" % b
        got_traded = s["role_counts"].get("traded", 0)
        # The quota is a CAP as well as a target -- a regression that just
        # takes every traded candidate available (old priority-fill behaviour)
        # would blow past it whenever traded candidates are plentiful (true
        # for BR: 398 raw candidates book-wide).
        assert got_traded <= s["target_traded"], (
            "bucket %s picked %d traded cards against a stated target of %d "
            "-- the quota is not capping the pick" % (b, got_traded, s["target_traded"]))
    print("PASS  every bucket's traded count is <= the stated per-bucket quota")

    # ---- 2. every card's role is independently true, re-derived from the book
    book = json.load(open(hb.BOOK, encoding="utf-8"))
    all_by_day = defaultdict(list)
    for r in book["trades"]:
        all_by_day[(r["sym"], r["day"])].append(r)

    n_ok = realtrade.role_guard(cards, label="test_deck_selection")
    assert n_ok == len(cards), "role_guard failed on the pick"

    for c in cards:
        assert c.get("role") in ("traded", "silent"), \
            "%s %s: role is %r, not traded/silent" % (c["symbol"], c["day"], c.get("role"))
        rows = all_by_day[(c["symbol"], c["day"])]
        real = realtrade.day_trade(rows)
        if c["role"] == "traded":
            assert real is not None, \
                "%s %s: role=traded but the engine booked nothing that day" \
                % (c["symbol"], c["day"])
            assert real.get("et") == c["rep"].get("et") \
                and real.get("setup") == c["rep"].get("setup"), (
                "%s %s: role=traded but the card's signal (%s %s) is not the "
                "engine's first booked trade (%s %s) -- this is exactly the "
                "wrong-chart bug" % (c["symbol"], c["day"], c["rep"].get("setup"),
                                    c["rep"].get("et"), real.get("setup"), real.get("et")))
        else:
            assert real is None, (
                "%s %s: role=silent but the engine booked a trade that day "
                "(%s %s) -- a silent-day card must be a true refusal"
                % (c["symbol"], c["day"], real.get("setup"), real.get("et")))
    print("PASS  every card's role independently matches g77_realtrade_pick.day_trade "
          "(%d cards, %d traded / %d silent)"
          % (len(cards), sum(1 for c in cards if c["role"] == "traded"),
             sum(1 for c in cards if c["role"] == "silent")))

    # no card may be built from a day the engine traded SOMETHING ELSE on --
    # the specific defect g77_wrongchart.md found in 14 of 30 served cards.
    wrong_chart = [c for c in cards
                  if (real := realtrade.day_trade(all_by_day[(c["symbol"], c["day"])]))
                  is not None
                  and not (real.get("et") == c["rep"].get("et")
                          and real.get("setup") == c["rep"].get("setup"))]
    assert not wrong_chart, "wrong-chart cards survived selection: %s" \
        % [(c["symbol"], c["day"]) for c in wrong_chart]
    print("PASS  no card was built from a signal the engine set aside for a different trade")

    # ---- 3. the answer key never reaches the rendered page, in either role
    by_role = {}
    for c in cards:
        by_role.setdefault(c["role"], c)
    assert set(by_role) == {"traded", "silent"} or len(cards) < 2, \
        "need at least one card of each role in this pick to test both -- " \
        "widen N_SLATES/seed"

    for role, c in by_role.items():
        html = hb.render_card(1, c)
        export = json.loads(html.split('data-export="', 1)[1].split('"', 1)[0]
                            .replace("&quot;", '"'))
        assert set(export) <= {"symbol", "date", "claimed_setup", "claimed_level", "bucket"}, \
            "role=%s card's export blob carries extra keys: %s" % (role, sorted(export))
        # role="img" is a pre-existing, unrelated SVG accessibility attribute --
        # strip it before scanning so it cannot mask (or fake) a real leak.
        stripped = html.lower().replace('role="img"', "")
        for term in ("traded", '"role"', "sgrade", "downgrade", '"outcome"'):
            assert term not in stripped, \
                "role=%s card HTML leaks the answer key -- found %r" % (role, term)
    print("PASS  rendered HTML carries no answer-key term, for a traded-role and a "
          "silent-role card")

    # ---- manifest actually records the role and the quota (requirement: "record
    # the quota and each card's role in the manifest")
    with tempfile.TemporaryDirectory() as td:
        tmp_path = os.path.join(td, "test-manifest.jsonl")
        hb.write_manifest(slates, path=tmp_path, target_traded=stats["BR"]["target_traded"])
        rows = [json.loads(l) for l in open(tmp_path, encoding="utf-8") if l.strip()]
    assert len(rows) == len(cards)
    for row in rows:
        assert row.get("role") in ("traded", "silent"), \
            "manifest row for %s missing/bad role" % row.get("card_id")
        assert row.get("traded_quota_frac") == hb.TRADED_QUOTA_FRAC
        assert row.get("bucket_target_traded") is not None
    print("PASS  the manifest records role and the stated quota for every card")

    print("OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
