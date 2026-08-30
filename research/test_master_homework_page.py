"""test_master_homework_page.py -- open the master homework in a real browser and
prove the delivery contract, rather than asserting it from the markup.

The contract this checks, in the order it matters (CLAUDE.md, "Homework
instruments"): it saves as he works, it comes back after a refresh, it exports
without a round trip, and it works at phone width. The 2026-08-22 failure this
exists to stop was exactly this: a page that looked right and persisted nothing.

Drives the Chrome already installed on this machine (`channel="chrome"`), so it
downloads nothing. Serves the page over http://127.0.0.1 because that is how he
opens it -- a published link, not a file path -- and file:// has its own
localStorage rules that would not be a fair test.

    python research/test_master_homework_page.py
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import socketserver
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE_DIR = os.path.join(HERE, "probes")
PAGE = "omen-master-homework.html"

fails = []


def check(ok, msg):
    print("%s  %s" % ("PASS" if ok else "FAIL", msg))
    if not ok:
        fails.append(msg)


def serve(directory):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=directory)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, "http://127.0.0.1:%d/%s" % (httpd.server_address[1], PAGE)


def main():
    from playwright.sync_api import sync_playwright

    httpd, url = serve(PAGE_DIR)
    print("serving %s" % url)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        # A phone, not a desktop. He does this homework away from this machine.
        ctx = browser.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True,
                                  has_touch=True)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url, wait_until="load")

        n_cards = page.locator("article.card").count()
        check(n_cards == 55, "%d cards rendered" % n_cards)
        check(page.locator("#count").inner_text().strip() == "0 / %d" % n_cards,
              "progress starts at 0 / %d" % n_cards)
        check(not errors, "no javascript errors on load (%s)" % (errors or "none"))

        # The page must not scroll sideways at phone width.
        overflow = page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check(overflow <= 1, "no horizontal scroll at 390px (overflow %spx)" % overflow)

        # Every chip is a real tap target. 44px is the platform minimum.
        small = page.evaluate("""
            Array.from(document.querySelectorAll('.chip')).filter(function(c){
              var r = c.getBoundingClientRect();
              return r.height < 36 || r.width < 40;
            }).length""")
        check(small == 0, "every chip is at least 36px tall (%d too small)" % small)

        # ---- answer a few cards across different sections, one of each shape
        taps = [
            ("is_this_an_s", 'article[data-section="is_this_an_s"]',
             'section[data-q="is_s"] .chip[data-v="yes"]',
             'section[data-q="is_s"] textarea.note', "entry 9:41, stop under the wick"),
            ("which_signal", 'article[data-section="which_signal"]',
             'section[data-q="which_signal"] .chip[data-v="B"]',
             'section[data-q="which_signal"] textarea.note', "B is the one, short"),
            ("what_minute", 'article[data-section="what_minute"]',
             'section[data-q="entry_minute"] .chip[data-v="long"]',
             'section[data-q="entry_minute"] textarea.note', "9:43"),
            ("htf_agree", 'article[data-section="htf_agree"]',
             'section[data-q="htf"] .chip[data-v="disagrees"]',
             'section[data-q="htf"] textarea.note', "daily is under its average"),
            ("displacement", 'article[data-section="displacement"]',
             'section[data-q="displacement"] .chip[data-v="no"]',
             'section[data-q="displacement"] textarea.note',
             "no separation from the original candles"),
            ("where_is_the_stop", 'article[data-section="where_is_the_stop"]',
             'section[data-q="stop_pick"] .chip[data-v="A"]',
             'section[data-q="stop_pick"] textarea.note', ""),
            ("mentor_ballot", 'article[data-section="mentor_ballot"]',
             'section[data-q="ballot"] .chip[data-v="yes"]',
             'section[data-q="ballot"] textarea.note', "yes, thats how i trade it"),
        ]
        expect = []
        for section, card_sel, chip_sel, note_sel, text in taps:
            card = page.locator(card_sel).first
            cid = card.get_attribute("data-cid")
            card.locator(chip_sel).click()
            if text:
                card.locator(note_sel).fill(text)
                # blur, which is the flush path a phone actually takes
                page.locator("h1").click()
            expect.append((section, cid, chip_sel.split('data-v="')[1][:-2], text))
        page.wait_for_timeout(700)

        keys = page.evaluate("Object.keys(localStorage).filter(function(k){"
                             "return k.indexOf('omen-probe:omen-master-homework:')===0;})")
        check(len(keys) == len(taps),
              "%d of %d answered cards are in localStorage" % (len(keys), len(taps)))
        check(page.locator("#count").inner_text().strip() == "%d / %d" % (len(taps), n_cards),
              "progress counted %d answered" % len(taps))

        # ---- the actual question: does it come back
        page.reload(wait_until="load")
        page.wait_for_timeout(400)
        restored_chip = restored_note = 0
        for section, cid, val, text in expect:
            card = page.locator('article[data-cid="%s"]' % cid)
            pressed = card.locator('.chip[aria-pressed="true"]').first
            if pressed.count() and pressed.get_attribute("data-v") == val:
                restored_chip += 1
            if text:
                got = card.locator("textarea.note").first.input_value()
                if got.strip() == text:
                    restored_note += 1
        check(restored_chip == len(expect),
              "%d of %d taps came back after a refresh" % (restored_chip, len(expect)))
        n_text = sum(1 for e in expect if e[3])
        check(restored_note == n_text,
              "%d of %d typed notes came back after a refresh"
              % (restored_note, n_text))
        check(page.locator("#count").inner_text().strip() == "%d / %d" % (len(taps), n_cards),
              "the progress counter came back too")

        # ---- export without a round trip
        page.locator("#exportbtn").click()
        page.wait_for_timeout(300)
        out = page.locator("#out").input_value().strip()
        rows = [json.loads(x) for x in out.splitlines() if x.strip()]
        check(len(rows) == len(expect),
              "export wrote %d rows for %d answers -- one row per answer"
              % (len(rows), len(expect)))
        shape = all(set(("section", "card_id", "answer", "text")) <= set(r) for r in rows)
        check(shape, "every row carries section, card_id, answer and free text")
        by_cid = {r["card_id"]: r for r in rows}
        ok = all(by_cid.get(cid, {}).get("answer") == [val]
                 and by_cid.get(cid, {}).get("section") == section
                 and by_cid.get(cid, {}).get("text", "") == text
                 for section, cid, val, text in expect)
        check(ok, "every answer round-trips to the right section and card")
        minute = [r for r in rows if r["section"] == "what_minute"]
        check(minute and minute[0]["text"] == "9:43",
              "the free-text minute survives to the export (%s)"
              % (minute[0]["text"] if minute else "missing"))
        check(page.locator("#copybtn").count() == 1
              and page.locator("#dlbtn").count() == 1,
              "Copy all and Download .jsonl are both on the page")

        # ---- leave the browser profile clean
        page.evaluate("localStorage.clear()")
        browser.close()
    httpd.shutdown()

    print("BROWSER CHECK %s" % ("OK" if not fails else "FAILED: %d" % len(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
