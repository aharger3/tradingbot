"""B3 B-13 regression test: market_open_healthcheck.py's Tastytrade cred
check must read the ONLY .env this repo has (BASE/.env), not the dead
C:\\Users\\aharg\\projects\\tradingbot\\... path (no such directory exists).

Run: python research/g_b13_test_healthcheck_creds.py
Exits 0 on pass, 1 on fail.
"""
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import market_open_healthcheck as hc  # noqa: E402


def test_cred_files_only_reference_base():
    """B-13: no CRED_FILES / path entry may point at the dead
    C:\\Users\\aharg\\projects\\tradingbot tree."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        _ok, checked = hc.find_tastytrade_creds(base)
        for label, path in checked:
            assert "aharg" + "\\projects\\tradingbot" not in str(path), (
                f"{label} still points at the dead path: {path}"
            )
            # every checked path must resolve under the given base dir
            assert str(path).startswith(str(base)), (
                f"{label} does not resolve under BASE: {path}"
            )


def test_finds_real_creds_in_main_env():
    """The bug: real credentials live in the repo's single .env, but the old
    code only ever matched a file at the dead projects\\tradingbot path, so
    tastytrade-creds-exist reported False even with valid creds present."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / ".env").write_text(
            "CLIENT_ID=abc\nCLIENT_SECRET=def\nREFRESH_TOKEN=eyJhbGciOiJIUzI1NiJ9.fake\n",
            encoding="utf-8",
        )
        ok, _checked = hc.find_tastytrade_creds(base)
        assert ok is True, "cred check did not find creds in the main .env"


def test_refresh_token_format_read_from_main_env():
    """The refresh-token format check must not be skipped just because the
    dead .env.tastytrade path doesn't exist — it must read the token from
    the same main .env the cred-exist check found it in."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / ".env").write_text(
            "CLIENT_ID=abc\nCLIENT_SECRET=def\nREFRESH_TOKEN=eyJhbGciOiJIUzI1NiJ9.fake\n",
            encoding="utf-8",
        )
        label, ok, detail = hc.check_refresh_token(base)
        assert label == "tastytrade-refresh-token-format", detail
        assert ok is True, detail


if __name__ == "__main__":
    tests = [
        test_cred_files_only_reference_base,
        test_finds_real_creds_in_main_env,
        test_refresh_token_format_read_from_main_env,
    ]
    failed = []
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failed.append(t.__name__)
    if failed:
        print(f"\n{len(failed)}/{len(tests)} failed: {failed}")
        sys.exit(1)
    print(f"\nAll {len(tests)} passed.")
    sys.exit(0)
