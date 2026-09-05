**UNBLOCKED 2026-09-05 01:55 ET.** Austin pasted a fresh OAuth grant (refresh token, client id, client secret) into `.env` and the keys vault; the remaining 401 was a header bug — `_headers()` sent the OAuth access token as `Token <t>` instead of `Bearer <t>`. Fixed in `tastytrade_feed.py` (test `research/test_tasty_bearer.py`). `validate_credentials()` → True, 2 accounts, `fetch_daily_levels('SPY')` answers. HTF bias is live again. No human task remains.

BLOCKED: Tastytrade OAuth refresh grant returns a token, but every resource-server call made with that token 401s — HTF bias is still dead.

## What was tried live tonight

`tastytrade_feed._get_access_token` now falls through from the `/sessions` username/password
path to the OAuth `CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN` grant on a 401 (previously it never
reached the OAuth path at all when a username was set — this fallthrough is the code change in
this commit, tested in `research/test_tasty_auth_fallthrough.py`).

Run live against the real `.env` creds tonight, in order:

1. `POST /sessions` (username/password) → **401** `invalid_credentials`, "Your login has been
   temporarily locked for 15 minutes" (a prior run's failed attempts tripped Tastytrade's own
   lockout — unrelated to this commit, but it means we could not retest the password path
   tonight).
2. Fell through, as designed, to `POST /oauth/token` (refresh_token grant) → **200**, an
   `access_token` came back that decodes as a JWT (`eyJhbGciOi...`).
3. That access token was then used against `GET /customers/me/accounts` → **401** and
   `GET /api-quote-tokens` (the DXLink token endpoint the HTF candle path calls, see
   `get_dxlink_token`) → **401** `token_invalid`, "This token is invalid or has expired".

So the grant itself succeeds (the refresh token is valid and produces a token), but the
resource server rejects that token on every call that matters — account listing and the
DXLink quote-token endpoint that HTF bias actually depends on. **HTF bias is not back.**

## Which call, which response

| call | endpoint | result |
|---|---|---|
| session auth | `POST /sessions` | 401 `invalid_credentials` (temp lockout, 15 min) |
| oauth refresh | `POST /oauth/token` | 200, `access_token` issued |
| account list | `GET /customers/me/accounts` | 401 |
| DXLink token (HTF path) | `GET /api-quote-tokens` | 401 `token_invalid` |

The most likely cause: the OAuth personal grant (`CLIENT_ID`/`CLIENT_SECRET`/`REFRESH_TOKEN`
in `.env`) was created without the account/streaming scopes this app needs, or the grant has
since been revoked/expired on Tastytrade's side independent of the lockout above.

## The exact clicks to fix it (~5 minutes)

1. Go to **my.tastytrade.com → Manage → My Profile → API**.
2. Under **OAuth Applications**, open (or recreate) the personal grant used for this bot.
3. When creating/re-authorizing the grant, make sure account access and streaming
   (market data / quote-token) scopes are checked — not just "read-only" account info.
4. Copy the new **refresh token** into `.env` as `REFRESH_TOKEN`, and confirm `CLIENT_ID` /
   `CLIENT_SECRET` still match the same OAuth application.
5. Wait out the 15-minute session lockout before testing the password path again (unrelated,
   but avoid stacking another failed attempt on top of it).

**Done-signal:**

```
python -c "from tastytrade_feed import TastytradeFeed; TastytradeFeed().validate_credentials()"
```

prints `OK` (currently prints `RESULT: False` — access token obtained but the accounts call
401s).

No credential value appears anywhere in this file or in any committed file; only status codes
and error codes from Tastytrade's own response bodies are shown above.
