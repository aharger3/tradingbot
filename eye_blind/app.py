"""Phone page for the blind test. A Flask blueprint so it can ride the eye-loop label server
(:9135) when EYE_BLIND=1, or run alone (`python -m eye_blind serve`, port 9136).
Same token pattern as eye_card/server.py (EYE_LABEL_TOKEN). Never shows date, price level or future bars."""
from __future__ import annotations

import hmac
import os
from pathlib import Path

from flask import Blueprint, Flask, Response, jsonify, request

from . import core

REPO = core.REPO
POOL = Path(os.environ.get("EYE_BLIND_POOL", REPO / "research" / "paper_journal" / "blind_pool.json"))
TAPS = Path(os.environ.get("EYE_BLIND_TAPS", REPO / "research" / "paper_journal" / "acks_blind.jsonl"))

blind_bp = Blueprint("blind", __name__)

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Blind test</title>
<style>
:root{--bg:#fff;--fg:#111;--mut:#666;--up:#1a9850;--dn:#d73027;--box:#4575b4;--s:#1a9850;--n:#555}
@media (prefers-color-scheme:dark){:root{--bg:#111;--fg:#eee;--mut:#999;--up:#4fc27f;--dn:#ef6b60;--box:#7aa2d6;--s:#2e9e5f;--n:#666}}
body{margin:0;padding:12px 16px;background:var(--bg);color:var(--fg);font:16px system-ui,sans-serif}
.m{color:var(--mut);font-size:14px;margin:4px 0}svg{width:100%;height:auto;max-height:60vh}
.g{stroke:var(--mut);stroke-opacity:.2}.t{fill:var(--mut);font-size:9px}
.up{stroke:var(--up);fill:var(--up)}.dn{stroke:var(--dn);fill:var(--dn)}.dec{stroke-width:2}
.or{fill:var(--box);fill-opacity:.12}.lv{stroke:var(--box);stroke-width:1}.sl{stroke:var(--dn);stroke-dasharray:4 3}
form{display:flex;gap:12px;margin-top:12px}button{flex:1;padding:22px 0;font-size:20px;font-weight:600;border:0;
border-radius:12px;color:#fff;background:var(--n)}button.s{background:var(--s)}
</style></head><body>__BODY__</body></html>"""


def _ok(tok: str) -> bool:
    return hmac.compare_digest(tok or "", os.environ.get("EYE_LABEL_TOKEN", "dev-local-only"))


def _page(body: str) -> Response:
    r = Response(PAGE.replace("__BODY__", body), mimetype="text/html")
    r.headers["Cache-Control"] = "no-store"
    return r


@blind_bp.route("/blind")
def blind_page():
    tok = request.args.get("token", "")
    if not _ok(tok):
        return Response("bad token", 403)
    if not POOL.exists():
        return _page('<p class="m">No session pool built yet (needs window-B data).</p>')
    pool = core.load_pool(POOL)
    taps = core.read_taps(TAPS)
    sid = core.next_session(pool, taps)
    if sid is None:
        return _page(f'<p>Pool finished: {len(taps)} taps logged.</p>')
    sess = pool["sessions"][sid]
    side = "LONG" if sess["side"] > 0 else "SHORT"
    body = (f'<p class="m">Session {len(taps)+1} of {len(pool["order"])} &middot; {side} candidate at the last bar</p>'
            + core.render_svg(sess, pool["cfg"])
            + f'<form method="post" action="/blind/tap"><input type="hidden" name="token" value="{tok}">'
              f'<input type="hidden" name="id" value="{sid}">'
              '<button class="s" name="label" value="S">S</button>'
              '<button name="label" value="notS">Not S</button></form>')
    return _page(body)


@blind_bp.route("/blind/tap", methods=["POST"])
def blind_tap():
    tok = request.values.get("token", "")
    if not _ok(tok):
        return jsonify(ok=False, error="bad token"), 403
    if not POOL.exists():
        return jsonify(ok=False, error="no pool"), 404
    pool = core.load_pool(POOL)
    try:
        core.append_tap(TAPS, pool, request.values.get("id", ""), request.values.get("label", ""))
    except ValueError:
        return jsonify(ok=False, error="label must be S or notS"), 400
    except KeyError:
        return jsonify(ok=False, error="unknown session"), 404
    except (FileExistsError, PermissionError) as e:
        return jsonify(ok=False, error=str(e)), 409
    r = Response("", 303)
    r.headers["Location"] = f"/blind?token={tok}"
    return r


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(blind_bp)
    return app
