"""B2 guard: committed evidence has no market data and the MNQ repro chain has no hardcoded checkout path."""
import os, subprocess
AR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AR))
DATA_EXT = (".csv", ".gz", ".parquet")
EVIDENCE = ("v2-t", "v3-", "t01-orb5/", "t02-break-retest/", "v2-s07-data/")  # dirs committed by B2
CHAIN = [r"v3-t-mnq\mnq.py", r"v2-t01-orb-1m\orb1m.py", r"v2-s07-data\omen_data.py"]


def tracked():
    out = subprocess.run(["git", "ls-files", "research/agent_runs"], cwd=REPO, capture_output=True, text=True, check=True)
    pre = "research/agent_runs/"
    return [l for l in out.stdout.splitlines() if l.startswith(pre) and l[len(pre):].startswith(EVIDENCE)]


def test_no_market_data_tracked_in_evidence_dirs():
    assert len(tracked()) > 100
    bad = [f for f in tracked() if f.lower().endswith(DATA_EXT) or "/bars/" in f or "/fut/" in f or "/cache/" in f]
    assert bad == []


def test_repro_chain_is_checkout_relative():
    for rel in CHAIN:
        src = open(os.path.join(AR, rel), encoding="utf-8").read()
        assert "Desktop\\Projects\\tradingbot" not in src, rel


def test_omen_data_points_at_this_checkout():
    import importlib.util
    spec = importlib.util.spec_from_file_location("omen_data", os.path.join(AR, "v2-s07-data", "omen_data.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    assert os.path.normcase(str(m.FUT_DIR)) == os.path.normcase(os.path.join(AR, "t01-orb5", "fut"))
    assert "2026-09-07" in m._NYSE_HOLIDAYS
