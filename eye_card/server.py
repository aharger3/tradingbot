"""Tiny local label endpoint (audition-hub/ev-dashboard Flask pattern):
one Flask app, one route, CSV storage, no DB. Reachable over
Tailscale/Cloudflare, never opened to the open internet without EYE_LABEL_TOKEN.

Run:  python -m eye_card.server           (port 9135)
"""
from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, request

from .labels import append_label

BASE = Path(__file__).parent
LABELS_CSV = Path(os.environ.get("EYE_LABELS_CSV", BASE / "labels.csv"))

app = Flask(__name__)


def _token() -> str:
    return os.environ.get("EYE_LABEL_TOKEN", "dev-local-only")


@app.route("/label", methods=["GET", "POST"])
def label():
    candidate_id = request.values.get("id", "")
    lbl = request.values.get("label", "")
    token = request.values.get("token", "")
    if token != _token():
        return jsonify(ok=False, error="bad token"), 403
    if not candidate_id or lbl not in ("S", "notS"):
        return jsonify(ok=False, error="need id + label=S|notS"), 400
    channel = request.values.get("channel", "ntfy")
    row = append_label(LABELS_CSV, candidate_id, lbl, source_ip=request.remote_addr or "",
                       channel=channel)
    return jsonify(ok=True, row=row)


@app.route("/healthz")
def healthz():
    return jsonify(ok=True, mode="PAPER")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("EYE_LABEL_PORT", 9135)))
