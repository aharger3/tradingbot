"""Build + send the ntfy phone card, in the OMEN Discord-card format
(s06-discord-notification.md), with the chart PNG attached and S / Not S
action buttons that hit the local label endpoint.

Every message is PAPER. Nothing here places a live order.

Reliability (2026-09-27): ntfy.sh timed out 6/6 on 9/27 and cards just
expired. ntfy now gets 3 tries; if all fail, the same card (PNG + S / Not S
label links, tagged PAPER) goes to the existing #signals Discord endpoint
that discord_bot.py already resolves. Neither path ever raises into the
runner loop.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from .chart import Candidate

DEFAULT_NTFY_BASE = "https://ntfy.sh"
NTFY_ATTEMPTS = 3
NTFY_BACKOFF = (1.0, 2.0)  # seconds between attempts (2 gaps for 3 attempts)


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


def label_urls(candidate: Candidate, token: str, channel: str | None = None) -> tuple[str, str]:
    """(S url, Not S url) for the label endpoint. `channel` tags the tap's
    source in labels.csv (e.g. channel=discord for the fallback card)."""
    base = _label_base_url().rstrip("/")
    ch = f"&channel={channel}" if channel else ""
    s_url = f"{base}/label?id={candidate.candidate_id}&label=S&token={token}{ch}"
    not_s_url = f"{base}/label?id={candidate.candidate_id}&label=notS&token={token}{ch}"
    return s_url, not_s_url


def build_actions(candidate: Candidate, token: str) -> str:
    s_url, not_s_url = label_urls(candidate, token)
    return (
        f"http, S, {s_url}, method=POST, clear=true; "
        f"http, Not S, {not_s_url}, method=POST, clear=true"
    )


@dataclass
class SendResult:
    ok: bool
    status_code: int | None
    url: str
    channel: str = "ntfy"   # "ntfy" | "discord" | "none" (both failed)
    error: str = ""


def build_discord_content(candidate: Candidate, token: str,
                          test_title_prefix: str | None = None) -> str:
    """Fallback card body: same title + message as ntfy, tagged PAPER, with
    the S / Not S label URLs as plain links (a Discord click is a GET, which
    the label endpoint accepts)."""
    title = build_title(candidate)
    if test_title_prefix:
        title = f"{test_title_prefix} {title}"
    s_url, not_s_url = label_urls(candidate, token, channel="discord")
    return "\n".join([
        f"**[PAPER] {title}**  (ntfy down, Discord fallback)",
        build_message(candidate),
        f"S: {s_url}",
        f"Not S: {not_s_url}",
    ])[:1990]


def _discord_target() -> tuple[str, dict]:
    """(url, headers) of the existing #signals endpoint, resolved exactly the
    way discord_bot.DiscordSignalBot does (bot-token channel or webhook).
    Imported lazily so eye_card stays importable without the bot deps."""
    from discord_bot import DiscordSignalBot
    bot = DiscordSignalBot()
    return bot.webhook_url, dict(bot._headers)


def _scrub(err: str, url: str) -> str:
    # The webhook token lives in the URL path; never let it reach a log line.
    from urllib.parse import urlparse
    path = urlparse(url).path
    err = err.replace(url, "<endpoint>")
    return err.replace(path, "<path>") if path else err


def send_discord_fallback(candidate: Candidate, chart_path: str | Path, token: str,
                          *, session=None, test_title_prefix: str | None = None,
                          timeout: float = 10.0) -> SendResult:
    """One multipart POST (PNG + content) to the #signals endpoint. Never raises."""
    sess = session or requests
    url = ""
    try:
        url, headers = _discord_target()
        payload = {"content": build_discord_content(candidate, token, test_title_prefix)}
        with open(chart_path, "rb") as fh:
            png = fh.read()
        resp = sess.post(url, headers=headers, timeout=timeout,
                         data={"payload_json": json.dumps(payload)},
                         files={"file": (f"{candidate.candidate_id}.png", png, "image/png")})
        return SendResult(ok=bool(resp.ok), status_code=resp.status_code,
                          url="<discord>", channel="discord" if resp.ok else "none",
                          error="" if resp.ok else f"discord HTTP {resp.status_code}")
    except Exception as e:  # noqa: BLE001 -- runner must keep looping
        return SendResult(ok=False, status_code=None, url="<discord>", channel="none",
                          error=_scrub(f"discord {type(e).__name__}: {e}", url) if url
                          else f"discord {type(e).__name__}: {e}")


def send_card(candidate: Candidate, chart_path: str | Path, token: str,
              *, session: requests.Session | None = None, test_title_prefix: str | None = None,
              timeout: float = 10.0, backoff: tuple[float, ...] = NTFY_BACKOFF,
              discord_fallback: bool = True) -> SendResult:
    """POST the chart PNG to ntfy with the card headers (3 tries); on final
    failure fall back to Discord #signals. Always PAPER. Never raises on a
    network error -- the eye runner must keep looping."""
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
        png = fh.read()
    last_status, last_err = None, ""
    for attempt in range(1, NTFY_ATTEMPTS + 1):
        try:
            resp = sess.post(url, data=png, headers=headers, timeout=timeout)
            last_status = resp.status_code
            if resp.ok:
                return SendResult(ok=True, status_code=resp.status_code, url=url)
            last_err = f"ntfy HTTP {resp.status_code}"
        except Exception as e:  # noqa: BLE001 -- ConnectTimeout etc.; runner must keep looping
            last_err = f"ntfy {type(e).__name__}"
        if attempt < NTFY_ATTEMPTS and attempt - 1 < len(backoff):
            time.sleep(backoff[attempt - 1])
    if not discord_fallback:
        return SendResult(ok=False, status_code=last_status, url=url, channel="none",
                          error=last_err)
    fb = send_discord_fallback(candidate, chart_path, token, session=session,
                               test_title_prefix=test_title_prefix, timeout=timeout)
    fb.error = f"{last_err} x{NTFY_ATTEMPTS}" + (f"; {fb.error}" if fb.error else "")
    return fb
