import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts import rule_drift_watcher as w

PAGE = ("below 55% of your Profit Target. Maximum Loss Limit (EOD) $2,000 Daily Loss Limit None "
        "Consistency 50% (Eval Only) Based on current promotions $209 Max Drawdown $2,000 "
        "50K Standard Eval $129 $175 one-time $49 / month")

def test_extract():
    r = w.extract(PAGE, dict(w.FIRMS[2][2]))
    assert r["dd"] == "2000" and r["dll"] == "None" and r["consistency"] == "50"

def test_planted_change_one_alert(tmp_path):
    snap = str(tmp_path / "s.json")
    assert w.main(["--snapshot", snap, "--no-ntfy"], fetch=lambda u: PAGE) == 0
    assert len(json.load(open(snap))["firms"]) >= 6
    assert w.main(["--snapshot", snap, "--no-ntfy"], fetch=lambda u: PAGE) == 0
    changed = PAGE.replace("Maximum Loss Limit (EOD) $2,000", "Maximum Loss Limit (EOD) $1,500")
    fetch = lambda u: changed if "13134709" in u else PAGE
    old = json.load(open(snap)); new = w.run(fetch)
    assert w.diff(old, new) == ["MFFU dd: 2000 -> 1500"]
