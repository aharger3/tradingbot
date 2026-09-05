Tastytrade is not blocked at tastytrade.com — the OAuth refresh grant in
`.env` is valid and works live. It is blocked by two bugs in
`tastytrade_feed.py`, both fixable in code with no website visit. This is a
finding for whoever picks up row L2 (out of scope for L1 to edit); no code
was changed here.

## What was tried tonight (live, real network, real `.env` creds)

1. `TastytradeFeed()._oauth_auth()` (the `CLIENT_ID`/`CLIENT_SECRET`/
   `REFRESH_TOKEN` grant against `POST /oauth/token`): **200**, access token
   issued. The refresh token in `.env` is not stale and was not the blocker.
2. Using that token to call `GET /customers/me/accounts` the way the code
   currently does it — `Authorization: Token <token>` (the header
   `_headers()` sends for every authenticated call) — **401 Unauthorized**.
3. Same call, same token, header changed to `Authorization: Bearer <token>`
   — **200**, real account data came back.

So the access token from the OAuth grant is good; only the auth-scheme
string sent with it is wrong.

## Why `validate_credentials()` still fails today

`_get_access_token()` (line ~99) tries `_session_auth()` first whenever a
username is set, and never reaches `_oauth_auth()` — confirmed live tonight,
`_session_auth()` returns `401 invalid_credentials` on `/sessions` (the known
outage). The OAuth path is unreachable from the normal call path, so this
report's finding never gets exercised in production even after the
fallthrough lands, until the second bug is also fixed.

`_headers()` (line 201-206) hardcodes `"Authorization": f"Token {token}"`
for every authenticated request, regardless of which auth method produced
the token. Tastytrade's session-token auth wants the `Token` scheme; its
OAuth access tokens want `Bearer`. Wiring the `/sessions` → `/oauth/token`
fallthrough (L2's `do`) without also making `_headers()` scheme-aware would
still 401 downstream on every call that actually uses the OAuth branch —
this is not a hypothetical, it reproduced live tonight.

## Not a human task

The spec's assumption was "if it 401s too, write the my.tastytrade.com click
path." It did not 401 at the OAuth-grant step, so there is no OAuth
application to recreate and no refresh token to regenerate. **Nothing to do
at tastytrade.com.** The fix is two code changes for L2 (or whoever takes
this row next), out of scope for this row to make:

1. In `_get_access_token()`, on a 401 from `_session_auth()`, fall through
   to `_oauth_auth()` when `CLIENT_ID`/`CLIENT_SECRET`/`REFRESH_TOKEN` are
   present (the fallthrough the spec asked for).
2. In `_headers()`, track which auth method produced the current token and
   send `Bearer` for an OAuth-issued token, `Token` for a session token.

Done-signal once both land: `python -c "from tastytrade_feed import
TastytradeFeed; TastytradeFeed().validate_credentials()"` prints `OK`. Not
run to green here since the fix is out of this row's file scope
(`tastytrade_feed.py` is not named in L1).

No credential value appears anywhere in this file or in any command run
tonight (`.env` was read, never echoed).
