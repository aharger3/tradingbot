"""Tests for opt_loader's cache-key fix (2026-09-26): a raw ':' in a Polygon
ticker (e.g. 'O:SPXW250326P05745000') used to land in the cache filename and
silently open an NTFS alternate data stream instead of a regular file. That
made the entry invisible to normal directory listings/copies and unrecoverable
from git after the omen-v2 branch-churn data loss. cache_key() now maps ':' to
'_' like it already did for '/'; find_cached() still locates pre-fix (':')
entries so nothing already on disk is orphaned.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import opt_loader as OL


TICKER_PATH = "/v2/aggs/ticker/O:SPXW250326P05745000/range/1/minute/2025-03-26/2025-03-26"
PARAMS = dict(adjusted="true", sort="asc", limit=50000)


def test_cache_key_has_no_colon(tmp_path, monkeypatch):
    monkeypatch.setattr(OL, "CACHE", tmp_path)
    key = OL.cache_key(TICKER_PATH, **PARAMS)
    assert ":" not in key.name
    assert "O_SPXW250326P05745000" in key.name


def test_cache_key_still_collapses_slashes(tmp_path, monkeypatch):
    monkeypatch.setattr(OL, "CACHE", tmp_path)
    key = OL.cache_key(TICKER_PATH, **PARAMS)
    assert "/" not in key.name


def test_find_cached_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(OL, "CACHE", tmp_path)
    assert OL.find_cached(TICKER_PATH, **PARAMS) is None


def test_find_cached_prefers_new_style_file(tmp_path, monkeypatch):
    monkeypatch.setattr(OL, "CACHE", tmp_path)
    new_key = OL.cache_key(TICKER_PATH, **PARAMS)
    new_key.write_text(json.dumps({"results": []}))
    hit = OL.find_cached(TICKER_PATH, **PARAMS)
    assert hit == new_key


def test_find_cached_falls_back_to_legacy_colon_name(tmp_path, monkeypatch):
    monkeypatch.setattr(OL, "CACHE", tmp_path)
    legacy_key = OL._cache_key_legacy(TICKER_PATH, **PARAMS)
    legacy_key.write_text(json.dumps({"results": []}))
    hit = OL.find_cached(TICKER_PATH, **PARAMS)
    assert hit == legacy_key


def test_get_reads_new_style_cache_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(OL, "CACHE", tmp_path)
    payload = {"results": [{"t": 0, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1, "vw": 1, "n": 1}]}
    OL.cache_key(TICKER_PATH, **PARAMS).write_text(json.dumps(payload))

    def _boom(*a, **k):
        raise AssertionError("network should not be hit on a cache hit")

    monkeypatch.setattr(OL._S, "get", _boom)
    assert OL._get(TICKER_PATH, **PARAMS) == payload


def test_get_reads_legacy_colon_cache_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(OL, "CACHE", tmp_path)
    payload = {"results": [{"t": 0, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1, "vw": 1, "n": 1}]}
    OL._cache_key_legacy(TICKER_PATH, **PARAMS).write_text(json.dumps(payload))

    def _boom(*a, **k):
        raise AssertionError("network should not be hit on a legacy cache hit")

    monkeypatch.setattr(OL._S, "get", _boom)
    assert OL._get(TICKER_PATH, **PARAMS) == payload
