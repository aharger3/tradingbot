import os, sys, json, threading, hashlib, urllib.request, urllib.error
import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "s2-stocks"))
import w9_blind as W
import w9_build as B
import s2_lib as L


# ---------------------------------------------------------------- helpers
def synth_bars(seed=1, base=100.0, up=True):
    rng = np.random.default_rng(seed)
    m = np.arange(240, 1200)                                 # 04:00..19:59
    c = base + np.cumsum(rng.normal(0, 0.05, len(m)))
    o = np.r_[base, c[:-1]]
    return dict(m=m, O=o, H=np.maximum(o, c) + 0.03, L=np.minimum(o, c) - 0.03, C=c, V=rng.integers(100, 5000, len(m)).astype(float))


def cand(sym, day, m, side=1, stop=99.0):
    return dict(sym=sym, day=day, m=m, side=side, stop=stop, level_px=100.0)


def fake_pool(n_days=6, per_day=12):
    out = []
    for d in range(n_days):
        day = "2025-02-%02d" % (d + 3)
        for k in range(per_day):
            out.append(cand(["AAA", "BBB", "CCC"][k % 3], day, 580 + 4 * k, 1 if k % 2 else -1, 99.0 if k % 2 else 101.0))
    return out


def write_prereg(path, extra=()):
    hs = [B.sha_text(os.path.join(HERE, f)) for f in ("w9_blind.py", "w9_build.py", "judged_marks_keys.txt")]
    hs.append(B.sha_text(os.path.join(HERE, "..", "s2-stocks", "s2_lib.py")))
    open(path, "w").write("prereg\n" + "\n".join(hs) + "\n" + "\n".join(extra))


def tiny_deck(tmp_path, n_decks=2, deck_size=3, min_s=2, rfn=None):
    judged = tmp_path / "judged.txt"
    judged.write_text("AAA_2025-02-03\n")
    pre = tmp_path / "pre.md"
    # the build hashes w9_blind.py, w9_build.py, s2_lib.py and the judged file it is handed
    hs = [B.sha_text(os.path.join(HERE, f)) for f in ("w9_blind.py", "w9_build.py")] + [B.sha_text(os.path.join(HERE, "..", "s2-stocks", "s2_lib.py")), B.sha_text(str(judged))]
    pre.write_text("\n".join(hs))
    k = [0]

    def check(c):
        k[0] += 1
        return dict(r=(rfn(c) if rfn else 0.5), how="tgt")
    out = tmp_path / "deck"
    info = B.build(str(out), str(pre), str(judged), key_file=str(tmp_path / "key" / "seal.key"), cands=fake_pool(), check=check,
                   bars_fn=lambda s, d: synth_bars(hash((s, d)) % 1000), pclose_fn=lambda s, d: 100.0, n_decks=n_decks, deck_size=deck_size, min_s=min_s)
    return out, info


# ---------------------------------------------------------------- sealing
def test_seal_roundtrip_and_tamper():
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    tok, com = W.seal({"cards": [{"id": "a", "r": 1.5}]}, key)
    assert b"1.5" not in tok and b'"r"' not in tok
    assert W.unseal(tok, key, com)["cards"][0]["r"] == 1.5
    with pytest.raises(ValueError):
        W.unseal(tok, key, "0" * 64)                          # commitment mismatch
    with pytest.raises(Exception):
        W.unseal(tok, Fernet.generate_key(), com)             # wrong key


# ---------------------------------------------------------------- lock rule
def test_lock_only_at_complete_deck_boundaries():
    ch = ["S"] * 35                                           # 35 S taps inside deck 1 of 40: no lock mid-deck
    assert W.lock_status(ch)["state"] == "IN_PROGRESS"
    assert W.lock_status(ch + ["notS"] * 5)["state"] == "LOCKED"
    assert W.lock_status(ch + ["notS"] * 5)["n_used"] == 40


def test_lock_second_deck_and_inconclusive():
    ch = ["S"] * 10 + ["notS"] * 30 + ["S"] * 25 + ["notS"] * 15
    st = W.lock_status(ch)
    assert st["state"] == "LOCKED" and st["decks"] == 2 and st["n_s"] == 35
    last = W.N_DECKS * W.DECK_SIZE
    few = ["notS"] * (last - 2) + ["S"]                       # last deck not complete
    assert W.lock_status(few)["state"] == "IN_PROGRESS"
    full = ["notS"] * last
    assert W.lock_status(full)["state"] == "LOCKED_INCONCLUSIVE"


def test_taps_after_lock_do_not_change_the_used_set():
    ch = ["S"] * 30 + ["notS"] * 10 + ["notS"] * 40
    assert W.lock_status(ch)["n_used"] == 40


# ---------------------------------------------------------------- taps chain
def test_tap_chain_detects_edit(tmp_path):
    p = str(tmp_path / "taps.jsonl")
    taps = []
    W.append_tap(p, "c0", taps, "x1", "S")
    W.append_tap(p, "c0", taps, "x2", "notS")
    assert [t["choice"] for t in W.load_taps(p, "c0")] == ["S", "notS"]
    txt = open(p).read().replace('"choice": "notS"', '"choice": "S"')
    open(p, "w").write(txt)
    with pytest.raises(ValueError):
        W.load_taps(p, "c0")
    with pytest.raises(ValueError):
        W.load_taps(p, "other-commitment")


# ---------------------------------------------------------------- scoring
def mk_cards(n_days=20, per=4, seed=3, day_effect=0.0, sig=None):
    rng = np.random.default_rng(seed)
    cards = []
    for d in range(n_days):
        eff = rng.normal(0, 1) * day_effect
        for k in range(per):
            cards.append(dict(id="c%d_%d" % (d, k), day="2025-03-%02d" % (d + 1) if d < 28 else "2025-04-%02d" % (d - 27), r=float(rng.normal(-0.2 + eff, 1.2)), k=k))
    return cards


def test_score_pass_when_taps_follow_outcome():
    cards = mk_cards(n_days=60, per=4)
    ch = ["S" if c["r"] > 0.5 else "notS" for c in cards]
    res = W.score(cards, ch, nperm=2000, nboot=500)
    assert res["verdict"] == "PASS" and res["day_perm_p_one_sided"] < 0.05 and res["S_mean_R"] >= 0.25


def test_score_fail_when_taps_are_random():
    cards = mk_cards(n_days=40, per=4, seed=5)
    rng = np.random.default_rng(9)
    ch = ["S" if rng.random() < 0.3 else "notS" for _ in cards]
    res = W.score(cards, ch, nperm=2000, nboot=500)
    assert res["verdict"] == "FAIL" and res["n_S"] >= 30


def test_score_day_stratified_cannot_be_won_by_picking_days():
    # S tapped on EVERY card of the good days: within-day reshuffling leaves the S set unchanged, so p must be 1
    cards = mk_cards(n_days=30, per=4, day_effect=2.0, seed=2)
    by = {}
    for c in cards:
        by.setdefault(c["day"], []).append(c["r"])
    good = {d for d, v in by.items() if np.mean(v) > np.median([np.mean(x) for x in by.values()])}
    ch = ["S" if c["day"] in good else "notS" for c in cards]
    res = W.score(cards, ch, nperm=500, nboot=200)
    assert res["day_perm_p_one_sided"] == pytest.approx(1.0)
    assert res["verdict"] in ("FAIL", "INCONCLUSIVE") and not res["bar"]["day_perm_p_lt_005"]


def test_score_needs_30_s_taps():
    cards = mk_cards(n_days=30, per=4)
    ch = ["S" if c["r"] > 1.5 else "notS" for c in cards]
    res = W.score(cards, ch, nperm=500, nboot=200)
    assert res["n_S"] < 30 and res["verdict"] == "INCONCLUSIVE"


def test_score_is_deterministic():
    cards = mk_cards(n_days=30, per=4)
    ch = ["S" if i % 3 == 0 else "notS" for i in range(len(cards))]
    a = W.score(cards, ch, nperm=800, nboot=200)
    b = W.score(cards, ch, nperm=800, nboot=200)
    assert a == b


# ---------------------------------------------------------------- chart: nothing after the decision bar, nothing identifying
def test_cut_bars_drops_everything_after_signal_bar():
    b = synth_bars()
    c = B.cut_bars(b, 615)
    assert c["m"].max() == 615 and c["m"].min() == 480


def test_render_ignores_future_bars_and_identity(tmp_path):
    c = cand("AAA", "2025-02-03", 615, 1, 99.0)
    b1 = synth_bars(4)
    b2 = {k: v.copy() for k, v in b1.items()}
    future = b2["m"] > 615
    for k in ("O", "H", "L", "C"):
        b2[k][future] = 1000.0
    b2["V"][future] = 1e9
    p1, p2, p3 = (str(tmp_path / n) for n in ("a.png", "b.png", "c.png"))
    B.render_card(p1, b1, c, 100.0)
    B.render_card(p2, b2, c, 100.0)
    B.render_card(p3, b1, dict(c, sym="ZZZZ", day="2020-01-01"), 100.0)
    h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    assert h(p1) == h(p2) == h(p3)
    assert os.path.getsize(p1) < 60_000


# ---------------------------------------------------------------- selection
def test_select_excludes_nothing_it_is_not_told_and_balances_days():
    pool = fake_pool(n_days=6, per_day=12)
    chosen = B.select_cards(pool, lambda c: dict(r=0.0, how="x"), seed=1, n_total=24)
    per = {}
    for c in chosen:
        per[c["day"]] = per.get(c["day"], 0) + 1
    assert len(chosen) == 24 and max(per.values()) - min(per.values()) <= 1
    sd = {}
    for c in chosen:
        sd.setdefault((c["sym"], c["day"]), []).append(c["m"])
    assert all(len(v) <= B.SYMDAY_CAP for v in sd.values())
    assert all(abs(a - b) >= B.MIN_GAP for v in sd.values() for a in v for b in v if a != b)


def test_selection_never_looks_at_r():
    pool = fake_pool()
    a = B.select_cards(pool, lambda c: dict(r=5.0, how="x"), seed=7, n_total=20)
    b = B.select_cards(pool, lambda c: dict(r=-9.0, how="y"), seed=7, n_total=20)
    assert [(c["sym"], c["day"], c["m"]) for c in a] == [(c["sym"], c["day"], c["m"]) for c in b]


def test_select_skips_unsimulable_and_raises_when_exhausted():
    pool = fake_pool(n_days=2, per_day=6)
    ch = lambda c: None if c["m"] < 590 else dict(r=0.0, how="x")
    got = B.select_cards(pool, ch, seed=3, n_total=4)
    assert all(c["m"] >= 590 for c in got)
    with pytest.raises(ValueError):
        B.select_cards(pool, ch, seed=3, n_total=500)


def test_make_check_reads_real_format_and_gap_rule(tmp_path, monkeypatch):
    arch = tmp_path / "arch" / "ZZZ"
    arch.mkdir(parents=True)
    rows = ["Datetime,Open,High,Low,Close,Adj Close,Volume"]
    for mm in range(240, 1200):
        px = 100 + (mm - 570) * 0.001
        rows.append("2025-02-04T%02d:%02d:00-05:00,%f,%f,%f,%f,%f,1000" % (mm // 60, mm % 60, px, px + 0.05, px - 0.05, px, px))
    (arch / "2025-02-04.csv").write_text("\n".join(rows))
    prior = [r for r in rows if r.startswith("Datetime") or True]
    (arch / "2025-02-03.csv").write_text("\n".join(rows).replace("2025-02-04", "2025-02-03"))
    monkeypatch.setattr(L, "ARCH", str(tmp_path / "arch"))
    L._cache.clear()
    chk = B.make_check()
    got = chk(dict(sym="ZZZ", day="2025-02-04", m=600, side=1, stop=99.0))
    assert got is not None and "r" in got
    assert B.prev_close("ZZZ", "2025-02-04") == pytest.approx(100 + (959 - 570) * 0.001)
    assert B.full_day_bars("ZZZ", "2025-02-04")["m"][0] == 240
    # a day with only a few regular-session bars is not a card
    thin = [r for r in rows if r.startswith("Datetime") or int(r[11:13]) * 60 + int(r[14:16]) < 570 or int(r[11:13]) * 60 + int(r[14:16]) in (600, 601, 602)]
    (arch / "2025-02-05.csv").write_text("\n".join(thin).replace("2025-02-04", "2025-02-05"))
    L._cache.clear()
    assert chk(dict(sym="ZZZ", day="2025-02-05", m=600, side=1, stop=99.0)) is None
    assert chk(dict(sym="NOPE", day="2025-02-05", m=600, side=1, stop=99.0)) is None


# ---------------------------------------------------------------- build + serve end to end
def test_build_refuses_without_hashes_in_prereg(tmp_path):
    judged = tmp_path / "j.txt"; judged.write_text("AAA_2025-02-03\n")
    pre = tmp_path / "p.md"; pre.write_text("no hashes here")
    with pytest.raises(SystemExit):
        B.build(str(tmp_path / "d"), str(pre), str(judged), key_file=str(tmp_path / "k"), cands=fake_pool(), check=lambda c: dict(r=0.0, how="x"),
                bars_fn=lambda s, d: synth_bars(), pclose_fn=lambda s, d: 100.0, n_decks=1, deck_size=2)
    assert not (tmp_path / "k").exists()


def test_build_output_is_blind_and_excludes_judged_days(tmp_path):
    out, info = tiny_deck(tmp_path)
    man = json.load(open(out / "deck.json"))
    assert info["n_cards"] == 6 and len(man["cards"]) == 6 and {c["deck"] for c in man["cards"]} == {1, 2}
    raw = open(out / "deck.json").read()
    assert not any(s in raw for s in ("AAA", "BBB", "CCC", "2025-02", '"r"', "sym", "stop"))
    assert len(os.listdir(out / "img")) == 6
    key = W.read_key(str(tmp_path / "key" / "seal.key"))
    sealed = W.unseal(open(out / "sealed.bin", "rb").read(), key, man["commitment"])
    assert "2025-02-03" not in {c["day"] for c in sealed["cards"]}         # the judged day is gone
    assert W.sha256(open(out / "sealed.bin", "rb").read()) == man["sealed_sha256"]
    assert W.cmd_verify(str(out))
    with pytest.raises(SystemExit):                                         # never overwrite the key of an existing deck
        tiny_deck_again = B.build(str(tmp_path / "d2"), str(tmp_path / "pre.md"), str(tmp_path / "judged.txt"), key_file=str(tmp_path / "key" / "seal.key"),
                                  cands=fake_pool(), check=lambda c: dict(r=0.0, how="x"), bars_fn=lambda s, d: synth_bars(), pclose_fn=lambda s, d: 100.0, n_decks=1, deck_size=2)


def serve(deck_dir):
    deck = W.Deck(str(deck_dir))
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), W.make_handler(deck, "tok123"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d/t/tok123" % srv.server_address[1], deck


def call(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_server_flow_order_lock_and_no_outcome_leak(tmp_path):
    out, _ = tiny_deck(tmp_path, rfn=lambda c: 1.0)
    srv, base, deck = serve(out)
    try:
        assert call(base.replace("tok123", "bad") + "/api/state")[0] == 403
        code, body = call(base + "/api/state"); st = json.loads(body)
        assert code == 200 and st["state"] == "IN_PROGRESS" and st["pos"] == 1 and st["deck"] == 1
        assert set(st) <= {"state", "answered", "total", "n_S", "deck_size", "n_decks", "card", "deck", "pos", "between_decks", "decks_done", "message"}
        cid = st["card"]["id"]
        code, png = call(base + "/" + st["card"]["img"])
        assert code == 200 and png[:4] == b"\x89PNG"
        assert call(base + "/img/not-a-card.png")[0] == 404
        assert call(base + "/img/..%2f..%2fdeck.json.png")[0] == 404
        assert call(base + "/api/tap", {"id": "W9-other", "choice": "S"})[0] == 409          # out of order
        assert call(base + "/api/tap", {"id": cid, "choice": "maybe"})[0] == 409
        assert call(base + "/api/tap", {"id": cid, "choice": "S"})[0] == 200
        assert call(base + "/api/tap", {"id": cid, "choice": "notS"})[0] == 409            # no edit
        for _ in range(2):                                                                   # finish deck 1 (3 cards): 1 S so far, min_s=2
            st = json.loads(call(base + "/api/state")[1])
            assert call(base + "/api/tap", {"id": st["card"]["id"], "choice": "notS"})[0] == 200
        st = json.loads(call(base + "/api/state")[1])
        assert st["state"] == "IN_PROGRESS" and st["between_decks"] and st["decks_done"] == 1 and st["n_S"] == 1
        for _ in range(3):
            st = json.loads(call(base + "/api/state")[1])
            assert call(base + "/api/tap", {"id": st["card"]["id"], "choice": "S"})[0] == 200
        st = json.loads(call(base + "/api/state")[1])
        assert st["state"] == "LOCKED" and "card" not in st
        assert call(base + "/api/tap", {"id": "x", "choice": "S"})[0] == 409                  # past the lock
        assert "1.0" not in json.dumps(st) and "sealed" not in json.dumps(st).lower()
    finally:
        srv.shutdown()
    again = W.Deck(str(out))                                                                  # restart resumes from the chain
    assert len(again.taps) == 6


def test_status_and_score_refuse_before_lock_and_never_unseal(tmp_path, capsys, monkeypatch):
    out, _ = tiny_deck(tmp_path)
    monkeypatch.setattr(W, "unseal", lambda *a, **k: (_ for _ in ()).throw(AssertionError("unsealed before the lock")))
    W.cmd_status(str(out))
    assert W.cmd_score(str(out), str(tmp_path / "key" / "seal.key")) is None
    txt = capsys.readouterr().out
    assert "refused" in txt and "mean" not in txt.lower() and "verdict\"" not in txt


def test_score_after_lock_matches_commitment(tmp_path, capsys):
    out, _ = tiny_deck(tmp_path, n_decks=2, deck_size=4, min_s=2, rfn=lambda c: 0.75)
    deck = W.Deck(str(out))
    taps = []
    for i, c in enumerate(deck.cards[:4]):
        W.append_tap(deck.taps_path, deck.commitment, taps, c["id"], "S" if i < 2 else "notS")
    res = W.cmd_score(str(out), str(tmp_path / "key" / "seal.key"))
    assert res["verdict"] in ("FAIL", "INCONCLUSIVE", "PASS") and res["n_S"] == 2 and res["S_mean_R"] == pytest.approx(0.75)
    assert res["lock"]["state"] == "LOCKED"
    assert os.path.exists(out / "result.json")
    # a tampered sealed file is refused
    open(out / "sealed.bin", "ab").write(b"x")
    with pytest.raises(ValueError):
        W.cmd_score(str(out), str(tmp_path / "key" / "seal.key"))


def test_status_projects_decks_from_counts_only(tmp_path, capsys):
    out, _ = tiny_deck(tmp_path, n_decks=2, deck_size=3, min_s=2)
    deck = W.Deck(str(out))
    taps = []
    for i, c in enumerate(deck.cards[:3]):
        W.append_tap(deck.taps_path, deck.commitment, taps, c["id"], "S" if i == 0 else "notS")
    W.cmd_status(str(out))
    j = json.loads(capsys.readouterr().out)
    assert j["n_S"] == 1 and j["decks_complete"] == 1 and j["projected_decks_to_lock"] == 2 and "mean" not in json.dumps(j)
