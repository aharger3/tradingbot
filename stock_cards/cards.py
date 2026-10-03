"""Card builder for the S2 feed: chart cut at the signal bar, ntfy payload, S / Not S / Skip buttons.

The card shows the ticker, side, the bars through the signal bar, the level, entry/stop/2R lines and the time.
It never shows a machine grade, a score, a "looks like your S" badge or any outcome (prereg-S2.md, "The card").
The buttons post to the existing tap-to-answer endpoint (eye_card.tap): TAP_BASE_URL (Cloudflare tunnel,
<base>/tap/<token>) when that secret is set, else the private ntfy answer topic relay that the pm2 service
`tap-answer` already streams. Neither route touches Tailscale.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from eye_card import tap as eyetap
from eye_card.chart import Candidate, render_candidate_chart

from .config import ET, MAX_CARDS_PER_DAY, TAP_WINDOW_SECONDS

SETUP_LABEL = "break/retest"         # neutral: no grade, no engine tag text on the card
PLACEHOLDER_CFG = {"token": "<TOKEN>", "answer_topic": "<ANSWER_TOPIC>", "base_url": "", "topic": "<ALERT_TOPIC>"}


def candidate_id(c: dict) -> str:
    return f"W9-{c['sym']}-{c['day'].replace('-', '')}-{c['sig_t'].replace(':', '')}{c['side']}"


def to_eye_candidate(c: dict) -> Candidate:
    risk = abs(c["entry"] - c["stop"])
    long_ = c["side"] == "L"
    t1 = c["entry"] + (2 * risk if long_ else -2 * risk)
    return Candidate(candidate_id=candidate_id(c), symbol=c["sym"], direction="LONG" if long_ else "SHORT",
                     trigger_time=c["sig_t"] + ":00", entry=c["entry"], stop=c["stop"], targets=[round(t1, 2)],
                     level=c["level"], level_label=(c.get("level_name") or "Level"), setup=SETUP_LABEL, reason="")


def chart_bars(rth: list, sig_t: str) -> list[dict]:
    """Bars 09:30 through the signal bar, nothing after. The chart code also cuts at trigger_time; this is belt and braces."""
    out = []
    for k in rth:
        out.append({"time": k.timestamp, "open": k.open, "high": k.high, "low": k.low, "close": k.close})
        if k.timestamp[:5] == sig_t:
            break
    return out


def render_card(c: dict, rth: list, out_dir: Path) -> Path:
    ec = to_eye_candidate(c)
    return render_candidate_chart(ec, chart_bars(rth, c["sig_t"]), Path(out_dir) / f"{ec.candidate_id}.png")


def build_payload(c: dict, card_id: str, seq: int, cfg: dict, *, chart_url: str = "", cap: int = MAX_CARDS_PER_DAY) -> dict:
    ec = to_eye_candidate(c)
    p = eyetap.build_tap_payload(ec, card_id, topic=cfg["topic"], token=cfg["token"], answer_topic=cfg["answer_topic"],
                                 base_url=cfg["base_url"], blind=False, seq=seq, cap=cap, chart_url=chart_url)
    p["message"] += f"\nTap within {TAP_WINDOW_SECONDS // 60} min of the bar close"
    return p


def load_cfg(live: bool) -> dict:
    """Live needs the vault secrets (raises TapConfigError if missing). Dry falls back to masked placeholders."""
    try:
        return eyetap.load_config()
    except eyetap.TapConfigError:
        if live:
            raise
        return dict(PLACEHOLDER_CFG)


def deliver(c: dict, rth: list, seq: int, now: datetime, *, live: bool, out_dir: Path, session=None,
            cfg: dict | None = None) -> dict:
    """Render the chart and either push the card (live) or build the payload it would send (dry). Returns the ledger row."""
    cfg = cfg or load_cfg(live)
    png = render_card(c, rth, out_dir)
    card_id = eyetap.card_id_for(candidate_id(c), blind=False)
    row = {"card_id": card_id, "candidate_id": candidate_id(c), "mode": "live" if live else "dry", "seq": seq,
           "day": c["day"], "sym": c["sym"], "sig_t": c["sig_t"], "side": c["side"], "stop": c["stop"],
           "entry": c["entry"], "sig_close_ts": c["sig_close_ts"], "sent_at": now.astimezone(ET).isoformat(timespec="seconds"),
           "chart": png.name}
    if live:
        import requests
        sess = session or requests
        base = eyetap.NTFY_BASE
        chart_url = eyetap.upload_chart(png, session=sess, ntfy_base=base)      # '' on failure: card goes out without it
        payload = build_payload(c, card_id, seq, cfg, chart_url=chart_url)      # same builder as the dry run
        resp = sess.post(base + "/", json=payload, timeout=15.0)
        row.update(ok=bool(resp.ok), http=resp.status_code, chart_attached=bool(chart_url))
    else:
        payload = build_payload(c, card_id, seq, cfg, chart_url="https://ntfy.sh/file/<chart>.png")
        row.update(ok=None, would_send=json.loads(eyetap.redacted(payload, cfg["token"], cfg["answer_topic"], cfg["topic"])))
    return row
