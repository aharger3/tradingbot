"""Tap-to-answer eye cards: one ntfy push per candidate, S / Not S / Skip buttons on the lock screen.

The push goes to the private alert topic (NTFY_TOPIC from the keys vault). Each button POSTs
{card_id, choice} to <tunnel>/tap/<token>: the Cloudflare tunnel hostname in front of the eye label
server (eye_card/server.py, :9135), never the Tailscale IP. The server turns an `EYE-...` tap into a
row in eye_card/labels.csv (S / notS) or eye_card/skips.csv (skip), so the tap is recorded with no
typing and scored later against the frozen fills. The old ntfy relay (token in the push, answered by
the pm2 `tap-answer` service) is still here but off unless EYE_TAP_RELAY=1.
Every card is PAPER; nothing here places an order.

Secrets come from env, then the keys vault (python keys.py get NAME). They are never logged,
never written to a file, and `redacted()` masks them when a payload is printed.

    python -m eye_card.tap sample [--blind]     # print a payload, secrets masked, send nothing
"""
from __future__ import annotations

import json
import os
import secrets as _secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .chart import Candidate
from .vault import secret

ET = ZoneInfo("America/New_York")
NTFY_BASE = "https://ntfy.sh"
# Where the phone's buttons POST: the Cloudflare tunnel hostname that fronts the eye label server (:9135).
# omen.* is the one tunnel hostname with no Access login page, so a bare button tap reaches the server.
# Override with env/vault EYE_TAP_BASE_URL. (TAP_BASE_URL is the answer-engine's, a different server.)
DEFAULT_TUNNEL_BASE = "https://omen.austinharger.com"
CARD_PREFIX = "EYE-"            # the tap server routes this prefix to labels.csv / skips.csv
LEDGER = Path(__file__).with_name("cards_sent.jsonl")   # one line per card actually sent (+ id map)

# Schedule: Mon-Thu only (the OmenEyeLoopReplay trigger and money-hour blind-tap days).
SCHEDULE_WEEKDAYS = (0, 1, 2, 3)
# Cap: the frozen slice A limit (prereg_slice_a.PREREG_SLICE_A.max_trades_per_day = 5).
# money-hour.md gives a 25-minute tap slot, not a card count, so the prereg number is the cap.
MAX_CARDS_PER_DAY = 5

# (button label shown, choice posted). ntfy allows at most 3 buttons.
BUTTONS = (("S", "S"), ("Not S", "notS"), ("Skip", "skip"))


class TapConfigError(RuntimeError):
    pass


# ---- schedule + daily cap ---------------------------------------------------------------

def schedule_ok(now: datetime, weekdays=SCHEDULE_WEEKDAYS) -> tuple[bool, str]:
    et = now.astimezone(ET)
    if et.weekday() in weekdays:
        return True, "ok"
    return False, f"{et:%A} is outside the Mon-Thu card schedule"


def cards_sent_on(day: str, ledger: Path = LEDGER) -> int:
    """Cards already sent on ET calendar day `day` (YYYY-MM-DD)."""
    try:
        lines = ledger.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    n = 0
    for ln in lines:
        try:
            if json.loads(ln).get("sent_day") == day:
                n += 1
        except ValueError:
            continue
    return n


def may_send(now: datetime, ledger: Path = LEDGER, cap: int = MAX_CARDS_PER_DAY) -> tuple[bool, str]:
    ok, why = schedule_ok(now)
    if not ok:
        return False, why
    n = cards_sent_on(f"{now.astimezone(ET):%Y-%m-%d}", ledger)
    if n >= cap:
        return False, f"daily cap reached ({n}/{cap})"
    return True, "ok"


def record_card(card_id: str, candidate_id: str, now: datetime, *, blind: bool, seq: int,
                ledger: Path = LEDGER) -> None:
    """Append the id map (card_id -> candidate_id) the later scorer needs when ids are opaque."""
    ledger.parent.mkdir(parents=True, exist_ok=True)
    row = {"card_id": card_id, "candidate_id": candidate_id, "blind": blind, "seq": seq,
           "sent_at": now.astimezone(ET).isoformat(timespec="seconds"),
           "sent_day": f"{now.astimezone(ET):%Y-%m-%d}"}
    with open(ledger, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def load_id_map(ledger: Path = LEDGER) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for ln in ledger.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
                out[r["card_id"]] = r["candidate_id"]
            except (ValueError, KeyError):
                continue
    except OSError:
        pass
    return out


# ---- ids, text, payload -----------------------------------------------------------------

def card_id_for(candidate_id: str, blind: bool) -> str:
    """Blind: opaque id (no date, grade or sequence in it). Otherwise the readable candidate id plus a
    random 4-hex suffix, so a replayed candidate never reuses an id and an old labels.csv row cannot
    answer today's card. Stays under the server's 40-char CARD_RE."""
    if blind:
        return CARD_PREFIX + _secrets.token_hex(4)
    return CARD_PREFIX + candidate_id + "-" + _secrets.token_hex(2)


def _px(x: float) -> str:
    """Price to the tick: 29609.75, not the 6-significant-digit '29609.8' that :g gives."""
    return f"{x:.2f}".rstrip("0").rstrip(".")


def _risk_reward(c: Candidate) -> tuple[float, float]:
    risk = abs(c.entry - c.stop)
    r1 = abs(c.targets[0] - c.entry) / risk if (risk and c.targets) else 0.0
    return risk, r1


def build_text(c: Candidate, *, blind: bool, seq: int, cap: int, title_prefix: str = "") -> tuple[str, str]:
    """(title, message). Short enough for a lock screen. Blind hides ticker, date, grade, absolute prices."""
    side = "Long" if c.direction.upper() == "LONG" else "Short"
    risk, r1 = _risk_reward(c)
    pre = f"{title_prefix} - " if title_prefix else ""
    if blind:
        title = f"{pre}S or Not S? {side}"
        pct = risk / c.entry * 100 if c.entry else 0.0
        lines = [f"{c.trigger_time[:5]} ET - stop {pct:.2f}% away - T1 {r1:.1f}R",
                 f"Card {seq}/{cap} - PAPER - ticker and date hidden"]
    else:
        title = f"{pre}S or Not S? {c.symbol} {side}"
        lines = [f"{c.trigger_time[:5]} ET - {c.setup}",
                 f"Entry {_px(c.entry)} - Stop {_px(c.stop)} ({_px(risk)} pt) - T1 {r1:.1f}R",
                 f"Card {seq}/{cap} - PAPER"]
    return title, "\n".join(lines)


def build_actions(card_id: str, token: str, *, answer_topic: str = "", base_url: str = "",
                  ntfy_base: str = NTFY_BASE) -> list[dict]:
    """The three tap buttons, ntfy JSON action format (same wire format as answer-engine tap/send.py)."""
    actions = []
    for label, choice in BUTTONS:
        body = {"card_id": card_id, "choice": choice}
        if base_url:
            target = {"url": f"{base_url.rstrip('/')}/tap/{token}",
                      "headers": {"Content-Type": "application/json"}}
        elif answer_topic:
            target = {"url": f"{ntfy_base.rstrip('/')}/{answer_topic}"}
            body["token"] = token
        else:
            raise TapConfigError("need TAP_BASE_URL or TAP_ANSWER_TOPIC")
        actions.append({"action": "http", "label": label, "method": "POST", "clear": True,
                        "body": json.dumps(body), **target})
    return actions


def build_tap_payload(c: Candidate, card_id: str, *, topic: str, token: str, answer_topic: str = "",
                      base_url: str = "", blind: bool = False, seq: int = 1,
                      cap: int = MAX_CARDS_PER_DAY, title_prefix: str = "", chart_url: str = "") -> dict:
    """The ntfy JSON publish body. `chart_url` is the chart image link; omitted when there is none."""
    title, message = build_text(c, blind=blind, seq=seq, cap=cap, title_prefix=title_prefix)
    payload = {"topic": topic, "title": title, "message": message, "priority": 4,
               "tags": ["eyes", "paper"],
               "actions": build_actions(card_id, token, answer_topic=answer_topic, base_url=base_url)}
    if chart_url:
        payload["attach"] = chart_url
        payload["filename"] = f"{card_id}.png"
    return payload


def redacted(payload: dict, *secret_values: str) -> str:
    out = json.dumps(payload, indent=1)
    for label, v in zip(("<TOKEN>", "<ANSWER_TOPIC>", "<ALERT_TOPIC>"), secret_values):
        if v:
            out = out.replace(v, label)
    return out


# ---- sending ----------------------------------------------------------------------------

@dataclass
class TapSendResult:
    ok: bool
    status_code: int | None
    card_id: str
    chart_url: str
    error: str = ""          # "tunnel down" when the pre-send probe failed (nothing was sent)


def tunnel_base() -> str:
    return (secret("EYE_TAP_BASE_URL") or DEFAULT_TUNNEL_BASE).rstrip("/")


def tunnel_up(base_url: str, *, session=None, timeout: float = 6.0) -> bool:
    """True if <base_url>/healthz answers {"ok": true} (the label server through the tunnel).
    A card whose buttons point at a dead tunnel would lose every tap, so the sender checks first."""
    import requests
    try:
        r = (session or requests).get(base_url.rstrip("/") + "/healthz", timeout=timeout)
        return bool(r.ok and r.json().get("ok") is True)
    except Exception:
        return False


def load_config() -> dict:
    """Buttons go through the tunnel unless EYE_TAP_RELAY=1 asks for the old ntfy answer-topic relay."""
    relay = os.environ.get("EYE_TAP_RELAY") == "1"
    cfg = {"token": secret("ANSWER_TAP_TOKEN"), "topic": secret("NTFY_TOPIC"),
           "answer_topic": secret("TAP_ANSWER_TOPIC") if relay else "",
           "base_url": "" if relay else tunnel_base()}
    if not (cfg["token"] and cfg["topic"] and (cfg["base_url"] or cfg["answer_topic"])):
        raise TapConfigError("missing ANSWER_TAP_TOKEN / NTFY_TOPIC (/ TAP_ANSWER_TOPIC with EYE_TAP_RELAY=1)")
    if not cfg["base_url"] and cfg["topic"] == "aharg-deadlines":
        # relay mode puts the token in the push: never on the guessable legacy topic
        raise TapConfigError("relay mode needs the private NTFY_TOPIC, not aharg-deadlines")
    return cfg


def upload_chart(png_path: str | Path, *, session=None, ntfy_base: str = NTFY_BASE,
                 timeout: float = 15.0) -> str:
    """Put the PNG on ntfy's attachment store (via a throwaway random topic nobody reads) and return
    its URL for the card's `attach` field. '' on any failure: the card still goes out without an image.
    The URL is only guessable by someone who can read the alert topic. [UNVERIFIED live: never run
    against ntfy.sh from the build box.]"""
    import requests
    sess = session or requests
    try:
        with open(png_path, "rb") as fh:
            r = sess.put(f"{ntfy_base.rstrip('/')}/eyechart-{_secrets.token_hex(8)}", data=fh.read(),
                         headers={"Filename": Path(png_path).name, "Title": "chart"}, timeout=timeout)
        if not r.ok:
            return ""
        return str((r.json().get("attachment") or {}).get("url") or "")
    except Exception:
        return ""


def send_tap_card(c: Candidate, png_path: str | Path | None, card_id: str, *, blind: bool = False,
                  seq: int = 1, cap: int = MAX_CARDS_PER_DAY, title_prefix: str = "",
                  session=None, config: dict | None = None, ntfy_base: str | None = None,
                  timeout: float = 15.0) -> TapSendResult:
    import requests
    cfg = config or load_config()
    base = (ntfy_base or os.environ.get("NTFY_BASE_URL") or NTFY_BASE).rstrip("/")
    sess = session or requests
    if cfg.get("base_url") and not tunnel_up(cfg["base_url"], session=sess):
        return TapSendResult(ok=False, status_code=None, card_id=card_id, chart_url="", error="tunnel down")
    chart_url = upload_chart(png_path, session=sess, ntfy_base=base) if png_path else ""
    payload = build_tap_payload(c, card_id, topic=cfg["topic"], token=cfg["token"],
                                answer_topic=cfg["answer_topic"], base_url=cfg["base_url"],
                                blind=blind, seq=seq, cap=cap, title_prefix=title_prefix,
                                chart_url=chart_url)
    resp = sess.post(base + "/", json=payload, timeout=timeout)
    return TapSendResult(ok=resp.ok, status_code=resp.status_code, card_id=card_id, chart_url=chart_url)


# ---- CLI: print a sample payload, send nothing ------------------------------------------

def _sample_candidate() -> Candidate:
    return Candidate(candidate_id="S43-1-20260907", symbol="MNQ", direction="SHORT",
                     trigger_time="10:11:00", entry=29609.75, stop=29617.25,
                     targets=[29594.75, 29579.75], level=29612.5, level_label="ORB level",
                     setup="ORB break/retest (S)", reason="S-gate clean")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m eye_card.tap")
    ap.add_argument("cmd", choices=["sample"])
    ap.add_argument("--blind", action="store_true")
    ap.add_argument("--chart-url", default="https://ntfy.sh/file/<chart>.png")
    a = ap.parse_args(argv)
    cfg = load_config()
    cand = _sample_candidate()
    payload = build_tap_payload(cand, card_id_for(cand.candidate_id, a.blind), topic=cfg["topic"],
                                token=cfg["token"], answer_topic=cfg["answer_topic"],
                                base_url=cfg["base_url"], blind=a.blind, seq=2,
                                title_prefix="OMEN REPLAY TEST", chart_url=a.chart_url)
    print(redacted(payload, cfg["token"], cfg["answer_topic"], cfg["topic"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
