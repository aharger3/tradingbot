"""premarket_card.main: wait for network, never post an all-empty card, exit nonzero on failure."""
import premarket_card as pc

REAL = {"embeds": [{"fields": [{"value": "**BULLISH** gap +0.50% (400.00 vs PDC 398.00)"}]}]}
EMPTY = {"embeds": [{"fields": [{"value": "QQQ bias: unknown (no pre-market data)"},
                                {"value": "```\nTSLA        —  | PDH —\n```"}]}]}


def run(monkeypatch, payload, net=True, ok=True):
    monkeypatch.setattr(pc, "build_card", lambda syms: payload)
    posted = []
    rc = pc.main(["--symbols", "QQQ"], wait=lambda host: net,
                 post=lambda p: posted.append(p) or ok)
    return rc, posted


def test_network_down_exits_1_without_posting(monkeypatch):
    rc, posted = run(monkeypatch, REAL, net=False)
    assert rc == 1 and posted == []


def test_empty_card_not_posted(monkeypatch):
    rc, posted = run(monkeypatch, EMPTY)
    assert rc == 1 and posted == []


def test_failed_post_exits_1(monkeypatch):
    rc, posted = run(monkeypatch, REAL, ok=False)
    assert rc == 1 and len(posted) == 1


def test_good_post_exits_0(monkeypatch):
    rc, posted = run(monkeypatch, REAL)
    assert rc == 0 and len(posted) == 1
