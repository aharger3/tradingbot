# T65 — execution architecture for OMEN trading autonomously

Design document. No code in this file; nothing in the repo changes because of it.

---

## 0. The number that governs everything else in this document

As of 2026-08-24, **OMEN has no measured edge.**

`research/t60_baseline.md`, the current baseline (`30_30_30_10` ladder, ticket-17 stop
fix applied): 905 trades, mean **+0.0787R**, 95% CI **-0.0628R to +0.2202R**. The
interval straddles zero. The money gate Austin set is mean R ≥ 2.0 with every month
green; the measured number is 39x below that gate and is not statistically
distinguishable from zero. Recall against Austin's own grading is worse: the engine
finds **3 of 28 (10.7%)** of his S-days, against a 90% target. Nine of the engine's
fires land on days Austin explicitly refused (`grade: none`). This is in-sample —
the rules were fitted on the same 120 days they are scored against — so even
+0.0787R is an optimistic read, not a conservative one.

Automating execution today would automate a system that has not been shown to make
money, running on a detector that misses 9 of 10 of the trades its own author
considers clean. Every section below is written against that fact. **"When is it
safe to turn this on" is Section 4, not a footnote** — it is the section that gates
every other section from mattering. Nothing in Sections 1–3, 5, 6 is contingent on
the edge existing; they are the machine you'd want *if* it existed, or if you decide
to spend real money finding out it doesn't. Section 4 is the only section that says
whether you should.

This document assumes the answer is currently **no**, and designs the architecture
so that "no" is the honest default state of the system, not a manual discipline
Austin has to maintain by not clicking a button.

---

## 1. Phased build order

Nothing below builds broker order-routing before the paper path is airtight. That
is not caution for its own sake — it's sequencing so each phase's failure mode is
cheap to observe and cheap to fix.

| phase | ships | why this order |
|---|---|---|
| **1** | State machine + broker interface, **simulator backend only** (paper trading, code path identical to live) | Proves the state machine, the ladder, the recovery logic, and the kill switches against a backend with zero financial risk. Every bug found here is free. |
| **2** | Observability + notifications, still simulator-only | Austin needs to trust the state machine's *decisions* (what it logged, what it would have done) before it's worth watching it touch money. Phase 2 is "can Austin supervise this from his phone," proven before there's anything real to supervise. |
| **3** | Broker interface implemented against one real venue, **still gated OFF** by the Section 4 gates — orders route to the real broker's own paper/sandbox account if it has one, or stay simulator-backed if it doesn't | Validates the adapter (auth, rate limits, order acks, fill reporting) without money on the table. This is where "broker swap = config change" gets its first real test. |
| **4** | Real-money execution, small size, gated by Section 4's numeric thresholds | Only phase where OMEN risks Austin's capital. Ships only after the gates pass, and the gates are numbers, not a feeling. |

Phase 3 and Phase 4 are separated on purpose: a broker integration can be *correct*
(order gets placed, fill gets reported, position reconciles) while the *strategy*
is still unproven. Conflating "the plumbing works" with "the edge is real" is
exactly the mistake the 2026-08-23 exit-lab bug made in reverse (a modelling bug
made the strategy look better than it was); here the risk runs the other way — a
working broker adapter could tempt turning on real money before the edge is
proven. Keeping them as separate phases with separate gates removes that
temptation structurally.

Regime detection, the 84%-reentry sizing multiplier, and the futures/index venues
already exist in `live_scanner.py`/`options_sizer.py` as signal-generation logic —
this document does not redesign them. It designs the layer *underneath* signal
generation: given a signal SignalRunner already decided to fire, what actually
places, tracks, and closes an order.

---

## 2. The state machine — one trading day

### 2.1 States

```
PRE_MARKET
  → ARMED               (09:30, levels computed, scanner polling)
    → SIGNAL_PENDING     (a signal fired, sizing/order-build in progress)
      → ORDER_WORKING     (order sent, awaiting fill)
        → PARTIAL_FILL     (some but not all of tranche size filled)
        → POSITION_OPEN     (tranche 1 fully filled)
          → BREAKEVEN_ARMED   (stop moved to entry after tranche 1)
            → TRANCHE_EXIT     (2/3/4 firing at HOD/target/BE)
              → POSITION_OPEN | POSITION_FLAT
        → ORDER_CANCELLED   (unfilled at cutoff, or manually cancelled)
      → ORDER_REJECTED    (broker rejects: bad size, no buying power, symbol halt)
    → SIGNAL_SKIPPED      (grade below floor, kill switch active, entries_ok=False)
  → FORCE_FLAT           (11:00 ET, or a kill switch trips)
    → RECONCILING          (compare broker position/orders against local state)
      → DAY_CLOSED
  → HALTED               (a kill switch tripped mid-day — see Section 3)
CRASH_RECOVERY            (process restart at any point — see 2.4)
```

Every state transition is a **broker call plus a state-file write**, in that order
reversed on the way *out* of a risky state: write "attempting X" to the state file
**before** calling the broker, and write "X confirmed" only after the broker
confirms. This is what makes 2.4 (crash recovery) possible — the log always shows
either "we intended to do X and don't know if it happened" or "X happened," never
silence.

### 2.2 Happy path, one signal

1. **PRE_MARKET → ARMED** (09:30 ET): daily levels (PDH/PDL/PMH/PML/HTF bias) are
   already computed by `get_daily_context()` in `live_scanner.py` — this document
   does not change that. ARMED means the scanner is polling and entries are legal
   (`entries_ok`, `NEWS_HALT`, `ENTRY_CUTOFF` — all pre-existing gates in
   `live_scanner.py:scan_once`).
2. **ARMED → SIGNAL_PENDING**: `SignalRunner.detect_signals()` fires (unchanged).
   The state machine takes the signal dict, applies grade→size (`GRADE_SIZE_PCT`,
   `options_sizer.py`), and builds an order.
3. **SIGNAL_PENDING → ORDER_WORKING**: order sent through the broker interface
   (Section 3) for tranche 1 (30% of the sized position).
4. **ORDER_WORKING → POSITION_OPEN**: fill confirmed. Position, entry price, entry
   time, and the *intended* full ladder (all four tranche sizes and trigger
   conditions) are written to the position-state file.
5. **POSITION_OPEN → BREAKEVEN_ARMED**: immediately after tranche 1 fills, per
   Austin's rule, the stop order is moved to entry (candle-close basis, not a wick
   stop — same rule as the backtest's exit policy). This is not a discretionary
   step; it is mechanical and happens on every fill of tranche 1, no exceptions.
6. **Tranches 2/3/4** fire on their own trigger conditions (HOD for tranche 1's
   *exit* target per the rulebook's `tranche 1 at HOD`, remaining ladder per
   `30/30/30/10`). Each fill updates POSITION_OPEN's remaining size.
7. **11:00 ET**: FORCE_FLAT. Market-sell whatever remains except the 10% runner,
   which the rulebook explicitly permits to stay live past 11:00 — encode this as
   a named exception in FORCE_FLAT, not a blanket close-everything, or the ladder's
   own rule gets violated by the safety net meant to enforce a *different* rule.
8. **RECONCILING**: after every force-flat or every EOD, compare local
   position-state against the broker's actual reported positions (Section 3.4).
   Any mismatch halts new trading the next day until a human clears it (Section 3).
9. **DAY_CLOSED**.

### 2.3 Partial fills

A tranche order can fill 0%, partially, or fully. The state machine treats a
partial fill as **POSITION_OPEN at the filled size**, never as "waiting for the
rest" blocking the day. Concretely:

- If tranche 1 partially fills (e.g., broker fills 18 of 30 contracts before the
  price moves away and the rest expires/cancels per the order's time-in-force),
  the break-even-after-tranche-1 rule arms on the **filled** size, not the intended
  size. Waiting for a fill that isn't coming defeats the whole point of arming a
  protective stop early.
- The *intended* ladder percentages (30/30/30/10) are always computed against the
  **actual filled tranche-1 size**, not the original signal's sized position. If
  tranche 1 undersizes, tranches 2–4 undersize with it — the ladder is a ratio of
  what's actually on, not a fixed absolute schedule that can end up over-exiting.
- A tranche order that has not filled at all by the time the *next* tranche's
  trigger condition is met is cancelled, not stacked. Two live tranche-2 orders
  because tranche-2's trigger fired twice is a sizing bug waiting to happen.

### 2.4 Gaps through a stop

The backtest's stop model (candle-close trigger, fill at that close, floored at
−1.25R — `research/exit_lab.py`, ticket 17) assumes a fill exists at or near the
stop price. A live market gap (an overnight or fast intrabar move) can print a
close well past −1.25R with **no fill available at the modelled price** — the
option premium or the underlying can gap through the stop level entirely.

Design position: **the broker interface never promises a fill price**, only a fill
report (Section 3.1). The state machine's job on a stop trigger is to *send* an
exit order (market, not limit — a limit order at a stale stop price will not fill
through a gap) and then reconcile whatever price actually comes back. The
**−1.25R floor is a backtest modelling assumption, not a live guarantee** — this
document deliberately does not promise Austin the live loss on any trade is capped
at 1.25R. That gap between backtested floor and live reality is exactly the kind
of thing Section 5 (observability) has to surface loudly, not smooth over: a fill
materially worse than −1.25R should be a distinct, flagged event, not folded
silently into the day's P&L.

### 2.5 Process crash mid-position — the recovery path

This matters more than the happy path because a crash with an open position and no
recovery plan is the one failure mode that can turn "no measured edge" into
"unbounded, unmanaged loss." Design:

1. **Every state transition writes to a local, durable position-state file before
   and after the broker call** (2.1). On restart, the recovery routine reads this
   file first, before polling for new signals.
2. **If the last written state is "attempting X, broker call in flight"** (crash
   happened between "we're about to call the broker" and "broker confirmed"): the
   recovery routine's first action is a broker query — call `positions()` and
   `open_orders()` (Section 3.1) and reconcile against what was intended. It never
   assumes the broker call succeeded or failed; it asks the broker.
3. **If the broker reports an open position the local state doesn't know about, or
   vice versa**: this is the reconciliation-mismatch kill switch (Section 3) — it
   halts new entries and pages Austin. A crash-recovery routine that silently
   "fixes" a mismatch by trusting one side is a bug generator; a human confirms
   which side is right.
4. **If the broker confirms the position matches local state**: the recovery
   routine restores in-memory state (current ladder position, breakeven-armed
   flag, remaining tranches) from the position-state file and resumes polling.
   It does **not** re-evaluate whether the position should still be open — that
   would re-run signal logic against a position that already exists, which isn't
   what re-arming means here.
5. **A crash that happens with the position flat** (between trades, or after
   FORCE_FLAT) recovers trivially: there's nothing to reconcile, just resume
   polling if inside the window.
6. **Time-of-crash matters**: if the process is down long enough that the market
   moved meaningfully with an open position unattended (no stop-loss order resting
   at the broker — see 3.1 on why resting stops matter for exactly this reason),
   that is itself a kill-switch condition on restart, not a quiet resume.

The single design commitment underneath all of 2.4–2.5: **the broker, not the
local process, is the source of truth for what is actually open.** The local
process's job is to converge to what the broker reports, never the reverse. This
is why 3.1 requires `positions()` as a first-class call, not an afterthought.

---

## 3. The broker interface

Narrow surface, so a venue swap (shares → futures → options → a different broker
entirely) is a config change, not a rewrite — the same principle the sizing layer
(`research/sizing.py`) already applies to R→dollars. The interface hides all
venue-specific complexity (auth, rate limits, order types, contract lookup,
margin/buying-power checks) behind four calls. Nothing in the state machine
(Section 2) or the kill switches (Section 4) needs to know which venue it's
talking to.

```
place(order) -> OrderHandle
cancel(order_handle) -> bool
positions() -> list[Position]
fills(since=None) -> list[Fill]
```

Design notes on why the surface stops here, deep-module style — narrow interface,
all the mess lives inside the implementation, not leaked into the caller:

- **`place`** takes one order description (symbol/contract, direction, size, order
  type, time-in-force, and — critically — an idempotency key derived from the
  signal that generated it). It does not take a "strategy" or "ladder position" —
  the state machine decides *what* to order; the broker adapter's only job is
  placing it. The idempotency key exists specifically for crash recovery (2.5): if
  the process crashes after sending an order but before recording the ack, retrying
  `place` with the same key must not double-order. Whether the underlying broker
  API supports idempotency keys natively (some do) or the adapter has to fake it
  with a pre-flight `positions()`/`open_orders()` check is exactly the kind of
  complexity that belongs *inside* the adapter, invisible to the caller.
- **`cancel`** takes the handle `place` returned. Every broker has a different
  notion of "did the cancel land before or after a fill raced it" — the adapter
  resolves that internally and returns a simple bool; the state machine reacts to
  "cancelled" or "not cancelled (probably filled — check `fills`)," nothing finer.
- **`positions()`** is the reconciliation primitive (2.5, 3.4) — it must return
  the broker's own ground truth, not a cached mirror of what the adapter thinks it
  sent. If the adapter caches this, a crash-recovery reconcile against the cache
  proves nothing.
- **`fills(since=...)`** is how the state machine learns tranches filled, at what
  price, without polling `positions()` in a tight loop for something that's really
  an event feed. `since` takes a fill-id or timestamp cursor so a restart can ask
  "what happened while I was down" instead of re-deriving it from a position diff.

Explicitly **not** in this interface, and why leaving them out now is correct
rather than an oversight:

- **No `modify_order`.** A stop-loss move (e.g., break-even after tranche 1) is
  cancel-then-replace, not modify-in-place. Some brokers support true order
  modification, but building the state machine around cancel/replace means it
  works identically on a broker that doesn't, and cancel/replace's race condition
  (cancel confirmed, is the old stop still briefly live?) is a known, bounded
  problem rather than a broker-specific one.
- **No `get_quote` / market-data calls.** Those belong to the existing
  `TastytradeFeed`-style data layer, not the order-execution interface. Conflating
  "what is the market doing" with "what did I order" is exactly the kind of scope
  creep a narrow interface exists to prevent.
- **No venue-specific order types (bracket orders, OCO, trailing stops) in the
  interface signature.** If a venue supports a native bracket order that would
  simplify the ladder, that's an *internal* optimization the adapter can make
  (e.g., translate the state machine's cancel/replace pattern into one native
  bracket order under the hood) without changing what `place`/`cancel` look like
  from outside. Exposing venue-specific order types in the shared interface is the
  first crack that turns "config change" into "rewrite" the next time a venue is
  swapped.

Each of `place`, `cancel`, `positions`, `fills` is implemented once per venue:
**simulator** (Phase 1–2, fills instantly or with configurable slippage/latency
for realism testing), and one implementation per real broker as venues are
researched separately. The state machine, kill switches, and observability layer
are written once, against this interface, and never import a broker-specific
module directly.

---

## 4. Paper-trading first, and the gates to real money

### 4.1 Same code path, different backend

The state machine (Section 2) and every kill switch (Section 3) run **unmodified**
against the simulator broker implementation. This is the entire point of the
narrow interface in Section 3 — "paper trading" is not a separate mode with
separate logic that has to be kept in sync with the real path; it is the same
state machine pointed at `SimulatorBroker` instead of `TastytradeBroker`. Anything
that only exists in one path and not the other is a bug in the design, because it
means the thing being validated in paper mode is not the thing that runs live.

The existing `--paper` flag and `paper_trader.PaperBook` in the current codebase
mark positions to stop/target using precomputed premium estimates — that's a
reasonable Phase 1 simulator, but it currently lives as a side-channel inside
`live_scanner.py` rather than behind the broker interface. Folding it behind
`place`/`cancel`/`positions`/`fills` (rather than replacing it — the fill logic it
already has is fine) is Phase 1's actual scope of work.

### 4.2 The gates — tied to OMEN 6 and the frozen forward book

Real money is not authorized by a calendar date or a vibe. It is authorized when
**all** of the following are true, drawn directly from the OMEN 6 gates already
defined in `omen-rulebook.md` and the forward-book mechanism in
`research/omen6_forward.py`:

| gate | source | current state |
|---|---|---|
| **S-day recall ≥ 90%** | rulebook, "The gate is... S-day recall governs OMEN 6" | **10.7% (3/28)** — fails by a wide margin |
| **mean R ≥ 2.0**, 95% CI entirely above zero | rulebook money gate + "settled by default" table | **+0.0787R**, CI includes zero — fails |
| **every month green** | rulebook durability slice | **6 of 13 months negative** in the current baseline — fails |
| **the forward book has enough trades to quote a mean** | `omen6_forward.py`'s own sample-size math: N for a 95% CI half-width of 0.25R, computed from the baseline's dispersion at freeze time | book not yet frozen as of this document; `cmd_freeze` computes `trades_needed` from `baseline_sd_r` — that number is not guessed, it falls out of the script, so it is not restated here as a fixed figure |
| **the forward book's own mean clears the same mean-R ≥ 2.0 gate, in-sample and forward agreeing in direction** | `omen6_forward.py`'s stated purpose: the in-sample number has been shown to be an optimistic ceiling (break-even-stop bug, 2026-08-23) — the forward book is the check on that | not yet running |

All five gates are **AND**, not OR. The forward-book gate exists specifically
because the in-sample baseline has already been shown once to overstate the
strategy (the break-even-stop bug that made the pre-ticket-17 baseline read
+1.5R/64.8%win instead of the real +0.0787R/30.1%win) — a design that let real
money trade off the in-sample number alone would be repeating exactly the mistake
that number already made.

### 4.3 What "safe to turn on" does NOT mean

Passing the gates above authorizes moving from Phase 3 (broker adapter proven, no
real money) to Phase 4 (real money, small size). It does not authorize skipping
Phase 4's own ramp — **the size and ramp schedule for Phase 4 is Austin's call, not
this document's**, and is one of the blank thresholds in the report below. A
reasonable default shape (smallest size the broker allows, a fixed number of
trades or a fixed number of trading days before any size increase, one manual
sign-off per size increase) is a discipline device, not a technical requirement —
the technical requirement is that the code has no mechanism to increase size on
its own once real money is live. Sizing decisions live outside the kill-switch
system entirely; they are Austin's, made deliberately, not something the state
machine ramps automatically.

---

## 5. Kill switches

Every kill switch below halts **new entries immediately** on trip. What happens to
an **already-open position** differs per switch and is stated explicitly, because
"halt everything including flattening an open position" is not always the safer
choice — force-flattening into a bad print can be worse than holding to the
existing stop.

| # | switch | trips on | open positions |
|---|---|---|---|
| 1 | **Daily loss limit** | Realized + open-position mark-to-market loss for the day crosses a threshold (**Austin's number — not set here**, see report) | Existing protective stops stay resting at the broker (they were already there — see design note below). No *new* entries. Does not force-close a position that's still inside its own stop; the daily limit is a new-trade gate, not an emergency liquidation trigger by itself. |
| 2 | **Consecutive losers** | N losing trades in a row within the session (existing `consecutive_loss_halt` concept in `live_scanner.py`'s `SESSION` object — this design reuses that mechanism rather than inventing a second one) | Same as #1: stops stay resting, no new entries. |
| 3 | **Stale market data** | No new bar/quote from the feed within a configured freshness window (the existing `socket.setdefaulttimeout(30)` in `live_scanner.py` guards the *fetch* hanging; this switch guards the *data* going stale even when fetches keep succeeding — e.g., a feed that returns the same last bar repeatedly) | No new entries (a signal computed on stale data is not trustworthy). Existing resting stops are unaffected — they live at the broker, not in the local process, precisely so a data outage doesn't strand a position without protection. This is a hard requirement on the broker adapter: **every open position must have a resting stop order live at the broker at all times**, not a stop the local process "watches" and sends only when triggered. If the adapter can't guarantee a resting stop, that broker isn't viable for live execution regardless of anything else in this document. |
| 4 | **Broker API errors** | Repeated `place`/`cancel`/`positions` calls fail or the broker returns an authentication/connectivity error (threshold: **Austin's number** — how many consecutive failures, over what window) | No new entries. Existing resting stops (see #3's design note) protect open positions independent of the local process being able to talk to the broker at all — this is the entire reason resting stops are a hard requirement rather than a nice-to-have. |
| 5 | **Clock drift** | Local system clock and broker/exchange time disagree beyond a tolerance (matters because every rule in this system — force-flat at 11:00, entry cutoff, tranche timing — is time-based) | No new entries. Does not touch existing positions/stops; a clock drift doesn't change what's resting at the broker. |
| 6 | **Position/broker reconciliation mismatch** | `positions()` disagrees with local state (Section 2.5, 2.4) — a position the local process doesn't know about, a position it thinks is open that the broker shows flat, or a size mismatch | No new entries, and this one **pages Austin rather than auto-resolving** (2.5, point 3). Existing stops are untouched — the mismatch itself is a "we don't know what's true" state, and guessing which side to trust and acting on that guess is the actual danger, not the mismatch existing for the few minutes it takes Austin to look. |
| 7 | **Manual panic stop** | Austin, deliberately (Section 6 — a single reachable action from his phone) | Configurable at trip time between "halt new entries only" and "flatten everything now" — a panic stop that can *only* liquidate removes the option to just stop the bleeding on new risk while leaving a position that's fine where it is. Default posture (which one fires with no extra input) is **Austin's call**, see report. |

Design note that applies to all seven: a kill switch trips **once** and stays
tripped until a human clears it. None of them auto-resume the next session or the
next hour on their own — a daily-loss-limit trip that quietly resets at midnight
and lets the same bug fire again the next morning defeats the purpose of having it.

---

## 6. Observability

Austin is often away from the machine, so "watch the terminal" is not a viable
default — everything here is designed to be checkable from a phone, and to notify
rather than require polling.

**Logged (every event, structured, local files — the durable record):**
- Every state transition (Section 2.1) with a timestamp and the state-file
  contents at that moment — this is also the crash-recovery input, so it is not
  optional logging, it is load-bearing.
- Every `place`/`cancel` call and its broker response, and every `fills()` result,
  raw.
- Every kill-switch evaluation, not just trips — a log that only records trips
  can't answer "was switch #3 ever close to firing."
- Every reconciliation check (Section 2.5, 3.4) and its result, pass or fail.

**Notified (pushed to Austin, not something he has to go look for):** the existing
Discord webhook path (`runner.discord`) already used for signal alerts in
`live_scanner.py` is the natural channel to extend, since it's already proven to
reach him — this document does not propose adding a new notification channel
unless Austin wants one.
- Any kill switch trip (Section 5) — immediate, named, with the tripping condition
  stated in plain language ("daily loss limit hit: -$X, no new entries today").
- Every fill (tranche opens and closes), with price and size.
- The FORCE_FLAT event and its outcome.
- A reconciliation mismatch (Section 5, #6) — flagged as needing his attention
  specifically, distinct from routine fill notifications.
- End-of-day summary: trades taken, R result, ladder behavior, any switch that
  came close to tripping without tripping.

**Checkable from his phone (a status view, not a log tail):** the existing
`journal/scanner_status.json` pattern (atomic write, dashboard reads it) is the
right shape to extend — a single current-state snapshot: what state the machine
is in right now, what's open, what today's realized/unrealized R is, which kill
switches are armed vs. tripped, and time since last successful broker
`positions()` call (a cheap proxy for "is this actually still alive"). This
document does not design the phone-side viewer (web dashboard vs. a
Discord-command query vs. something else) — that's an implementation choice for
whoever builds Phase 2, not an architectural one.

---

## 7. The honest gap list

Everything this design assumes exists but currently does not, split by size.

**Small — hours to a few days each:**
- **Resting stop orders at the broker.** The current codebase (`paper_trader.py`)
  marks positions against polled bars and closes them in-process; it does not send
  a real stop order to rest at a broker. Section 5's kill-switch design *requires*
  this (a stale-feed or crashed-process kill switch is meaningless if the only
  thing protecting a position is the same process that just went stale/crashed).
  This is broker-adapter work, gated on which broker Phase 3 targets.
- **Idempotency keys on `place`.** Needed for crash-recovery correctness (2.5);
  whether the target broker supports them natively or the adapter has to
  synthesize them is a small research task once the broker is chosen.
- **The position-state file format and its read/write discipline** (2.1, 2.5) —
  straightforward to build, but must exist before Phase 1 ships, not bolted on
  after.

**Medium — a project, but bounded:**
- **A live intraday bar feed.** `TastytradeFeed`/`_yf_recent_bars` already pull
  live-ish 1-minute bars for signal generation during market hours — this exists
  and is not a gap for *detection*. What's a gap is a feed contract suited to
  *execution*: freshness guarantees the stale-data kill switch (Section 5, #3) can
  actually check against, not just "did the HTTP call succeed."
- **Order routing and the broker adapter itself** (Section 3's second
  implementation, beyond the simulator) — bounded once a venue is chosen, but not
  started, since venue research is explicitly out of scope for this document.
- **Position reconciliation logic** (2.5, 3.4, Section 5 #6) — the concept is
  designed here; the actual comparison logic (what counts as "matches," tolerance
  for in-flight fills at the reconciliation moment) is unbuilt.

**Larger — real projects in their own right, not a subtask of this one:**
- **An options chain / real option quotes.** `research/sizing.py`'s own docstring
  already states this plainly: OMEN has "1-minute underlying bars and no options
  chain," so options P&L is a delta-scaled approximation tagged `confidence: low`,
  not a measurement. Execution against real option contracts needs real strikes,
  real bid/ask, and real fills — a materially bigger build than anything in this
  document, and probably the single biggest gap standing between "the state
  machine works" and "the state machine trades the actual instrument Austin
  wants." Worth flagging that Phase 3/4 might reasonably start on **futures**
  (price-level stops, no premium/chain complexity — `options_sizer.build_futures_plan`
  already exists) rather than options, precisely because this gap is smaller there.
- **The T-15-second decision-clock ON WATCH mechanic** (`omen-rulebook.md`,
  "ON WATCH — corrected... it is a decision clock, not a price trigger"). Austin's
  stated design fires near the *end* of a forming candle, not on a price cross.
  The archive is 1-minute bars, so this isn't observable historically at all — but
  live execution, unlike backtesting, *can* watch a bar form in real time and act
  at T-15s. That's new plumbing (sub-bar polling, a genuine intrabar clock) that
  doesn't exist anywhere in the current codebase and isn't a small extension of it.
- **A production-grade version of Section 6's phone-side status viewer** — the
  data source (`scanner_status.json`-style snapshot) is a small gap; a real UI
  Austin actually opens is a project, and this document deliberately leaves its
  design open (Section 6).

---

## Thresholds left blank — need Austin's number

Marked here rather than guessed, per the house rule against inventing figures:

1. **Daily loss limit** (Section 5, #1) — dollar or R amount that halts new entries
   for the day.
2. **Consecutive-loser count** (Section 5, #2) — the current codebase has a
   `consecutive_loss_halt` concept already in play for signal generation; whether
   the *execution* kill switch reuses the same number or sets its own is Austin's
   call.
3. **Stale-data freshness window** (Section 5, #3) — how many seconds/minutes
   without a fresh bar counts as "stale" for the purpose of halting new entries.
4. **Broker-API-error threshold** (Section 5, #4) — consecutive failure count
   and/or time window before it trips.
5. **Clock-drift tolerance** (Section 5, #5) — how many seconds of disagreement
   between local and broker/exchange time is acceptable before halting.
6. **Panic stop's default behavior** (Section 5, #7) — halt-new-entries-only vs.
   flatten-everything as the no-extra-input default when Austin hits it.
7. **Phase 4 ramp schedule** (Section 4.3) — starting size, what triggers a size
   increase, whether increases are automatic-after-N-trades or require a fresh
   manual sign-off each time.
