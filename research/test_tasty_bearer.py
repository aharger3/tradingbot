"""OAuth access tokens must be sent as `Bearer`, session tokens as `Token`.

Until 2026-09-05 both went out as "Token <t>", so every call made with an
OAuth refresh-grant token 401'd even though the grant itself succeeded
(research/g141_tastytrade_unblock.md). Runs offline: the token calls are stubbed.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tastytrade_feed as tf  # noqa: E402


def test_scheme_follows_token_source():
    f = tf.TastytradeFeed(username="u", password="p")
    f._get_access_token = lambda: "abc"          # stub the network
    assert f._headers()["Authorization"] == "Token abc", "default stays Token"
    f._token_scheme = "Bearer"                   # what _oauth_auth sets
    assert f._headers()["Authorization"] == "Bearer abc"
    f._token_scheme = "Token"                    # what _session_auth sets
    assert f._headers()["Authorization"] == "Token abc"


if __name__ == "__main__":
    test_scheme_follows_token_source()
    print("PASS: OAuth tokens go out as Bearer, session tokens as Token")
