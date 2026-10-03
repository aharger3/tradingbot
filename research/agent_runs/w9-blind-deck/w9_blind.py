"""W9 blind stock deck: runtime (serve the cards, log taps, lock, score). Paper research, not investment advice, no orders.

Pre-registered in life-plan 07-money/omen/night-1003/prereg-blind-stocks.md. Stdlib + numpy + cryptography only, so a copy of this
file can sit next to the deck (build copies it there) and run without the tradingbot checkout.

  python w9_blind.py serve  [--dir D] [--port 9137] [--lan]   phone-friendly tap page, one card at a time, in order
  python w9_blind.py status [--dir D]                          counts only, never outcomes
  python w9_blind.py verify [--dir D]                          image + sealed-file hashes vs deck.json (no decryption)
  python w9_blind.py score  [--dir D] [--key-file F]           refuses until the verdict locks; then unseals, checks the commitment, scores

Rules enforced in code (not by promise):
  * taps arrive strictly in deck order, one per card, no edit, no skip;
  * the verdict locks at the end of the first complete 40-card deck where cumulative S taps >= 30 (or after the last of the 20 decks: INCONCLUSIVE);
    taps past the lock are refused, so nothing tapped after seeing a result can change it;
  * the outcomes (R per card) exist only inside sealed.bin (Fernet) with a sha256 commitment in deck.json; `score` unseals them only
    after the lock and aborts if the commitment does not match;
  * `status` and the page print counts only.
Sealing keeps outcomes out of casual sight and makes later tampering detectable. It cannot stop someone who re-runs the frozen sim
on the 1-minute bars; that is a limit of any blind test on history and is stated in the prereg.
"""
import os, sys, json, hashlib, secrets, threading, argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import numpy as np

DECK_SIZE, N_DECKS, MIN_S = 40, 20, 30
BAR_MEAN, BAR_P = 0.25, 0.05
SEED_PERM, NPERM, NBOOT = 20261009, 10000, 5000
DEFAULT_KEY_FILE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "w9-blind", "seal.key")
CHOICES = ("S", "notS")


# ------------------------------------------------------------------ sealing
def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def seal(payload, key):
    """-> (ciphertext bytes, commitment hex). commitment = sha256(salt ':' canonical(payload)); the salt rides inside the ciphertext."""
    from cryptography.fernet import Fernet
    salt = secrets.token_hex(16)
    body = canonical(payload)
    commitment = sha256(salt.encode() + b":" + body)
    return Fernet(key).encrypt(canonical({"salt": salt, "body": payload})), commitment


def unseal(token, key, commitment):
    from cryptography.fernet import Fernet
    d = json.loads(Fernet(key).decrypt(token))
    if sha256(d["salt"].encode() + b":" + canonical(d["body"])) != commitment:
        raise ValueError("sealed outcomes do not match the commitment in deck.json: refusing to score")
    return d["body"]


def read_key(key_file=None):
    fp = key_file or os.environ.get("W9_SEAL_KEY_FILE") or DEFAULT_KEY_FILE
    with open(fp, "rb") as f:
        return f.read().strip()


# ------------------------------------------------------------------ taps (append-only, hash-chained to the deck commitment)
def load_taps(path, commitment):
    taps, prev = [], commitment
    if not os.path.exists(path):
        return taps
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            t = json.loads(line)
            h = t.pop("h")
            if t["prev"] != prev or sha256(canonical(t)) != h:
                raise ValueError("taps.jsonl chain is broken at tap %d" % (len(taps) + 1))
            t["h"] = h
            taps.append(t)
            prev = h
    return taps


def append_tap(path, commitment, taps, card_id, choice, ts=None):
    prev = taps[-1]["h"] if taps else commitment
    t = dict(i=len(taps), id=card_id, choice=choice, ts=ts or datetime.now(timezone.utc).isoformat(timespec="seconds"), prev=prev)
    t["h"] = sha256(canonical(t))
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(t, sort_keys=True) + "\n")
    taps.append(t)
    return t


def lock_status(choices, deck_size=DECK_SIZE, n_decks=N_DECKS, min_s=MIN_S):
    """Verdict rule, decided on labels only. Looks only at complete decks."""
    for d in range(1, n_decks + 1):
        hi = d * deck_size
        if len(choices) < hi:
            break
        cum = sum(c == "S" for c in choices[:hi])
        if cum >= min_s:
            return dict(state="LOCKED", decks=d, n_used=hi, n_s=cum)
        if d == n_decks:
            return dict(state="LOCKED_INCONCLUSIVE", decks=d, n_used=hi, n_s=cum)
    return dict(state="IN_PROGRESS", decks=len(choices) // deck_size, n_used=len(choices), n_s=sum(c == "S" for c in choices))


def is_locked(st):
    return st["state"] != "IN_PROGRESS"


# ------------------------------------------------------------------ scoring
def score(cards, choices, seed=SEED_PERM, nperm=NPERM, nboot=NBOOT, min_s=MIN_S):
    """cards: [{id,day,r,...}] in deck order (sealed); choices: tap labels for the first len(choices) cards (the used decks).
    Primary test: day-stratified permutation. The S labels are reshuffled among the cards of the SAME day (each day keeps its number of
    S taps), so the null cannot be 'he picks good days'. One-sided, 10,000 shuffles."""
    n = len(choices)
    r = np.array([c["r"] for c in cards[:n]], float)
    day = np.array([c["day"] for c in cards[:n]])
    isS = np.array([c == "S" for c in choices])
    nS = int(isS.sum())
    out = dict(n_cards_used=n, n_S=nS, n_notS=int(n - nS))
    if nS == 0:
        out.update(verdict="INCONCLUSIVE", reason="no S taps")
        return out
    obs = float(r[isS].mean())
    rng = np.random.default_rng(seed)
    groups = [(r[day == d], int(isS[day == d].sum())) for d in np.unique(day)]
    perm = np.empty(nperm)
    for p in range(nperm):
        tot = 0.0
        for rd, k in groups:
            if k:
                tot += rd[rng.permutation(len(rd))[:k]].sum()
        perm[p] = tot / nS
    p_val = float((1 + np.sum(perm >= obs - 1e-9)) / (1 + nperm))
    sdays = day[isS]
    ud = np.unique(sdays)
    g = {d: r[isS][sdays == d] for d in ud}
    boots = np.array([np.concatenate([g[d] for d in ud[rng.integers(len(ud), size=len(ud))]]).mean() for _ in range(nboot)])
    dates = sorted(sdays)
    mid = dates[len(dates) // 2]
    h1 = sdays < mid
    byday = {}
    for rr, dd in zip(r[isS], sdays):
        byday[dd] = byday.get(dd, 0.0) + rr
    top5 = sorted(byday, key=lambda d: -byday[d])[:5]
    tot = r[isS].sum()
    out.update(
        S_mean_R=obs, S_win=float((r[isS] > 0).mean()), notS_mean_R=float(r[~isS].mean()) if (~isS).any() else None,
        all_cards_mean_R=float(r.mean()), S_minus_notS=float(obs - r[~isS].mean()) if (~isS).any() else None,
        perm_null_mean=float(perm.mean()), perm_null_sd=float(perm.std()), excess_vs_perm_null=float(obs - perm.mean()),
        day_perm_p_one_sided=p_val, S_mean_ci95_day_boot=[float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
        H1_S_mean=float(r[isS][h1].mean()) if h1.any() else None, H1_n=int(h1.sum()),
        H2_S_mean=float(r[isS][~h1].mean()) if (~h1).any() else None, H2_n=int((~h1).sum()),
        top5_day_share=float(sum(byday[d] for d in top5) / tot) if tot > 0 else None, n_S_days=int(len(ud)),
    )
    bar = dict(n_S_ge_30=nS >= min_s, S_mean_ge_025=obs >= BAR_MEAN, day_perm_p_lt_005=p_val < BAR_P)
    out["bar"] = bar
    out["verdict"] = "PASS" if all(bar.values()) else ("FAIL" if nS >= min_s else "INCONCLUSIVE")
    return out


# ------------------------------------------------------------------ deck dir
class Deck:
    def __init__(self, d):
        self.dir = d
        with open(os.path.join(d, "deck.json"), encoding="utf-8") as f:
            self.m = json.load(f)
        self.cards = self.m["cards"]          # public: id, deck, pos, img, img_sha256  (no ticker, no date, no outcome)
        self.commitment = self.m["commitment"]
        self.taps_path = os.path.join(d, "taps.jsonl")
        self.taps = load_taps(self.taps_path, self.commitment)
        self.lock = threading.Lock()

    def choices(self):
        return [t["choice"] for t in self.taps]

    def state(self):
        st = lock_status(self.choices(), self.m["deck_size"], self.m["n_decks"], self.m["min_s"])
        n = len(self.taps)
        out = dict(state=st["state"], answered=n, total=len(self.cards), n_S=self.choices().count("S"),
                   deck_size=self.m["deck_size"], n_decks=self.m["n_decks"])
        if is_locked(st):
            out["message"] = ("Done. Your taps are locked in and the verdict gets computed from them; nothing more to tap." if st["state"] == "LOCKED"
                              else "All decks tapped with fewer than %d S taps: inconclusive. Nothing more to tap." % self.m["min_s"])
            return out
        c = self.cards[n]
        out.update(card=dict(id=c["id"], img="img/%s.png" % c["id"]), deck=c["deck"], pos=c["pos"],
                   between_decks=(n > 0 and n % self.m["deck_size"] == 0), decks_done=n // self.m["deck_size"])
        return out

    def tap(self, card_id, choice):
        with self.lock:
            st = lock_status(self.choices(), self.m["deck_size"], self.m["n_decks"], self.m["min_s"])
            if is_locked(st):
                return False, "locked"
            if choice not in CHOICES:
                return False, "bad choice"
            if card_id != self.cards[len(self.taps)]["id"]:
                return False, "not the current card"
            append_tap(self.taps_path, self.commitment, self.taps, card_id, choice)
            return True, "ok"

    def image(self, card_id):
        ids = {c["id"] for c in self.cards}
        if card_id not in ids:
            return None
        with open(os.path.join(self.dir, "img", card_id + ".png"), "rb") as f:
            return f.read()


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blind deck</title><style>
:root{--bg:#fff;--fg:#111;--mut:#666;--s:#0a7f3f;--n:#8a2be2;--card:#f4f4f6}
@media (prefers-color-scheme:dark){:root{--bg:#111;--fg:#eee;--mut:#999;--card:#1c1c20}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px system-ui,sans-serif;display:flex;flex-direction:column;min-height:100vh}
main{max-width:720px;width:100%;margin:0 auto;padding:12px 16px;box-sizing:border-box;flex:1}
img{width:100%;height:auto;border-radius:8px;background:var(--card)}
.bar{color:var(--mut);display:flex;justify-content:space-between;margin:4px 0 10px}
.btns{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}
button{font-size:26px;padding:22px 0;border:0;border-radius:12px;color:#fff;font-weight:700}
#bS{background:var(--s)}#bN{background:var(--n)}button:disabled{opacity:.4}
.note{color:var(--mut);margin-top:12px;font-size:14px}.big{font-size:20px;margin:30px 0}
</style></head><body><main id="m"><p>Loading...</p></main><script>
const base=location.pathname.replace(/\\/$/,'');let st=null,busy=false,cont=false;
async function load(){st=await (await fetch(base+'/api/state',{cache:'no-store'})).json();draw()}
function draw(){const m=document.getElementById('m');
 if(st.state!=='IN_PROGRESS'){m.innerHTML='<p class="big">'+st.message+'</p><p class="note">'+st.answered+' cards tapped.</p>';return}
 if(st.between_decks&&!cont){m.innerHTML='<p class="big">Deck '+st.decks_done+' done ('+st.answered+' cards).</p><p class="note">Stop here or keep going. Taps so far: '+st.n_S+' S.</p><div class="btns"><button id="bS" onclick="cont=true;draw()">Next deck</button><button id="bN" style="background:#555" onclick="document.getElementById(\\'m\\').innerHTML=\\'<p class=big>Paused. Close this tab; come back any time.</p>\\'">Stop</button></div>';return}
 m.innerHTML='<div class="bar"><span>Deck '+st.deck+' of '+st.n_decks+'</span><span>Card '+st.pos+' / '+st.deck_size+'</span></div><img src="'+base+'/'+st.card.img+'" alt="chart cut at the decision bar">'+
 '<div class="btns"><button id="bS">S</button><button id="bN">Not S</button></div><p class="note">Trade it as shown: next bar, the stop on the chart. Keys: S / N. No undo, no skip.</p>';
 document.getElementById('bS').onclick=()=>tap('S');document.getElementById('bN').onclick=()=>tap('notS')}
async function tap(c){if(busy)return;busy=true;const r=await fetch(base+'/api/tap',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:st.card.id,choice:c})});
 if(r.ok){cont=false;await load()}else{await load()}busy=false}
document.addEventListener('keydown',e=>{if(!st||st.state!=='IN_PROGRESS'||(st.between_decks&&!cont))return;if(e.key==='s'||e.key==='S')tap('S');if(e.key==='n'||e.key==='N')tap('notS')});
load();</script></body></html>"""


def make_handler(deck, token):
    prefix = "/t/" + token

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _route(self):
            p = urlparse(self.path).path
            if not (p == prefix or p.startswith(prefix + "/")):
                return None
            return p[len(prefix):] or "/"

        def do_GET(self):
            r = self._route()
            if r is None:
                return self._send(403, {"error": "forbidden"})
            if r == "/":
                return self._send(200, PAGE, "text/html; charset=utf-8")
            if r == "/api/state":
                return self._send(200, deck.state())
            if r.startswith("/img/") and r.endswith(".png"):
                b = deck.image(r[5:-4])
                return self._send(200, b, "image/png") if b else self._send(404, {"error": "no such card"})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            r = self._route()
            if r is None:
                return self._send(403, {"error": "forbidden"})
            if r != "/api/tap":
                return self._send(404, {"error": "not found"})
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                ok, msg = deck.tap(str(body.get("id")), str(body.get("choice")))
            except Exception:
                return self._send(400, {"error": "bad request"})
            return self._send(200 if ok else 409, {"ok": ok, "msg": msg})

    return H


def get_token(d):
    fp = os.path.join(d, "token.txt")
    if not os.path.exists(fp):
        with open(fp, "w") as f:
            f.write(secrets.token_urlsafe(12))
    return open(fp).read().strip()


# ------------------------------------------------------------------ CLI
def cmd_status(d):
    deck = Deck(d)
    st = lock_status(deck.choices(), deck.m["deck_size"], deck.m["n_decks"], deck.m["min_s"])
    n_s, done = deck.choices().count("S"), len(deck.taps) // deck.m["deck_size"]
    proj = None
    if done and n_s:                                   # counts only: decks needed at the S rate so far
        proj = max(done, -(-deck.m["min_s"] * done // n_s))
    print(json.dumps(dict(state=st["state"], taps=len(deck.taps), n_S=n_s, decks_complete=done, cards=len(deck.cards),
                          lock_needs="S taps >= %d at the end of a complete deck" % deck.m["min_s"],
                          projected_decks_to_lock=proj, decks_available=deck.m["n_decks"])))
    return st


def cmd_verify(d):
    deck = Deck(d)
    bad = []
    for c in deck.cards:
        with open(os.path.join(d, "img", c["id"] + ".png"), "rb") as f:
            if sha256(f.read()) != c["img_sha256"]:
                bad.append(c["id"])
    with open(os.path.join(d, "sealed.bin"), "rb") as f:
        if sha256(f.read()) != deck.m["sealed_sha256"]:
            bad.append("sealed.bin")
    print(json.dumps(dict(cards=len(deck.cards), decks=len({c["deck"] for c in deck.cards}), commitment=deck.commitment,
                          sealed_sha256=deck.m["sealed_sha256"], bad=bad)))
    return not bad


def cmd_score(d, key_file=None):
    deck = Deck(d)
    st = lock_status(deck.choices(), deck.m["deck_size"], deck.m["n_decks"], deck.m["min_s"])
    if not is_locked(st):
        print(json.dumps(dict(refused="verdict not locked yet", taps=len(deck.taps), n_S=st["n_s"],
                              needs="complete decks until cumulative S taps >= %d (or all %d decks)" % (deck.m["min_s"], deck.m["n_decks"]))))
        return None
    with open(os.path.join(d, "sealed.bin"), "rb") as f:
        token = f.read()
    if sha256(token) != deck.m["sealed_sha256"]:
        raise ValueError("sealed.bin hash differs from deck.json")
    sealed = unseal(token, read_key(key_file), deck.commitment)
    by_id = {c["id"]: c for c in sealed["cards"]}
    cards = [by_id[c["id"]] for c in deck.cards]
    res = score(cards, deck.choices()[:st["n_used"]], min_s=deck.m["min_s"])
    if st["state"] == "LOCKED_INCONCLUSIVE":
        res["verdict"] = "INCONCLUSIVE"
    res["lock"] = st
    res["commitment"] = deck.commitment
    with open(os.path.join(d, "result.json"), "w") as f:
        json.dump(res, f, indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["serve", "status", "verify", "score"])
    ap.add_argument("--dir", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--port", type=int, default=9137)
    ap.add_argument("--lan", action="store_true", help="listen on all interfaces (phone on the same Wi-Fi); default is this PC only")
    ap.add_argument("--key-file", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "status":
        cmd_status(a.dir)
    elif a.cmd == "verify":
        sys.exit(0 if cmd_verify(a.dir) else 1)
    elif a.cmd == "score":
        cmd_score(a.dir, a.key_file)
    else:
        deck = Deck(a.dir)
        tok = get_token(a.dir)
        srv = ThreadingHTTPServer(("0.0.0.0" if a.lan else "127.0.0.1", a.port), make_handler(deck, tok))
        host = "127.0.0.1"
        if a.lan:
            import socket
            try:
                host = socket.gethostbyname(socket.gethostname())
            except OSError:
                pass
        print("Blind deck: open http://%s:%d/t/%s/ (keep this window open; Ctrl+C stops it)" % (host, a.port, tok), flush=True)
        srv.serve_forever()


if __name__ == "__main__":
    main()
