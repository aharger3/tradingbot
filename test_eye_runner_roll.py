"""pytest test_eye_runner_roll.py -- eye runner refuses cards on a roll mismatch."""
import sys
import types
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent


def _stub(name):
    """Research modules the runner imports but that live only in the untracked
    data tree (omen_data, orb1m, ...). The roll guard never calls them."""
    mod = types.ModuleType(name)
    mod.__getattr__ = lambda attr: (lambda *a, **k: None)
    sys.modules[name] = mod


for _ in range(10):
    try:
        import eye_runner  # noqa: E402
        break
    except ModuleNotFoundError as e:
        _stub(e.name)
else:
    raise ImportError("eye_runner still unimportable after stubbing")


def _bars(contract, day):
    return pd.DataFrame({"date": [day] * 3, "contract": [contract] * 3,
                         "open": [1.0] * 3, "high": [1.0] * 3, "low": [1.0] * 3, "close": [1.0] * 3})


def test_roll_guard_pass_and_fail():
    pushes = []
    push = lambda title, body, **kw: pushes.append((title, body)) or True
    assert eye_runner.roll_guard("MNQH6", "MNQ", "2025-12-16", push=push) is True
    assert pushes == []
    assert eye_runner.roll_guard("MNQZ5", "MNQ", "2025-12-16", push=push) is False
    assert pushes[0][0] == "ROLL MISMATCH" and "MNQH6" in pushes[0][1]


def test_runner_refuses_on_fixture_mismatch(monkeypatch, tmp_path):
    pushes, cards = [], []
    # stale Dec contract on 2025-12-16, the day after the Dec->Mar roll
    monkeypatch.setattr(eye_runner, "load_fut", lambda *a, **k: _bars("NQZ5", "2025-12-16"))
    monkeypatch.setattr(eye_runner.notify_ntfy, "push",
                        lambda title, body, **kw: pushes.append(title) or True)
    monkeypatch.setattr(eye_runner, "send_card", lambda *a, **k: cards.append(a))
    rc = eye_runner.main(["--date", "2025-12-16", "--title-prefix", "OMEN TEST -- ignore",
                          "--journal-path", str(tmp_path / "j.jsonl"),
                          "--labels-csv", str(tmp_path / "labels.csv")])
    assert rc == eye_runner.ROLL_MISMATCH_RC
    assert pushes == ["ROLL MISMATCH"]
    assert cards == []
