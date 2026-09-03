# The one-click plan — and the thing that has to be true before it is worth building

*Written 2026-08-29. Every number below comes from three scripts committed beside this file,
all reading `research/bt2y_trades.json` — the same two-year book the board quotes:*
`research/g73_oneclick_delay.py`, `research/g73_oneclick_leadtime.py`,
`research/g73_oneclick_pretouch.py`. *Every web page was read 2026-08-29.*

---

## 1. The answer in one paragraph

**Your idea is right and it is legal.** A human tapping a prepared order is manual trading by
every prop firm's own wording, and one firm says so in a sentence you can hold them to.
The alert can reach your phone in seconds using something you already have installed.
And being slow costs you far less than you feared.

**But the measurement turned up something worse than slowness, and it is not about you at all.**
The $721 a day in the book is earned at a price nobody can pay. Eighty-three percent of the
book's trades enter at a price the market had already traded *earlier in that same minute,
before the signal existed*. When the book pays a price you could actually get, **$721 a day
becomes $131 a day** — and the error bar on that runs from **$3 to $280**.

So the honest order of work is: **prove the strategy survives a real fill before building
anything at all.** That is one command and about forty minutes of computer time. If it
survives, the design in §5 takes about two weeks. If it does not, no alert system on earth
fixes it.

---

## 2. Being slow costs almost nothing — because there is almost nothing left to lose

Here is the whole thing in one table. **One trade a day, 500 sessions, your real rule.**
The bracket is the honest range — resample the 500 days ten thousand times and 95% of the
answers land inside it.

| what he gets | dollars a day | honest range |
|---|---:|---|
| **The book, as published** | **$733** | $567 … $913 |
| Pay the closing price of the signal minute — instant, no human | $111 | −$2 … $234 |
| A robot buying at the next price on the tape | $131 | $3 … $280 |
| **You tap 1 minute later** | **$161** | $20 … $310 |
| **You tap 2 minutes later** | **$194** | $13 … $396 |
| **You tap 5 minutes later** | **−$81** | −$186 … $34 |
| **You tap 15 minutes later** | **−$72** | −$160 … $23 |

Read the first two rows against each other. **The drop from $733 to $111 has nothing to do
with you.** That is the price change alone, with zero delay, on the identical trades. Your
reaction time then moves it around inside a band that touches zero the whole way to five
minutes.

The rig that produced this is deliberately dumb: it changes **one** thing, the price you pay.
The stop and the target are the same, so the trade leaves at the same price on the same
minute whether you got in at 09:43 or 09:58. It also proves itself before it is allowed to
speak — fed the book's own entry price it reproduces **$733 a day and 0.582 R** against the
published **$721 and 0.58 R**. If it could not do that, none of the other rows would be
quotable.

**Three honest notes on that table.**

1. **Waiting one or two minutes looks better than acting instantly. That is not skill.**
   Waiting quietly throws away trades that already hit their stop or already ran to target —
   1,498 of 4,508 by the two-minute mark. It is a filter, not an edge, and every one of those
   rows sits inside its own error bar.
2. **A five-minute delay does destroy one-trade-a-day.** It is the only row that goes clearly
   negative. But it was already down to $131 before you were late.
3. **Every loss is still exactly $1,000 at every delay.** Entering later moves your position
   size, not your risk. Delay makes winners smaller; it never makes losers bigger.

### The book's own data says the same thing, with no model in between

Split all 4,508 traded rows by how the book got its fill. This is straight arithmetic on the
book, not my rig:

| how the book got in | trades | average result |
|---|---:|---:|
| At the level — an order already resting there | **3,748 (83%)** | **+0.71 R** |
| At the minute's closing price — what you would pay | 760 (17%) | **−0.02 R** |

**Every dollar of the edge is in the first row.** On the trades where the book actually paid a
price you could have paid, it loses money. That is the finding, and it was sitting in the book
the whole time.

---

## 3. Why "just leave the orders sitting there overnight" does not work

The obvious fix is: if the winning fill is a resting order, park the orders before the bell and
go to work. Four of your six levels — yesterday's high and low, the premarket high and low —
are known before 09:30, and they carry **53% of the one-trade-a-day money** (287 of 499 days,
$191,287).

**It cannot be done, and the reason is simple.** A buy order resting at a level *below* the
current price fills the instant you place it. The setup needs price to break *through* the
level, leave it, and come back — and only then is a resting order the right instrument. I
counted how often each trade's level had already been touched before the engine fired:

| touches before the signal | days | share |
|---|---:|---:|
| 0 | **0** | 0% |
| 1 | 3 | 0.6% |
| 2 | 50 | 10% |
| 3 | 104 | 21% |
| 4 | 133 | 27% |
| 5 or more | 209 | **42%** |

**Not one of 499 trades had a clean level.** Every single one had been touched at least once
first — usually four or more times. An order parked at 09:25 is gone long before the trade you
wanted.

So the order can only go in **after** the break, in the window while price is coming back. How
long is that window?

| warning you get | 1 day in 10 | typical | 9 days in 10 |
|---|---:|---:|---:|
| From the first touch of the level | 5 min | **8 min** | 14 min |
| From the last touch before the entry | 1 min | **2 min** | 3 min |

**Typically two minutes, at best about eight.** Two minutes is exactly where the table in §2
still shows a small positive number and exactly where the error bar still contains zero. That
is the whole design constraint, in one number.

And the clock is kinder than expected: **490 of your 499 trades happen between 09:30 and
09:59.** Nine days in two years needed you after 10:00. It is a half-hour problem, not a
ninety-minute one.

---

## 4. What actually exists for a "one-click order"

**Short version: no US broker publishes anything like a one-click bet link, and nobody is
going to build you one.** A bet link is a marketing URL. A broker order is a regulated
instruction, so the tap has to happen inside something that holds your login. That means a
small page you own, not a link you click into someone else's app. I checked tastytrade,
Robinhood, Interactive Brokers and the Trade The Pool platform; none of them documents a
URL that opens a pre-filled order ticket.

**But the thing you actually want does exist, and it is called a dry run.**

| route | can it stage an order for a human to confirm? | is a human-confirmed order allowed? |
|---|---|---|
| **Your own tastytrade account** | **Yes.** Build the order, send it as a *dry run* — the broker validates it, returns the buying-power effect and any rejection, and **does not place it**. You show that on screen, he taps, you resend with the dry-run flag off. That is literally an order confirmation screen. | **Yes, in writing.** Their API terms permit *"algorithmic trading systems"* on your own account — and no prop rule applies, because there is no prop firm and no payout to void. |
| **Take Profit Trader** (futures) | Yes — nothing stops it | **Yes, and this is the cleanest sentence on the board:** *"No Trading bots/Algos — We do not allow any automated or bot trading of any kind. **All trades must be manually executed by the trader.**"* You tapping Confirm **is** manual execution. Their own rule authorises the design. *(Their help site refuses automated reading today — this is the quote `g72_instrument_decision.md` read off the page directly on 2026-08-29, and independent write-ups of their policy say the same thing. Strongly established, not re-confirmed first-hand today.)* |
| **Trade The Pool** (the g72 pick) | Not the sanctioned path | **Their contract still says two opposite things, and the newer detail makes it worse for you.** Program Terms: *"Support for automated trading, including the specific integration with SignalStack, is currently in a beta state"* and *"the trader is responsible for all trades conducted on the account regardless of whether manually or automatically created."* Terms & Conditions §11: *"The User may not use any custom, algorithmic, or other automated trading software… to execute trades."* And the permission they do give is **narrow: automation is allowed only through SignalStack** — which fires the order *without* your tap. The one route they bless is the one that removes the human. |
| **Apex Trader Funding** | Yes in principle | Their ban names *"any form of AI, Autobots, algorithms, fully automated trading systems, and HFTs."* A human confirming each order is none of those — but they publish no sentence saying so, their site blocks automated reading, and the penalty is *"forfeiture of all funds."* **Do not build against silence.** |
| **Topstep** | Yes | Bots are fine in the Combine, banned in the Live Funded Account. Same problem: the ban lands exactly where the real money is. |
| Robinhood / IBKR | No public deep link either | IBKR has an API; Robinhood has no supported one. Neither adds anything tastytrade does not. |

**The line every firm draws is the same line, and it is the one you spotted:** an order a human
confirms is manual; an order placed without a human is automated. Take Profit Trader wrote it
down. tastytrade does not care either way, because it is your money.

**One warning about Trade The Pool specifically.** The §7 email in `g72_instrument_decision.md`
is still unsent and still gates that whole route. Add a second question to it: *"Is a system
that sends me an alert, which I then confirm by hand on a web page that places the order
through your platform, permitted under section 11?"* If the answer is no, the entire
one-click design only works on your own tastytrade account.

---

## 5. The design, if the fill test in §6 passes

Three parts. Nothing here is a robot at any point.

**Part one — the alert, and it is free.** You already have Discord on your phone and the repo
already posts every signal to it with retries and a failure log (`discord_bot.py`). It
already carries symbol, direction, entry, stop, target, size and the setup name. No SMS
service, no Twilio bill, nothing new to sign up for. **The one thing missing is *when* it
fires.** Today the alert goes out at the same moment the trade is booked — zero warning. What
has to be built is an **arming alert**: the engine already knows when price has broken a level
and left it, minutes before the entry. It just never tells anybody. That is the change.

**Part two — the tap.** The alert carries a link to a small page you own. The page shows the
prepared order in large type — *NVDA, long, buy at 128.00, stop 127.89, target 128.22, size
X, break-and-retest of the premarket high* — and one button. Tapping it runs the tastytrade
dry run, shows what it will cost in buying power, and asks once more. Second tap places a
bracket: entry, stop and target in one order, so the trade manages itself after that. **Two
taps, about eight seconds, and you never open a chart.**

**Part three — the fallback, and it is deliberately boring.** If you cannot look at your
phone, **nothing happens and the day is skipped.** The fallback must not be "let it fire on
its own", because that is the exact line that voids a prop payout and it is also the line
between your idea and a robot. The measurement backs this up: a missed day costs you one
average day — about $700 in the book, about $200 at a fill you can get — never a disaster.

**What it costs and how long.**

| piece | build time | running cost |
|---|---|---|
| Arming alert into the existing Discord bot | ~2 days | $0 |
| Confirm page + tastytrade order path | ~1 week | $0 (API is free with the account) |
| Sandbox provisioning and shape-checking | ~2 days | $0 |
| **Total** | **~2 weeks** | **$0/month** |

The order path is the real work and the honest risk: `broker/tastytrade.py` is locked to the
sandbox, no sandbox account has been created, and **it has never made a single network call.**
Whatever route you pick, placing an order is unwritten code.

---

## 6. What has to happen first, and it is not a build

**Rebuild the two-year book paying a price you could actually get.** The switch already
exists — nothing new to write:

```
STOP_FILL_ORDER=market_on_close python backtest_2y.py --out research/bt2y_honest_fill.json
python research/g72_after_headline.py --book research/bt2y_honest_fill.json
```

That makes every entry book at the minute's closing price instead of the back-dated one.
About forty minutes of computer time, no decision from you.

My rig estimates the answer at **$111 a day** and I want to be careful about why that is an
estimate and not the answer: my rig re-prices the *same* trades, whereas a real rebuild also
changes *which* trades fire, because the entry price feeds the minimum-risk check and the
grade. The real number could land either side. **It is the most important unmeasured number
in this project right now**, and it is bigger than the choice of broker, the choice of prop
firm, and the whole one-click build put together.

**Then the decision is arithmetic.** If the honest-fill book still clears a few hundred
dollars a day, build §5 — two minutes of warning is enough and your idea works. If it is near
zero, then manual execution is not what is broken. The fill is. And no amount of clicking
fixes a fill.

---

## 7. What only you can decide

1. **Say yes to running the honest-fill rebuild.** Forty minutes of computer time. Nothing
   else on this page should be built until it comes back.
2. **Add the section-11 question to the Trade The Pool email** that is still unsent from
   `g72_instrument_decision.md`: does a human confirming an alert on a web page count as
   manual under section 11?
3. **Confirm the fallback is acceptable**: on a day you cannot reach your phone, the day is
   skipped. No automatic firing, ever. That is what keeps this legal everywhere and it is
   also what stops it becoming the thing every firm bans.

---

*Sources read 2026-08-29:*
[tastytrade Open API](https://tastytrade.com/api/) ·
[tastytrade order submission / dry run](https://developer.tastytrade.com/order-submission/) ·
[tastytrade API terms (PDF)](https://assets.tastyworks.com/production/documents/USA/open_api_terms_and_conditions.pdf) ·
[Take Profit Trader PRO Account Rules](https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15171769361053-PRO-Account-Rules) ·
[Trade The Pool Program Terms](https://tradethepool.com/program-terms/) ·
[Trade The Pool Terms & Conditions](https://tradethepool.com/terms-and-conditions/) ·
[Topstep Live Funded Account Parameters](https://help.topstep.com/en/articles/10657969-live-funded-account-parameters) ·
[IBKR Mobile](https://www.interactivebrokers.com/en/trading/ibkr-mobile.php)
