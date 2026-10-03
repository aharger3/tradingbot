"""Ledger + tap files -> the CSVs s2_confirm.py reads. Counting only; no outcome is computed."""
import csv
import json

from stock_cards import export_taps as ex
from stock_cards import ledger

S2_TAP_COLUMNS = ["sym", "day", "sig_t", "side", "stop", "label", "sig_close_ts", "tap_ts"]      # prereg-S2 / s2_confirm docstring
S2_CAND_COLUMNS = ["sym", "day", "sig_t", "side", "stop"]


def card(i, sig_t="09:40", sym="NVDA"):
    return {"card_id": f"EYE-W9-{sym}-{i}", "sym": sym, "day": "2026-10-05", "sig_t": sig_t, "side": "L", "stop": 100.5,
            "sig_close_ts": f"2026-10-05T{sig_t[:2]}:{int(sig_t[3:]) + 1:02d}:00-04:00", "mode": "live"}


def write_labels(path, rows, header="logged_at,candidate_id,label,mode,source_ip"):
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_header_matches_the_s2_confirm_input_spec():
    assert ex.TAP_FIELDS[:8] == S2_TAP_COLUMNS and ex.CAND_FIELDS == S2_CAND_COLUMNS


def test_taps_join_on_card_id_and_classify(tmp_path):
    cs = [card(1), card(2, "09:50"), card(3, "10:00"), card(4, "10:10"), card(5, "10:20")]
    labels = tmp_path / "labels.csv"
    # 09:41:00 ET = 13:41:00Z. card1 S after 30 s, card2 notS after 200 s (late), card3 skip, card4/5 no tap
    write_labels(labels, ["2026-10-05T13:41:30+00:00,EYE-W9-NVDA-1,S,PAPER,tap",
                          "2026-10-05T13:54:20+00:00,EYE-W9-NVDA-2,notS,PAPER,tap",
                          "2026-10-05T13:30:00+00:00,EYE-W9-OTHER-9,S,PAPER,tap"])
    (tmp_path / "skips.csv").write_text(
        "logged_at,candidate_id,label,mode,source_ip\n2026-10-05T14:01:10+00:00,EYE-W9-NVDA-3,skip,PAPER,tap\n",
        encoding="utf-8")
    rows, counts = ex.build_tap_rows(cs, ex.read_taps(labels))
    assert counts["cards"] == 5 and counts["S"] == 1 and counts["notS"] == 1 and counts["skip"] == 1
    assert counts["no_tap"] == 2
    assert counts["in_time_taps"] == 1 and counts["late_or_early"] == 1 and counts["response_in_time"] == 0.2
    by = {r["card_id"]: r for r in rows}
    assert by["EYE-W9-NVDA-1"]["in_time"] == 1 and by["EYE-W9-NVDA-1"]["latency_s"] == 30.0
    assert by["EYE-W9-NVDA-2"]["in_time"] == 0 and "EYE-W9-NVDA-3" not in by       # skip is counted, never a label
    assert counts["median_latency_s"] == 30.0


def test_main_writes_the_files(tmp_path):
    for c in (card(1), card(2, "09:50")):
        ledger.log_card("live", c, tmp_path)
    base = {"day": "2026-10-05", "stop": 5.0, "status": "fired", "tags": ["clean"]}
    ledger.log_candidate({**base, "sym": "NVDA", "sig_t": "09:40", "side": "L", "stop": 100.5, "key": "k1"}, "sent", "x", tmp_path)
    ledger.log_candidate({**base, "sym": "AMD", "sig_t": "11:30", "side": "S", "key": "k2"}, "window", "x", tmp_path)
    ledger.log_candidate({**base, "sym": "AMD", "sig_t": "10:00", "side": "S", "key": "k3", "status": "skipped_d"}, "ineligible", "x", tmp_path)
    labels = tmp_path / "labels.csv"
    write_labels(labels, ["2026-10-05T13:41:05+00:00,EYE-W9-NVDA-1,S,PAPER,tap"])
    counts = ex.main([], data_dir=tmp_path, labels_csv=labels)
    out = tmp_path / "export"
    taps = list(csv.DictReader(open(out / "s2_taps.csv", encoding="utf-8")))
    cands = list(csv.DictReader(open(out / "s2_candidates_iex_all.csv", encoding="utf-8")))
    elig = list(csv.DictReader(open(out / "s2_candidates_iex_eligible.csv", encoding="utf-8")))
    assert len(taps) == 1 and taps[0]["label"] == "S" and taps[0]["sym"] == "NVDA"
    assert [(c["sym"], c["sig_t"]) for c in cands] == [("NVDA", "09:40"), ("AMD", "10:00")]      # 11:30 is outside the window
    assert [(c["sym"], c["sig_t"]) for c in elig] == [("NVDA", "09:40")]           # the null pool = what cards are drawn from
    assert json.loads((out / "tap_counts.json").read_text())["cards"] == 2 and counts["S"] == 1
