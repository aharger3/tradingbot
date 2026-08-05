#!/usr/bin/env python3
r"""
T4 (omen-3.1) -- Name the top 300 clusters with local qwen3:4b.

Reads `research/rule_clusters.json` written by T3, which is a dict of the form

    {"threshold": 0.86, "clusters": [
        {"cluster_id": int, "size": int, "n_records": int,
         "sources": [...], "exemplars": [up to 5 texts],
         "member_ids": [...]}, ...
    ]}

Takes the first 300 clusters by `n_records` (they are already sorted descending
by T3, but we re-sort defensively). For each cluster, sends its 5 exemplars to
the local `qwen3:4b` model over Ollama at

    POST http://localhost:11434/api/generate   {"stream": false}

with a User-Agent header, asking for two things back as JSON:
  - `canonical`: a one-sentence canonical statement of the rule these five are
    all saying, and
  - `bucket`: one of exactly `B&R`, `order block`, `84%`, `X-reject`,
    `entry-timing`, `risk`, `regime`, `other`.

Buckets are deliberately wider than the four in `rebuild_rules_index.py`: the
old regex bucketing dumped 21,647 of 28,405 rules into `candidate`, so the
taxonomy, not the data, was the problem.

Writes `research/rule_cards.jsonl`, one line per named cluster:

    {"cluster_id", "canonical", "bucket", "n_records", "size",
     "sources", "exemplars"}

Checkpoints after every cluster (append + flush) so the run resumes: on restart
it skips any `cluster_id` already present in the jsonl.

If a model reply does not parse as JSON, it retries the same cluster once; if
the retry also fails to parse it writes the row with `"bucket": "other"` and
`"canonical"` set to the longest exemplar, and counts it -- one bad reply does
not stop the run.

No paid model. qwen3:4b is local and free; if its output is unusable that is a
finding for the report in T7, not a reason to route out.

Environment: `set PYTHONIOENCODING=utf-8`. Python 3.13 system interpreter
(not the hermes venv). Stdlib only -- no third-party deps.
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

# --- configuration -----------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
CLUSTERS_PATH = os.path.join(HERE, "rule_clusters.json")
CARDS_PATH = os.path.join(HERE, "rule_cards.jsonl")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:4b"
USER_AGENT = "omen-3.1-T4-name_clusters/1.0"
HTTP_TIMEOUT = 180
N_CLUSTERS = 300

BUCKETS = (
    "B&R",
    "order block",
    "84%",
    "X-reject",
    "entry-timing",
    "risk",
    "regime",
    "other",
)

PROMPT = """\
You are labelling a cluster of trading rules. Five example rules from the
cluster are listed below. They are all paraphrases of one underlying rule.

Read the five examples and return ONLY a JSON object (no prose, no markdown
fences) with exactly two keys:

  "canonical" -- ONE sentence stating the rule all five examples are expressing.
                 Be specific and concrete; do not hedge.
  "bucket"     -- exactly one of these eight strings, picking the single best
                 fit: "B&R", "order block", "84%", "X-reject", "entry-timing",
                 "risk", "regime", "other".

Definitions:
  B&R           -- break-and-retest / break of a level and retest as entry.
  order block   -- order block / supply-demand zone / institutional zone.
  84%           -- the "84% rule" or any 84%-win-rate / 84%-probability claim.
  X-reject      -- wick/rejection at a level (X-shape, pin bar, rejection).
  entry-timing  -- when to enter: time of day, session, confirmation trigger.
  risk          -- position sizing, stops, risk-of-ruin, R-multiple, risk mgmt.
  regime        -- market regime / trend / range / HTF context / condition.
  other         -- anything that does not fit the above.

The five examples:
1. {ex0}
2. {ex1}
3. {ex2}
4. {ex3}
5. {ex4}

Return only the JSON object now.
"""


# --- helpers -----------------------------------------------------------------

def load_clusters(path):
    """Load rule_clusters.json and return the clusters list (sorted by n_records desc)."""
    if not os.path.exists(path):
        sys.exit(
            f"ERROR: clusters not found at {path}. "
            "rule_clusters.json is the output of T3 and only exists where T2/T3 "
            "ran against the (untracked) rule_ledger_v2.jsonl with local Ollama; "
            "this script must run there with local Ollama serving qwen3:4b."
        )
    data = json.load(open(path, "r", encoding="utf-8"))
    clusters = data["clusters"] if isinstance(data, dict) and "clusters" in data else data
    # defensive: ensure sorted by n_records descending
    clusters.sort(key=lambda c: c.get("n_records", 0), reverse=True)
    return clusters


def load_done_ids(path):
    """Return the set of cluster_ids already written to the jsonl (for resume)."""
    done = set()
    if not os.path.exists(path):
        return done
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = rec.get("cluster_id")
            if cid is not None:
                done.add(cid)
    return done


def generate(prompt, retries=2):
    """POST prompt to Ollama /api/generate (stream:false) and return the response text."""
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }).encode("utf-8")
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
            return data.get("response", "") or ""
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"generate failed after {retries} retries: {last_err}")


_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text):
    """
    Pull the first JSON object out of a model reply that may wrap it in
    markdown fences, thinking tags, or surrounding prose. Returns the parsed
    dict or None if no valid object is found.
    """
    if not text:
        return None
    # strip <think>...</think> blocks qwen3 sometimes emits
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # try a fenced block first
    m = _JSON_FENCE.search(text)
    candidate = m.group(1) if m else text
    # find the outermost {...}
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    snippet = candidate[start:end + 1]
    try:
        obj = json.loads(snippet)
    except json.JSONDecodeError:
        # try fixing trailing commas / single quotes lightly
        cleaned = re.sub(r",\s*([}\]])", r"\1", snippet)
        try:
            obj = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
    return obj if isinstance(obj, dict) else None


def normalise_bucket(obj):
    """Validate/coerce the bucket value into the allowed set, else None."""
    b = obj.get("bucket")
    if isinstance(b, str):
        b = b.strip()
        # case-insensitive match against the allowed set
        low = {x.lower(): x for x in BUCKETS}
        if b.lower() in low:
            return low[b.lower()]
    return None


def longest_exemplar(exemplars):
    """Return the longest exemplar text (fallback canonical when the model fails)."""
    exemplars = [e for e in exemplars if isinstance(e, str) and e.strip()]
    if not exemplars:
        return "(unnamed cluster)"
    return max(exemplars, key=len)


def name_cluster(cluster):
    """
    Call qwen3:4b on the cluster's exemplars. Returns a card dict.

    On JSON parse failure the same call is retried once (a fresh generate
    request). If the retry also fails, the row is written with bucket "other"
    and canonical set to the longest exemplar -- and it still counts.
    """
    exemplars = list(cluster.get("exemplars", []) or [])
    # pad / truncate to exactly 5 slots for the prompt template
    ex = (exemplars + [""] * 5)[:5]
    prompt = PROMPT.format(ex0=ex[0], ex1=ex[1], ex2=ex[2], ex3=ex[3], ex4=ex[4])

    canonical = None
    bucket = None
    for attempt in range(2):  # one original + one retry on parse failure
        try:
            reply = generate(prompt)
        except RuntimeError:
            # transport failure -- treat as unparseable, fall through to retry
            reply = ""
        obj = extract_json(reply)
        if obj is not None:
            cand = obj.get("canonical")
            if isinstance(cand, str) and cand.strip():
                canonical = cand.strip()
            bucket = normalise_bucket(obj)
            if canonical and bucket:
                break  # got both, done

    if not canonical:
        canonical = longest_exemplar(exemplars)
    if not bucket:
        bucket = "other"

    return {
        "cluster_id": cluster.get("cluster_id"),
        "canonical": canonical,
        "bucket": bucket,
        "n_records": cluster.get("n_records"),
        "size": cluster.get("size"),
        "sources": cluster.get("sources", []),
        "exemplars": exemplars,
    }


def append_card(path, card):
    """Append one card as a JSON line and flush (checkpoint after every cluster)."""
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(card, ensure_ascii=False) + "\n")
        fh.flush()


# --- main --------------------------------------------------------------------

def main():
    clusters = load_clusters(CLUSTERS_PATH)
    print(f"loaded {len(clusters)} clusters from {CLUSTERS_PATH}", flush=True)

    top = clusters[:N_CLUSTERS]
    print(f"naming top {len(top)} by n_records", flush=True)

    done_ids = load_done_ids(CARDS_PATH)
    print(f"already named: {len(done_ids)}  (resuming)", flush=True)

    todo = [c for c in top if c.get("cluster_id") not in done_ids]
    print(f"remaining: {len(todo)}", flush=True)

    for i, cluster in enumerate(todo, start=1):
        card = name_cluster(cluster)
        append_card(CARDS_PATH, card)
        print(
            f"[{i}/{len(todo)}] cluster {card['cluster_id']} "
            f"-> {card['bucket']} | n_records={card['n_records']} "
            f"| {card['canonical'][:80]}",
            flush=True,
        )

    # final tally
    total = len(load_done_ids(CARDS_PATH))
    print(f"DONE: {total} cards in {CARDS_PATH}", flush=True)


if __name__ == "__main__":
    main()
