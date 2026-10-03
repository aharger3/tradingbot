"""Tests never touch the keys vault, the network, or the real data directories."""
import os

os.environ["TAP_KEYS_PY"] = os.path.join(os.path.dirname(__file__), "no-such-keys.py")   # read at import by eye_card.tap
os.environ["NTFY_NO_VAULT"] = "1"
for _k in ("ALPACA_PAPER_KEY", "ALPACA_PAPER_SECRET", "NTFY_TOPIC", "ANSWER_TAP_TOKEN", "TAP_ANSWER_TOPIC", "TAP_BASE_URL"):
    os.environ.pop(_k, None)
os.environ["ARCHIVE_READONLY"] = "1"
