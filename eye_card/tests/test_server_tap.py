"""Tests for the tunnel tap endpoint on the eye label server (POST /tap/<token>).

Run:  python -m pytest eye_card/tests/test_server_tap.py -q   (from repo root)
"""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eye_card import labels, server

TOKEN = "T" * 43
REAL_TAP_TOKEN = server._tap_token       # setUp swaps the module attribute for a stub


def read(p):
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TapRouteTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.csv = Path(self.td.name) / "labels.csv"
        self.skips = Path(self.td.name) / "skips.csv"
        self.patches = [mock.patch.object(server, "LABELS_CSV", self.csv),
                        mock.patch.object(server, "_tap_token", lambda: TOKEN)]
        for p in self.patches:
            p.start()
        self.c = server.app.test_client()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.td.cleanup()

    def post(self, card="EYE-S43-1-20260907-ab12", choice="S", token=TOKEN, **kw):
        return self.c.post(f"/tap/{token}", json={"card_id": card, "choice": choice}, **kw)

    def test_s_and_not_s_land_in_labels_csv_with_the_loop_columns(self):
        self.assertEqual(self.post("EYE-a1", "S").get_json(), {"ok": True, "recorded": True, "label": "S"})
        self.post("EYE-a2", "notS")
        rows = read(self.csv)
        self.assertEqual([(r["candidate_id"], r["label"], r["mode"]) for r in rows],
                         [("EYE-a1", "S", "PAPER"), ("EYE-a2", "notS", "PAPER")])
        self.assertEqual(list(rows[0]), labels.FIELDS)

    def test_skip_lands_in_skips_csv_not_labels(self):
        self.assertEqual(self.post("EYE-a1", "skip").get_json()["label"], "skip")
        self.assertFalse(self.csv.exists())
        self.assertEqual(read(self.skips)[0]["candidate_id"], "EYE-a1")

    def test_first_tap_per_card_wins_across_both_files(self):
        self.post("EYE-a1", "S")
        again = self.post("EYE-a1", "notS").get_json()
        self.assertEqual(again, {"ok": True, "recorded": False, "label": None})
        self.post("EYE-a1", "skip")
        self.assertEqual(len(read(self.csv)), 1)
        self.assertFalse(self.skips.exists())

    def test_wrong_token_is_403_and_writes_nothing(self):
        for tok in ("bad", "T" * 42, TOKEN + "x"):
            self.assertEqual(self.post(token=tok).status_code, 403)
        self.assertFalse(self.csv.exists())

    def test_unset_server_token_refuses_everything(self):
        with mock.patch.object(server, "_tap_token", lambda: ""):
            self.assertEqual(self.post(token="").status_code, 404)    # empty path segment: no route
            self.assertEqual(self.post(token="anything").status_code, 403)

    def test_bad_card_id_or_choice_is_400(self):
        for card in ("S43-1-20260907", "EYE-", "EYE-a b", "EYE-" + "x" * 37, "../EYE-x", ""):
            self.assertEqual(self.post(card=card).status_code, 400, card)
        self.assertEqual(self.post(choice="maybe").status_code, 400)
        self.assertFalse(self.csv.exists())

    def test_non_json_body_is_400(self):
        r = self.c.post(f"/tap/{TOKEN}", data="card_id=EYE-a&choice=S")
        self.assertEqual(r.status_code, 400)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.c.get(f"/tap/{TOKEN}").status_code, 405)

    def test_healthz_is_the_probe_target(self):
        self.assertEqual(self.c.get("/healthz").get_json(), {"mode": "PAPER", "ok": True})

    def test_legacy_label_route_still_works(self):
        with mock.patch.object(server, "_token", lambda: "legacy"):
            r = self.c.post("/label", data={"id": "O1", "label": "S", "token": "legacy"})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(self.c.post("/label", data={"id": "O1", "label": "S", "token": "x"}).status_code, 403)

    def test_token_comes_from_the_vault_and_is_cached(self):
        server._tok_cache.update(v="", t=-1e9)
        with mock.patch.object(server, "_tap_token", REAL_TAP_TOKEN), \
             mock.patch.object(server, "secret", return_value="vault-tok") as sec:
            self.assertEqual(server._tap_token(), "vault-tok")
            self.assertEqual(server._tap_token(), "vault-tok")
            self.assertEqual(sec.call_count, 1)
        server._tok_cache.update(v="", t=-1e9)


if __name__ == "__main__":
    unittest.main()
