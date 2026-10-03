"""R03: every OMEN default push topic is the single topic aharg-deadlines."""
import re
from pathlib import Path

ROOT = Path(__file__).parent
ONE = "aharg-deadlines"


def test_no_old_topic_names_in_code():
    for rel in ("eye_report.py", "eye_card/notify.py", "research/prove_it.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert not re.search(r"aharg-ev-eo5zvp|omen-prove-it|aharg-omen", text), rel
        assert ONE in text, rel
