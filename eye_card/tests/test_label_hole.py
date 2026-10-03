import os
import unittest
from unittest import mock

from eye_card import server


class LabelHoleClosed(unittest.TestCase):
    def test_unset_or_default_token_refused(self):
        c = server.app.test_client()
        for env in ({}, {"EYE_LABEL_TOKEN": "dev-local-only"}):
            with mock.patch.dict(os.environ, env, clear=False):
                if not env:
                    os.environ.pop("EYE_LABEL_TOKEN", None)
                for tok in ("", "dev-local-only"):
                    r = c.post("/label", data={"id": "x", "label": "S", "token": tok})
                    self.assertEqual(r.status_code, 403)
