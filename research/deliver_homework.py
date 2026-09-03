"""deliver_homework.py -- get the blind deck onto Austin's phone. One command.

    python research/deliver_homework.py --day 2026-09-03
    python research/deliver_homework.py --day 2026-09-03 --dry-run

`research/daily_homework.py --mode s-blind` writes the deck; this sends it. The
two are separate because a build that succeeded and a send that failed are
different mornings and want different retries.

WHY NTFY AND NOT A HOSTED LINK. The deck is one self-contained HTML file --
charts are static SVG rendered in Python, persistence is localStorage, export is
a textarea -- so the file IS the app and there is nothing to host. ntfy stores
the attachment and the push carries a link to it: no server, no account, no
round trip, and it survives a locked phone.

The headless-artifact route was tried first, 2026-09-03: `claude -p` on this box
answers **"Credit balance is too low"**, so publishing to a stable claude.ai URL
is not a lane a scheduled task can rely on. If that changes, this is the one file
that has to know.

THE MIRROR IS NOT A BACKUP OF THE DECK, it is a second delivery lane. ntfy keeps
attachments for a limited window and a push can be missed; the copy under
`Desktop\\AI-Outputs\\omen-daily\\` is openable from this box forever, and is
where the deck is fetched from if he asks for yesterday's.

THE TOPIC IS A SECRET AND LIVES IN THE ENVIRONMENT. `aharger3/tradingbot` is a
PUBLIC repository. An ntfy topic is its own authentication -- anyone holding the
name can read every homework deck and push anything they like to his phone -- so
it is set once on the box (`setx OMEN_NTFY_TOPIC ...`) and read from
`notify_ntfy.resolve_topic`. It must never be written into a file in this repo.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import notify_ntfy                                  # noqa: E402

DECKS = ROOT / "research" / "decks"
MIRROR = Path.home() / "Desktop" / "AI-Outputs" / "omen-daily"


def deck_paths(day: str) -> tuple[Path, Path]:
    return (DECKS / ("omen-daily-%s-s.html" % day),
            ROOT / "research" / ("daily_%s_s.json" % day))


def summarise(data_path: Path) -> tuple[int, int]:
    """(cards, cards carrying an OCR or 84% candidate). (0, 0) if unreadable --
    the count decorates the notification, it does not gate the send."""
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0, 0
    cards = data.get("cards") or []
    ocr = sum(1 for c in cards
              if any(s.get("ocr84") for s in c.get("signals", [])))
    return len(cards), ocr


def mirror(deck: Path, day: str) -> Path | None:
    try:
        MIRROR.mkdir(parents=True, exist_ok=True)
        out = MIRROR / ("%s.html" % day)
        shutil.copyfile(deck, out)
        return out
    except OSError as e:
        print("  mirror failed: %s: %s" % (type(e).__name__, e))
        return None


def body_for(day: str, n_cards: int, n_ocr: int) -> str:
    """Plain English. Austin reads this on a lock screen -- no flag names, no
    ticket ids, no letters from a retired ladder."""
    lines = [
        "%d charts from this morning, all cut at 11:00 - you are seeing exactly "
        "what the engine saw, nothing after." % n_cards,
    ]
    if n_ocr:
        lines.append("%d of them have a one-candle-rule or 84%% setup on the "
                     "tape. Some of those never traded; the card says which gate "
                     "stopped it. Tell me if the gate was wrong." % n_ocr)
    lines.append("Grade each one, mark where you would have got in and where the "
                 "stop goes, and write a comment. The comment is the part that "
                 "changes the engine.")
    lines.append("When you are done: Export, then Copy all, and paste it back.")
    return "\n\n".join(lines)


def deliver(day: str, dry_run: bool = False, topic: str | None = None) -> bool:
    deck, data = deck_paths(day)
    if not deck.exists():
        print("no deck for %s at %s -- run daily_homework.py --mode s-blind first"
              % (day, deck))
        return False
    n_cards, n_ocr = summarise(data)
    title = "AUGUR homework %s, %d cards" % (day, n_cards)
    body = body_for(day, n_cards, n_ocr)

    saved = mirror(deck, day)
    if saved:
        print("  mirrored -> %s" % saved)

    if dry_run:
        print("  DRY RUN, nothing sent")
        print("  title: %s" % title)
        print("  body:\n%s" % "\n".join("    " + ln for ln in body.splitlines()))
        print("  file:  %s (%d bytes)" % (deck, deck.stat().st_size))
        return True

    ok = notify_ntfy.attach(deck, title, body=body,
                            filename="omen-daily-%s.html" % day,
                            priority="default", tags="books", topic=topic)
    print("  sent" if ok else "  SEND FAILED")
    return ok


def main():
    ap = argparse.ArgumentParser(description="Send the blind deck to the phone")
    ap.add_argument("--day", required=True, help="session (YYYY-MM-DD)")
    ap.add_argument("--topic", default=None,
                    help="ntfy topic; defaults to $OMEN_NTFY_TOPIC")
    ap.add_argument("--dry-run", action="store_true",
                    help="mirror and print, send nothing")
    a = ap.parse_args()
    sys.exit(0 if deliver(a.day, dry_run=a.dry_run, topic=a.topic) else 1)


if __name__ == "__main__":
    main()
