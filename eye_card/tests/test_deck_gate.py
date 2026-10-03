"""Tests for the PIN-gated W9 blind deck front (eye_card/deck_gate.py, served at /deck on the eye label server).

Uses a throwaway 6-card deck built in a temp dir, with the frozen w9_blind.py copied from the real deck folder
(env W9_DECK_DIR, default Desktop\\AI-Outputs\\w9-blind-deck). Skipped where that file does not exist.
The real deck, its taps and its seal are never touched.

Run:  python -m pytest eye_card/tests/test_deck_gate.py -q   (from repo root)
"""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eye_card import deck_gate, server

SRC = deck_gate.deck_dir() / "w9_blind.py"
PIN = "p1n-for-tests"
SENTINEL = b"SEALED-OUTCOME-SENTINEL-R-0.42"
PNG = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def build_deck(d: Path):
    (d / "img").mkdir(parents=True)
    cards = []
    for i in range(6):
        cid = f"W9-{i:08x}"
        (d / "img" / f"{cid}.png").write_bytes(PNG + bytes([i]))
        cards.append(dict(id=cid, deck=i // 3 + 1, pos=i % 3 + 1, img=f"img/{cid}.png", img_sha256=sha(PNG + bytes([i]))))
    (d / "sealed.bin").write_bytes(SENTINEL)
    (d / "deck.json").write_text(json.dumps(dict(version=1, n_decks=2, deck_size=3, min_s=2, cards=cards,
                                                 commitment="c" * 64, sealed_sha256=sha(SENTINEL))), encoding="utf-8")
    shutil.copy(SRC, d / "w9_blind.py")
    return cards


@unittest.skipUnless(SRC.exists(), "frozen w9_blind.py not on this box")
class DeckGateTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.dir = Path(self.td.name)
        self.cards = build_deck(self.dir)
        self.hash_before = {n: sha((self.dir / n).read_bytes()) for n in ("sealed.bin", "deck.json", "w9_blind.py")}
        self.patches = [mock.patch.dict("os.environ", {"W9_DECK_DIR": str(self.dir)}),
                        mock.patch.object(deck_gate, "_pin", lambda: PIN)]
        for p in self.patches:
            p.start()
        deck_gate._fails.update(n=0, until=0.0)
        self.c = server.app.test_client()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.td.cleanup()

    def login(self, pin=PIN):
        return self.c.post("/deck/login", data={"pin": pin})

    # ---- auth required ----
    def test_everything_needs_the_pin(self):
        cid = self.cards[0]["id"]
        self.assertEqual(self.c.get("/deck/").status_code, 401)
        self.assertEqual(self.c.get("/deck/api/state").status_code, 401)
        self.assertEqual(self.c.get(f"/deck/img/{cid}.png").status_code, 401)
        r = self.c.post("/deck/api/tap", json={"id": cid, "choice": "S"})
        self.assertEqual(r.status_code, 401)
        self.assertFalse((self.dir / "taps.jsonl").exists())

    def test_deck_json_and_sealed_are_not_served(self):
        self.login()
        for path in ("/deck/deck.json", "/deck/sealed.bin", "/deck/taps.jsonl", "/deck/w9_blind.py", "/deck/img/../sealed.bin"):
            self.assertEqual(self.c.get(path).status_code, 404, path)

    def test_wrong_pin_401_and_no_cookie_then_lockout_429(self):
        for _ in range(4):
            r = self.login("nope")
            self.assertEqual(r.status_code, 401)
            self.assertNotIn("Set-Cookie", r.headers)
        self.assertEqual(self.login("nope").status_code, 429)
        self.assertEqual(self.login(PIN).status_code, 429)          # locked even for the right PIN
        self.assertEqual(self.c.get("/deck/api/state").status_code, 401)

    def test_right_pin_sets_cookie_and_opens(self):
        r = self.login()
        self.assertEqual(r.status_code, 303)
        ck = r.headers["Set-Cookie"]
        self.assertIn("HttpOnly", ck)
        self.assertIn("SameSite=Lax", ck)
        self.assertEqual(self.c.get("/deck/").status_code, 200)

    def test_forged_and_expired_cookie_rejected(self):
        self.c.set_cookie("w9deck", "9999999999." + "0" * 64, path="/deck")
        self.assertEqual(self.c.get("/deck/api/state").status_code, 401)
        self.c.set_cookie("w9deck", "1." + deck_gate._sign(PIN, 1), path="/deck")
        self.assertEqual(self.c.get("/deck/api/state").status_code, 401)

    def test_no_pin_configured_fails_closed(self):
        with mock.patch.object(deck_gate, "_pin", lambda: ""):
            self.assertEqual(self.c.get("/deck/").status_code, 503)
            self.assertEqual(self.c.post("/deck/login", data={"pin": ""}).status_code, 503)
            self.assertEqual(self.c.get("/deck/api/state").status_code, 401)

    # ---- no outcomes anywhere ----
    def test_no_outcome_fields_in_any_response(self):
        self.login()
        cid = self.cards[0]["id"]
        seen = [self.c.get("/deck/"), self.c.get("/deck/api/state")]
        st = seen[1].get_json()
        self.assertEqual(set(st["card"]), {"id", "img"})
        for k in st:
            self.assertNotIn(k, ("r", "outcome", "sealed", "ticker", "date", "day"))
        seen.append(self.c.post("/deck/api/tap", json={"id": cid, "choice": "S"}))
        seen.append(self.c.post("/deck/api/tap", json={"id": cid, "choice": "S"}))        # 409
        seen.append(self.c.get("/deck/api/state"))
        for r in seen:
            self.assertNotIn(SENTINEL, r.get_data())
            self.assertNotIn(b"commitment", r.get_data())
            self.assertNotIn(b"sealed", r.get_data().lower())
        # the image route serves the PNG only
        r = self.c.get(f"/deck/img/{cid}.png")
        self.assertEqual((r.status_code, r.mimetype), (200, "image/png"))
        self.assertNotIn(SENTINEL, r.get_data())

    def test_unknown_card_image_404(self):
        self.login()
        self.assertEqual(self.c.get("/deck/img/W9-ffffffff.png").status_code, 404)
        self.assertEqual(self.c.get("/deck/img/not-a-card.png").status_code, 404)

    # ---- taps ----
    def test_tap_is_recorded_with_card_id_in_order_and_chained(self):
        self.login()
        a, b = self.cards[0]["id"], self.cards[1]["id"]
        r = self.c.post("/deck/api/tap", json={"id": a, "choice": "S"})
        self.assertEqual((r.status_code, r.get_json()["ok"]), (200, True))
        lines = (self.dir / "taps.jsonl").read_text(encoding="utf-8").splitlines()
        t = json.loads(lines[0])
        self.assertEqual((t["id"], t["choice"], t["i"], t["prev"]), (a, "S", 0, "c" * 64))
        # same card again, out-of-order card, bad choice, and Skip are all refused and write nothing
        for body in ({"id": a, "choice": "notS"}, {"id": self.cards[3]["id"], "choice": "S"}, {"id": b, "choice": "skip"},
                     {"id": b, "choice": "x"}):
            r = self.c.post("/deck/api/tap", json=body)
            self.assertEqual(r.status_code, 409, body)
        self.assertEqual(len((self.dir / "taps.jsonl").read_text(encoding="utf-8").splitlines()), 1)
        self.assertEqual(self.c.post("/deck/api/tap", json={"id": b, "choice": "notS"}).status_code, 200)
        st = self.c.get("/deck/api/state").get_json()
        self.assertEqual((st["answered"], st["n_S"], st["card"]["id"]), (2, 1, self.cards[2]["id"]))
        t2 = [json.loads(x) for x in (self.dir / "taps.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(t2[1]["prev"], t2[0]["h"])

    def test_bad_body_400(self):
        self.login()
        self.assertEqual(self.c.post("/deck/api/tap", data="nope").status_code, 400)

    def test_sitting_end_and_lock_stop_taps_and_hide_outcomes(self):
        self.login()
        for c in self.cards[:3]:
            self.assertEqual(self.c.post("/deck/api/tap", json={"id": c["id"], "choice": "S"}).status_code, 200)
        st = self.c.get("/deck/api/state").get_json()
        self.assertEqual(st["state"], "LOCKED")                    # min_s=2 reached at the end of deck 1
        r = self.c.post("/deck/api/tap", json={"id": self.cards[3]["id"], "choice": "S"})
        self.assertEqual(r.status_code, 409)
        self.assertNotIn(SENTINEL, self.c.get("/deck/api/state").get_data())

    def test_between_decks_flag_after_40th_equivalent(self):
        self.login()
        for c in self.cards[:3]:
            self.c.post("/deck/api/tap", json={"id": c["id"], "choice": "notS"})
        st = self.c.get("/deck/api/state").get_json()
        self.assertEqual(st["state"], "IN_PROGRESS")
        self.assertTrue(st["between_decks"])
        self.assertEqual(st["decks_done"], 1)

    # ---- sealed material untouched ----
    def test_sealed_hash_and_frozen_code_unchanged_after_use(self):
        self.login()
        for c in self.cards[:4]:
            self.c.post("/deck/api/tap", json={"id": c["id"], "choice": "S"})
        self.c.get("/deck/api/state")
        for n, h in self.hash_before.items():
            self.assertEqual(sha((self.dir / n).read_bytes()), h, n)
        m = deck_gate._w9()
        self.assertFalse(hasattr(deck_gate, "unseal") or hasattr(deck_gate, "score"))
        self.assertTrue(callable(m.unseal))                         # frozen module is loaded but this gate never calls it

    def test_page_reloads_on_expired_session(self):
        self.login()
        html = self.c.get("/deck/").get_data(as_text=True)
        self.assertIn("location.reload()", html)
        self.assertIn("/api/state", html)
        self.assertEqual(self.c.get("/deck/").headers["Cache-Control"], "no-store")


class ExistingRoutesStillGated(unittest.TestCase):
    def test_tap_route_still_needs_its_token(self):
        c = server.app.test_client()
        with mock.patch.object(server, "_tap_token", lambda: "T" * 43):
            self.assertEqual(c.post("/tap/wrong", json={"card_id": "EYE-x", "choice": "S"}).status_code, 403)
        self.assertEqual(c.get("/healthz").status_code, 200)


if __name__ == "__main__":
    unittest.main()
