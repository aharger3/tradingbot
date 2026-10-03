"""PIN-gated phone front for the W9 blind stock deck, served by the eye label server (omen.austinharger.com).

Paper research on Austin's own taps. Not investment advice, no orders.

The deck itself (cards, tap chain, lock rule, sealing) is the frozen `w9_blind.py` that sits in the deck folder; its sha256 is in
the prereg and in deck.json, so this module LOADS it unmodified and never edits it. Rules kept here:

  * every route except the PIN page needs a valid PIN cookie (page 401, api 401). No PIN configured = 503 (fail closed).
  * 5 wrong PINs = 429 for 15 minutes (global counter: behind the tunnel every caller is localhost).
  * only public deck fields leave this module: card id, image, deck/pos, counts. It never opens sealed.bin or the seal key and never
    calls unseal/score, so outcomes cannot reach a client. deck.json is not served.
  * two buttons only (S / Not S), in deck order, one tap per card: the prereg says "no skip, no undo, no edit" and w9_blind.Deck.tap
    enforces it. A Skip button would break the hash-chained tap order, so it is deliberately absent.

Routes (all under /deck)
  GET  /deck/            PIN form (401) or the tap page (200)
  POST /deck/login       form field `pin` -> 303 + 30-day cookie, or 401 / 429
  GET  /deck/api/state   {state, answered, total, n_S, card:{id,img}, deck, pos, ...}   (counts only)
  GET  /deck/img/<id>.png
  POST /deck/api/tap     JSON {id, choice: S|notS}
"""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import os
import re
import threading
import time
from html import escape
from pathlib import Path

from flask import Blueprint, Response, jsonify, redirect, request

from .vault import secret

DEFAULT_DECK_DIR = r"C:\Users\aharg\Desktop\AI-Outputs\w9-blind-deck"
COOKIE = "w9deck"
COOKIE_TTL_S = 30 * 24 * 3600
MAX_FAILS, LOCKOUT_S = 5, 15 * 60
PIN_CACHE_S = 60.0
CARD_ID_RE = re.compile(r"W9-[A-Za-z0-9]{1,16}")

bp = Blueprint("w9deck", __name__, url_prefix="/deck")

_lock = threading.Lock()          # serialises taps (the tap chain is a file) and guards the fail counter
_pin_cache: dict = {"v": "", "t": -1e9}
_fails: dict = {"n": 0, "until": 0.0}
_mod: dict = {}


def deck_dir() -> Path:
    return Path(os.environ.get("W9_DECK_DIR", DEFAULT_DECK_DIR))


def _w9():
    """Load w9_blind.py from the deck folder, unmodified (its hash is in the prereg). Cached per path."""
    p = deck_dir() / "w9_blind.py"
    key = str(p)
    if key not in _mod:
        spec = importlib.util.spec_from_file_location("w9_blind_frozen", p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _mod[key] = m
    return _mod[key]


def _deck():
    """A fresh Deck per request: re-reads deck.json and verifies the tap chain, so a second process cannot leave us stale."""
    return _w9().Deck(str(deck_dir()))


def _pin() -> str:
    """W9_DECK_PIN from env/vault, else READER_PIN (one PIN for the phone sites). Cached a minute."""
    now = time.monotonic()
    if now - _pin_cache["t"] > PIN_CACHE_S:
        _pin_cache["v"] = secret("W9_DECK_PIN") or secret("READER_PIN")
        _pin_cache["t"] = now
    return _pin_cache["v"]


def _sign(pin: str, exp: int) -> str:
    key = hashlib.sha256(b"w9deck-cookie:" + pin.encode()).digest()
    return hmac.new(key, str(exp).encode(), hashlib.sha256).hexdigest()


def _authed() -> bool:
    pin = _pin()
    raw = request.cookies.get(COOKIE, "")
    if not pin or "." not in raw:
        return False
    exp_s, sig = raw.split(".", 1)
    if not exp_s.isdigit() or int(exp_s) < time.time():
        return False
    return hmac.compare_digest(sig.encode(), _sign(pin, int(exp_s)).encode())


def _secure() -> bool:
    return request.is_secure or request.headers.get("X-Forwarded-Proto", "") == "https"


def _nostore(resp):
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Robots-Tag"] = "noindex"
    return resp


LOGIN = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blind deck</title><style>
:root{color-scheme:light dark}body{font:18px system-ui,sans-serif;max-width:420px;margin:12vh auto;padding:0 20px}
input,button{font-size:22px;padding:14px;width:100%;box-sizing:border-box;margin-top:12px;border-radius:10px;border:1px solid #888}
button{background:#0a7f3f;color:#fff;border:0;font-weight:700}.e{color:#c0392b}</style></head><body>
<h2>Blind deck</h2><form method="post" action="login"><input name="pin" type="password" inputmode="text" autocomplete="current-password" autofocus placeholder="PIN">
<button type="submit">Open</button></form><p class="e">@@MSG@@</p></body></html>"""


# an expired cookie makes the frozen page's fetches return 401: reload so the PIN form shows instead of "undefined"
RELOAD_ON_401 = "const _f=window.fetch;window.fetch=async(...a)=>{const r=await _f(...a);if(r.status===401)location.reload();return r};"


def _login_page(msg: str = "", code: int = 401):
    return _nostore(Response(LOGIN.replace("@@MSG@@", escape(msg)), status=code, mimetype="text/html"))


def _api_denied():
    return _nostore(jsonify(ok=False, error="PIN required")), 401


@bp.route("/", methods=["GET"])
def page():
    if not _pin():
        return _nostore(Response("deck not configured", status=503))
    if not _authed():
        return _login_page()
    html = _w9().PAGE.replace("<script>", "<script>" + RELOAD_ON_401, 1)
    return _nostore(Response(html, mimetype="text/html"))


@bp.route("/login", methods=["POST"])
def login():
    pin = _pin()
    if not pin:
        return _nostore(Response("deck not configured", status=503))
    with _lock:
        now = time.time()
        if now < _fails["until"]:
            return _login_page("Too many tries. Wait 15 minutes.", 429)
        ok = hmac.compare_digest(request.form.get("pin", "").encode(), pin.encode())
        if not ok:
            _fails["n"] += 1
            if _fails["n"] >= MAX_FAILS:
                _fails["n"], _fails["until"] = 0, now + LOCKOUT_S
                return _login_page("Too many tries. Wait 15 minutes.", 429)
            return _login_page("Wrong PIN.")
        _fails["n"] = 0
    exp = int(time.time()) + COOKIE_TTL_S
    resp = redirect("./", code=303)
    resp.set_cookie(COOKIE, f"{exp}.{_sign(pin, exp)}", max_age=COOKIE_TTL_S, httponly=True, samesite="Lax",
                    secure=_secure(), path="/deck")
    return _nostore(resp)


@bp.route("/api/state", methods=["GET"])
def state():
    if not _authed():
        return _api_denied()
    return _nostore(jsonify(_deck().state()))


@bp.route("/img/<card_id>.png", methods=["GET"])
def img(card_id):
    if not _authed():
        return _api_denied()
    if not CARD_ID_RE.fullmatch(card_id):
        return _nostore(jsonify(ok=False, error="no such card")), 404
    b = _deck().image(card_id)
    if b is None:
        return _nostore(jsonify(ok=False, error="no such card")), 404
    return _nostore(Response(b, mimetype="image/png"))


@bp.route("/api/tap", methods=["POST"])
def tap():
    if not _authed():
        return _api_denied()
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _nostore(jsonify(ok=False, error="need JSON {id, choice}")), 400
    with _lock:
        ok, msg = _deck().tap(str(body.get("id", "")), str(body.get("choice", "")))
    return _nostore(jsonify(ok=ok, msg=msg)), (200 if ok else 409)
