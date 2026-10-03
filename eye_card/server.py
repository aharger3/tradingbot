"""Tiny local label endpoint (audition-hub/ev-dashboard Flask pattern):
one Flask app, CSV storage, no DB. Reachable over the Cloudflare tunnel (omen.austinharger.com ->
:9135), never open without a token.

Routes
  POST /tap/<token>   phone buttons on the eye cards: JSON {card_id: "EYE-...", choice: S|notS|skip}.
                      <token> is ANSWER_TAP_TOKEN (env, else the keys vault). Wrong token = 403.
  /label              legacy GET/POST id+label+token (EYE_LABEL_TOKEN), S|notS only.
  /healthz            {"ok": true, "mode": "PAPER"}; the card sender probes this before every card.
  /deck/...           W9 blind stock deck for the phone, behind a PIN cookie (eye_card/deck_gate.py).

Run:  python -m eye_card.server           (port 9135)
"""
from __future__ import annotations

import hmac
import logging
import os
import re
import time
from pathlib import Path

from flask import Flask, jsonify, request

from .deck_gate import bp as deck_bp
from .labels import append_label, record_tap
from .vault import secret

BASE = Path(__file__).parent
LABELS_CSV = Path(os.environ.get("EYE_LABELS_CSV", BASE / "labels.csv"))
CARD_RE = re.compile(r"EYE-[A-Za-z0-9_.-]{1,36}")        # same alphabet and 40-char cap as answer-engine
TOKEN_TTL_S = 60.0

app = Flask(__name__)
app.register_blueprint(deck_bp)
# The tap token rides in the URL path, so the server never writes request lines.
logging.getLogger("werkzeug").setLevel(logging.ERROR)

_tok_cache: dict = {"v": "", "t": -1e9}

if os.environ.get("EYE_BLIND") == "1":  # E5 blind test; off unless explicitly enabled
    from eye_blind.app import blind_bp
    app.register_blueprint(blind_bp)


def _token() -> str:
    return os.environ.get("EYE_LABEL_TOKEN", "")


def _tap_token() -> str:
    """ANSWER_TAP_TOKEN, cached a minute so a bad-token flood cannot spawn a vault read per request."""
    now = time.monotonic()
    if now - _tok_cache["t"] > TOKEN_TTL_S:
        _tok_cache["v"], _tok_cache["t"] = secret("ANSWER_TAP_TOKEN"), now
    return _tok_cache["v"]


@app.route("/label", methods=["GET", "POST"])
def label():
    candidate_id = request.values.get("id", "")
    lbl = request.values.get("label", "")
    token = request.values.get("token", "")
    want = _token()
    if not want or want == "dev-local-only" or not hmac.compare_digest(token.encode(), want.encode()):
        return jsonify(ok=False, error="bad token"), 403
    if not candidate_id or lbl not in ("S", "notS"):
        return jsonify(ok=False, error="need id + label=S|notS"), 400
    row = append_label(LABELS_CSV, candidate_id, lbl, source_ip=request.remote_addr or "")
    return jsonify(ok=True, row=row)


@app.route("/tap/<token>", methods=["POST"])
def tap(token):
    want = _tap_token()
    if not want or not hmac.compare_digest(token.encode(), want.encode()):
        return jsonify(ok=False, error="forbidden"), 403
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(ok=False, error="need JSON {card_id, choice}"), 400
    card_id, choice = str(body.get("card_id", "")).strip(), str(body.get("choice", ""))
    if not CARD_RE.fullmatch(card_id):
        return jsonify(ok=False, error="bad card_id"), 400
    try:
        row = record_tap(LABELS_CSV, card_id, choice, source_ip="tunnel")
    except ValueError:
        return jsonify(ok=False, error="bad choice"), 400
    return jsonify(ok=True, recorded=row is not None, label=(row or {}).get("label"))


@app.route("/healthz")
def healthz():
    return jsonify(ok=True, mode="PAPER")


if __name__ == "__main__":
    if _token() in ("", "dev-local-only"):
        raise SystemExit("refusing to start: EYE_LABEL_TOKEN unset or default")
    app.run(host="0.0.0.0", port=int(os.environ.get("EYE_LABEL_PORT", 9135)))
