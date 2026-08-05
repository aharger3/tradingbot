#!/usr/bin/env python3
r"""
T2 (omen-3.1) -- Embed the distinct rule texts with nomic-embed-text.

Reads research/rule_ledger_v2.jsonl (34,695 records), dedups the `text` field on
    re.sub(r'\W+', ' ', text.lower()).strip()
which yields 32,956 distinct texts (~3.46M chars), and embeds each distinct text
with the local `nomic-embed-text:latest` model served by Ollama at
http://localhost:11434/api/embeddings.

Checkpoints every 500 embeddings to:
    research/rule_embeddings.npy  -- float32, shape (n, 768), row order == ids order
    research/rule_ids.json        -- list of {"key":normalised, "id":ledger_id,
                                       "text":original, "source":source,
                                       "setup":setup, "confidence":confidence}

On restart both files are loaded and already-embedded keys are skipped.

Environment: `set PYTHONIOENCODING=utf-8`. Python 3.13 system interpreter
(not the hermes venv). numpy is required for the .npy output.
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

import numpy as np

# --- configuration -----------------------------------------------------------

LEDGER_PATH = os.path.join(os.path.dirname(__file__), "rule_ledger_v2.jsonl")
EMB_PATH = os.path.join(os.path.dirname(__file__), "rule_embeddings.npy")
IDS_PATH = os.path.join(os.path.dirname(__file__), "rule_ids.json")

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL = "nomic-embed-text:latest"
EMB_DIM = 768
BATCH = 500
USER_AGENT = "omen-3.1-T2-embed_rules/1.0"
HTTP_TIMEOUT = 120


def normalise(text):
    """Dedup key: collapse non-word runs to single spaces and lower-case."""
    return re.sub(r"\W+", " ", text.lower()).strip()


def load_ledger_distinct(path):
    """
    Walk the ledger in file order and return the ordered list of distinct
    records (one per normalised key), preserving first-seen order.

    Returns a list of dicts with keys: key, id, text, source, setup, confidence.
    """
    seen = set()
    distinct = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            text = rec.get("text", "") or ""
            key = normalise(text)
            if not key:
                # skip empty texts; they carry no embedding signal
                continue
            if key in seen:
                continue
            seen.add(key)
            distinct.append({
                "key": key,
                "id": rec.get("id"),
                "text": text,
                "source": rec.get("source"),
                "setup": rec.get("setup"),
                "confidence": rec.get("confidence"),
            })
    return distinct


def load_checkpoint():
    """Load existing npy + ids, return (ids, embeddings) or ([], None)."""
    if os.path.exists(IDS_PATH) and os.path.exists(EMB_PATH):
        ids = json.load(open(IDS_PATH, "r", encoding="utf-8"))
        emb = np.load(EMB_PATH)
        # sanity: rows must align with ids
        if emb.shape[0] == len(ids):
            return ids, emb
        # corrupt/truncated checkpoint -- fall back to what ids claims
        return ids, emb
    return [], None


def embed_one(text, retries=3):
    """POST a single text to Ollama and return its embedding vector (list[float])."""
    payload = json.dumps({"model": MODEL, "prompt": text}).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            vec = data["embedding"]
            if len(vec) != EMB_DIM:
                raise ValueError(
                    f"expected {EMB_DIM}-d vector, got {len(vec)}"
                )
            return vec
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as exc:
            last_err = exc
            # brief backoff before retrying the same text
            time.sleep(1 + attempt)
    raise RuntimeError(f"embedding failed after {retries} retries: {last_err}")


def save_checkpoint(ids, emb):
    """Flush ids + embeddings to disk atomically-ish (write tmp then replace)."""
    tmp_ids = IDS_PATH + ".tmp"
    tmp_emb = EMB_PATH + ".tmp"
    with open(tmp_ids, "w", encoding="utf-8") as fh:
        json.dump(ids, fh, ensure_ascii=False)
    emb.astype(np.float32).tofile(tmp_emb)
    # rebuild npy header by saving through numpy
    np.save(tmp_emb, emb.astype(np.float32))
    os.replace(tmp_ids, IDS_PATH)
    os.replace(tmp_emb, EMB_PATH)


def main():
    if not os.path.exists(LEDGER_PATH):
        sys.exit(
            f"ERROR: ledger not found at {LEDGER_PATH}. "
            "rule_ledger_v2.jsonl is untracked and only exists on the PC; "
            "this script must run there with local Ollama serving nomic-embed-text."
        )

    distinct = load_ledger_distinct(LEDGER_PATH)
    print(f"distinct rule texts: {len(distinct)}", flush=True)

    ids, emb = load_checkpoint()
    done_keys = {r["key"] for r in ids}

    todo = [r for r in distinct if r["key"] not in done_keys]
    print(f"already embedded: {len(ids)}  remaining: {len(todo)}", flush=True)

    if emb is None:
        emb = np.zeros((0, EMB_DIM), dtype=np.float32)

    for i, rec in enumerate(todo, start=1):
        vec = embed_one(rec["text"])
        emb = np.vstack([emb, np.asarray(vec, dtype=np.float32)[None, :]])
        ids.append({
            "key": rec["key"],
            "id": rec["id"],
            "text": rec["text"],
            "source": rec["source"],
            "setup": rec["setup"],
            "confidence": rec["confidence"],
        })
        if len(ids) % BATCH == 0:
            save_checkpoint(ids, emb)
            print(f"checkpoint: {len(ids)} embeddings", flush=True)

    save_checkpoint(ids, emb)
    print(f"DONE: {len(ids)} embeddings, shape {emb.shape}", flush=True)


if __name__ == "__main__":
    main()
