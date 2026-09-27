"""Regression test for the 2026-09-26 stall: a dead DNS/connection window
must not hang the scraper indefinitely. Network is mocked; no real calls."""
import importlib.util
import socket
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPT = Path(__file__).parent / "youtube_scraper.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("youtube_scraper", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_global_socket_timeout_set_on_import():
    prev = socket.getdefaulttimeout()
    try:
        mod = _load_module()
        assert socket.getdefaulttimeout() == 30, (
            "youtube_scraper.py must set a global socket timeout so a stuck "
            "network call cannot hang forever"
        )
    finally:
        socket.setdefaulttimeout(prev)
        sys.modules.pop("youtube_scraper", None)


def test_get_transcripts_survives_network_timeout():
    """A per-video socket.timeout must be caught and skipped, not crash the run."""
    mod = _load_module()
    mod.ALL_IDS = ["deadbeef000"]
    mod.DATA_DIR = Path("_test_youtube_data_tmp")

    fake_api = MagicMock()
    fake_api.list.side_effect = socket.timeout("timed out")

    with patch.object(mod, "YouTubeTranscriptApi", return_value=fake_api):
        mod.get_transcripts()  # must not raise

    assert not (mod.DATA_DIR / "deadbeef000_transcript.txt").exists()
    if mod.DATA_DIR.exists():
        mod.DATA_DIR.rmdir()
