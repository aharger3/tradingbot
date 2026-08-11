import json, collections, sys

# === SOURCE FILES AND THEIR PRIORITY (higher = wins on tier conflict) ===
SOURCES = [
    # (filename, label, priority, has_id_field)
    ("research/marks_clean.jsonl",       "marks_clean",       0,  False),
    ("research/blind_marks_all.jsonl",   "blind_marks_all",   1,  False),
    ("research/austin_marks_v2.jsonl",   "v2",                2,  False),
    ("research/austin_marks_v3.jsonl",   "v3",                3,  False),
    ("research/austin_marks_v4.jsonl",   "v4",                4,  False),
    ("research/austin_marks_v5.jsonl",   "v5",                5,  False),
    ("research/austin_marks_v6.jsonl",   "v6",                6,  False),
    ("research/mark_batch_02_grades.jsonl", "mark_batch_02",  7,  False),
    ("research/mark_batch_03_regrades.jsonl","mark_batch_03",  8,  True),
    ("research/mark_batch_04_grades.jsonl","mark_batch_04",    9,  True),
]

# The 80 batch05 rows
BATCH05_ROWS = [
 {"id":"MSTR_2026-01-27_35_48","symbol":"MSTR","day":"2026-01-27","batch":"batch05_84","entry_i":35,"austin_tier":"X","setup":"84","note":"","reclaim_i":48},
 {"id":"MSTR_2024-08-08_23_27","symbol":"MSTR","day":"2024-08-08","batch":"batch05_84","entry_i":23,"austin_tier":"A","setup":"84","note":"3 candles earlier is also an A entry, 84 percent rule same stop is ok","reclaim_i":27},
 {"id":"MSTR_2024-09-26_11_14","symbol":"MSTR","day":"2024-09-26","batch":"batch05_84","entry_i":11,"austin_tier":"X","setup":"84","note":"I dont see the stop out until later, stop out happens when candle CLOSES below the level ","reclaim_i":14},
 {"id":"MSTR_2024-04-24_33_52","symbol":"MSTR","day":"2024-04-24","batch":"batch05_84","entry_i":33,"austin_tier":"X","setup":"84","note":"candle PA ugly, would even trade this stock not apart of our top 14","reclaim_i":52},
 {"id":"MSTR_2026-04-22_79_87","symbol":"MSTR","day":"2026-04-22","batch":"batch05_84","entry_i":79,"austin_tier":"X","setup":"84","note":"","reclaim_i":87},
 {"id":"AAPL_2026-07-06_14_25","symbol":"AAPL","day":"2026-07-06","batch":"batch05_84","entry_i":14,"austin_tier":"X","setup":"84","note":"","reclaim_i":25},
 {"id":"AAPL_2024-03-28_7_61","symbol":"AAPL","day":"2024-03-28","batch":"batch05_84","entry_i":7,"austin_tier":"X","setup":"84","note":"4 candles after is an S entry OCR","reclaim_i":61},
 {"id":"AAPL_2025-01-13_18_28","symbol":"AAPL","day":"2025-01-13","batch":"batch05_84","entry_i":18,"austin_tier":"A","setup":"84","note":"3 candles earlier is an S entry, reclaim if you would've taken my s entry would've been two candles earlier, but yours is correct for the a trade","reclaim_i":28},
 {"id":"SPCX_2026-06-30_33_55","symbol":"SPCX","day":"2026-06-30","batch":"batch05_84","entry_i":33,"austin_tier":"X","setup":"84","note":"one candle earlier s entry, two candles earlier is the reclaim but could've taken off HOD earlier and stoped out on the rest and thats that. ill mark it x because your entry is wrong one candle late","reclaim_i":55},
 {"id":"MSTR_2026-05-21_70_77","symbol":"MSTR","day":"2026-05-21","batch":"batch05_84","entry_i":70,"austin_tier":"X","setup":"84","note":"","reclaim_i":77},
 {"id":"AAPL_2025-04-01_62_277","symbol":"AAPL","day":"2025-04-01","batch":"batch05_84","entry_i":62,"austin_tier":"X","setup":"84","note":"cans see what first two candles look like for the entry ","reclaim_i":277},
 {"id":"AAPL_2025-03-28_55_91","symbol":"AAPL","day":"2025-03-28","batch":"batch05_84","entry_i":55,"austin_tier":"X","setup":"84","note":"break and retest straddling the line","reclaim_i":91},
 {"id":"TSLA_2024-01-24_59_246","symbol":"TSLA","day":"2024-01-24","batch":"batch05_84","entry_i":59,"austin_tier":"X","setup":"84","note":"","reclaim_i":246},
 {"id":"PLTR_2026-05-06_15_18","symbol":"PLTR","day":"2026-05-06","batch":"batch05_84","entry_i":15,"austin_tier":"X","setup":"84","note":"","reclaim_i":18},
 {"id":"AMD_2024-10-22_26_87","symbol":"AMD","day":"2024-10-22","batch":"batch05_84","entry_i":26,"austin_tier":"X","setup":"84","note":"can't see what happens earlier","reclaim_i":87},
 {"id":"MSTR_2025-12-05_17_102","symbol":"MSTR","day":"2025-12-05","batch":"batch05_84","entry_i":17,"austin_tier":"X","setup":"84","note":"can't see what happens earlier","reclaim_i":102},
 {"id":"MSTR_2024-03-20_73_78","symbol":"MSTR","day":"2024-03-20","batch":"batch05_84","entry_i":73,"austin_tier":"X","setup":"84","note":"stop outs only happen when candle closes by the way","reclaim_i":78},
 {"id":"TSLA_2026-02-12_38_71","symbol":"TSLA","day":"2026-02-12","batch":"batch05_84","entry_i":38,"austin_tier":"X","setup":"84","note":"","reclaim_i":71},
 {"id":"INTC_2025-02-27_72_153","symbol":"INTC","day":"2025-02-27","batch":"batch05_84","entry_i":72,"austin_tier":"X","setup":"84","note":"I see an entry 14 candles later an S entry, your I would need to see what happened earlier, and I dont trade past 11 am remember","reclaim_i":153},
 {"id":"MU_2026-07-24_16_20","symbol":"MU","day":"2026-07-24","batch":"batch05_84","entry_i":16,"austin_tier":"A","setup":"84","note":"another a entry 6 candles earlier, I dont see a stop out because you would've held a OCR green candle wick","reclaim_i":20},
 {"id":"NVDA_2025-05-21_18_80","symbol":"NVDA","day":"2025-05-21","batch":"batch05_84","entry_i":18,"austin_tier":"X","setup":"84","note":"dont know what earlier candles look like","reclaim_i":80},
 {"id":"MSFT_2025-04-17_16_36","symbol":"MSFT","day":"2025-04-17","batch":"batch05_84","entry_i":16,"austin_tier":"X","setup":"84","note":"3 candles earlier is an S our entry, wouldn't need 84 percent becasse you would have gotten LOD, but your trade was wrong","reclaim_i":36},
 {"id":"MU_2026-02-09_24_36","symbol":"MU","day":"2026-02-09","batch":"batch05_84","entry_i":24,"austin_tier":"S","setup":"84","note":"first well understanding ive seen, however stop out would've been 5 candles later because thats when the close below happened","reclaim_i":36},
 {"id":"MU_2026-03-24_40_41","symbol":"MU","day":"2026-03-24","batch":"batch05_84","entry_i":40,"austin_tier":"X","setup":"84","note":"","reclaim_i":41},
 {"id":"TSLA_2025-06-12_56_61","symbol":"TSLA","day":"2025-06-12","batch":"batch05_84","entry_i":56,"austin_tier":"X","setup":"84","note":"","reclaim_i":61},
 {"id":"MSFT_2026-04-17_21_60","symbol":"MSFT","day":"2026-04-17","batch":"batch05_84","entry_i":21,"austin_tier":"X","setup":"84","note":"","reclaim_i":60},
 {"id":"PLTR_2025-12-10_45_52","symbol":"PLTR","day":"2025-12-10","batch":"batch05_84","entry_i":45,"austin_tier":"X","setup":"84","note":"perfect S entry orc BR confluence, however because the candle didn't close BELOW the stop, there is no 84 percent rule, you would've taken off at HOD and stopped out BE","reclaim_i":52},
 {"id":"MU_2025-07-17_6_8","symbol":"MU","day":"2025-07-17","batch":"batch05_84","entry_i":6,"austin_tier":"X","setup":"84","note":"your trades was wrong. S BR entry, LOD hit so no need for 84 percent rule here","reclaim_i":8},
 {"id":"INTC_2024-11-22_18_137","symbol":"INTC","day":"2024-11-22","batch":"batch05_84","entry_i":18,"austin_tier":"X","setup":"84","note":"can't see what happens before","reclaim_i":137},
 {"id":"NVDA_2026-02-05_48_52","symbol":"NVDA","day":"2026-02-05","batch":"batch05_84","entry_i":48,"austin_tier":"X","setup":"84","note":"1 candle earlier is your  A entry, stop out doesn't happen until 10:37, so dont see an 84 percent rule occur","reclaim_i":52},
 {"id":"NVDA_2025-09-29_13_23","symbol":"NVDA","day":"2025-09-29","batch":"batch05_84","entry_i":13,"austin_tier":"X","setup":"84","note":"1 candle earlier is S entry, no stop out occurs ","reclaim_i":23},
 {"id":"AAPL_2025-10-01_26_48","symbol":"AAPL","day":"2025-10-01","batch":"batch05_84","entry_i":26,"austin_tier":"X","setup":"84","note":"","reclaim_i":48},
 {"id":"AAPL_2025-06-11_20_37","symbol":"AAPL","day":"2025-06-11","batch":"batch05_84","entry_i":20,"austin_tier":"X","setup":"84","note":"","reclaim_i":37},
 {"id":"MSFT_2024-01-25_52_70","symbol":"MSFT","day":"2024-01-25","batch":"batch05_84","entry_i":52,"austin_tier":"X","setup":"84","note":"your entry never closed below the stop so no need 84 percent rule, but get a better fill not at HOD","reclaim_i":70},
 {"id":"META_2025-09-18_45_58","symbol":"META","day":"2025-09-18","batch":"batch05_84","entry_i":45,"austin_tier":"X","setup":"84","note":"1 candle earlier A entry, 6 candles earlier then that is an A entry too","reclaim_i":58},
 {"id":"AMD_2025-10-14_75_137","symbol":"AMD","day":"2025-10-14","batch":"batch05_84","entry_i":75,"austin_tier":"X","setup":"84","note":"dont know what happened before and its late in the day","reclaim_i":137},
 {"id":"AMD_2024-11-11_22_29","symbol":"AMD","day":"2024-11-11","batch":"batch05_84","entry_i":22,"austin_tier":"A","setup":"84","note":"s entry 4 candles earlier, still decent entry and reclaim would've been the same","reclaim_i":29},
 {"id":"AMD_2025-08-27_7_64","symbol":"AMD","day":"2025-08-27","batch":"batch05_84","entry_i":7,"austin_tier":"X","setup":"84","note":"dont know what happens earlier","reclaim_i":64},
 {"id":"MSTR_2026-04-02_77_91","symbol":"MSTR","day":"2026-04-02","batch":"batch05_84","entry_i":77,"austin_tier":"X","setup":"84","note":"","reclaim_i":91},
 {"id":"NVDA_2025-11-28_14_22","symbol":"NVDA","day":"2025-11-28","batch":"batch05_84","entry_i":14,"austin_tier":"S","setup":"84","note":"I would raise the stop after the second time to the higher piece of the pivot structure","reclaim_i":22},
 {"id":"AAPL_2025-03-12_329","symbol":"AAPL","day":"2025-03-12","batch":"batch05_OCR","entry_i":329,"austin_tier":"X","setup":"none","note":""},
 {"id":"AAPL_2025-03-24_244","symbol":"AAPL","day":"2025-03-24","batch":"batch05_OCR","entry_i":244,"austin_tier":"X","setup":"none","note":""},
 {"id":"AAPL_2025-06-12_162","symbol":"AAPL","day":"2025-06-12","batch":"batch05_OCR","entry_i":162,"austin_tier":"X","setup":"none","note":""},
 {"id":"AAPL_2025-09-09_123","symbol":"AAPL","day":"2025-09-09","batch":"batch05_OCR","entry_i":123,"austin_tier":"X","setup":"none","note":""},
 {"id":"AAPL_2025-12-22_290","symbol":"AAPL","day":"2025-12-22","batch":"batch05_OCR","entry_i":290,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"AMD_2025-03-28_31","symbol":"AMD","day":"2025-03-28","batch":"batch05_OCR","entry_i":31,"austin_tier":"X","setup":"none","note":"earlier entry at 9:39 as candle forming not at HOD was s trade, yours a fail"},
 {"id":"AMZN_2025-12-09_370","symbol":"AMZN","day":"2025-12-09","batch":"batch05_OCR","entry_i":370,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"GOOGL_2026-01-20_67","symbol":"GOOGL","day":"2026-01-20","batch":"batch05_OCR","entry_i":67,"austin_tier":"X","setup":"none","note":"I see way to Many break and retests with no displacement and red candles respected earlier, way too late"},
 {"id":"INTC_2024-01-23_219","symbol":"INTC","day":"2024-01-23","batch":"batch05_OCR","entry_i":219,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"META_2025-03-05_335","symbol":"META","day":"2025-03-05","batch":"batch05_OCR","entry_i":335,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"MSFT_2024-06-07_327","symbol":"MSFT","day":"2024-06-07","batch":"batch05_OCR","entry_i":327,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"MSTR_2024-10-16_188","symbol":"MSTR","day":"2024-10-16","batch":"batch05_OCR","entry_i":188,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"MSTR_2024-12-17_89","symbol":"MSTR","day":"2024-12-17","batch":"batch05_OCR","entry_i":89,"austin_tier":"X","setup":"none","note":"chop"},
 {"id":"MSTR_2026-01-13_307","symbol":"MSTR","day":"2026-01-13","batch":"batch05_OCR","entry_i":307,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"MSTR_2026-04-02_285","symbol":"MSTR","day":"2026-04-02","batch":"batch05_OCR","entry_i":285,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"MSTR_2026-06-12_362","symbol":"MSTR","day":"2026-06-12","batch":"batch05_OCR","entry_i":362,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"MU_2024-01-05_151","symbol":"MU","day":"2024-01-05","batch":"batch05_OCR","entry_i":151,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"NVDA_2024-10-31_276","symbol":"NVDA","day":"2024-10-31","batch":"batch05_OCR","entry_i":276,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"PLTR_2025-06-04_311","symbol":"PLTR","day":"2025-06-04","batch":"batch05_OCR","entry_i":311,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"SPCX_2026-06-15_226","symbol":"SPCX","day":"2026-06-15","batch":"batch05_OCR","entry_i":226,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"SPCX_2026-06-24_271","symbol":"SPCX","day":"2026-06-24","batch":"batch05_OCR","entry_i":271,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"SPCX_2026-07-01_306","symbol":"SPCX","day":"2026-07-01","batch":"batch05_OCR","entry_i":306,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"SPCX_2026-07-13_272","symbol":"SPCX","day":"2026-07-13","batch":"batch05_OCR","entry_i":272,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"SPCX_2026-08-04_107","symbol":"SPCX","day":"2026-08-04","batch":"batch05_OCR","entry_i":107,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"TSLA_2025-05-22_379","symbol":"TSLA","day":"2025-05-22","batch":"batch05_OCR","entry_i":379,"austin_tier":"X","setup":"OCR","note":""},
 {"id":"AAPL_2024-01-02_19","symbol":"AAPL","day":"2024-01-02","batch":"batch05_BR","entry_i":19,"austin_tier":"A","setup":"BR","note":"1 candle earlier is your entry"},
 {"id":"AAPL_2024-10-28_162","symbol":"AAPL","day":"2024-10-28","batch":"batch05_BR","entry_i":162,"austin_tier":"X","setup":"none","note":"tight and chop in-between channels"},
 {"id":"AAPL_2025-09-09_279","symbol":"AAPL","day":"2025-09-09","batch":"batch05_BR","entry_i":279,"austin_tier":"C","setup":"none","note":"never retested any kind of level or green candle with displacement, but below all the levels and with a good thesis I can see it but its risky"},
 {"id":"MSTR_2024-01-02_244","symbol":"MSTR","day":"2024-01-02","batch":"batch05_BR","entry_i":244,"austin_tier":"X","setup":"none","note":""},
 {"id":"MSTR_2024-08-14_66","symbol":"MSTR","day":"2024-08-14","batch":"batch05_BR","entry_i":66,"austin_tier":"X","setup":"none","note":""},
 {"id":"MSTR_2025-04-14_183","symbol":"MSTR","day":"2025-04-14","batch":"batch05_BR","entry_i":183,"austin_tier":"X","setup":"BR","note":"analyzing if this was from 9:30-11: displacement on entry but a couple candles exist from earlier in the day but they are volitale and lengthy so its not as big of a issue"},
 {"id":"MSTR_2025-12-12_11","symbol":"MSTR","day":"2025-12-12","batch":"batch05_BR","entry_i":11,"austin_tier":"A","setup":"BR","note":"5 candles earlier is your s entry"},
 {"id":"MU_2024-01-02_26","symbol":"MU","day":"2024-01-02","batch":"batch05_BR","entry_i":26,"austin_tier":"X","setup":"none","note":""},
 {"id":"NVDA_2024-01-03_98","symbol":"NVDA","day":"2024-01-03","batch":"batch05_BR","entry_i":98,"austin_tier":"A","setup":"OCR","note":"outside timeframe I trade but if it was its an A because there were nearly earlier entries"},
 {"id":"PLTR_2024-01-02_196","symbol":"PLTR","day":"2024-01-02","batch":"batch05_BR","entry_i":196,"austin_tier":"X","setup":"none","note":"wrong timeframe"},
 {"id":"SPCX_2024-01-30_7","symbol":"SPCX","day":"2024-01-30","batch":"batch05_BR","entry_i":7,"austin_tier":"A","setup":"BR","note":"hard to tell how great the candles look for the b and r"},
 {"id":"SPCX_2026-06-29_47","symbol":"SPCX","day":"2026-06-29","batch":"batch05_BR","entry_i":47,"austin_tier":"X","setup":"none","note":"overextended and no great entry presented itself"},
 {"id":"SPCX_2026-07-15_55","symbol":"SPCX","day":"2026-07-15","batch":"batch05_BR","entry_i":55,"austin_tier":"X","setup":"none","note":""},
 {"id":"SPCX_2026-07-30_215","symbol":"SPCX","day":"2026-07-30","batch":"batch05_BR","entry_i":215,"austin_tier":"X","setup":"none","note":""},
 {"id":"TSLA_2024-01-03_16","symbol":"TSLA","day":"2024-01-03","batch":"batch05_BR","entry_i":16,"austin_tier":"X","setup":"none","note":"2 or 3 candles later is a S BR for puts"},
]

# Build priority lookup: priority per batch label
SOURCE_PRIORITY = {label: pri for _, label, pri, _ in SOURCES}

# Stat tracking
stats = collections.defaultdict(lambda: {"rows_read": 0, "rows_new": 0, "tier_overwritten": 0, "notes_preserved": 0})

def make_id(row):
    """Generate id from symbol_day_entry_i, or use existing."""
    if "id" in row and row["id"]:
        return row["id"]
    return f"{row['symbol']}_{row['day']}_{row['entry_i']}"

def resolve_tier(row):
    """Get austin_tier from various field names."""
    for key in ("austin_tier", "austin_grade", "tier"):
        if key in row and row[key]:
            v = row[key]
            if v and v.strip() in ("S","A","C","X","NONE","none",""):
                return v.strip()
            return v
    return ""

def resolve_setup(row):
    """Get setup string. 'setups' is a list, 'setup' is a string."""
    if "setup" in row and row["setup"]:
        s = row["setup"]
        if s.lower() == "none":
            return ""
        return s
    if "setups" in row and row["setups"]:
        # Could be a list
        setups = row["setups"]
        if isinstance(setups, list) and setups:
            # Join multiple setups
            return ",".join(setups)
    return ""

def resolve_note(row):
    """Get note string."""
    n = row.get("note", "") or ""
    return n.strip()

def resolve_batch(row, label):
    """Determine batch name."""
    if "batch" in row and row["batch"]:
        return row["batch"]
    return label

def parse_id(rid):
    """Parse id like SYMBOL_DATE_ENTRYI or SYMBOL_DATE_ENTRYI_RECLAIMI into parts."""
    parts = rid.split("_")
    if len(parts) < 3:
        return None, None, None
    # Date is at position 1 (YYYY-MM-DD), but date has dashes so it's one part
    # Format: SYMBOL_YYYY-MM-DD_ENTRYI or SYMBOL_YYYY-MM-DD_ENTRYI_RECLAIMI or SYMBOL_YYYY-MM-DD_ENTRYI
    symbol = parts[0]
    day = parts[1]  # YYYY-MM-DD
    # Date is YYYY-MM-DD so next is entry_i
    if len(parts) >= 3:
        entry_i = int(parts[2])
    else:
        entry_i = 0
    return symbol, day, entry_i

def read_rows(filepath, label, has_id):
    """Read and normalize rows from a source file."""
    rows = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)

            # Skip rows that aren't actual marks (e.g. _no_trade markers)
            if "entry_i" not in raw and not (has_id and "id" in raw):
                continue

            stats[label]["rows_read"] += 1

            row_id = raw["id"] if has_id and "id" in raw else make_id(raw)
            # For rows without explicit symbol/day/entry_i, parse from id
            if "symbol" not in raw or "day" not in raw:
                sym, day, ei = parse_id(row_id)
                if sym:
                    raw["symbol"] = sym
                    raw["day"] = day
                    raw["entry_i"] = ei

            tier = resolve_tier(raw)
            setup = resolve_setup(raw)
            note = resolve_note(raw)
            batch = resolve_batch(raw, label)

            entry = {
                "id": row_id,
                "symbol": raw["symbol"],
                "day": raw["day"],
                "entry_i": raw["entry_i"],
                "austin_tier": tier,
                "setup": setup,
                "note": note,
                "batch": batch,
                "source_files": label,
            }

            # Preserve reclaim_i if present (84% rule marks)
            if "reclaim_i" in raw:
                entry["reclaim_i"] = raw["reclaim_i"]

            rows.append(entry)
    return rows

# Read all sources in priority order (low to high, so later overwrites earlier)
all_rows = []  # flat list of (priority, row) tuples

for filepath, label, priority, has_id in SOURCES:
    rows = read_rows(filepath, label, has_id)
    for r in rows:
        all_rows.append((priority, r))

# Add batch05 rows with highest priority (10)
for r in BATCH05_ROWS:
    stats["batch05"]["rows_read"] += 1
    entry = {
        "id": r["id"],
        "symbol": r["symbol"],
        "day": r["day"],
        "entry_i": r["entry_i"],
        "austin_tier": r["austin_tier"],
        "setup": r.get("setup", ""),
        "note": r.get("note", ""),
        "batch": r["batch"],
        "source_files": "batch05",
    }
    if "reclaim_i" in r:
        entry["reclaim_i"] = r["reclaim_i"]
    all_rows.append((10, entry))

# === MERGE ===
# Sort by priority ascending, so highest priority (latest batch) comes last
all_rows.sort(key=lambda x: x[0])

merged = {}  # id -> row

for priority, row in all_rows:
    rid = row["id"]
    if rid not in merged:
        merged[rid] = row.copy()
        merged[rid]["note"] = row["note"]  # ensure it's a string
        # Track which source contributed
        continue

    existing = merged[rid]

    # Never drop a note — concatenate with " | "
    new_note = row["note"]
    if new_note and existing.get("note", ""):
        # If the incoming note is different from existing, concatenate
        if new_note != existing["note"]:
            existing["note"] = existing["note"] + " | " + new_note
            stats[row["source_files"]]["notes_preserved"] += 1
    elif new_note and not existing.get("note", ""):
        existing["note"] = new_note
        stats[row["source_files"]]["notes_preserved"] += 1

    # Higher priority source overwrites tier and setup
    existing_tier = existing.get("austin_tier", "")
    new_tier = row.get("austin_tier", "")
    if existing_tier and existing_tier != new_tier:
        stats[row["source_files"]]["tier_overwritten"] += 1
    existing["austin_tier"] = new_tier

    # Preserve setup when any source has one (unless it's none/null)
    new_setup = row.get("setup", "")
    if new_setup and new_setup not in ("none", "null", ""):
        existing["setup"] = new_setup

    # Keep higher priority source_files (append if different)
    existing["batch"] = row["batch"]

    # Always update reclaim_i if new one exists
    if "reclaim_i" in row:
        existing["reclaim_i"] = row["reclaim_i"]

# Convert to list and write
result = list(merged.values())

# Ensure all have note as string
for r in result:
    if r.get("note") is None:
        r["note"] = ""

with open("research/austin_marks_v7.jsonl", "w") as f:
    for r in result:
        f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")

# === REPORT ===
print(f"Total unique rows: {len(result)}")
noted = [r for r in result if (r.get("note") or "").strip()]
print(f"Rows with notes: {len(noted)}")
b5 = [r for r in result if str(r.get("batch", "")).startswith("batch05")]
print(f"batch05 rows: {len(b5)}")

# Verify batch05 tiers
from collections import Counter
c = Counter(r["austin_tier"] for r in b5)
print(f"batch05 tier counts: {dict(c)}")

print()
print("=== Source stats ===")
print(f"{'Source':20s} {'Read':>6s} {'New':>6s} {'TierOver':>9s} {'NotesPres':>10s}")
print("-"*55)
for label in sorted(stats.keys()):
    s = stats[label]
    print(f"{label:20s} {s['rows_read']:>6d} {s['rows_new']:>6d} {s['tier_overwritten']:>9d} {s['notes_preserved']:>10d}")