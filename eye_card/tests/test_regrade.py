"""Blind re-grade deck: selection, no-grade-on-card, dry-run send, kappa on synthetic taps."""
from __future__ import annotations

import csv
import io
import json

import pytest

from eye_card.regrade import build_deck, kappa, send_regrade


def _row(i, sym, grade, src="austin_marks_v7.jsonl"):
    return {"sig_id": f"{sym}_2024-01-{i:02d}_0945_L", "sym": sym, "grade": grade,
            "mark_src": src, "side": "L", "sig_t": "09:45", "eng_stop": "99",
            "level_px": "100", "orh15": "101", "orl15": "99"}


def test_select_deck_20_20_v7_only_stratified():
    syms = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    rows = []
    for k, s in enumerate(syms):
        rows += [_row(i + 10 * k, s, "S") for i in range(1, 9)]
        rows += [_row(i + 10 * k, s, "one-off" if i % 2 else "two-off") for i in range(1, 9)]
    # S-only probe/autopsy sources must never enter
    rows += [_row(i, "ZZZ", "S", "probe_s_sweep_2026-08-28.jsonl") for i in range(1, 30)]
    rows += [_row(i, "YYY", "S", "probe_autopsy_2026-08-23.jsonl") for i in range(1, 30)]
    deck = build_deck.select_deck(rows, seed=1)
    assert len(deck) == 40
    assert sum(build_deck.binarize(r["grade"]) == "S" for r in deck) == 20
    assert all(r["mark_src"] == "austin_marks_v7.jsonl" for r in deck)
    per_sym = {s: sum(r["sym"] == s for r in deck if r["grade"] == "S") for s in syms}
    assert max(per_sym.values()) - min(per_sym.values()) <= 1  # round-robin
    assert build_deck.select_deck(rows, seed=1) == deck  # deterministic


def test_candidate_carries_no_grade():
    bar = {"time": "09:45:00", "open": 100, "high": 101, "low": 99.5, "close": 100.5}
    c = build_deck.to_candidate("RG0927-01", _row(1, "AAA", "S"), bar)
    text = " ".join(str(v) for v in vars(c).values())
    assert "one-off" not in text and "two-off" not in text and "_L" not in text
    assert c.setup == "regrade" and c.reason == "" and c.candidate_id == "RG0927-01"
    assert c.stop < c.entry < c.targets[0]


def _manifest(orig_bins):
    return {"cards": [{"card_id": f"RG0927-{i:02d}", "n": i, "orig_bin": b,
                       "png": f"cards/RG0927-{i:02d}.png",
                       "candidate": {"symbol": "AAA", "direction": "LONG",
                                     "trigger_time": "09:45:00", "entry": 1.0, "stop": 0.5,
                                     "targets": [2.0], "level": 1.0, "level_label": "Level",
                                     "setup": "regrade", "reason": "", "or_high": None,
                                     "or_low": None}}
                      for i, b in enumerate(orig_bins, start=1)]}


def _write_labels(path, taps):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["logged_at", "candidate_id", "label", "mode", "source_ip"])
        w.writeheader()
        for cid, lbl in taps:
            w.writerow({"logged_at": "t", "candidate_id": cid, "label": lbl,
                        "mode": "PAPER", "source_ip": ""})


def test_kappa_synthetic_taps(tmp_path):
    orig = ["S"] * 20 + ["notS"] * 20
    m = _manifest(orig)
    new = ["S"] * 16 + ["notS"] * 4 + ["S"] * 2 + ["notS"] * 18
    taps = [(f"RG0927-{i:02d}", lbl) for i, lbl in enumerate(new, start=1)]
    taps.insert(0, ("RG0927-01", "notS"))          # earlier tap, overridden (last wins)
    taps.append(("O11-1-20260917", "S"))           # unrelated eye-loop label, ignored
    lab = tmp_path / "labels.csv"
    _write_labels(lab, taps)
    res = kappa.score(m, kappa.load_taps(lab, {c["card_id"] for c in m["cards"]}))
    # po = 34/40 = .85 ; pe = .5*.45 + .5*.55 = .5 ; kappa = .7
    assert res["kappa"] == pytest.approx(0.7)
    assert res["agreement_pct"] == pytest.approx(85.0)
    assert (res["S_to_notS"], res["notS_to_S"]) == (4, 2)
    assert res["n_answered"] == 40 and res["missing"] == []
    print("\n" + kappa.report(res))


def test_kappa_partial_and_perfect(tmp_path):
    m = _manifest(["S", "notS", "S", "notS"])
    lab = tmp_path / "labels.csv"
    _write_labels(lab, [("RG0927-01", "S"), ("RG0927-02", "notS")])
    res = kappa.score(m, kappa.load_taps(lab, {c["card_id"] for c in m["cards"]}))
    assert res["kappa"] == pytest.approx(1.0)
    assert res["missing"] == ["RG0927-03", "RG0927-04"]
    assert kappa.cohen_kappa([("S", "notS"), ("notS", "S")]) == pytest.approx(-1.0)


class _Resp:
    ok, status_code = True, 200


class _Sess:
    def __init__(self):
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append(headers)
        return _Resp()


def test_send_dry_run_and_mock_send(tmp_path):
    m = _manifest(["S", "notS"])
    (tmp_path / "cards").mkdir()
    for c in m["cards"]:
        (tmp_path / c["png"]).write_bytes(b"png")
    (tmp_path / "manifest.json").write_text(json.dumps(m))
    buf = io.StringIO()
    sess = _Sess()
    assert send_regrade.run(tmp_path, send=False, session=sess, out=buf) == 0
    assert sess.calls == [] and "REGRADE 1/2" in buf.getvalue()
    assert send_regrade.run(tmp_path, send=True, session=sess, token="t", sleep=0, out=buf) == 2
    h = sess.calls[0]
    assert h["Title"].startswith("REGRADE 1/2")
    assert "label=S" in h["Actions"] and "label=notS" in h["Actions"]
    assert "id=RG0927-01" in h["Actions"]
    blob = json.dumps(sess.calls)
    assert "orig_bin" not in blob and "one-off" not in blob
