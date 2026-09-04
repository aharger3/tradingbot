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
    # -s10 = the per-signal core deck daily_run_1105.cmd builds since
    # 2026-09-04; -s is the older one-card-per-symbol shape, kept as fallback.
    for tag in ("s10", "s"):
        html = DECKS / ("omen-daily-%s-%s.html" % (day, tag))
        if html.exists():
            return html, ROOT / "research" / ("daily_%s_%s.json" % (day, tag))
    return (DECKS / ("omen-daily-%s-s10.html" % day),
            ROOT / "research" / ("daily_%s_s10.json" % day))


def summarise(data_path: Path) -> int:
    """How many cards. 0 if unreadable -- the count decorates the notification,
    it does not gate the send.

    THIS IS THE ONLY NUMBER THAT MAY LEAVE THE SIDECAR. The sidecar is deck kind
    3's answer key: it says which cards are fires, which are silent, and what the
    engine graded each one. A push that says "18 of these fired" hands him the
    base rate before he opens the deck, and a blind test with a known base rate
    is not blind. The earlier version of this function returned an OCR count and
    the body printed it; that was a leak and it is why the return type is now a
    single int.
    """
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    return len(data.get("cards") or [])


def mirror(deck: Path, day: str) -> Path | None:
    try:
        MIRROR.mkdir(parents=True, exist_ok=True)
        out = MIRROR / ("%s.html" % day)
        shutil.copyfile(deck, out)
        return out
    except OSError as e:
        print("  mirror failed: %s: %s" % (type(e).__name__, e))
        return None


# A blank line between the push body's paragraphs.
SEP = chr(10) * 2


def body_for(n_cards: int) -> str:
    """Plain English, and it says nothing about the engine.

    Austin reads this on a lock screen -- no flag names, no ticket ids, no
    letters from a retired ladder, and (see `summarise`) no count of what fired.
    """
    return SEP.join([
        "%d charts from this morning. Each one stops where it stops - that is "
        "all you get, and it is all a trader would have had." % n_cards,
        "Grade every card, say what kind of trade it is, and mark your entry "
        "and stop on the ones you would take.",
        "Write a comment on every card, including the ones you would not touch. "
        "The comment is the part that changes the engine.",
        "When you are done: Export, then Copy all, and paste it back.",
    ])


def deliver(day: str, dry_run: bool = False, topic: str | None = None,
            title_suffix: str = "") -> bool:
    deck, data = deck_paths(day)
    if not deck.exists():
        print("no deck for %s at %s -- run daily_homework.py --mode s-blind first"
              % (day, deck))
        return False
    n_cards = summarise(data)
    title = "AUGUR homework %s%s, %d cards" % (day, title_suffix, n_cards)
    body = body_for(n_cards)

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
    ap.add_argument("--title-suffix", default="",
                    help='appended to the title, e.g. " (test)"')
    a = ap.parse_args()
    sys.exit(0 if deliver(a.day, dry_run=a.dry_run, topic=a.topic,
                          title_suffix=a.title_suffix) else 1)


if __name__ == "__main__":
    main()
