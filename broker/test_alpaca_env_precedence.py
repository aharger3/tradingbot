"""broker/test_alpaca_env_precedence.py — .env must win over a stale
Machine-level ALPACA_PAPER_KEY/SECRET (omen-env-precedence, found via
omen-v4-paper-check / g88: python-dotenv's load_dotenv() never overrides a
variable already set in the process environment, so a stale Machine-level
value silently shadows .env for every process on Windows).

No network calls: only _load_paper_credentials_from_dotenv is exercised.

Run: `python broker/test_alpaca_env_precedence.py` or
`pytest broker/test_alpaca_env_precedence.py -v`.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from broker.alpaca import _ENV_OVERRIDE_KEYS, _load_paper_credentials_from_dotenv  # noqa: E402


def test_dotenv_wins_over_stale_machine_env():
    saved = {k: os.environ.get(k) for k in _ENV_OVERRIDE_KEYS}
    try:
        # Simulate a stale Machine-level env var already sitting in the
        # process environment before .env is ever read.
        os.environ["ALPACA_PAPER_KEY"] = "stale-machine-key"
        os.environ["ALPACA_PAPER_SECRET"] = "stale-machine-secret"

        with tempfile.TemporaryDirectory() as tmp:
            dotenv_path = Path(tmp) / ".env"
            dotenv_path.write_text(
                "ALPACA_PAPER_KEY=dotenv-key\nALPACA_PAPER_SECRET=dotenv-secret\n"
            )
            _load_paper_credentials_from_dotenv(str(dotenv_path))

        assert os.environ["ALPACA_PAPER_KEY"] == "dotenv-key", ".env must override the stale machine key"
        assert os.environ["ALPACA_PAPER_SECRET"] == "dotenv-secret", ".env must override the stale machine secret"
        print("test_dotenv_wins_over_stale_machine_env: PASS")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_machine_env_used_when_dotenv_has_no_value():
    saved = {k: os.environ.get(k) for k in _ENV_OVERRIDE_KEYS}
    try:
        os.environ["ALPACA_PAPER_KEY"] = "only-machine-key"
        os.environ["ALPACA_PAPER_SECRET"] = "only-machine-secret"

        with tempfile.TemporaryDirectory() as tmp:
            dotenv_path = Path(tmp) / ".env"
            dotenv_path.write_text("")  # no ALPACA_PAPER_* entries at all
            _load_paper_credentials_from_dotenv(str(dotenv_path))

        assert os.environ["ALPACA_PAPER_KEY"] == "only-machine-key"
        assert os.environ["ALPACA_PAPER_SECRET"] == "only-machine-secret"
        print("test_machine_env_used_when_dotenv_has_no_value: PASS")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    test_dotenv_wins_over_stale_machine_env()
    test_machine_env_used_when_dotenv_has_no_value()
    print("\nALL ALPACA ENV PRECEDENCE TESTS PASSED")
