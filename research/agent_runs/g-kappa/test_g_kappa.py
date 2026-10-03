"""Tests for the g-kappa blind re-grade deck + kappa. Run:
python -m pytest research/agent_runs/g-kappa -q"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import kappa  # noqa: E402
import regrade  # noqa: E402


def _rows(n_s=25, n_not=30):
    rows = []
    for i in range(n_s + n_not):
        rows.append(dict(sig_id=f"AAA_2024-01-{i:02d}_0945_L", mark_src=regrade.V7_SRC, has_bars="1",
                         grade="S" if i < n_s else ("one-off" if i % 2 else "two-off")))
    rows.append(dict(sig_id="PROBE_x", mark_src="probe.jsonl", has_bars="1", grade="S"))
    return rows


def test_pick_20_20_shuffled_deterministic():
    d1, d2 = regrade.pick(_rows()), regrade.pick(_rows())
    assert len(d1) == 40 and [r["sig_id"] for r in d1] == [r["sig_id"] for r in d2]
    assert sum(r["prior"] == "S" for r in d1) == 20
    assert all(r["mark_src"] == regrade.V7_SRC for r in d1)
    assert [r["kappa_id"] for r in d1][:2] == ["KAPPA-01", "KAPPA-02"]
    assert [r["prior"] for r in d1] != sorted(r["prior"] for r in d1)  # shuffled


def test_cohen_kappa_known_values():
    assert kappa.cohen_kappa(["S", "notS"] * 20, ["S", "notS"] * 20) == 1.0
    assert kappa.cohen_kappa(["S", "notS"] * 20, ["notS", "S"] * 20) == -1.0
    # 2x2 table 20/5/10/15 -> po .7, pe .5 -> kappa .4
    a = ["S"] * 25 + ["notS"] * 25
    b = ["S"] * 20 + ["notS"] * 5 + ["S"] * 10 + ["notS"] * 15
    assert abs(kappa.cohen_kappa(a, b) - 0.4) < 1e-9


def test_eta_mapping():
    assert kappa.eta_from_agreement(1.0) == 0.0
    assert abs(kappa.eta_from_agreement(0.58) - 0.3) < 1e-9  # .7^2+.3^2
    assert kappa.eta_from_agreement(0.4) == 0.5


def _write(path, fields, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader(); w.writerows(rows)


def test_synthetic_all_agree_kappa_is_one(tmp_path):
    deck = regrade.pick(_rows())
    _write(tmp_path / "key.csv", ["kappa_id", "sig_id", "prior"],
           [{k: r[k] for k in ("kappa_id", "sig_id", "prior")} for r in deck])
    labels = tmp_path / "labels.csv"
    for r in deck:
        regrade.append_label(labels, r["kappa_id"], r["prior"])
    regrade.append_label(labels, "O11-1-20260917", "S")  # non-KAPPA tap ignored
    pairs = kappa.join(labels, tmp_path / "key.csv")
    assert len(pairs) == 40
    res = kappa.stats(pairs, boot=200)
    assert res["kappa"] == 1.0 and res["eta"] == 0.0 and res["verdict"].startswith("eta<=.15")


def test_last_tap_wins_and_s_trades_grade_used(tmp_path):
    _write(tmp_path / "key.csv", ["kappa_id", "sig_id", "prior"], [dict(kappa_id="KAPPA-01", sig_id="X", prior="notS")])
    _write(tmp_path / "s.csv", ["sig_id", "grade"], [dict(sig_id="X", grade="S")])
    labels = tmp_path / "labels.csv"
    regrade.append_label(labels, "KAPPA-01", "notS")
    regrade.append_label(labels, "KAPPA-01", "S")
    [p] = kappa.join(labels, tmp_path / "key.csv", tmp_path / "s.csv")
    assert p["old"] == "S" and p["new"] == "S"


def test_render_blind_card(tmp_path):
    arch = tmp_path / "arch" / "AAA"; arch.mkdir(parents=True)
    rows = []
    for m in range(40):
        t = f"2024-01-02T{9 + (30 + m) // 60:02d}:{(30 + m) % 60:02d}:00-05:00"
        p = 100 + m * 0.1
        rows.append(dict(Datetime=t, Open=p, High=p + 0.2, Low=p - 0.2, Close=p + 0.05, Volume=1))
    _write(arch / "2024-01-02.csv", ["Datetime", "Open", "High", "Low", "Close", "Volume"], rows)
    r = dict(kappa_id="KAPPA-07", sig_t="09:50", side="L", eng_stop="99.5", level_px="101",
             orh15="101.6", orl15="99.8")
    bars = regrade.load_bars(tmp_path / "arch", "AAA", "2024-01-02")
    c = regrade.to_candidate(r, bars)
    assert c.symbol == "BLIND" and c.trigger_time == "09:50:00" and c.targets[1] > c.targets[0] > c.entry
    png = regrade.render_candidate_chart(c, bars, tmp_path / "k.png")
    assert png.stat().st_size > 1000
    from eye_card.notify import build_message
    msg = build_message(c)
    assert "#KAPPA-07" in msg and "AAA" not in msg and "2024" not in msg
