"""
eye_runner.py -- the eye loop, end to end:
    candidate generator (v3-eye2-candidates/candidates.py)
    -> phone card (eye_card: chart PNG + ntfy S/Not-S buttons)
    -> S-confirmation gate, 120s window (v3-eye4-paper/eye_paper.py)
    -> paper trade simulation -> journal (research/paper_journal/*.jsonl)

REPLAY MODE ONLY as of 2026-09-26. No live 1-min feed is wired into this repo
(v3-eye2-candidates/README.md: "no live data feed is wired up here"). This
script replays historical NQ sessions' recovered bars (sized as MNQ). Default
(pool mode, R8-1 2026-10-03): ONE card from each of several fresh, liquid sessions
of the fit window, drawn from eye_card/session_pool.py -- a session is never shown
twice, and the old hard-coded Labor Day (2026-09-07, ~10% volume) replay is gone.
--date D replays one named session instead, pacing each card to the minute it fired
at. Every card title carries the caller's --title-prefix (e.g.
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

Usage:
    python eye_runner.py --title-prefix "OMEN REPLAY TEST" --blind
    python eye_runner.py --date 2026-09-17 --speed 60 --title-prefix "OMEN TEST -- ignore"
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v3-eye2-candidates"))
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v3-eye4-paper"))
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v2-s07-data"))
sys.path.insert(0, str(REPO))

import candidates as eye2          # noqa: E402
import eye_paper                   # noqa: E402
from eye_card.chart import Candidate as ChartCandidate, render_candidate_chart  # noqa: E402
from eye_card.notify import send_card                                           # noqa: E402
from eye_card import session_pool                                               # noqa: E402
from eye_card import tap as eyetap                                              # noqa: E402
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


def first_sendable(A, date: str, instrument: str):
    """Earliest slice-A (S or A grade) candidate of the session, or None."""
    cands = [c for c in eye2.detect_candidates(A, date, instrument) if prereg_allowed(c.grade_hint)]
    cands.sort(key=lambda c: c.features["minutes_after_open"])
    return cands[0] if cands else None


def build_plan(args, df, labels_csv: Path, skips_csv: Path, n_cards: int) -> list[dict]:
    """What to send, in order: [{date, A, cand, due_s}].

    --date D     one session, every sendable candidate, paced at its minute after the open (old behavior).
    default      pool mode: one card per session, each from a fresh liquid session never shown before
                 (eye_card/session_pool.py), `card_gap_s` apart."""
    by_date = {str(d): g for d, g in df.groupby(df["date"].astype(str))}

    def arrays(date):
        return eye2.day_arrays(by_date[date])

    if args.date:
        if args.date not in by_date:
            return []
        A = arrays(args.date)
        cands = [c for c in eye2.detect_candidates(A, args.date, args.instrument) if prereg_allowed(c.grade_hint)]
        cands.sort(key=lambda c: c.features["minutes_after_open"])
        log(f"REPLAY {args.date} {args.instrument}: {len(cands)} sendable ({[c.grade_hint for c in cands]})")
        return [{"date": args.date, "A": A, "cand": c, "due_s": c.features["minutes_after_open"] * 60.0}
                for c in cands]

    used = session_pool.used_days(labels_csv=labels_csv, skips_csv=skips_csv, ledger=eyetap.LEDGER,
                                  journal=Path(args.journal_path),
                                  marks_json=Path(args.marks_json) if args.marks_json else None)
    pool = session_pool.liquid_sessions(df)
    found = {}

    def usable(date):
        A = arrays(date)
        c = first_sendable(A, date, args.instrument)
        if c is not None:
            found[date] = (A, c)
        return c is not None

    picked = session_pool.pick_sessions(pool, used, n_cards, usable=usable)
    log(f"POOL {args.instrument}: {len(pool)} liquid sessions, {len(used)} already seen, "
        f"{len(picked)} picked for {n_cards} cards")
    return [{"date": d, "A": found[d][0], "cand": found[d][1], "due_s": i * float(args.card_gap_s)}
            for i, d in enumerate(picked)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", default="MNQ")
    ap.add_argument("--date", default=None,
                    help="replay ONE named session YYYY-MM-DD (dev/test). Default: one card from each of "
                         "several fresh liquid sessions drawn from the rotating pool, none ever repeated")
    ap.add_argument("--card-gap-s", type=float, default=180.0,
                    help="pool mode: seconds between card sends (one-at-a-time rule still applies)")
    ap.add_argument("--marks-json", default=os.environ.get(
        "EYE_MARKS_JSON", str(REPO / "_omen_mark_days.json")),
        help="Austin's blind marking set; sessions where he marked an index ETF are never replayed")
    ap.add_argument("--title-prefix", required=True, help='e.g. "OMEN REPLAY TEST" or "OMEN TEST -- ignore"')
    ap.add_argument("--speed", type=float, default=1.0, help="pacing multiplier; 1.0 = real-time, 60 = 60x fast")
    ap.add_argument("--confirm-window-s", type=int, default=120)
    ap.add_argument("--management", default="flat_2r", choices=["flat_2r", "ladder_4tier"])
    ap.add_argument("--journal-path", default=str(REPLAY_JOURNAL))
    ap.add_argument("--labels-csv", default=os.environ.get("EYE_LABELS_CSV", str(REPO / "eye_card" / "labels.csv")))
    ap.add_argument("--token", default=os.environ.get("EYE_LABEL_TOKEN", "dev-local-only"))
    ap.add_argument("--blind", action="store_true",
                    help="hide ticker, date, grade and absolute prices on the card and chart; opaque card id")
    ap.add_argument("--legacy-label-server", action="store_true",
                    help="old path: chart PNG to the old ntfy topic, buttons to the label server's GET /label")
    ap.add_argument("--max-cards-per-day", type=int, default=eyetap.MAX_CARDS_PER_DAY)
    ap.add_argument("--ignore-schedule", action="store_true", help="dev only: skip the Mon-Thu gate")
    ap.add_argument("--max-wall-minutes", type=float, default=95.0, help="hard stop regardless of pacing")
    args = ap.parse_args(argv)

    journal_path = Path(args.journal_path)
    labels_csv = Path(args.labels_csv)

    log(f"prereg slice={PREREG_SLICE_A.slice_id} config_hash={PREREG_SLICE_A.config_hash()} "
        f"grades={PREREG_SLICE_A.allowed_grades} max_concurrent={PREREG_SLICE_A.max_concurrent_trades} "
        f"max_per_day={PREREG_SLICE_A.max_trades_per_day} day_stop_r={PREREG_SLICE_A.day_stop_r}")

    tap_mode = not args.legacy_label_server
    if tap_mode and not args.ignore_schedule:
        ok, why = eyetap.may_send(datetime.now(ET), cap=args.max_cards_per_day)
        if not ok:
            log(f"no cards today: {why}")
            return 0
    if tap_mode:
        eyetap.load_config()   # fail before any work if the tap secrets are missing

    sent_today = eyetap.cards_sent_on(f"{datetime.now(ET):%Y-%m-%d}") if tap_mode else 0
    df = load_fut(args.instrument, "09:30", "11:01")
    skips_csv = labels_csv.with_name("skips.csv")
    plan = build_plan(args, df, labels_csv, skips_csv, max(1, args.max_cards_per_day - sent_today))
    if not plan:
        log("ERROR: nothing to send (no bars for --date, or no fresh liquid session left in the pool)")
        return 2

    run_start = datetime.now(ET)
    hard_stop = run_start + timedelta(minutes=args.max_wall_minutes)
    seen_labels: set = set()
    seen_skips: set = set()
    cid_by_card: dict[str, str] = {}   # tap card id -> candidate id (identity unless blind)
    pending: dict[str, dict] = {}   # id -> {paper_cand, sent_wall, date}
    # the prereg day limits (-1R/+1R stop, trades per day) apply to one replayed session, not across
    # the unrelated sessions of a pool run
    confirmed_count: dict[str, int] = defaultdict(int)
    daily_r: dict[str, float] = defaultdict(float)
    seq_by_grade: dict[str, int] = {}
    sent_dates: list[str] = []

    def halted(date):
        return should_halt_day(confirmed_count[date], daily_r[date])

    def sweep_labels():
        for row in read_new_labels(skips_csv, seen_skips):
            cid = cid_by_card.get(row["candidate_id"], row["candidate_id"])
            if pending.pop(cid, None) is not None:
                log(f"skip {cid}: Skip tapped -- no trade, nothing journaled")
        for row in read_new_labels(labels_csv, seen_labels):
            cid = cid_by_card.get(row["candidate_id"], row["candidate_id"])
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
                confirmed_count[pending[cid]["date"]] += n
                daily_r[pending[cid]["date"]] += float(result.get("r") or 0.0)
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

    for item in plan:
        date, A, cand = item["date"], item["A"], item["cand"]
        if halted(date):
            log(f"HALT {date}: prereg day limit reached (trades={confirmed_count[date]}, "
                f"r={daily_r[date]:.2f}) -- no more candidates sent")
            continue

        minute = cand.features["minutes_after_open"]
        target_wall = run_start + timedelta(seconds=item["due_s"] / args.speed)
        while True:
            now = datetime.now(ET)
            slot_free = concurrent_slot_free(len(pending))
            if (now >= target_wall and slot_free) or now >= hard_stop:
                break
            sweep_labels()
            expire_pending()
            if halted(date):
                break
            time.sleep(min(2.0, max(0.05, (target_wall - now).total_seconds())) / max(args.speed, 1.0))
        if datetime.now(ET) >= hard_stop:
            log("hard stop reached before all candidates sent")
            break
        if halted(date):
            log(f"HALT {date}: prereg day limit reached (trades={confirmed_count[date]}, "
                f"r={daily_r[date]:.2f}) -- no more candidates sent")
            continue
        if not concurrent_slot_free(len(pending)):
            log(f"SKIP {cand.instrument} minute={minute}: prereg one-at-a-time slot busy ({list(pending)})")
            continue

        sent_count = eyetap.cards_sent_on(f"{datetime.now(ET):%Y-%m-%d}")
        if tap_mode and sent_count >= args.max_cards_per_day:
            log(f"STOP: daily card cap reached ({sent_count}/{args.max_cards_per_day})")
            break

        grade = cand.grade_hint
        seq_by_grade[grade] = seq_by_grade.get(grade, 0) + 1
        cid = f"{grade[0].upper()}{minute:02d}-{seq_by_grade[grade]}-{date.replace('-', '')}"
        chart_cand = to_chart_candidate(cand, cid)
        bars = bars_from_day_array(A, minute)
        CHART_DIR.mkdir(parents=True, exist_ok=True)
        card_id = eyetap.card_id_for(cid, args.blind) if tap_mode else cid
        # blind: the PNG name travels with the push, so it must not carry the date/grade in cid
        png_path = CHART_DIR / f"{card_id if (tap_mode and args.blind) else cid}.png"
        render_candidate_chart(chart_cand, bars, png_path, blind=args.blind and tap_mode)
        sent_wall = datetime.now(ET)
        card_sent_ts = sent_wall  # replay: card_sent_ts anchors the confirm window
        if tap_mode:
            cid_by_card[card_id] = cid
            result = eyetap.send_tap_card(chart_cand, png_path, card_id, blind=args.blind,
                                          seq=sent_count + 1, cap=args.max_cards_per_day,
                                          title_prefix=args.title_prefix)
            if result.ok:
                eyetap.record_card(card_id, cid, sent_wall, blind=args.blind, seq=sent_count + 1)
        else:
            result = send_card(chart_cand, png_path, args.token, test_title_prefix=args.title_prefix)
        log(f"sent {cid} grade={grade} dir={chart_cand.direction} "
            f"entry={chart_cand.entry} stop={chart_cand.stop} -> ntfy ok={result.ok} "
            f"status={result.status_code}" + (f" tap card={card_id} blind={args.blind}" if tap_mode else ""))
        if not result.ok:
            # not delivered: nothing to wait for, and the session stays unused for the next run
            err = getattr(result, "error", "")
            log(f"NOT SENT {cid}: {err or 'push failed'}")
            if err == "tunnel down":
                log("tunnel down: the buttons would lose every tap -- stopping, no more cards this run")
                break
            continue
        sent_dates.append(date)
        paper_cand = to_paper_candidate(cand, cid, date, card_sent_ts)
        pending[cid] = {"paper_cand": paper_cand, "sent_wall": sent_wall, "date": date}

    # drain remaining confirmation windows
    while pending and datetime.now(ET) < hard_stop:
        sweep_labels()
        expire_pending()
        time.sleep(1.0 / max(args.speed, 1.0))
    sweep_labels()
    expire_pending()

    for d in dict.fromkeys(sent_dates):
        log(f"DONE {d}: {confirmed_count[d]} confirmed+journaled, daily_r={daily_r[d]:.2f}, "
            f"summary={eye_paper.daily_summary(d, path=journal_path)}")
    log(f"DONE run: {len(sent_dates)} cards sent from {len(set(sent_dates))} sessions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
