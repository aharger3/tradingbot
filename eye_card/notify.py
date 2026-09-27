"""Build + send the ntfy phone card, in the OMEN Discord-card format
(s06-discord-notification.md), with the chart PNG attached and S / Not S
action buttons that hit the local label endpoint.

Every message is PAPER. Nothing here places a live order.
"""
from __future__ import annotations

import math
import os
import re
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


# u07 sizing (flat 2R, MNQ micros): n = floor(RISK_BUDGET / (stop_pt * $/pt + 2.25)),
# clipped to MAX_MICROS. Displayed risk is net of the $1.24 round-trip commission.
RISK_BUDGET = 200.0
U07_COST_PAD = 2.25
RT_COMMISSION = 1.24
MAX_MICROS = 40
FLAT_TIME = "10:30"
MICRO_ROOT = {"NQ": "MNQ", "ES": "MES", "YM": "MYM", "RTY": "M2K"}
MICRO_USD_PT = {"MNQ": 2.0, "MES": 5.0, "MYM": 0.5, "M2K": 5.0}
_CONTRACT_RE = re.compile(r"^([A-Z0-9]*?[A-Z])([FGHJKMNQUVXZ])(\d{1,2})$")


def contract_symbol(candidate: Candidate) -> str:
    """Micro contract with month code, from the bar data's symbol
    (candidate.extra['bar_symbol'], e.g. 'NQZ6' -> 'MNQZ6'); falls back to
    candidate.symbol (root only if the bars carried no month)."""
    raw = str(candidate.extra.get("bar_symbol") or candidate.symbol).upper().strip()
    m = _CONTRACT_RE.match(raw)
    root, month = (m.group(1), m.group(2) + m.group(3)[-1]) if m else (raw, "")
    return MICRO_ROOT.get(root, root) + month


def u07_size(stop_pt: float, usd_pt: float = 2.0) -> int:
    n = math.floor(RISK_BUDGET / (abs(stop_pt) * usd_pt + U07_COST_PAD))
    return max(0, min(MAX_MICROS, n))


def ticket_line(candidate: Candidate, size: int | None = None) -> str:
    """One copy-typeable bracket ticket, e.g.
    'TICKET: BUY 3 MNQZ6 MKT · SL 24812.00 STP-MKT · TP 24890.00 LMT · OCO · FLAT 10:30 · risk $198'.
    TP is the u07 flat 2R target; size defaults to the u07 formula. PAPER only."""
    contract = contract_symbol(candidate)
    usd_pt = MICRO_USD_PT.get(re.sub(r"[FGHJKMNQUVXZ]\d$", "", contract), 2.0)
    stop_pt = abs(candidate.entry - candidate.stop)
    n = u07_size(stop_pt, usd_pt) if size is None else int(size)
    if n <= 0:
        return f"TICKET: NO TRADE - {stop_pt:.2f} pt stop is past the u07 ${RISK_BUDGET:.0f} cap"
    long_ = candidate.direction.upper() == "LONG"
    side = "BUY" if long_ else "SELL"
    tp = candidate.entry + (2 if long_ else -2) * stop_pt
    risk = n * (stop_pt * usd_pt + RT_COMMISSION)
    return (
        f"TICKET: {side} {n} {contract} MKT \u00b7 SL {candidate.stop:.2f} STP-MKT"
        f" \u00b7 TP {tp:.2f} LMT \u00b7 OCO \u00b7 FLAT {FLAT_TIME} \u00b7 risk ${risk:.0f}"
    )


def build_title(candidate: Candidate) -> str:
    arrow = "UP" if candidate.direction.upper() == "LONG" else "DOWN"
    return f"eye-check: {candidate.symbol} {arrow} {candidate.direction}"


def build_message(candidate: Candidate) -> str:
    """Newline-joined body (ASCII bar the ticket line's middle dots). Callers that put this in an HTTP
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
    lines.append(ticket_line(candidate))
    lines.append(f"OMEN - eye-loop - PAPER - #{candidate.candidate_id}")
    return "\n".join(lines)


def _header_safe(text: str) -> str:
    """HTTP header values can't carry real newlines or non-ascii; ntfy
    renders the literal two-char '\\n' sequence as a line break."""
    text = text.replace("\u00b7", "|")  # ticket-line separator survives ASCII
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
