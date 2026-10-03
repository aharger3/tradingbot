"""Tests for rubric_check (E4). Synthetic bars only; the real dataset is not needed.
Run: python -m pytest research/agent_runs/v3-e4-rubric -q"""
import os, sys, csv, gzip
import pytest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rubric_check as rc

LEVEL = 100.0


def mk(rows):
    """rows of (o, h, l, c) -> bar dicts."""
    return [dict(o=o, h=h, l=l, c=c) for (o, h, l, c) in rows]


def flat(n, px=99.0, rng=0.4):
    """n quiet up-coloured bars around px, body 0.2 (no counter-coloured candles)."""
    return [(px - 0.1, px + rng / 2, px - rng / 2, px + 0.1) for _ in range(n)]


def clean_long():
    """quiet base, one big displacement bar through 100, 2 up bars, retest touching 100, up trigger."""
    rows = flat(12)
    rows.append((99.0, 101.6, 98.9, 101.5))      # 12: break, body 2.5 vs avg 0.2
    rows.append((101.5, 102.0, 101.4, 101.9))    # 13: up
    rows.append((101.9, 102.1, 101.7, 102.0))    # 14: up
    rows.append((102.0, 102.1, 100.1, 102.05))   # 15: retest touches 100 (within eps), closes up
    return mk(rows)


def mirror(bars, axis=200.0):
    return [dict(o=axis - b["o"], h=axis - b["l"], l=axis - b["h"], c=axis - b["c"]) for b in bars]


# ---------------------------------------------------------------- grade arithmetic
@pytest.mark.parametrize("net,g", [(-1, "S"), (0, "S"), (1, "A"), (2, "C"), (3, "C"), (7, "C")])
def test_net_to_grade_floors_at_c(net, g):
    assert rc.net_to_grade(net) == g


# ---------------------------------------------------------------- break bar
def test_break_bar_is_the_close_through_bar():
    b = clean_long()
    assert rc.break_bar(b, 15, LEVEL, True) == 12


def test_break_bar_none_when_never_crossed():
    b = mk(flat(8, px=101.0))
    assert rc.break_bar(b, 7, LEVEL, True) is None


# ---------------------------------------------------------------- the eight variables
def test_clean_setup_trips_nothing_long_and_short():
    b = clean_long()
    assert rc.trips(b, 15, LEVEL, True, rc.Spec()) == []
    assert rc.trips(mirror(b), 15, 200 - LEVEL, False, rc.Spec()) == []


def test_no_displacement_small_break_body():
    rows = flat(12)
    rows.append((99.95, 100.1, 99.9, 100.05))    # break, body 0.1 < 1.5 * avg body 0.2
    rows += [(100.05, 100.2, 99.98, 100.15)]
    rows += [(100.15, 100.2, 100.0, 100.18)]     # retest touches
    b = mk(rows)
    assert "no_displacement" in rc.trips(b, len(b) - 1, LEVEL, True, rc.Spec())


def test_no_displacement_unjudgeable_when_no_break_unless_engine_convention():
    b = mk(flat(8, px=101.0))
    assert "no_displacement" not in rc.trips(b, 7, LEVEL, True, rc.Spec())
    assert "no_displacement" in rc.trips(b, 7, LEVEL, True, rc.Spec(nobreak_trips_disp=True))


def test_stale_retest_boundary_is_strictly_more_than_ten_bars():
    def build(gap):
        rows = flat(12) + [(99.0, 101.6, 98.9, 101.5)]
        rows += [(101.5, 102.0, 101.4, 101.9)] * (gap - 1)      # bars br+1 .. br+gap-1 stay away
        rows += [(101.9, 102.1, 100.1, 102.0)]                  # br+gap touches
        return mk(rows)
    b10, b11 = build(10), build(11)
    assert "stale_retest" not in rc.trips(b10, len(b10) - 1, LEVEL, True, rc.Spec())
    assert "stale_retest" in rc.trips(b11, len(b11) - 1, LEVEL, True, rc.Spec())


def test_level_not_respected_counts_closes_through_not_wicks():
    base = clean_long()
    wick = list(base); wick[15] = dict(o=102.0, h=102.1, l=99.5, c=102.05)   # wick through, close above
    assert "level_not_respected" not in rc.trips(wick, 15, LEVEL, True, rc.Spec())
    one = list(base); one[14] = dict(o=101.9, h=101.95, l=99.4, c=99.6)       # one close back through
    assert "level_not_respected" not in rc.trips(one, 15, LEVEL, True, rc.Spec(t3=2))
    assert "level_not_respected" in rc.trips(one, 15, LEVEL, True, rc.Spec(t3=1))
    two = list(one); two[13] = dict(o=101.9, h=101.95, l=99.3, c=99.5)
    assert "level_not_respected" in rc.trips(two, 15, LEVEL, True, rc.Spec(t3=2))


def test_exhausted_after_big_move_from_open():
    b = clean_long()
    assert "exhausted" not in rc.trips(b, 15, LEVEL, True, rc.Spec())
    b[0] = dict(o=60.0, h=99.2, l=59.0, c=99.1)       # session open far below -> spent move
    assert "exhausted" in rc.trips(b, 15, LEVEL, True, rc.Spec())


def test_counter_trend_not_respected_needs_two_unbought_counter_candles():
    rows = flat(12) + [(99.0, 101.6, 98.9, 101.5),
                       (101.5, 102.6, 101.0, 101.1),     # red, high 102.6
                       (101.1, 101.3, 100.7, 100.9),     # red, high 101.3; nothing closes above 102.6
                       (100.9, 101.0, 100.1, 100.5),     # red; nothing closes above 101.3
                       (100.5, 100.9, 100.1, 100.4)]
    b = mk(rows)
    assert "counter_trend_not_respected" in rc.trips(b, len(b) - 1, LEVEL, True, rc.Spec())
    # only one red that is not bought back -> below the threshold of 2
    rows2 = flat(12) + [(99.0, 101.6, 98.9, 101.5),
                        (101.5, 102.0, 101.4, 101.9),
                        (101.9, 102.1, 101.7, 102.0),
                        (102.0, 102.1, 100.1, 102.05)]
    assert "counter_trend_not_respected" not in rc.trips(mk(rows2), len(rows2) - 1, LEVEL, True, rc.Spec(counter_post_break=True))


def test_counter_trend_post_break_window_ignores_pre_break_reds():
    # three pre-break red candles that are never bought back: the 12-bar window sees them, post-break does not
    reds = [(99.5, 99.6, 98.9, 99.0)] * 3
    rows = flat(4) + reds + flat(5) + [(99.0, 101.6, 98.9, 101.5), (101.5, 102.0, 101.4, 101.9),
                                       (101.9, 102.1, 101.7, 102.0), (102.0, 102.1, 100.1, 102.05)]
    b = mk(rows)
    i = len(b) - 1
    assert "counter_trend_not_respected" in rc.trips(b, i, LEVEL, True, rc.Spec())
    assert "counter_trend_not_respected" not in rc.trips(b, i, LEVEL, True, rc.Spec(counter_post_break=True))


def test_no_retest_and_break_then_rejection():
    rows = flat(12) + [(99.0, 101.6, 98.9, 101.5), (101.5, 102.0, 101.4, 101.9), (101.9, 102.4, 101.8, 102.3)]
    b = mk(rows)
    t = rc.trips(b, len(b) - 1, LEVEL, True, rc.Spec())
    assert "no_retest" in t and "break_then_rejection" not in t
    rows2 = flat(12) + [(99.0, 101.6, 98.9, 101.5), (101.5, 101.6, 99.2, 99.4), (99.4, 100.9, 99.3, 100.8)]
    b2 = mk(rows2)
    assert "break_then_rejection" in rc.trips(b2, len(b2) - 1, LEVEL, True, rc.Spec())


def ocr_setup():
    return mk(flat(12) + [(99.0, 101.6, 98.9, 101.5),
                          (101.5, 101.9, 101.4, 101.8),
                          (101.8, 101.85, 100.5, 100.8),    # 14: the OCR (down candle between up candles)
                          (100.8, 102.0, 100.7, 101.9),
                          (101.9, 102.1, 100.1, 102.0)])    # retest touches level, closes up


def test_ocr_and_confluence():
    b = ocr_setup()
    i = len(b) - 1
    assert rc.find_ocr(b, i, True) == 14
    assert rc.has_confluence(b, i, LEVEL, True) is True
    bad = list(b); bad[16] = dict(o=100.8, h=101.0, l=100.2, c=100.3)         # later close through the OCR low
    assert rc.ocr_not_respected(bad, i, LEVEL, True) is True
    assert rc.has_confluence(bad, i, LEVEL, True) is False


def test_ocr_must_be_isolated():
    rows = flat(12) + [(99.0, 101.6, 98.9, 101.5), (101.5, 101.9, 101.4, 101.8),
                       (101.8, 101.85, 101.0, 101.1), (101.1, 101.2, 100.6, 100.7),   # two reds in a row
                       (100.7, 102.0, 100.6, 101.9), (101.9, 102.1, 100.1, 102.0)]
    b = mk(rows)
    assert rc.find_ocr(b, len(b) - 1, True) is None


def test_large_counter_body_contained_in_neighbours():
    rows = flat(12) + [(99.0, 101.6, 98.9, 101.5),
                       (101.5, 102.6, 101.0, 102.5),
                       (102.5, 102.6, 101.5, 101.6),   # big red body inside the neighbours' span
                       (101.6, 102.7, 101.0, 102.6),
                       (102.6, 102.7, 100.1, 102.0)]
    b = mk(rows)
    assert rc.large_counter_body(b, len(b) - 1, LEVEL, True) is True
    rows[-3] = (103.3, 103.4, 101.5, 101.6)             # pokes outside the neighbours -> a breakout, not chop
    assert rc.large_counter_body(mk(rows), len(rows) - 1, LEVEL, True) is False


def test_chase_when_close_far_beyond_level():
    b = clean_long()
    assert rc.chase(b, 15, LEVEL, True) is True       # 102.05 is 2% beyond 100
    assert rc.chase(b, 15, 101.9, True) is False


# ---------------------------------------------------------------- score arithmetic
def test_one_downgrade_plus_confluence_is_still_s():
    b = ocr_setup()
    sp = rc.Spec(disp_exempt=False)
    b[0] = dict(o=60.0, h=99.2, l=59.0, c=99.1)       # force exactly one downgrade: exhausted
    r = rc.score(b, len(b) - 1, LEVEL, True, sp)
    assert r["confluence"] is True
    assert r["tripped"] == ["exhausted"] and r["net"] == 0 and r["grade"] == "S"


def test_two_downgrades_no_confluence_is_c():
    b = clean_long()
    b[0] = dict(o=60.0, h=99.2, l=59.0, c=99.1)                        # exhausted
    b[14] = dict(o=101.9, h=101.95, l=99.4, c=99.6)                    # two closes back through
    b[13] = dict(o=101.9, h=101.95, l=99.3, c=99.5)
    r = rc.score(b, 15, LEVEL, True, rc.Spec(disp_exempt=False))
    assert r["grade"] == "C" and r["net"] >= 2


def test_weight_two_reading_doubles_level_and_counter_costs():
    b = clean_long()
    b[14] = dict(o=101.9, h=101.95, l=99.4, c=99.6)
    b[13] = dict(o=101.9, h=101.95, l=99.3, c=99.5)
    cnt = rc.score(b, 15, LEVEL, True, rc.Spec(disp_exempt=False))
    dbl = rc.score(b, 15, LEVEL, True, rc.Spec(disp_exempt=False, w2=True))
    assert "level_not_respected" in cnt["tripped"] and dbl["cost"] == cnt["cost"] + 1


def test_displacement_exempt_when_confluence():
    rows = flat(12) + [(99.95, 100.1, 99.9, 100.05),
                       (100.05, 100.6, 100.0, 100.5),
                       (100.5, 100.55, 100.15, 100.2),    # OCR (down between up candles)
                       (100.2, 100.9, 100.18, 100.8),
                       (100.8, 100.9, 100.1, 100.7)]
    b = mk(rows)
    i = len(b) - 1
    on = rc.score(b, i, LEVEL, True, rc.Spec(disp_exempt=True))
    off = rc.score(b, i, LEVEL, True, rc.Spec(disp_exempt=False))
    assert on["confluence"] and "no_displacement" in off["tripped"] and "no_displacement" not in on["tripped"]


def test_drop_switches_off_a_variable_and_confluence():
    b = clean_long()
    b[0] = dict(o=60.0, h=99.2, l=59.0, c=99.1)
    assert rc.trips(b, 15, LEVEL, True, rc.Spec())[0] == "exhausted"
    assert rc.trips(b, 15, LEVEL, True, rc.Spec(drop=("exhausted",))) == []
    o = ocr_setup()
    assert rc.score(o, len(o) - 1, LEVEL, True, rc.Spec())["confluence"] is True
    assert rc.score(o, len(o) - 1, LEVEL, True, rc.Spec(drop=("confluence",)))["confluence"] is False


def test_score_is_causal():
    b = clean_long()
    r1 = rc.score(b, 15, LEVEL, True, rc.Spec())
    junk = b + mk([(50, 200, 1, 3)] * 5)
    assert r1 == rc.score(junk, 15, LEVEL, True, rc.Spec())


def test_score_returns_none_without_bars():
    assert rc.score([], 0, LEVEL, True, rc.Spec()) is None


# ---------------------------------------------------------------- metrics
HIS = ["S", "S", "S", "A", "A", "C"]
RUB = ["S", "A", "S", "A", "S", "C"]


def test_confusion_and_exact_match():
    m = rc.metrics(HIS, RUB)
    assert m["exact"] == pytest.approx(4 / 6)
    assert m["confusion"]["S"] == {"S": 2, "A": 1, "C": 0}
    assert m["confusion"]["A"] == {"S": 1, "A": 1, "C": 0}
    assert m["confusion"]["C"] == {"S": 0, "A": 0, "C": 1}


def test_s_recall_and_precision():
    m = rc.metrics(HIS, RUB)
    assert m["s_recall"] == pytest.approx(2 / 3)        # his 3 S, rubric hits 2
    assert m["s_precision"] == pytest.approx(2 / 3)     # rubric 3 S, 2 are his S
    assert m["majority_baseline"] == pytest.approx(0.5)


def test_metrics_handles_no_rubric_s():
    m = rc.metrics(["S", "A"], ["A", "A"])
    assert m["s_precision"] is None and m["s_recall"] == 0.0


def test_shuffle_p_is_small_for_perfect_and_large_for_random_like():
    his = ["S"] * 30 + ["A"] * 30
    assert rc.shuffle_p(his, list(his), iters=300, seed=1) < 0.02
    rub = ["S", "A"] * 30
    assert rc.shuffle_p(his, rub, iters=300, seed=1) > 0.2


# ---------------------------------------------------------------- mismatch picker
def test_pick_mismatches_groups_by_decisive_variable_and_is_deterministic():
    rows = []
    def r(sid, date, his, rub, tripped, conf=False, note=""):
        rows.append(dict(sig_id=sid, date=date, his=his, rub=rub, tripped=tripped, confluence=conf, note=note))
    r("a", "2025-01-01", "S", "A", ["no_displacement"])
    r("b", "2025-01-02", "S", "A", ["no_displacement"])
    r("c", "2025-01-03", "S", "C", ["no_displacement", "exhausted"])
    r("d", "2025-01-04", "A", "S", [])
    r("e", "2025-01-05", "S", "S", [])
    out = rc.pick_mismatches(rows, k=5)
    assert out[0]["sig_id"] == "a"                      # biggest group (no_displacement x3), cleanest example
    assert {o["sig_id"] for o in out} <= {"a", "b", "c", "d"}
    assert out == rc.pick_mismatches(list(reversed(rows)), k=5)
    assert all(o["his"] != o["rub"] for o in out)


# ---------------------------------------------------------------- day-level permutation
def test_day_perm_p_detects_separation_and_preserves_day_structure():
    days = [f"d{k}" for k in range(40)]
    flag = [k % 2 == 0 for k in range(40)]
    rv = [1.0 if f else -1.0 for f in flag]
    assert rc.day_perm_p(days, flag, rv, iters=300, seed=3) < 0.02
    assert rc.day_perm_p(days, flag, [0.5] * 40, iters=100, seed=3) == 1.0


# ---------------------------------------------------------------- loader
def test_load_rows_locates_signal_bar_by_time():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "s_trades.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["sig_id", "grade", "sym", "date", "sig_t", "side", "level_px", "eng_level", "half", "has_bars", "note", "R2_wick"])
            w.writerow(["X_2025-01-02_0933_L", "S", "X", "2025-01-02", "09:33", "L", "100", "OR high", "H1", "1", "hi", "1.5"])
            w.writerow(["Y_2025-01-02_0933_S", "one-off", "Y", "2025-01-02", "09:33", "S", "50", "PMH", "H1", "0", "", ""])
        with gzip.open(os.path.join(d, "s_bars_0930_1100.csv.gz"), "wt", newline="") as fh:
            w = csv.writer(fh); w.writerow(["sig_id", "t", "o", "h", "l", "c", "v"])
            for k, t in enumerate(["09:30", "09:31", "09:32", "09:33", "09:34"]):
                w.writerow(["X_2025-01-02_0933_L", t, 99 + k, 100 + k, 98 + k, 99.5 + k, 10])
        rows, skipped = rc.load_rows(d)
    assert len(rows) == 1 and skipped == 1                  # the no-bars row is skipped and counted
    x = rows[0]
    assert x["i"] == 3 and x["is_long"] is True and x["his"] == "S" and x["level"] == 100.0 and x["start"] == 5
    assert x["bars"][3] == dict(o=102.0, h=103.0, l=101.0, c=102.5)


def test_first_crossing_not_most_recent_so_whipsaw_is_visible():
    # break, close back through twice, re-break, retest: the break is the FIRST crossing
    rows = flat(12) + [(99.0, 101.6, 98.9, 101.5), (101.5, 101.6, 99.2, 99.4), (99.4, 99.6, 99.0, 99.3),
                       (99.3, 101.2, 99.2, 101.0), (101.0, 101.3, 100.1, 101.2)]
    b = mk(rows)
    i = len(b) - 1
    assert rc.break_bar(b, i, LEVEL, True) == 12
    t = rc.trips(b, i, LEVEL, True, rc.Spec())
    assert "break_then_rejection" in t and "level_not_respected" in t


def test_or_level_break_cannot_precede_start_bar():
    b = clean_long()
    assert rc.break_bar(b, 15, LEVEL, True, 5) == 12
    assert rc.break_bar(b, 15, LEVEL, True, 13) is None


def test_grid_is_declared_and_bounded():
    names = [n for n, _ in rc.GRID]
    assert len(names) == len(set(names)) <= rc.MAX_VARIANTS == 34
    assert rc.PRIMARY in names


# ---------------------------------------------------------------- referee fixes (E4-rubric)
@pytest.mark.parametrize("note,his,sig_t,mark_t,expect", [
    ("3 candles earlier is an S entry, reclaim", "A", "09:45", "09:45", True),
    ("{'entry': '9:39 A entry no displacement, S entry at 10'}", "S", "09:39", "09:39", True),   # 9:39 is graded A, his mark says S
    ("{'s_call': '10:04 S entry, double chop areas'}", "S", "10:04", "10:04", False),           # same time, same letter
    ("{'s_call': '10:04  S entry'}", "S", "10:04", "10:03", False),
    ("{'min': '9:49', 'why': 'as candle forming not lod. a entry few candles earlier'}", "S", "09:49", "09:49", True),
    ("{'comment': \"4 candle earlier may be entry but my downgrade is entry didn't close\"}", "A", "09:40", "09:39", False),  # 'is entry' is not 's entry'
    ("{'min': '9:44', 'why': 'A candle entry wouldve been 9:36, rare s entry after an a'}", "S", "09:44", "09:44", True),
    ("no clean break it just respect pivot structures", "A", "10:20", "10:23", False),
    ("", "S", "10:20", "10:20", False),
])
def test_note_reassigns_entry(note, his, sig_t, mark_t, expect):
    assert rc.note_reassigns_entry(note, his, sig_t, mark_t) is expect


def test_pick_mismatches_skips_rows_whose_note_reassigns_the_entry():
    rows = []
    def r(sid, date, tripped, reassigns=False):
        rows.append(dict(sig_id=sid, date=date, his="S", rub="A", tripped=tripped, confluence=False, note="", reassigns=reassigns))
    r("clean_but_relabelled", "2025-01-01", ["counter_trend_not_respected"], reassigns=True)
    r("next_cleanest", "2025-01-02", ["counter_trend_not_respected"])
    r("messier", "2025-01-03", ["counter_trend_not_respected", "exhausted"])
    out = rc.pick_mismatches(rows, k=5)
    assert out[0]["sig_id"] == "next_cleanest"
    assert "clean_but_relabelled" not in {o["sig_id"] for o in out}
    assert out[0]["group_size"] == 3            # group size still counts every mismatch


def _mark_csv(d, note_b=""):
    with open(os.path.join(d, "s_trades.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["sig_id", "grade", "sym", "date", "sig_t", "side", "mark_t", "level_px", "eng_level", "half", "has_bars", "note", "R2_wick"])
        w.writerow(["X_2025-01-02_0933_L", "S", "X", "2025-01-02", "09:33", "L", "09:31", "100", "PDH", "H1", "1", "", "1.5"])
        w.writerow(["Z_2025-01-02_0933_L", "S", "Z", "2025-01-02", "09:33", "L", "09:33", "100", "PDH", "H1", "1", note_b, "1.5"])
    with gzip.open(os.path.join(d, "s_bars_0930_1100.csv.gz"), "wt", newline="") as fh:
        w = csv.writer(fh); w.writerow(["sig_id", "t", "o", "h", "l", "c", "v"])
        for sid in ("X_2025-01-02_0933_L", "Z_2025-01-02_0933_L"):
            for k, t in enumerate(["09:30", "09:31", "09:32", "09:33", "09:34"]):
                w.writerow([sid, t, 99 + k, 100 + k, 98 + k, 99.5 + k, 10])


def test_load_rows_carries_mark_index_and_reassign_flag():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        _mark_csv(d, note_b="2 candles earlier is an S entry")
        rows, _ = rc.load_rows(d)
    by = {r["sym"]: r for r in rows}
    assert by["X"]["i"] == 3 and by["X"]["i_mark"] == 1 and by["X"]["reassigns"] is False
    assert by["Z"]["i_mark"] == 3 and by["Z"]["reassigns"] is True


def test_run_spec_at_mark_scores_the_mark_bar_not_the_signal_bar():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        _mark_csv(d)
        rows, _ = rc.load_rows(d)
    sig = rc.run_spec(rows, rc.Spec())
    mark = rc.run_spec(rows, rc.Spec(), at="mark")
    assert [r["sig_t"] for r in sig] == ["09:33", "09:33"]
    assert [r["score_t"] for r in mark] == ["09:31", "09:33"]


def test_sensitivity_drops_reassign_rows_and_reports_beside_primary():
    rows = [dict(sig_id="a", date="d", sym="a", sig_t="09:33", half="H1", his="S", level=100.0, is_long=True, start=1,
                 bars=clean_long(), i=15, i_mark=15, mark_t="09:33", reassigns=False, R2_wick=None, R2_eng=None, note=""),
            dict(sig_id="b", date="d", sym="b", sig_t="09:33", half="H1", his="A", level=100.0, is_long=True, start=1,
                 bars=clean_long(), i=15, i_mark=15, mark_t="09:33", reassigns=True, R2_wick=None, R2_eng=None, note="")]
    s = rc.sensitivity(rows)
    assert s["primary"]["n"] == 2 and s["mark_clean"]["n"] == 1 and s["n_reassign"] == 1
    assert s["sig_clean"]["n"] == 1                       # same subset, signal bar: separates the two effects
    assert set(s["mark_clean"]) >= {"n", "exact", "s_recall", "s_precision"}
