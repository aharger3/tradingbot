"""Build + send the ntfy phone card, in the OMEN Discord-card format
(s06-discord-notification.md), with the chart PNG attached and S / Not S
action buttons that hit the local label endpoint.

Every message is PAPER. Nothing here places a live order.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests

from .chart import Candidate

DEFAULT_NTFY_BASE = "https://ntfy.sh"


def _ntfy_topic() -> str:
    # Reuse ev-dashboard's ntfy topic (see Projects/ev-dashboard/.env NTFY_TOPIC).
    return os.environ.get("NTFY_TOPIC", "aharg-ev-eo5zvp")


def _ntfy_base() -> str:
    return os.environ.get("NTFY_BASE_URL", DEFAULT_NTFY_BASE)


def _label_base_url() -> str:
    # Where the phone reaches the label endpoint: the Cloudflare tunnel, never the Tailscale IP
    # (the phone is often off the tailnet, so a Tailscale button tap is lost).
    return os.environ.get("EYE_LABEL_BASE_URL", "https://omen.austinharger.com")


def build_title(candidate: Candidate) -> str:
    """Title in the mentors' entry order: side, instrument, price.
    J-Dub's own futures alerts read "Short NQ 18210"; the #signals S card
    title is "{SYM} ... {CALL|PUT}". The rocket emoji comes from the ntfy
    `rocket` tag (headers stay ASCII)."""
    return f"{candidate.direction.upper()} {candidate.symbol} {candidate.entry:g}"


def _side_word(candidate: Candidate) -> str:
    # Mentor wording: "Stop above 18233" on shorts, "risk below PDH" on longs.
    return "above" if candidate.direction.upper() == "SHORT" else "below"


def build_message(candidate: Candidate) -> str:
    """Plain-ASCII, newline-joined body. Callers that put this in an HTTP
    header (ntfy's Message header) must escape real newlines first -- see
    `_header_safe`. The body form (real '\\n') is what tests assert on.

    Field order and labels copy Austin's #signals S card (discord_bot.py
    `_format_options_embed`, msg 1550153955668004945): Setup | Grade | Time,
    Contracts, Entry | Stop | Target (xR), Stop level, Max Loss / Reward,
    Reason, footer. Stop and target are also named by their level, the way
    Scarface / J-Dub word them ("Stop above 18233", "targets hod").
    Optional `extra` keys: grade, contract, contracts, point_value,
    target_label.
    """
    x = candidate.extra or {}
    risk = abs(candidate.entry - candidate.stop)
    t1 = candidate.targets[0] if candidate.targets else None
    reward = abs(t1 - candidate.entry) if t1 is not None else 0.0
    r_mult = reward / risk if risk else 0.0
    grade = x.get("grade") or "?"
    lines = [f"Setup: {candidate.setup} | Grade: {grade} | Time: {candidate.trigger_time} ET"]
    contract_bits = []
    if x.get("contract"):
        contract_bits.append(f"Contract: {x['contract']}")
    if x.get("contracts"):
        contract_bits.append(f"Contracts: {x['contracts']}")
    if contract_bits:
        lines.append(" | ".join(contract_bits))
    tgt = f"{t1:g}" if t1 is not None else "-"
    if x.get("target_label") and t1 is not None:
        tgt = f"{t1:g} ({x['target_label']})"
    lines.append(f"Entry: {candidate.entry:g} | Stop: {candidate.stop:g} | "
                 f"Target ({r_mult:.1f}R): {tgt}")
    if len(candidate.targets) > 1:
        lines.append("Scale: " + " | ".join(
            f"T{i} {t:g}" for i, t in enumerate(candidate.targets, 1)))
    pct = (risk / candidate.entry * 100) if candidate.entry else 0.0
    lines.append(f"Stop level: {_side_word(candidate)} {candidate.level_label} "
                 f"{candidate.level:g} ({pct:.2f}%)")
    if x.get("contracts") and x.get("point_value"):
        n, pv = float(x["contracts"]), float(x["point_value"])
        lines.append(f"Max Loss / Reward: -${risk * pv * n:,.0f} / +${reward * pv * n:,.0f}")
    reason = f" {candidate.reason}" if candidate.reason else ""
    lines.append(f"Reason: WATCH | [{candidate.symbol}]{reason}")
    lines.append(f"Omen Signal Bot | Grade {grade} | PAPER | #{candidate.candidate_id}")
    return "\n".join(lines)


def _header_safe(text: str) -> str:
    """HTTP header values can't carry real newlines or non-ascii; ntfy
    renders the literal two-char '\\n' sequence as a line break."""
    return text.replace("\n", "\\n").encode("ascii", "ignore").decode()


def build_actions(candidate: Candidate, token: str) -> str:
    base = _label_base_url().rstrip("/")
    s_url = f"{base}/label?id={candidate.candidate_id}&label=S&token={token}"
    not_s_url = f"{base}/label?id={candidate.candidate_id}&label=notS&token={token}"
    return (
        f"http, S, {s_url}, method=POST, clear=true; "
        f"http, Not S, {not_s_url}, method=POST, clear=true"
    )


@dataclass
class SendResult:
    ok: bool
    status_code: int | None
    url: str


def send_card(candidate: Candidate, chart_path: str | Path, token: str,
              *, session: requests.Session | None = None, test_title_prefix: str | None = None,
              timeout: float = 10.0) -> SendResult:
    """POST the chart PNG to ntfy with the card headers. Always PAPER."""
    sess = session or requests
    topic = _ntfy_topic()
    url = f"{_ntfy_base().rstrip('/')}/{topic}"
    title = build_title(candidate)
    if test_title_prefix:
        title = f"{test_title_prefix} {title}"
    headers = {
        "Title": _header_safe(title) or "OMEN",
        "Message": _header_safe(build_message(candidate)),
        "Priority": "default",
        "Tags": "rocket,paper",
        "Filename": f"{candidate.candidate_id}.png",
        "Actions": build_actions(candidate, token),
    }
    chart_path = Path(chart_path)
    with open(chart_path, "rb") as fh:
        resp = sess.post(url, data=fh.read(), headers=headers, timeout=timeout)
    return SendResult(ok=resp.ok, status_code=resp.status_code, url=url)
