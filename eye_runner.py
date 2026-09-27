"""
eye_runner.py -- the eye loop, end to end:
    candidate generator (v3-eye2-candidates/candidates.py)
    -> phone card (eye_card: chart PNG + ntfy S/Not-S buttons)
    -> S-confirmation gate, 120s window (v3-eye4-paper/eye_paper.py)
    -> paper trade simulation -> journal (research/paper_journal/*.jsonl)

REPLAY MODE ONLY as of 2026-09-26. No live 1-min feed is wired into this repo
(v3-eye2-candidates/README.md: "no live data feed is wired up here"). This
script replays one historical Mon-Thu session's recovered NQ bars (sized as
MNQ), pacing card sends to the same wall-clock offset from 09:30 ET that each
setup actually fired at -- so a run feels like a live session for tapping
practice -- but every card title carries the caller's --title-prefix (e.g.
"OMEN REPLAY TEST") and every journal row lands in a REPLAY-only file
(research/paper_journal/acks_replay.jsonl), never the live acks.jsonl that a
real feed would write to. No orders are ever placed. See eye-live.md.

R06 (2026-09-27): candidates are filtered through the frozen pre-registered
slice A (life-plan/07-money/omen-paper-trade-prereg.md, decision A5) --
S+A grades only, one trade at a time, max 5/day, +-1R day stop. See
research/agent_runs/v3-eye4-paper/prereg_slice_a.py -- that file is the
frozen config; this runner only consumes it. Every confirmed+journaled fill
carries the config's hash (PREREG_SLICE_A.config_hash()) so any forward-test
row can be traced back to the exact rule set that produced it.

Prop guard (2026-09-27): before every card, research/prop_guard.py checks the
LucidFlex 50K paper account (config/accounts.json) against today's journal:
BLOCK -> card suppressed + one 'GUARD: <reason>' ntfy line; OK -> card footer
'GUARD OK'. Paper only.

Usage:
    python eye_runner.py --title-prefix "OMEN REPLAY TEST"
    python eye_runner.py --date 2026-09-17 --speed 60 --title-prefix "OMEN TEST -- ignore"
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v3-eye2-candidates"))
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v3-eye4-paper"))
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v2-s07-data"))
sys.path.insert(0, str(REPO / "research"))
sys.path.insert(0, str(REPO))

import candidates as eye2          # noqa: E402
import eye_paper                   # noqa: E402
from eye_card.chart import Candidate as ChartCandidate, render_candidate_chart  # noqa: E402
from eye_card.notify import send_card, send_line                                # noqa: E402
import prop_guard                                                               # noqa: E402
from omen_data import load_fut                                                  # noqa: E402
from prereg_slice_a import (                                                    # noqa: E402
    PREREG_SLICE_A,
    allowed as prereg_allowed,
    concurrent_slot_free,
    should_halt_day,
)

ET = ZoneInfo("America/New_York")
REPLAY_JOURNAL = REPO / "research" / "paper_journal" / "acks_replay.jsonl"
CHART_DIR = REPO / "eye_card" / "sent_charts"


def pick_replay_date(instrument: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    _, sessions_used = eye2.run(instrument, n_sessions=1)
    return str(sessions_used[-1])


def bars_from_day_array(A, up_to_idx: int) -> list[dict]:
    """day_arrays() gives 0=09:30..90=11:00 minute arrays. Return bar dicts
    for every non-NaN minute from 0..up_to_idx inclusive, HH:MM:SS ET."""
    out = []
    for i in range(0, up_to_idx + 1):
        o = A["open"][i]
        if o != o:  # NaN
            continue
        hh = 9 + (30 + i) // 60
        mm = (30 + i) % 60
        out.append({
            "time": f"{hh:02d}:{mm:02d}:00",
            "open": float(A["open"][i]), "high": float(A["high"][i]),
            "low": float(A["low"][i]), "close": float(A["close"][i]),
        })
    return out


def to_chart_candidate(cand: eye2.Candidate, cid: str) -> ChartCandidate:
    hh_mm = cand.time.split("T")[1][:8]
    return ChartCandidate(
        candidate_id=cid,
        symbol=cand.instrument,
        direction="LONG" if cand.direction == "long" else "SHORT",
        trigger_time=hh_mm,
        entry=cand.entry,
        stop=cand.stop,
        targets=[cand.target_1r, cand.target_2r],
        level=cand.level,
        level_label="ORB level",
        setup=f"ORB break/retest ({cand.grade_hint})",
        reason=f"missing={cand.missing}" if cand.missing else "S-gate clean",
        or_high=cand.features.get("or_high"),
        or_low=cand.features.get("or_low"),
    )


def to_paper_candidate(cand: eye2.Candidate, cid: str, date: str, card_sent_ts: datetime) -> dict:
    return {
        "id": cid,
        "symbol": cand.instrument,
        "date": date,
        "side": 1 if cand.direction == "long" else -1,
        "signal_minute": cand.features["minutes_after_open"],
        "stop": cand.stop,
        "session_extreme": None,
        "named_levels": {},
        "card_sent_ts": card_sent_ts.isoformat(),
        "cutoff_minute": eye_paper.DEFAULT_CUTOFF_MINUTE,
    }


def read_new_labels(labels_csv: Path, seen: set) -> list[dict]:
    if not labels_csv.exists():
        return []
    rows = []
    with open(labels_csv, newline="", encoding="utf-8") as fh:
        for i, row in enumerate(csv.DictReader(fh)):
            key = (row["candidate_id"], row["logged_at"])
            if key not in seen:
                seen.add(key)
                rows.append(row)
    return rows


def log(msg: str):
    print(f"[{datetime.now(ET).isoformat(timespec='seconds')}] {msg}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", default="MNQ")
    ap.add_argument("--date", default=None, help="replay date YYYY-MM-DD; default = most recent session")
    ap.add_argument("--title-prefix", required=True, help='e.g. "OMEN REPLAY TEST" or "OMEN TEST -- ignore"')
    ap.add_argument("--speed", type=float, default=1.0, help="pacing multiplier; 1.0 = real-time, 60 = 60x fast")
    ap.add_argument("--confirm-window-s", type=int, default=120)
    ap.add_argument("--management", default="flat_2r", choices=["flat_2r", "ladder_4tier"])
    ap.add_argument("--journal-path", default=str(REPLAY_JOURNAL))
    ap.add_argument("--labels-csv", default=os.environ.get("EYE_LABELS_CSV", str(REPO / "eye_card" / "labels.csv")))
    ap.add_argument("--token", default=os.environ.get("EYE_LABEL_TOKEN", "dev-local-only"))
    ap.add_argument("--max-wall-minutes", type=float, default=95.0, help="hard stop regardless of pacing")
    ap.add_argument("--account", default="lucidflex_50k_paper", help="config/accounts.json entry for prop_guard")
    args = ap.parse_args(argv)

    journal_path = Path(args.journal_path)
    labels_csv = Path(args.labels_csv)

    log(f"prereg slice={PREREG_SLICE_A.slice_id} config_hash={PREREG_SLICE_A.config_hash()} "
        f"grades={PREREG_SLICE_A.allowed_grades} max_concurrent={PREREG_SLICE_A.max_concurrent_trades} "
        f"max_per_day={PREREG_SLICE_A.max_trades_per_day} day_stop_r={PREREG_SLICE_A.day_stop_r}")

    date = pick_replay_date(args.instrument, args.date)
    df = load_fut(args.instrument, "09:30", "11:01")
    g = df[df["date"].astype(str) == date]
    if g.empty:
        log(f"ERROR: no bars for {args.instrument} on {date}")
        return 2
    A = eye2.day_arrays(g)
    raw_cands = eye2.detect_candidates(A, date, args.instrument)
    cands = [c for c in raw_cands if prereg_allowed(c.grade_hint)]
    cands.sort(key=lambda c: c.features["minutes_after_open"])
    log(f"REPLAY {date} {args.instrument}: {len(raw_cands)} raw candidates, "
        f"{len(cands)} sendable ({[c.grade_hint for c in cands]})")

    run_start = datetime.now(ET)
    hard_stop = run_start + timedelta(minutes=args.max_wall_minutes)
    seen_labels: set = set()
    pending: dict[str, dict] = {}   # id -> {paper_cand, sent_wall}
    confirmed_count = 0
    daily_r = 0.0
    seq_by_grade: dict[str, int] = {}
    guard = prop_guard.CardGate(
        prop_guard.load_account(args.account), date, journal_path,
        notify=lambda line: send_line(line, test_title_prefix=args.title_prefix),
        since=run_start.isoformat())

    def sweep_labels():
        nonlocal confirmed_count, daily_r
        for row in read_new_labels(labels_csv, seen_labels):
            cid = row["candidate_id"]
            if cid not in pending:
                continue
            tap = {"candidate_id": cid, "grade": "S" if row["label"] == "S" else "not_s",
                   "tap_ts": row["logged_at"]}
            paper_cand = pending[cid]["paper_cand"]
            result = eye_paper.run_confirmed(paper_cand, tap, management=args.management,
                                              confirm_window_s=args.confirm_window_s)
            if result.get("confirmed"):
                result["config_hash"] = PREREG_SLICE_A.config_hash()
            n = eye_paper.append_journal([result], path=journal_path)
            log(f"tap {cid}: label={row['label']} confirmed={result['confirmed']} "
                f"reason={result.get('reason')} r={result.get('r')} journaled={n}")
            if result["confirmed"]:
                confirmed_count += n
                daily_r += float(result.get("r") or 0.0)
            del pending[cid]

    def expire_pending():
        now = datetime.now(ET)
        for cid in list(pending):
            sent = pending[cid]["sent_wall"]
            if (now - sent).total_seconds() > args.confirm_window_s + 2:
                paper_cand = pending[cid]["paper_cand"]
                result = eye_paper.run_confirmed(paper_cand, None, management=args.management,
                                                  confirm_window_s=args.confirm_window_s)
                eye_paper.append_journal([result], path=journal_path)  # no-op (unconfirmed)
                log(f"expire {cid}: no S tap within {args.confirm_window_s}s -- skipped, not traded")
                del pending[cid]

    for cand in cands:
        if should_halt_day(confirmed_count, daily_r):
            log(f"HALT: prereg day limit reached (trades={confirmed_count}, r={daily_r:.2f}) "
                f"-- no more candidates sent")
            break

        minute = cand.features["minutes_after_open"]
        target_wall = run_start + timedelta(seconds=(minute * 60) / args.speed)
        while True:
            now = datetime.now(ET)
            slot_free = concurrent_slot_free(len(pending))
            if (now >= target_wall and slot_free) or now >= hard_stop:
                break
            sweep_labels()
            expire_pending()
            if should_halt_day(confirmed_count, daily_r):
                break
            time.sleep(min(2.0, max(0.05, (target_wall - now).total_seconds())) / max(args.speed, 1.0))
        if datetime.now(ET) >= hard_stop:
            log("hard stop reached before all candidates sent")
            break
        if should_halt_day(confirmed_count, daily_r):
            log(f"HALT: prereg day limit reached (trades={confirmed_count}, r={daily_r:.2f}) "
                f"-- no more candidates sent")
            break
        if not concurrent_slot_free(len(pending)):
            log(f"SKIP {cand.instrument} minute={minute}: prereg one-at-a-time slot busy ({list(pending)})")
            continue

        footer = guard.allow()
        if footer is None:
            log(f"GUARD suppressed {cand.instrument} minute={minute}: {guard.last.reason}")
            continue

        grade = cand.grade_hint
        seq_by_grade[grade] = seq_by_grade.get(grade, 0) + 1
        cid = f"{grade[0].upper()}{minute:02d}-{seq_by_grade[grade]}-{date.replace('-', '')}"
        chart_cand = to_chart_candidate(cand, cid)
        bars = bars_from_day_array(A, minute)
        CHART_DIR.mkdir(parents=True, exist_ok=True)
        png_path = CHART_DIR / f"{cid}.png"
        render_candidate_chart(chart_cand, bars, png_path)
        sent_wall = datetime.now(ET)
        card_sent_ts = sent_wall  # replay: card_sent_ts anchors the confirm window
        result = send_card(chart_cand, png_path, args.token, test_title_prefix=args.title_prefix,
                           footer=footer)
        log(f"sent {cid} grade={grade} dir={chart_cand.direction} "
            f"entry={chart_cand.entry} stop={chart_cand.stop} -> ntfy ok={result.ok} status={result.status_code}")
        paper_cand = to_paper_candidate(cand, cid, date, card_sent_ts)
        pending[cid] = {"paper_cand": paper_cand, "sent_wall": sent_wall}

    # drain remaining confirmation windows
    while pending and datetime.now(ET) < hard_stop:
        sweep_labels()
        expire_pending()
        time.sleep(1.0 / max(args.speed, 1.0))
    sweep_labels()
    expire_pending()

    summary = eye_paper.daily_summary(date, path=journal_path)
    log(f"DONE {date}: {len(cands)} sent, {confirmed_count} confirmed+journaled, "
        f"daily_r={daily_r:.2f}, summary={summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
