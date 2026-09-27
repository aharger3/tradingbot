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
    # Where the phone reaches the label endpoint (Tailscale/Cloudflare).
    return os.environ.get("EYE_LABEL_BASE_URL", "http://100.66.129.60:9135")


def build_title(candidate: Candidate) -> str:
    arrow = "UP" if candidate.direction.upper() == "LONG" else "DOWN"
    return f"eye-check: {candidate.symbol} {arrow} {candidate.direction}"


def build_message(candidate: Candidate) -> str:
    """Plain-ASCII, newline-joined body. Callers that put this in an HTTP
    header (ntfy's Message header) must escape real newlines first -- see
    `_header_safe`. The body form (real '\\n') is what tests assert on.
    """
    targets = " | ".join(f"T{i} {t:g}" for i, t in enumerate(candidate.targets, 1))
    risk = candidate.entry - candidate.stop
    reward1 = (candidate.targets[0] - candidate.entry) if candidate.targets else 0.0
    r_mult = abs(reward1 / risk) if risk else 0.0
    lines = [
        f"{candidate.setup} - {candidate.trigger_time} ET",
        f"Entry {candidate.entry:g} - Stop {candidate.stop:g} "
        f"({abs(risk):g} pt) - {targets} ({r_mult:.1f}R)",
        f"{candidate.level_label}: {candidate.level:g}",
    ]
    if candidate.reason:
        lines.append(f"WATCH - {candidate.reason}")
    lines.append(f"OMEN - eye-loop - PAPER - #{candidate.candidate_id}")
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
        "Title": _header_safe(title) or "eye-check",
        "Message": _header_safe(build_message(candidate)),
        "Priority": "default",
        "Tags": "eyes,paper",
        "Filename": f"{candidate.candidate_id}.png",
        "Actions": build_actions(candidate, token),
    }
    chart_path = Path(chart_path)
    with open(chart_path, "rb") as fh:
        resp = sess.post(url, data=fh.read(), headers=headers, timeout=timeout)
    return SendResult(ok=resp.ok, status_code=resp.status_code, url=url)
