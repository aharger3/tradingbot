"""notify_ntfy.py — the phone lane. One function, one job, never raises.

omen-8 ticket 01. Austin is away from the keyboard when OMEN would trade, so the
one thing the machine owes him is a notification at the moment it fires. ntfy.sh
is the surface: a public topic, no auth, no account, and the box already talks to
it (`Desktop\\Scripts\\card_relay.py` has used the same POST since 2026-09-03).

Slack is where AUGUR's daily structure will go (the 11:00 summary text, the
homework link, the evening reveal). The live S push stays here — a trade alert
has to survive a locked phone, and that is what ntfy does and Slack does not.

**This module must never take the scanner down.** A notification is a courtesy;
a missed trade is the actual cost. Every failure path returns False and logs one
line. Nothing in here raises, including a completely unreachable ntfy.

    from notify_ntfy import push
    push("OMEN S TSLA CALL", "entry 412.50 / stop 410.80 ...", priority="high",
         tags="rocket")

Topic resolution, in order: the `topic` argument, then `OMEN_NTFY_TOPIC`. With
neither set the call is a NO-OP that logs what it would have sent — so a dev box,
a test run, and a fresh clone are all silent by default, and going live is one
environment variable rather than a code change. Blackout dates do not apply: this
lane is Austin's own alert, not an outward-facing post.
"""
from __future__ import annotations

import os
import sys

import requests

NTFY_BASE = "https://ntfy.sh"
TOPIC_ENV = "OMEN_NTFY_TOPIC"
TIMEOUT_SECONDS = 8


def _log(msg: str) -> None:
    """One line to stdout. The scanner's log is the only place this is read."""
    print(f"  ntfy: {msg}", file=sys.stdout, flush=True)


def resolve_topic(topic: str | None = None) -> str | None:
    """The topic this process would publish to, or None when unconfigured.

    Exposed so a caller can decide whether to bother BUILDING a push body at
    all, and so a test can assert the unset-env case without monkeypatching.
    """
    return (topic or os.getenv(TOPIC_ENV) or "").strip() or None


def push(title: str, body: str, priority: str = "default",
         tags=None, click: str | None = None,
         topic: str | None = None) -> bool:
    """POST one notification. Returns True only on a 2xx.

    `tags` may be a string ("rocket") or any iterable of strings; ntfy wants a
    comma-separated header either way. `priority` takes ntfy's own names
    ("min", "low", "default", "high", "urgent") or "1".."5".

    Retries once. Two attempts is the right number here: a single transient
    blip is worth a retry, and anything more is an ntfy outage — in which case
    the scanner has better things to do than sit in a backoff loop while a
    trading window is open.
    """
    resolved = resolve_topic(topic)
    if resolved is None:
        _log(f"{TOPIC_ENV} unset — not sending. Would have been: {title!r} / "
             f"{body.splitlines()[0] if body else ''!r}")
        return False

    if tags is None:
        tag_header = None
    elif isinstance(tags, str):
        tag_header = tags
    else:
        tag_header = ",".join(str(t) for t in tags)

    # ntfy reads the metadata off headers, and a header must be latin-1 clean.
    # Austin's cards are plain ASCII, but a symbol or a reason string arriving
    # with a stray unicode dash would otherwise raise INSIDE requests, which is
    # exactly the "never take the scanner down" case this module exists for.
    def _hdr(v: str) -> str:
        return v.encode("latin-1", "replace").decode("latin-1")

    headers = {"Title": _hdr(title), "Priority": _hdr(priority)}
    if tag_header:
        headers["Tags"] = _hdr(tag_header)
    if click:
        headers["Click"] = _hdr(click)

    url = f"{NTFY_BASE}/{resolved}"
    last = ""
    for attempt in (1, 2):
        try:
            resp = requests.post(url, data=body.encode("utf-8"),
                                 headers=headers, timeout=TIMEOUT_SECONDS)
            if resp.ok:
                _log(f"sent to {resolved}: {title} [{resp.status_code}]")
                return True
            last = f"HTTP {resp.status_code}"
        except Exception as e:                      # noqa: BLE001 — see docstring
            last = f"{type(e).__name__}: {str(e)[:120]}"
        if attempt == 1:
            _log(f"attempt 1 failed ({last}), retrying once")
    _log(f"FAILED to {resolved} after 2 attempts ({last}): {title}")
    return False


MAX_ATTACH_BYTES = 15 * 1024 * 1024      # ntfy.sh's documented per-file ceiling


def attach(path, title: str, body: str = "", filename: str | None = None,
           priority: str = "default", tags=None,
           topic: str | None = None) -> bool:
    """PUT one FILE to the topic as an ntfy attachment. Returns True on a 2xx.

    AUGUR's 11:05 lane (omen-8 ticket 02). The homework deck is a single
    self-contained HTML file -- charts are static SVG rendered in Python and
    persistence is localStorage, so the file IS the app and there is nothing to
    host. ntfy stores the attachment and the phone notification carries a link
    to it, which is the whole delivery: no server, no account, no round trip.

    The headless-artifact route was tried first on 2026-09-03 and the `claude`
    CLI on this box answered "Credit balance is too low", so it is not a lane
    that can be scheduled. This is.

    Same never-raise contract as `push`: every failure path returns False and
    logs one line. A deck that failed to send is a bad morning, not a crash.

    ONE NOTIFICATION, NOT TWO. On an attachment PUT the request body IS the
    file, so the sentence travels in the `Message` header instead; ntfy turns a
    literal backslash-n there into a real newline, which is why `body` is escaped
    rather than sent raw (a raw newline in an HTTP header is not sendable at
    all). The first cut of this function pushed the text separately and then the
    file, and his phone buzzed twice for one deck.
    """
    resolved = resolve_topic(topic)
    if resolved is None:
        _log(f"{TOPIC_ENV} unset — not sending {path}")
        return False
    try:
        data = open(path, "rb").read()
    except OSError as e:
        _log(f"cannot read {path}: {type(e).__name__}: {e}")
        return False
    if len(data) > MAX_ATTACH_BYTES:
        _log(f"{path} is {len(data)} bytes, over ntfy's {MAX_ATTACH_BYTES} "
             f"limit — not sending")
        return False

    def _hdr(v: str) -> str:
        return v.encode("latin-1", "replace").decode("latin-1")

    import os.path
    headers = {"Title": _hdr(title), "Priority": _hdr(priority),
               "Filename": _hdr(filename or os.path.basename(str(path)))}
    if body:
        # Newlines are escaped for the header and ntfy unescapes them; a stray
        # carriage return would be a header-injection vector, so both go.
        headers["Message"] = _hdr(
            body.replace(chr(13), "").replace(chr(10), chr(92) + "n"))
    if tags:
        headers["Tags"] = _hdr(tags if isinstance(tags, str)
                               else ",".join(str(t) for t in tags))
    url = f"{NTFY_BASE}/{resolved}"
    last = ""
    for attempt in (1, 2):
        try:
            # A 770 KB upload over a phone-grade link needs more than the 8s a
            # text push gets; the retry then costs at most another minute.
            resp = requests.put(url, data=data, headers=headers, timeout=60)
            if resp.ok:
                _log(f"attached {headers['Filename']} ({len(data)} bytes) to "
                     f"{resolved} [{resp.status_code}]")
                return True
            last = f"HTTP {resp.status_code}"
        except Exception as e:                      # noqa: BLE001 — see docstring
            last = f"{type(e).__name__}: {str(e)[:120]}"
        if attempt == 1:
            _log(f"attach attempt 1 failed ({last}), retrying once")
    _log(f"FAILED to attach {path} to {resolved} after 2 attempts ({last})")
    return False


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Send one ntfy notification")
    ap.add_argument("--topic", default=None, help=f"overrides ${TOPIC_ENV}")
    ap.add_argument("--title", default="OMEN test")
    ap.add_argument("--body", default="Live S pushes start next session. "
                                      "Reply not needed.")
    ap.add_argument("--priority", default="default")
    ap.add_argument("--tags", default=None)
    ap.add_argument("--file", default=None,
                    help="send this file as an attachment instead of a text push")
    ap.add_argument("--filename", default=None, help="name the phone shows")
    a = ap.parse_args()
    if a.file:
        ok = attach(a.file, a.title, body=a.body, filename=a.filename,
                    priority=a.priority, tags=a.tags, topic=a.topic)
    else:
        ok = push(a.title, a.body, priority=a.priority, tags=a.tags,
                  topic=a.topic)
    sys.exit(0 if ok else 1)
