"""T12 -- the earlier-entry gap.

Question (omen-7.1 spec, Group 3): T1 concluded the engine's entry timing is
exact, median +0.0 bars.  But T1 measured HIS marked minutes on days he traded.
On the engine's OWN proposed entries he repeatedly says the good trade is
earlier.  Measure the signed bar offset between the engine's proposed entry and
the entry he indicates, on every card where he names or implies one.

Three sections, three subcommands (`all` runs them in order):

  corpus  -- the adjudicated offset table.  Every mark corpus is scanned for
             entry-timing prose; each hit is hand-adjudicated ONCE, in the
             ADJUDICATION table below, with his exact words carried alongside
             the verdict so any reader can re-check the call.  Reports the
             earlier/later split with a binomial CI (the error bar for this
             track) and the mean/median magnitude with a bootstrap CI.
  t1check -- re-reads T1's own published table (research/t1_entry_minute_autopsy.md)
             and shows what its "median +0.0 bars" is conditioned on.
  fsm     -- the mechanism.  On the shipped book's traded break-and-retest rows,
             how many bars pass between the last bar that TOUCHED the broken
             level and the bar the engine entered on.  That gap is what
             detect_break_retest's step-4 CONFIRM-on-close costs.

READ-ONLY on every mark file.  Nothing here writes to research/marks/.

Run:  python research/t12_earlier_entry_gap.py all
"""
from __future__ import annotations

import csv
import glob
import json
import os
import random
import re
import statistics
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(ROOT, "data_archive")
BOOK = os.path.join(ROOT, "research", "bt2y_trades.json")
T1_MD = os.path.join(ROOT, "research", "t1_entry_minute_autopsy.md")

# --------------------------------------------------------------------------
# THE ADJUDICATION TABLE
# --------------------------------------------------------------------------
# One row per note in which Austin refers to a candle offset around an entry.
# The scan that produced the candidate pool is `scan()` below; it is re-run on
# every invocation and the script FAILS LOUD if the scan finds a timing note
# that is not adjudicated here, so the table cannot silently go stale.
#
# fields:
#   key    -- (basename of the corpus file, row id / card_id or symbol|day)
#   ref    -- whose entry the offset is measured FROM:
#             "engine" = the card showed an engine-proposed entry
#             "self"   = he was marking his own entry (blind pass / autopsy)
#   cls    -- ENTRY     he names an alternative ENTRY
#             STOP      the offset is a stop or a structure, not an entry
#             CONTEXT   timing prose with no offset (e.g. "late in the day")
#             ELSEWHERE a different setup at a different time, not this one
#                       shifted
#             AMBIG     internally inconsistent or truncated
#   dirn   -- -1 earlier than the card's entry, +1 later, 0 retracted
#   bars   -- magnitude in bars when he states a number, else None
#   quote  -- his words, verbatim (trimmed)
#
# SIGN CONVENTION for the reported offset: NEGATIVE = the entry he names is
# EARLIER than the entry on the card.  (research/austin_marks_v7.jsonl's own
# `offset` column uses the opposite sign -- positive = earlier -- so it is
# re-signed on import; see v7_offset_rows().)
ADJUDICATION = [
    # ======================================================================
    # P-ENGINE -- the card in front of him showed an ENGINE-proposed entry
    # ======================================================================
    # -- probe_master_2026-08-29 : his verdicts on 40 engine vetoes ----------
    ("probe_master_2026-08-29.jsonl", "BABA_2026-02-17", "engine", "ENTRY", +1, None,
     "Few candles later good trade"),
    ("probe_master_2026-08-29.jsonl", "QQQ_2026-05-07", "engine", "ENTRY", -1, None,
     "Earlier entries"),
    ("probe_master_2026-08-29.jsonl", "GOOGL_2025-08-28", "engine", "ENTRY", -1, None,
     "Earlier S"),
    ("probe_master_2026-08-29.jsonl", "MU_2026-01-09", "engine", "ENTRY", -1, 2,
     "2 candles earlier s"),
    ("probe_master_2026-08-29.jsonl", "META_2025-12-22", "engine", "ENTRY", -1, 1,
     "1 candle earlier S and another s or a recently later"),
    ("probe_master_2026-08-29.jsonl", "ORCL_2026-04-27", "engine", "ENTRY", -1, None,
     "Wouldn't have traded goood trade happens earlier"),
    ("probe_master_2026-08-29.jsonl", "fact_ocr_demote", "engine", "CONTEXT", 0, None,
     "s trades are all about being early"),

    # -- probe_master_homework_2026-08-26 : cal_ cards are engine entries ----
    ("probe_master_homework_2026-08-26.jsonl", "cal_QQQ_2026-06-29_b10", "engine", "ENTRY", -1, 1,
     "the engine entered one candle late, thats why it doesn't see the textbook s trade OCR"),
    ("probe_master_homework_2026-08-26.jsonl", "cal_QQQ_2026-07-24_b20", "engine", "ENTRY", -1, 5,
     "5 candles earlier possible, but candle entered on fine as long as not all the way at LOD"),
    ("probe_master_homework_2026-08-26.jsonl", "cal_QQQ_2026-07-02_b61", "engine", "ENTRY", +1, 1,
     "1 candle later better entry, stock already fails BR of ORH to upside."),
    ("probe_master_homework_2026-08-26.jsonl", "cal_QQQ_2026-07-16_b10", "engine", "AMBIG", 0, None,
     "c is fine because there is an earlier A entry 2-3 candles later"),
    ("probe_master_homework_2026-08-26.jsonl", "cal_QQQ_2026-07-28_b58", "engine", "ELSEWHERE", 0, None,
     "no earlier trade changes and missed opportunities. I see one 9:50 OCR"),

    # -- probe_omen_test1_2026-08-27 : 100 engine cards carrying entry_t -----
    ("probe_omen_test1_2026-08-27.jsonl", "t1_HOOD_2026-03-27", "engine", "ENTRY", -1, 4,
     "4 candle earlier may be entry but my downgrade is entry didn't close below nearby level"),
    ("probe_omen_test1_2026-08-27.jsonl", "t1_NFLX_2026-05-12", "engine", "ENTRY", -1, 2,
     "two candles earlier couldve been S entry too"),
    ("probe_omen_test1_2026-08-27.jsonl", "t1_AMZN_2025-08-22", "engine", "ENTRY", -1, 6,
     "9:57 was an earlier put entry as candle forming not LOD"),  # card entry 10:03
    ("probe_omen_test1_2026-08-27.jsonl", "t1_META_2025-07-03", "engine", "ENTRY", -1, None,
     "earlier entries and missed the OCR"),
    ("probe_omen_test1_2026-08-27.jsonl", "t1_AMZN_2026-03-09", "engine", "ENTRY", -1, None,
     "overextended, earlier trades that should've but didn't happen"),
    ("probe_omen_test1_2026-08-27.jsonl", "t1_SPY_2026-04-29", "engine", "ENTRY", +1, 7,
     "7 candles later good c entry for OCR"),
    ("probe_omen_test1_2026-08-27.jsonl", "t1_UBER_2025-09-18", "engine", "AMBIG", 0, None,
     "earlier entry at 10:52"),  # 10:52 is AFTER the card's 09:58 -- inconsistent
    ("probe_omen_test1_2026-08-27.jsonl", "t1_IWM_2025-05-02", "engine", "CONTEXT", 0, None,
     "possible c entry at 10:46 but late in the day"),  # card carries no entry bar
    ("probe_omen_test1_2026-08-27.jsonl", "t1_AAPL_2025-08-25", "engine", "CONTEXT", 0, None,
     "can be forgiven with such an early trade like this"),

    # -- recovered_reviews.jsonl : reviews of ENGINE trades, no v7 twin ------
    ("recovered_reviews.jsonl", "AMD|2026-01-08", "engine", "ENTRY", -1, 8,
     "I see a possible earlier entry 8 candles before"),
    ("recovered_reviews.jsonl", "CRM|2025-10-27", "engine", "ENTRY", -1, None,
     "I see other one candle rules earlier so earlier possible entries as well"),
    ("recovered_reviews.jsonl", "GOOGL|2025-08-29", "engine", "ENTRY", -1, 2,
     "2 candles earlier an entry ... if entered 2 candles earlier"),
    ("recovered_reviews.jsonl", "HOOD|2025-09-15", "engine", "ENTRY", -1, 5.5,
     "11 candles before entry is an order block thats held so can enter 5-6 candles earlier"),
    ("recovered_reviews.jsonl", "INTC|2026-01-26", "engine", "ENTRY", -1, 1,
     "the one candle before is a better entry"),
    ("recovered_reviews.jsonl", "INTC|2026-02-25", "engine", "ENTRY", -1, 1,
     "candle before is the entry"),
    ("recovered_reviews.jsonl", "META|2025-10-24", "engine", "ENTRY", -1, 5,
     "earlier signal to enter on break of the pivot structure ... happens 5 candles before entry"),
    ("recovered_reviews.jsonl", "META|2026-04-07", "engine", "ENTRY", -1, 1,
     "one candle before entry better one"),
    ("recovered_reviews.jsonl", "MSFT|2025-08-26", "engine", "ENTRY", -1, 1,
     "i would enter on the candle earlier targeting LOD"),
    ("recovered_reviews.jsonl", "MSFT|2026-03-11", "engine", "ENTRY", -1, None,
     "your entry is late and done make sense ... few one candle rule examples earlier"),
    ("recovered_reviews.jsonl", "MSFT|2026-03-16", "engine", "ENTRY", +1, None,
     "you didn't enter on that though should've entered a few candles later"),
    ("recovered_reviews.jsonl", "NVDA|2025-11-07", "engine", "ENTRY", -1, 4,
     "even though the wick missed 4 candles earlier, i think that was a good entry too"),
    ("recovered_reviews.jsonl", "TSLA|2025-08-29", "engine", "ENTRY", +1, 16.5,
     "potentially 16-17 candles later could've been your entry"),
    ("recovered_reviews.jsonl", "TSLA|2026-01-16", "engine", "ENTRY", -1, None,
     "earlier entries couldve been had"),
    ("recovered_reviews.jsonl", "UBER|2025-09-12", "engine", "ENTRY", -1, 5,
     "5 candles before entry is clean break and retest with weak PA"),
    ("recovered_reviews.jsonl", "IREN_2026-05-21_9", "engine", "STOP", 0, None,
     "stop loss one candle rule 6 candles before or the bottom wick of candle you entered"),
    ("recovered_reviews.jsonl", "AVGO|2025-09-26", "engine", "STOP", 0, None,
     "4 candles before is a green candle confluence"),
    ("recovered_reviews.jsonl", "COIN|2026-01-22", "engine", "STOP", 0, None,
     "3 candles before entry close is within pivot structure"),
    ("recovered_reviews.jsonl", "COIN|2026-02-10", "engine", "STOP", 0, None,
     "10 candles before order block"),
    ("recovered_reviews.jsonl", "MU|2025-08-12", "engine", "STOP", 0, None,
     "red candle 6 candles before entry"),
    ("recovered_reviews.jsonl", "TSLA|2025-10-07", "engine", "STOP", 0, None,
     "9 candles before is also an order block"),
    ("recovered_reviews.jsonl", "TSLA|2025-12-15", "engine", "STOP", 0, None,
     "one candle rule 6 candles before entry. so lower stop"),
    ("recovered_reviews.jsonl", "AMZN|2026-02-17", "engine", "CONTEXT", 0, None,
     "never touched pml orl for earlier entry"),
    ("recovered_reviews.jsonl", "AVGO|2025-12-17", "engine", "CONTEXT", 0, None,
     "by the time it retested one it was too late"),
    ("recovered_reviews.jsonl", "BABA|2026-01-30", "engine", "CONTEXT", 0, None,
     "you want to catch the big moves early"),
    ("recovered_reviews.jsonl", "CRM|2025-11-10", "engine", "CONTEXT", 0, None,
     "we want to end the day as early as possible"),
    ("recovered_reviews.jsonl", "HOOD|2025-09-10", "engine", "CONTEXT", 0, None,
     "clean break and retest if you take everything away all the earlier candles"),
    ("recovered_reviews.jsonl", "ORCL|2025-10-24", "engine", "CONTEXT", 0, None,
     "not even clear break and retest if we get rid of the earlier candle section"),
    ("recovered_reviews.jsonl", "INTC|2025-08-21", "engine", "AMBIG", 0, None,
     "maybe 4 candles before there's a one candle rule8 candles before"),
    ("recovered_reviews.jsonl", "NVDA|2025-12-12", "engine", "AMBIG", 0, None,
     "break and no rest usually invaludates later entries <row text corrupted>"),
    # -- recovered rows whose id already exists in austin_marks_v7 ----------
    ("recovered_reviews.jsonl", "AMD_2025-11-21_12", "engine", "DUP", 0, None, "v7 twin"),
    ("recovered_reviews.jsonl", "AVGO_2026-04-23_12", "engine", "DUP", 0, None, "v7 twin"),
    ("recovered_reviews.jsonl", "BABA_2026-05-14_69", "engine", "DUP", 0, None, "v7 twin"),
    ("recovered_reviews.jsonl", "COIN_2025-11-07_16", "engine", "DUP", 0, None, "v7 twin"),
    ("recovered_reviews.jsonl", "COIN_2025-12-18_11", "engine", "DUP", 0, None, "v7 twin"),
    ("recovered_reviews.jsonl", "GOOGL_2026-05-27_11", "engine", "DUP", 0, None, "v7 twin"),
    ("recovered_reviews.jsonl", "INTC_2026-06-26_42", "engine", "DUP", 0, None, "v7 twin"),
    ("recovered_reviews.jsonl", "IREN_2026-06-03_9", "engine", "DUP", 0, None, "v7 twin"),
    ("recovered_reviews.jsonl", "META_2026-01-16_81", "engine", "DUP", 0, None, "v7 twin"),
    ("recovered_reviews.jsonl", "PLTR_2026-03-18_28", "engine", "DUP", 0, None, "v7 twin"),
    ("recovered_reviews.jsonl", "QQQ_2025-10-29_84", "engine", "DUP", 0, None, "v7 twin"),
    ("recovered_reviews.jsonl", "TSLA_2026-02-04_35", "engine", "DUP", 0, None, "v7 twin"),

    # -- austin_marks_v7 : the `<sym>_<day>_<a>_<b>` id family is the batch05
    #    engine-entry review lane; second person ("your entry", "you missed",
    #    "yours") confirms the entry on the card was not his.
    ("austin_marks_v7.jsonl", "AAPL_2024-01-02_19", "engine", "ENTRY", -1, 1,
     "1 candle earlier is your entry"),
    ("austin_marks_v7.jsonl", "AAPL_2024-03-28_7_61", "engine", "ENTRY", +1, 4,
     "4 candles after is an S entry OCR"),
    ("austin_marks_v7.jsonl", "AAPL_2025-01-13_18_28", "engine", "ENTRY", -1, 3,
     "3 candles earlier is an S entry, reclaim ... but yours is correct for the a trade"),
    ("austin_marks_v7.jsonl", "AMD_2024-11-11_22_29", "engine", "ENTRY", -1, 4,
     "s entry 4 candles earlier, still decent entry"),
    ("austin_marks_v7.jsonl", "AMD_2025-03-28_31", "engine", "ENTRY", -1, 22,
     "earlier entry at 9:39 as candle forming not at HOD was s trade, yours a fail"),
    ("austin_marks_v7.jsonl", "AMD_2025-11-21_12", "engine", "ENTRY", -1, 5,
     "almost earlier entry 5 candles earlier"),
    ("austin_marks_v7.jsonl", "AMD_2026-05-14_17", "engine", "ENTRY", +1, 8,
     "later s entry 8 candles later OCR"),
    ("austin_marks_v7.jsonl", "AMD_2026-05-14_43", "engine", "ENTRY", -1, 2,
     "earlier s entry, this one took longer to develop, 2 candles earlier is entry"),
    ("austin_marks_v7.jsonl", "AMD_2026-05-14_67", "engine", "ENTRY", -1, 2,
     "two candles earlier is your s entry ... you were a little late"),
    ("austin_marks_v7.jsonl", "AVGO_2026-04-23_12", "engine", "ENTRY", -1, 2,
     "2 candles before is your entry and a clean break and retest! which would be an S"),
    ("austin_marks_v7.jsonl", "COIN_2025-10-21_8", "engine", "ENTRY", -1, 5,
     "blue line entry is C ... but earlier entry 5 candles earlier as the candle is closing"),
    ("austin_marks_v7.jsonl", "COIN_2025-11-07_16", "engine", "ENTRY", -1, 11,
     "at 9:35 I almost see an entry ... your entry way later in chop"),  # card 09:46
    ("austin_marks_v7.jsonl", "COIN_2025-12-18_11", "engine", "ENTRY", -1, 6,
     "6 candles before might've been an entry ... but your entry is clean too"),
    ("austin_marks_v7.jsonl", "GOOGL_2026-05-27_11", "engine", "ENTRY", +1, 12.5,
     "maybe 12 or 13 candles after is an entry"),
    ("austin_marks_v7.jsonl", "INTC_2025-02-27_72_153", "engine", "ENTRY", +1, 14,
     "I see an entry 14 candles later an S entry"),
    ("austin_marks_v7.jsonl", "INTC_2025-06-05_22", "engine", "ENTRY", -1, 1,
     "on candle earlier is your entry and then it would've been A"),
    ("austin_marks_v7.jsonl", "IREN_2026-06-03_9", "engine", "ENTRY", -1, 1,
     "one candle before maybe entry your stop is the 9:30 candle"),
    ("austin_marks_v7.jsonl", "META_2025-09-18_45_58", "engine", "ENTRY", -1, 1,
     "1 candle earlier A entry, 6 candles earlier then that is an A entry too"),
    ("austin_marks_v7.jsonl", "META_2026-01-16_81", "engine", "ENTRY", -1, 5,
     "I see earlier entry 5 candles before if it holds"),
    ("austin_marks_v7.jsonl", "MSFT_2025-04-17_16_36", "engine", "ENTRY", -1, 3,
     "3 candles earlier is an S our entry ... but your trade was wrong"),
    ("austin_marks_v7.jsonl", "MSTR_2024-08-08_23_27", "engine", "ENTRY", -1, 3,
     "3 candles earlier is also an A entry, 84 percent rule same stop is ok"),
    ("austin_marks_v7.jsonl", "MSTR_2025-12-12_11", "engine", "ENTRY", -1, 5,
     "5 candles earlier is your s entry"),
    ("austin_marks_v7.jsonl", "MU_2026-01-28_13", "engine", "ENTRY", -1, 9,
     "but your trade was an x, you missed the entry 9 candles earlier"),
    ("austin_marks_v7.jsonl", "MU_2026-07-24_16_20", "engine", "ENTRY", -1, 6,
     "another a entry 6 candles earlier"),
    ("austin_marks_v7.jsonl", "NVDA_2024-12-16_14", "engine", "ENTRY", -1, 2,
     "your trade never, two candles earlier is your S entry OCR and BR confluence"),
    ("austin_marks_v7.jsonl", "NVDA_2025-09-29_13_23", "engine", "ENTRY", -1, 1,
     "1 candle earlier is S entry, no stop out occurs"),
    ("austin_marks_v7.jsonl", "NVDA_2026-02-05_48_52", "engine", "ENTRY", -1, 1,
     "1 candle earlier is your A entry"),
    ("austin_marks_v7.jsonl", "PLTR_2026-03-18_28", "engine", "ENTRY", -1, None,
     "especially when you could enter earlier, I never like to enter late"),
    ("austin_marks_v7.jsonl", "QQQ_2025-10-29_84", "engine", "ENTRY", -1, 2,
     "reversal, 2 candles before I see a break and retest entry to downside"),
    ("austin_marks_v7.jsonl", "SPCX_2026-06-30_33_55", "engine", "ENTRY", -1, 1,
     "one candle earlier s entry ... your entry is wrong one candle late"),
    ("austin_marks_v7.jsonl", "GOOGL_2024-10-15_47", "engine", "ELSEWHERE", 0, None,
     "2 earlier entry opportunities that were S, first one 9:43, second 10:02"),
    ("austin_marks_v7.jsonl", "INTC_2026-06-26_42", "engine", "STOP", 0, None,
     "stop could've been 1 candle rule 5 candles earlier"),
    ("austin_marks_v7.jsonl", "MU_2026-02-09_24_36", "engine", "STOP", 0, None,
     "stop out would've been 5 candles later because thats when the close below happened"),
    ("austin_marks_v7.jsonl", "AMD_2024-10-22_26_87", "engine", "CONTEXT", 0, None,
     "can't see what happens earlier"),
    ("austin_marks_v7.jsonl", "AMD_2025-08-27_7_64", "engine", "CONTEXT", 0, None,
     "dont know what happens earlier"),
    ("austin_marks_v7.jsonl", "AMD_2025-10-14_75_137", "engine", "CONTEXT", 0, None,
     "dont know what happened before and its late in the day"),
    ("austin_marks_v7.jsonl", "MSTR_2025-12-05_17_102", "engine", "CONTEXT", 0, None,
     "can't see what happens earlier"),
    ("austin_marks_v7.jsonl", "NVDA_2025-05-21_18_80", "engine", "CONTEXT", 0, None,
     "dont know what earlier candles look like"),
    ("austin_marks_v7.jsonl", "BABA_2026-05-14_69", "engine", "CONTEXT", 0, None,
     "not sure how much overlap there is or if earlier entry possilble"),
    ("austin_marks_v7.jsonl", "TSLA_2026-02-04_35", "engine", "CONTEXT", 0, None,
     "if I only saw the 10 candles before you entered, looks good but your in a channel"),

    # ======================================================================
    # P-SELF -- he was marking / regrading HIS OWN entry.  Control population.
    # ======================================================================
    ("austin_marks_v7.jsonl", "AVGO_2024-08-07_15", "self", "ENTRY", +1, None,
     "couple entries couple candles later or way later"),          # blind pass
    ("austin_marks_v7.jsonl", "QQQ_2024-11-15_31", "self", "ENTRY", -1, None,
     "enter as the candle closing could enter earlier possibly"),  # blind pass
    ("austin_marks_v7.jsonl", "IWM_2024-04-03_73", "self", "ENTRY", -1, 1,
     "candle before is the entry actually"),                       # batch03 regrade
    ("austin_marks_v7.jsonl", "IWM_2025-10-21_9", "self", "ENTRY", -1, 1,
     "1 candle earlier is the entry, marking A"),                  # batch03 regrade
    ("austin_marks_v7.jsonl", "NVDA_2024-11-18_10", "self", "ENTRY", -1, 6,
     "6 candles earlier is a break and retest no displacement"),   # batch03 regrade
    ("austin_marks_v7.jsonl", "QQQ_2024-01-04_41", "self", "ENTRY", -1, 4,
     "4 candles earlier is an A trade ... this = C, earlier entry = A"),
    ("austin_marks_v7.jsonl", "QQQ_2024-12-16_28", "self", "ENTRY", -1, 7,
     "break and retest no displacement entry 7 candles before"),
    ("austin_marks_v7.jsonl", "ORCL_2025-11-03_17", "self", "ENTRY", -1, None,
     "my entry s criteria but late entry, because earlier one existed with less displacement"),
    ("austin_marks_v7.jsonl", "AAPL_2025-02-19_62", "self", "CONTEXT", 0, None,
     "just late in the day you always want earlier trades"),
    ("austin_marks_v7.jsonl", "AVGO_2025-04-10_34", "self", "CONTEXT", 0, None,
     "want to get the day done early with the cleanest setup out there"),
    ("austin_marks_v7.jsonl", "PLTR_2025-07-15_45", "self", "CONTEXT", 0, None,
     "most s trades happen very early"),
    ("austin_marks_v7.jsonl", "SOFI_2026-04-16_20", "self", "CONTEXT", 0, None,
     "I like this better then entry 6 candles earlier"),      # PREFERS the card's own entry
    ("austin_marks_v7.jsonl", "SPY_2024-12-03_10", "self", "STOP", 0, None,
     "later entry in the day would've lowered the stop"),
    ("austin_marks_v7.jsonl", "NVDA_2024-01-03_98", "self", "CONTEXT", 0, None,
     "outside timeframe I trade but ... there were nearly earlier entries"),
    ("austin_marks_v7.jsonl", "GOOGL_2026-01-20_67", "self", "CONTEXT", 0, None,
     "red candles respected earlier, way too late"),
    ("austin_marks_v7.jsonl", "META_2025-09-23_74", "self", "CONTEXT", 0, None,
     "late in day, not above key levels, slow mover"),
    ("austin_marks_v7.jsonl", "MU_2026-01-28_71", "self", "CONTEXT", 0, None,
     "s trades come early, sometime a and c can fire later"),
    ("deck_marks_index_2026-08-19.jsonl", "SPY_2026-06-30", "self", "CONTEXT", 0, None,
     "late trade and choppy to start the day"),
    # -- probe_autopsy_2026-08-23 : HIS entries on days the engine was SILENT
    ("probe_autopsy_2026-08-23.jsonl", "TSLA_2026-06-29", "self", "ENTRY", -1, 1,
     "one candle earlier almost had enough strength ... the candle i entered on follows that"),
    ("probe_autopsy_2026-08-23.jsonl", "QQQ_2026-07-23", "self", "ENTRY", -1, 2,
     "two candles earlier a better entry OCR S entry as candle forming"),
    ("probe_autopsy_2026-08-23.jsonl", "QQQ_2026-07-16", "self", "ENTRY", 0, 0,
     "I would actually enter one candle before i entered ... actually no the candle i entered was right"),
    ("probe_autopsy_2026-08-23.jsonl", "TSLA_2026-06-03", "self", "STOP", 0, None,
     "9 candles before entry is the clear OCR wick stop confluence"),
    # -- probe_s_sweep_2026-08-28 : the minutes HE typed --------------------
    ("probe_s_sweep_2026-08-28.jsonl", "MSFT_2025-03-13", "self", "ENTRY", -1, None,
     "as candle forming not lod. a entry few candles earlier"),
    ("probe_s_sweep_2026-08-28.jsonl", "META_2025-02-05", "self", "CONTEXT", 0, None,
     "not respecing red candles as early as would like"),
    ("probe_s_sweep_2026-08-28.jsonl", "AAPL_2025-07-21", "self", "CONTEXT", 0, None,
     "early trades have great probability"),

    # ======================================================================
    # P-MIXED -- mark_batch_02 ("40 S-miss bars + 20 unmarked ENGINE entries",
    # LEDGER.md) and batch04 rows with no pronoun.  The card's provenance
    # cannot be established row by row, so these are reported separately and
    # are in NEITHER headline population.
    # ======================================================================
    ("austin_marks_v7.jsonl", "AMZN_2026-04-10_27", "mixed", "ENTRY", -1, 5, "entry 5 candles earlier"),
    ("austin_marks_v7.jsonl", "HOOD_2026-07-10_23", "mixed", "ENTRY", -1, 4, "4 candles earlier is entry"),
    ("austin_marks_v7.jsonl", "MSFT_2025-03-04_20", "mixed", "ENTRY", -1, None, "possible earlier entry"),
    ("austin_marks_v7.jsonl", "PLTR_2025-09-18_14", "mixed", "ENTRY", -1, 1, "I candle earlier entry"),
    ("austin_marks_v7.jsonl", "QQQ_2025-01-10_30", "mixed", "ENTRY", -1, None, "same stock but earlier entry better"),
    ("austin_marks_v7.jsonl", "QQQ_2026-02-11_40", "mixed", "ENTRY", -1, 9.5, "earlier entry 9-10 candles earlier"),
    ("austin_marks_v7.jsonl", "TSM_2026-05-29_23", "mixed", "ENTRY", -1, 5, "entry 5 candles earlier but not at high of day"),
    ("austin_marks_v7.jsonl", "AMZN_2026-07-17_34", "mixed", "ENTRY", -1, 12, "earlier entry hold of one candle rule 12 bars earlier"),
    ("austin_marks_v7.jsonl", "MU_2026-01-28_10", "mixed", "ENTRY", -1, 5, "earlier S entry 9:35 OCR perfect setup"),   # card 09:40
    ("austin_marks_v7.jsonl", "PLTR_2024-10-23_10", "mixed", "ENTRY", +1, 11, "later entry 9:51 OCR, S trade"),        # card 09:40
    ("austin_marks_v7.jsonl", "TSLA_2024-01-03_16", "mixed", "ENTRY", +1, 2.5, "2 or 3 candles later is a S BR for puts"),
    ("austin_marks_v7.jsonl", "UBER_2024-09-10_17", "mixed", "ENTRY", -1, None, "could be entry slightly earlier"),

    # ======================================================================
    # Whole files that are contained in austin_marks_v7 / blind_marks_all.
    # LEDGER.md: "austin_marks_v7.jsonl is the terminal file -- every earlier
    # version's rows are contained inside it."  Adjudicated at the v7 row.
    # ======================================================================
    ("austin_marks_v7.jsonl", "AAPL_2024-03-28_11", "self", "DUP", 0, None, "derived_v2 clone of _7_61"),
    ("austin_marks_v7.jsonl", "AAPL_2025-01-13_15", "self", "DUP", 0, None, "derived_v2 clone of _18_28"),
    ("austin_marks_v7.jsonl", "AAPL_2025-01-13_16", "self", "DUP", 0, None, "derived_v2 clone of _18_28"),
    ("austin_marks_v7.jsonl", "AMD_2024-11-11_18", "self", "DUP", 0, None, "derived_v2 clone of _22_29"),
    ("austin_marks_v7.jsonl", "INTC_2025-02-27_86", "self", "DUP", 0, None, "derived_v2 clone of _72_153"),
    ("austin_marks_v7.jsonl", "META_2025-09-18_39", "self", "DUP", 0, None, "derived_v2 clone of _45_58"),
    ("austin_marks_v7.jsonl", "META_2025-09-18_44", "self", "DUP", 0, None, "derived_v2 clone of _45_58"),
    ("austin_marks_v7.jsonl", "MSFT_2025-04-17_13", "self", "DUP", 0, None, "derived_v2 clone of _16_36"),
    ("austin_marks_v7.jsonl", "MSTR_2024-08-08_20", "self", "DUP", 0, None, "derived_v2 clone of _23_27"),
    ("austin_marks_v7.jsonl", "MSTR_2025-12-12_6", "self", "DUP", 0, None, "derived_v2 clone of _11"),
    ("austin_marks_v7.jsonl", "MU_2026-07-24_10", "self", "DUP", 0, None, "derived_v2 clone of _16_20"),
    ("austin_marks_v7.jsonl", "NVDA_2024-11-18_4", "self", "DUP", 0, None, "derived_v2 clone of _10"),
    ("austin_marks_v7.jsonl", "NVDA_2025-09-29_12", "self", "DUP", 0, None, "derived_v2 clone of _13_23"),
    ("austin_marks_v7.jsonl", "NVDA_2026-02-05_47", "self", "DUP", 0, None, "derived_v2 clone of _48_52"),
    ("austin_marks_v7.jsonl", "QQQ_2024-01-04_37", "self", "DUP", 0, None, "derived_v2 clone of _41"),
    ("austin_marks_v7.jsonl", "QQQ_2024-12-16_21", "self", "DUP", 0, None, "derived_v2 clone of _28"),
    ("austin_marks_v7.jsonl", "SPCX_2026-06-30_32", "self", "DUP", 0, None, "derived_v2 clone of _33_55"),
    ("austin_marks_v7.jsonl", "TSLA_2024-01-03_19", "self", "DUP", 0, None, "derived_v2 clone of _16"),
    ("blind_marks_all.jsonl", "*", "self", "DUP", 0, None, "every marked row is inside austin_marks_v7"),
    ("marks_clean.jsonl", "*", "self", "DUP", 0, None, "marked-only subset of blind_marks_all"),
    ("mark_batch_02_grades.jsonl", "*", "mixed", "DUP", 0, None, "merged into austin_marks_v7"),
    ("mark_batch_03_regrades.jsonl", "*", "self", "DUP", 0, None, "merged into austin_marks_v7"),
    ("mark_batch_04_grades.jsonl", "*", "mixed", "DUP", 0, None, "merged into austin_marks_v7"),
    ("derived_marks_v1.jsonl", "*", "self", "DUP", 0, None, "merged into austin_marks_v7"),
    ("derived_marks_v2.jsonl", "*", "self", "DUP", 0, None, "merged into austin_marks_v7"),
]

# The scan pattern.  Deliberately WIDE -- it is a tripwire, not the measurement.
NUM = (r'(?:\d+(?:\s*[-or]{1,3}\s*\d+)?|one|two|three|four|five|six|seven|eight'
       r'|nine|ten|eleven|twelve|a few|few|couple|several)')
SCAN = re.compile(
    NUM + r'\s+(?:candles?|bars?)\s+(?:earlier|before|later|after|prior)'
    r'|(?:earlier|later)\s+(?:possible\s+)?(?:entr|s\b|a\b|trade|signal|put|call)'
    r'|entr\w*\s+(?:\w+\s+){0,2}(?:earlier|later)'
    r'|(?:trade )?happens earlier'
    r'|candle before is the entry'
    r'|enter\s+\w{0,12}\s?(?:earlier|later)'
    r'|entered\s+\w{0,3}\s?candle\s+late'
    r'|\bcandle\s+(?:earlier|late)\b'
    r'|(?:earlier|later)\s+candle'
    r'|\b(?:too )?(?:late|early)\b', re.I)

SCAN_FILES = ([os.path.join(ROOT, "research", f) for f in
               ("austin_marks_v7.jsonl", "blind_marks_all.jsonl", "recovered_reviews.jsonl",
                "marks_clean.jsonl", "mark_batch_02_grades.jsonl",
                "mark_batch_03_regrades.jsonl", "mark_batch_04_grades.jsonl",
                "derived_marks_v1.jsonl", "derived_marks_v2.jsonl")]
              + sorted(glob.glob(os.path.join(ROOT, "research", "marks", "*.jsonl"))))


def note_text(d):
    parts = []
    for k in ("note", "why", "missing", "comment"):
        v = d.get(k)
        if isinstance(v, str) and v:
            parts.append(v)
    v = d.get("notes")
    if isinstance(v, dict):
        for kk, vv in v.items():
            if isinstance(vv, str) and vv:
                parts.append("[%s] %s" % (kk, vv))
    elif isinstance(v, str) and v:
        parts.append(v)
    return " || ".join(parts)


def row_key(d):
    rid = d.get("id") or d.get("card_id")
    if rid:
        return str(rid)
    sym, day = d.get("symbol"), d.get("day") or d.get("date")
    return "%s|%s" % (sym, day)


def scan():
    """Return {(file, key): note} for every mark row whose prose mentions entry
    timing.  Re-run every invocation so the adjudication table cannot go stale."""
    hits = {}
    for path in SCAN_FILES:
        if not os.path.exists(path):
            continue
        base = os.path.basename(path)
        for line in open(path, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            txt = note_text(d)
            if txt and SCAN.search(txt):
                hits[(base, row_key(d))] = txt
    return hits


# --------------------------------------------------------------------------
# section 1 -- the corpus measurement
# --------------------------------------------------------------------------
def boot_ci(xs, stat=statistics.mean, n=20000, seed=12):
    if len(xs) < 2:
        return (float("nan"), float("nan"))
    rnd = random.Random(seed)
    reps = []
    for _ in range(n):
        reps.append(stat([rnd.choice(xs) for _ in xs]))
    reps.sort()
    return reps[int(0.025 * n)], reps[int(0.975 * n)]


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return c - h, c + h


def sign_test_p(k, n):
    """Two-sided exact binomial p at p0=0.5."""
    from math import comb
    if n == 0:
        return float("nan")
    tot = 2 ** n
    lo = min(k, n - k)
    tail = sum(comb(n, i) for i in range(lo + 1))
    return min(1.0, 2.0 * tail / tot)


def cmd_corpus(verbose=True):
    hits = scan()
    adj = {}
    wildcard = set()
    for f, key, ref, cls, dirn, bars, quote in ADJUDICATION:
        if key == "*":
            wildcard.add(f)
        else:
            adj[(f, key)] = (ref, cls, dirn, bars, quote)

    missing = [k for k in hits
               if k not in adj and k[0] not in wildcard]
    if missing:
        print("\n!! %d scanned timing notes are NOT adjudicated -- the table is stale."
              % len(missing))
        for f, key in sorted(missing)[:40]:
            print("   %-38s %-30s %s" % (f, key, hits[(f, key)][:120].replace("\n", " ")))
        print("   Add each to ADJUDICATION (class CONTEXT if it is not an entry offset).")

    # A row that the scan does NOT find is a phantom -- a key that does not
    # exist in any corpus.  It is dropped, loudly, so no number can rest on a
    # mark row that is not there.
    phantom = [k for k in adj if k not in hits]
    if phantom:
        print("\n!! %d adjudicated keys are NOT present in any corpus -- DROPPED:"
              % len(phantom))
        for f, key in sorted(phantom):
            print("   %-38s %s" % (f, key))

    rows = []
    for (f, key), (ref, cls, dirn, bars, quote) in adj.items():
        if (f, key) not in hits:
            continue
        rows.append(dict(file=f, key=key, ref=ref, cls=cls, dirn=dirn,
                         bars=bars, quote=quote))

    live = [r for r in rows if r["cls"] not in ("DUP",)]
    entries = [r for r in live if r["cls"] == "ENTRY"]

    out = {}
    for pop in ("engine", "self", "mixed"):
        E = [r for r in entries if r["ref"] == pop and r["dirn"] != 0]
        early = [r for r in E if r["dirn"] < 0]
        late = [r for r in E if r["dirn"] > 0]
        mags = [r["dirn"] * r["bars"] for r in E if r["bars"] is not None]
        lo_p, hi_p = wilson(len(early), len(E))
        m_lo, m_hi = boot_ci(mags) if mags else (float("nan"), float("nan"))
        md_lo, md_hi = boot_ci(mags, statistics.median) if mags else (float("nan"), float("nan"))
        out[pop] = dict(
            n=len(E), n_early=len(early), n_late=len(late),
            frac_early=len(early) / len(E) if E else float("nan"),
            frac_early_ci=(lo_p, hi_p),
            sign_p=sign_test_p(len(late), len(E)),
            n_numeric=len(mags),
            mean=statistics.mean(mags) if mags else float("nan"),
            mean_ci=(m_lo, m_hi),
            median=statistics.median(mags) if mags else float("nan"),
            median_ci=(md_lo, md_hi),
            mags=sorted(mags),
        )

    if verbose:
        print("=" * 78)
        print("T12 SECTION 1 -- the adjudicated offset corpus")
        print("=" * 78)
        print("scanned timing notes ............. %d" % len(hits))
        print("adjudicated rows ................. %d (%d marked DUP of an earlier corpus)"
              % (len(rows), sum(1 for r in rows if r["cls"] == "DUP")))
        cc = Counter(r["cls"] for r in live)
        print("classes (non-dup) ................ %s" % dict(cc))
        print()
        print("REACHABILITY (method rule 3): of the notes that mention entry timing at all,")
        print("  %d of %d (%.1f%%) name an alternative ENTRY rather than a stop, a piece of"
              % (len(entries), len(live), 100.0 * len(entries) / max(1, len(live))))
        print("  structure, or a general remark about time of day.")
        print("BASE RATE -- how often he volunteers a timing complaint at all, on the")
        print("three engine-card corpora with a countable denominator:")
        for f, denom, what in (
                ("probe_omen_test1_2026-08-27.jsonl", 100, "engine cards, part 1-5"),
                ("probe_master_2026-08-29.jsonl", 75, "veto+rare+runner engine cards"),
                ("recovered_reviews.jsonl", 176, "engine trades reviewed in chat")):
            E = [r for r in live if r["file"] == f and r["cls"] == "ENTRY"]
            e = sum(1 for r in E if r["dirn"] < 0)
            l = sum(1 for r in E if r["dirn"] > 0)
            print("  %-40s %3d cards  earlier %2d (%4.1f%%)  later %d"
                  % (what, denom, e, 100.0 * e / denom, l))
        print("  He raises it on a minority of cards.  The 85%% above is the direction")
        print("  GIVEN that he raised it, not the share of all cards that are late.")
        print()
        for pop, label in (
                ("engine", "P-ENGINE  the card showed an ENGINE-proposed entry"),
                ("self", "P-SELF    he was marking his OWN entry (control)"),
                ("mixed", "P-MIXED   card provenance not establishable row by row")):
            o = out[pop]
            print("-" * 78)
            print(label)
            print("  n with a direction ............. %d" % o["n"])
            print("  earlier / later ................ %d / %d" % (o["n_early"], o["n_late"]))
            print("  fraction EARLIER ............... %.3f  (95%% Wilson %.3f - %.3f)"
                  % (o["frac_early"], o["frac_early_ci"][0], o["frac_early_ci"][1]))
            print("  exact binomial sign test p ..... %.2e" % o["sign_p"])
            print("  n with a stated bar count ...... %d" % o["n_numeric"])
            print("  MEAN signed offset (bars) ...... %+.3f  (95%% boot %+.3f to %+.3f)"
                  % (o["mean"], o["mean_ci"][0], o["mean_ci"][1]))
            print("  MEDIAN signed offset (bars) .... %+.1f   (95%% boot %+.1f to %+.1f)"
                  % (o["median"], o["median_ci"][0], o["median_ci"][1]))
            print("  distribution ................... %s" % o["mags"])
        print()
    return out, rows


# --------------------------------------------------------------------------
# section 2 -- what T1's "+0.0 median" is conditioned on
# --------------------------------------------------------------------------
def cmd_t1check(verbose=True):
    deltas, matched = [], []
    if not os.path.exists(T1_MD):
        print("!! %s missing -- section 2 skipped" % T1_MD)
        return None
    for line in open(T1_MD, encoding="utf-8", errors="replace"):
        m = re.match(r"^\|\s*([A-Z]+)\s*\|\s*(\d{4}-\d\d-\d\d)\s*\|\s*[\d:]+\s*\|"
                     r"\s*[\d:]+\s*\|\s*([+-]\d+)\s*\|\s*(FIRED|DETECTED|ELSEWHERE)\s*\|",
                     line.strip())
        if m:
            d = int(m.group(3))
            deltas.append(d)
            if m.group(4) in ("FIRED", "DETECTED"):
                matched.append(d)
    if verbose:
        print("=" * 78)
        print("T12 SECTION 2 -- what T1's 'median +0.0 bars' is conditioned on")
        print("=" * 78)
        print("T1's rule: 'A signal counts as his idea when it lands within 2 bars of the")
        print("minute he typed.'  The +0.0 median is taken over exactly that subset.")
        print()
        print("  T1's reported subset (FIRED+DETECTED) .. n=%d  median %+.1f  mean %+.2f"
              % (len(matched), statistics.median(matched), statistics.mean(matched)))
        print("  max |delta| in that subset ............. %d  <-- the selection window"
              % max(abs(x) for x in matched))
        print("  ALL 34 days in T1's own table .......... n=%d  median %+.1f  mean %+.2f"
              % (len(deltas), statistics.median(deltas), statistics.mean(deltas)))
        print("  ALL 34, share where engine is LATE ..... %d of %d (%.0f%%)"
              % (sum(1 for x in deltas if x > 0), len(deltas),
                 100.0 * sum(1 for x in deltas if x > 0) / len(deltas)))
        print()
        print("  The statistic cannot leave [-2,+2] by construction, so '+0.0' is a")
        print("  property of the matching rule, not evidence that the engine is on time.")
    return dict(matched=matched, all=deltas)


# --------------------------------------------------------------------------
# section 3 -- the mechanism: CONFIRM-on-close costs N bars
# --------------------------------------------------------------------------
LEVEL_RE = re.compile(r"(?:above|below)\s+(.+?)\s+\$([0-9.]+)")


def rth_bars(sym, day):
    path = os.path.join(ARCHIVE, sym, "%s.csv" % day)
    if not os.path.exists(path):
        return None
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t = r["Datetime"][11:16]
            if "09:30" <= t <= "16:00":
                out.append((t, float(r["High"]), float(r["Low"]), float(r["Close"])))
    return out or None


def cmd_fsm(limit=0, verbose=True):
    if not os.path.exists(BOOK):
        print("!! %s missing -- section 3 skipped" % BOOK)
        return None
    book = json.load(open(BOOK, encoding="utf-8"))
    trades = [t for t in book["trades"]
              if t.get("traded") and t.get("setup") == "break_and_retest"
              and t.get("entry_i") is not None]
    if limit:
        trades = trades[:limit]
    gaps, missing, nolevel = [], 0, 0
    per_dir = Counter()
    for t in trades:
        m = LEVEL_RE.search(t.get("reason", ""))
        if not m:
            nolevel += 1
            continue
        level = float(m.group(2))
        bars = rth_bars(t["sym"], t["day"])
        if not bars:
            missing += 1
            continue
        ei = t["entry_i"]
        if ei >= len(bars):
            missing += 1
            continue
        # last bar AT OR BEFORE the entry bar whose RANGE contained the level.
        # The entry bar is included on purpose: if it touched the level itself
        # the engine did enter on the retest bar and the gap is a true 0.
        touch = None
        for i in range(ei, max(-1, ei - 25), -1):
            _, hi, lo, _ = bars[i]
            if lo <= level <= hi:
                touch = i
                break
        if touch is None:
            continue
        gaps.append(ei - touch)
        per_dir[t["side"]] += 1
    if verbose:
        print("=" * 78)
        print("T12 SECTION 3 -- the mechanism, measured on the shipped book")
        print("=" * 78)
        print("Population: every TRADED break_and_retest row in research/bt2y_trades.json")
        print("whose `reason` names the broken level's price and whose day is archived.")
        print("Measured: bars from the LAST bar whose range touched that level to the bar")
        print("the engine entered on.  Austin's stated fill is 'as the candle is forming'")
        print("at the retest; detect_break_retest step 4 needs a LATER bar to CLOSE back")
        print("through the level, so this gap is the floor on how late the engine can be.")
        print()
        print("  traded B&R rows ................ %d" % len(trades))
        print("  level price unparseable ........ %d" % nolevel)
        print("  day not in data_archive ........ %d" % missing)
        print("  measured ....................... %d" % len(gaps))
        if gaps:
            c = Counter(gaps)
            print("  gap = 0 (entry bar IS the retest) %d  (%.1f%%)"
                  % (c[0], 100.0 * c[0] / len(gaps)))
            print("  gap = 1 bar .................... %d  (%.1f%%)"
                  % (c[1], 100.0 * c[1] / len(gaps)))
            print("  gap >= 2 bars .................. %d  (%.1f%%)"
                  % (sum(v for k, v in c.items() if k >= 2),
                     100.0 * sum(v for k, v in c.items() if k >= 2) / len(gaps)))
            print("  MEDIAN gap ..................... %.1f bars" % statistics.median(gaps))
            print("  MEAN gap ....................... %.2f bars" % statistics.mean(gaps))
            lo, hi = boot_ci(gaps, n=4000)
            print("  95%% boot CI on the mean ........ %.2f to %.2f" % (lo, hi))
            print("  histogram (gap: n) ............. %s"
                  % dict(sorted(c.items())[:12]))
    return dict(gaps=gaps, n=len(trades), missing=missing, nolevel=nolevel)


# --------------------------------------------------------------------------
# section 4 -- where the lateness actually comes from
# --------------------------------------------------------------------------
def cmd_arrival(verbose=True):
    """Section 3 refutes the obvious mechanism.  This one finds the real one.

    For every TRADED row, look at the engine's OWN signal stream on the same
    symbol / day / direction and ask whether it had already emitted a candidate
    1-6 bars earlier -- the range Austin's own notes live in.  If it had, the
    engine SAW the earlier entry and chose not to take it: the lateness is a
    grading/routing decision, not blindness.
    """
    from collections import defaultdict
    if not os.path.exists(BOOK):
        print("!! %s missing -- section 4 skipped" % BOOK)
        return None
    book = json.load(open(BOOK, encoding="utf-8"))
    by = defaultdict(list)
    for t in book["trades"]:
        if t.get("entry_i") is not None:
            by[(t["sym"], t["day"], t["dir"])].append(t)

    n_traded = 0
    n_any_earlier = 0
    n_near = 0
    n_earlier_S = 0
    n_earlier_S_and_taken_worse = 0
    grade = Counter()
    status = Counter()
    sgrade = Counter()
    near_gaps = []
    for v in by.values():
        v.sort(key=lambda x: x["entry_i"])
        for i, t in enumerate(v):
            if not t.get("traded"):
                continue
            n_traded += 1
            earlier = [x for x in v[:i] if x["entry_i"] < t["entry_i"]]
            if earlier:
                n_any_earlier += 1
                near_gaps.append(t["entry_i"] - earlier[-1]["entry_i"])
            near = [x for x in earlier if 1 <= t["entry_i"] - x["entry_i"] <= 6]
            if not near:
                continue
            n_near += 1
            for x in near:
                grade[x["grade"]] += 1
                status[x["status"]] += 1
                sgrade[x.get("sgrade")] += 1
            if any(x.get("sgrade") == "S" for x in near):
                n_earlier_S += 1
                if t.get("sgrade") != "S":
                    n_earlier_S_and_taken_worse += 1

    if verbose:
        print("=" * 78)
        print("T12 SECTION 4 -- where the lateness actually comes from")
        print("=" * 78)
        print("For every TRADED row: did the engine ALREADY emit a candidate on the same")
        print("symbol / day / direction before the entry it took?")
        print()
        print("  traded rows .................... %d" % n_traded)
        print("  had ANY earlier candidate ...... %d  (%.1f%%)"
              % (n_any_earlier, 100.0 * n_any_earlier / n_traded))
        print("  median bars to the nearest one . %.0f" % statistics.median(near_gaps))
        print("  had one 1-6 bars earlier ....... %d  (%.1f%%)   <-- Austin's own range"
              % (n_near, 100.0 * n_near / n_traded))
        print()
        print("  Those 1-6-bar-earlier candidates, by the LEGACY grade that routes trades:")
        tot = sum(grade.values())
        for g, n in grade.most_common():
            print("      %-4s %5d  (%.1f%%)" % (g, n, 100.0 * n / tot))
        print("  ...and by status:")
        for g, n in status.most_common():
            print("      %-20s %5d  (%.1f%%)" % (g, n, 100.0 * n / tot))
        print("  ...and by AUSTIN'S ladder (sgrade), which routes nothing:")
        for g, n in sgrade.most_common():
            print("      %-4s %5d  (%.1f%%)" % (str(g), n, 100.0 * n / tot))
        print()
        print("  traded rows with an S-on-his-ladder candidate 1-6 bars earlier .. %d (%.1f%%)"
              % (n_earlier_S, 100.0 * n_earlier_S / n_traded))
        print("  ...where the row actually taken is NOT S on his ladder .......... %d (%.1f%%)"
              % (n_earlier_S_and_taken_worse,
                 100.0 * n_earlier_S_and_taken_worse / n_traded))
    return dict(n_traded=n_traded, n_near=n_near, n_earlier_S=n_earlier_S,
                grade=dict(grade), sgrade=dict(sgrade), status=dict(status))


# --------------------------------------------------------------------------
# section 5 -- the held-out read (method rule 2)
# --------------------------------------------------------------------------
SWEEP = os.path.join(ROOT, "research", "marks", "probe_s_sweep_2026-08-28.jsonl")


def cmd_heldout(verbose=True):
    """T1 measured the engine against his 34 stated S minutes with a +/-2-bar
    matching rule.  This re-reads the same held-out file against the RATIFIED
    book with NO matching window, so the sign of the gap is free to move."""
    if not (os.path.exists(SWEEP) and os.path.exists(BOOK)):
        print("!! held-out inputs missing -- section 5 skipped")
        return None
    cards = []
    for line in open(SWEEP, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        ans = [str(x).lower() for x in (d.get("answers", {}).get("s") or [])]
        mn = (d.get("notes") or {}).get("min")
        if "s" in ans and mn:
            hh, _, mm = mn.partition(":")
            try:
                his_i = (int(hh) * 60 + int(mm)) - (9 * 60 + 30)
            except ValueError:
                continue
            cards.append((d["symbol"], d["date"], his_i, d["card_id"]))
    book = json.load(open(BOOK, encoding="utf-8"))
    idx = {}
    for t in book["trades"]:
        if t.get("entry_i") is None:
            continue
        idx.setdefault((t["sym"], t["day"]), []).append(t)

    deltas, nearest, silent = [], [], 0
    early = late = exact = 0
    for sym, day, his_i, cid in cards:
        sigs = idx.get((sym, day))
        if not sigs:
            silent += 1
            continue
        best = min(sigs, key=lambda t: abs(t["entry_i"] - his_i))
        dlt = best["entry_i"] - his_i
        deltas.append(dlt)
        nearest.append((cid, his_i, best["entry_i"], dlt, best["grade"], best.get("sgrade")))
        if dlt > 0:
            late += 1
        elif dlt < 0:
            early += 1
        else:
            exact += 1

    if verbose:
        print("=" * 78)
        print("T12 SECTION 5 -- the held-out read, no matching window")
        print("=" * 78)
        print("Held-out set: research/marks/probe_s_sweep_2026-08-28.jsonl, the %d cards"
              % len(cards))
        print("he graded S AND typed a minute for.  Engine = the nearest signal that")
        print("symbol-day emits in the RATIFIED book, whatever its distance.")
        print()
        print("  cards with a typed minute ...... %d" % len(cards))
        print("  engine silent that symbol-day .. %d" % silent)
        print("  measured ....................... %d" % len(deltas))
        if deltas:
            print("  engine LATE / EXACT / EARLY .... %d / %d / %d" % (late, exact, early))
            print("  MEDIAN signed delta (bars) ..... %+.1f" % statistics.median(deltas))
            print("  MEAN signed delta (bars) ....... %+.2f" % statistics.mean(deltas))
            lo, hi = boot_ci(deltas, statistics.median, n=20000)
            print("  95%% boot CI on the median ...... %+.1f to %+.1f" % (lo, hi))
            within = [d for d in deltas if abs(d) <= 6]
            print("  within +/-6 bars of his minute . %d of %d" % (len(within), len(deltas)))
            if within:
                print("    of those, LATE / EARLY ....... %d / %d"
                      % (sum(1 for d in within if d > 0), sum(1 for d in within if d < 0)))
                print("    median .......................  %+.1f" % statistics.median(within))
    return dict(deltas=deltas, rows=nearest, silent=silent)


# --------------------------------------------------------------------------
# section 6 -- the decisive test: is the bar he NAMES in the engine's stream?
# --------------------------------------------------------------------------
def card_bar(key, d):
    """Resolve (symbol, day, entry bar index counted from 09:30) for a card."""
    sym = d.get("symbol")
    day = d.get("day") or d.get("date")
    bar = d.get("entry_i")
    if bar is None:
        t = d.get("entry_t") or d.get("entry_time") or d.get("et")
        if t and ":" in str(t):
            hh, _, mm = str(t)[:5].partition(":")
            try:
                bar = int(hh) * 60 + int(mm) - (9 * 60 + 30)
            except ValueError:
                bar = None
    if bar is None and key.startswith("cal_"):
        m = re.match(r"cal_([A-Z]+)_(\d{4}-\d\d-\d\d)_b(\d+)$", key)
        if m:
            sym, day, bar = m.group(1), m.group(2), int(m.group(3))
    if bar is None:
        m = re.match(r"([A-Z]+)_(\d{4}-\d\d-\d\d)_(\d+)", key)
        if m:
            sym, day, bar = m.group(1), m.group(2), int(m.group(3))
    if not sym or not day or bar is None:
        return None
    return sym, day, int(bar)


def cmd_named(verbose=True):
    """For every P-ENGINE row where he names a NUMBER of bars AND the card's own
    entry bar is recoverable, ask the shipped book: did the engine emit anything
    at the bar he named (+/-1)?  A HIT means the detector saw it and the GRADER
    refused it.  A MISS means the detector never produced it."""
    if not os.path.exists(BOOK):
        print("!! %s missing -- section 6 skipped" % BOOK)
        return None
    adj = {}
    for f, key, ref, cls, dirn, bars, quote in ADJUDICATION:
        if key != "*":
            adj[(f, key)] = (ref, cls, dirn, bars, quote)
    raw = {}
    for path in SCAN_FILES:
        if not os.path.exists(path):
            continue
        base = os.path.basename(path)
        for line in open(path, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            raw[(base, row_key(d))] = d

    book = json.load(open(BOOK, encoding="utf-8"))
    idx = {}
    for t in book["trades"]:
        if t.get("entry_i") is not None:
            idx.setdefault((t["sym"], t["day"]), []).append(t)

    rows, seen = [], set()
    for (f, key), (ref, cls, dirn, bars, quote) in sorted(adj.items()):
        if ref != "engine" or cls != "ENTRY" or bars is None:
            continue
        d = raw.get((f, key))
        if d is None:
            continue
        cb = card_bar(key, d)
        if cb is None:
            continue
        sym, day, ebar = cb
        sig = (sym, day, ebar, dirn, bars)
        if sig in seen:
            continue
        seen.add(sig)
        named = ebar + int(round(dirn * bars))
        sigs = idx.get((sym, day), [])
        hit = [t for t in sigs if abs(t["entry_i"] - named) <= 1]
        rows.append(dict(sym=sym, day=day, card=ebar, named=named, off=dirn * bars,
                         day_silent=not sigs, hit=bool(hit),
                         grades=sorted({t["grade"] for t in hit}),
                         sgrades=sorted({str(t.get("sgrade")) for t in hit}),
                         quote=quote))
    if verbose:
        print("=" * 78)
        print("T12 SECTION 6 -- is the bar he NAMES already in the engine's stream?")
        print("=" * 78)
        print("Rows: P-ENGINE cards where he states a bar COUNT and the card's own entry")
        print("bar is recoverable.  A HIT means the engine emitted a candidate within 1")
        print("bar of the entry he named -- detection worked and the GRADE refused it.")
        print()
        live = [r for r in rows if not r["day_silent"]]
        hits = [r for r in live if r["hit"]]
        print("  resolvable named-bar rows ...... %d" % len(rows))
        print("  engine silent that whole day ... %d" % sum(1 for r in rows if r["day_silent"]))
        print("  testable ....................... %d" % len(live))
        print("  HIT  (engine had it, refused) .. %d  (%.0f%%)"
              % (len(hits), 100.0 * len(hits) / max(1, len(live))))
        print("  MISS (detector never made it) .. %d  (%.0f%%)"
              % (len(live) - len(hits),
                 100.0 * (len(live) - len(hits)) / max(1, len(live))))
        if hits:
            g, sg = Counter(), Counter()
            for r in hits:
                g.update(r["grades"])
                sg.update(r["sgrades"])
            print("  legacy grades at the named bar . %s" % dict(g))
            print("  his-ladder grades there ........ %s" % dict(sg))
        print()
        print("  HIT rate by how far away the entry he named is:")
        for lo, hi, lbl in ((1, 1, "|offset| = 1 bar "),
                            (2, 2, "|offset| = 2 bars"),
                            (3, 99, "|offset| >= 3 bars")):
            b = [r for r in live if lo <= abs(r["off"]) <= hi]
            if b:
                print("    %s  %2d testable, %2d HIT (%.0f%%)"
                      % (lbl, len(b), sum(1 for r in b if r["hit"]),
                         100.0 * sum(1 for r in b if r["hit"]) / len(b)))
        print()
        print("  %-6s %-11s %5s %5s %6s %-7s %-14s" %
              ("sym", "day", "card", "his", "off", "found", "grade/sgrade"))
        for r in sorted(rows, key=lambda x: (x["sym"], x["day"])):
            print("  %-6s %-11s %5d %5d %+6.1f %-7s %-14s | %s" %
                  (r["sym"], r["day"], r["card"], r["named"], r["off"],
                   "SILENT" if r["day_silent"] else ("HIT" if r["hit"] else "miss"),
                   ",".join(r["grades"]) + "/" + ",".join(r["sgrades"]),
                   r["quote"][:50]))
    return rows


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("corpus", "all"):
        cmd_corpus()
    if cmd in ("t1check", "all"):
        print()
        cmd_t1check()
    if cmd in ("fsm", "all"):
        print()
        lim = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        cmd_fsm(limit=lim)
    if cmd in ("arrival", "all"):
        print()
        cmd_arrival()
    if cmd in ("heldout", "all"):
        print()
        cmd_heldout()
    if cmd in ("named", "all"):
        print()
        cmd_named()


if __name__ == "__main__":
    main()
