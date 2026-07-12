/* Mine trade-review judgments from Discord data using parallel agents */

/* Phase 1: Find every message that judges a specific trade good/bad with reason */
/* Then extract structured: ticker, direction, verdict, reason, PnL */
/* Output: flat array of structured trade-review records */

const DATA = JSON.parse(await readFile(
  'C:\\Users\\aharg\\tradingbot\\_trade_reviews_mined.json', 'utf-8'));

/* We have 1515 candidate messages. Group by channel, send batches of ~100 to agents. */
const BATCH_SIZE = 80;
const allMessages = [];
for (const ch of DATA.channels) {
  for (const m of ch.messages) {
    allMessages.push({ ...m, channel: ch.channel });
  }
}

log(`Processing ${allMessages.length} candidate messages across ${DATA.channels.length} channels...`);

const EXTRACT_SCHEMA = {
  type: 'object',
  properties: {
    tradeReviews: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          ticker:       { type: 'string', description: 'Ticker symbol (e.g. AAPL, ES, NQ). "N/A" if none.' },
          direction:    { type: 'string', enum: ['long', 'short', 'unknown'] },
          verdict:      { type: 'string', enum: ['good', 'bad', 'mixed'] },
          reason:       { type: 'string', description: 'WHY it was good/bad. Be specific: entry quality, exit timing, risk mgmt, discipline, setup validity, market conditions.' },
          pnl:          { type: 'string', description: 'Dollar PnL if mentioned, e.g. "+$500". "N/A" if not.' },
          lesson:       { type: 'string', description: 'Explicit lesson or takeaway the poster states. "N/A" if none.' },
          author:       { type: 'string' },
          timestamp:    { type: 'string' },
          channel:      { type: 'string' },
          content:      { type: 'string', description: 'Original message excerpt (first 500 chars)' },
        },
        required: ['ticker', 'direction', 'verdict', 'reason', 'pnl', 'lesson'],
      },
    },
  },
};

const EXTRACT_PROMPT = `You are mining Discord chat logs for trade-review judgments.

Read each message. Extract ONLY messages where a SPECIFIC trade is being JUDGED as good or bad WITH a reason why.

RULES:
- SKIP generic trading advice ("always cut losses", "trading is probability")
- SKIP general discussion of strategy without a specific trade
- SKIP questions asking for advice on future trades
- SKIP messages that only contain trade alerts without judgment
- EXTRACT only messages with: specific ticker + direction (long/short) + verdict (good/bad/mixed) + reason WHY

For each trade review found, populate:
- ticker: the instrument traded
- direction: long/short
- verdict: good / bad / mixed
- reason: WHY it worked or didn't (specifics — entry timing, exit discipline, missed setup, risk management failure, etc.)
- pnl: "$X" or "N/A"
- lesson: the explicit lesson/reflection, or "N/A"
- author, timestamp, channel, content (first 500 chars)

Return an empty array if NONE of the messages qualify. Do NOT force matches. Be strict.`;

/* Batch creation */
const batches = [];
for (let i = 0; i < allMessages.length; i += BATCH_SIZE) {
  batches.push(allMessages.slice(i, i + BATCH_SIZE));
}
log(`Split into ${batches.length} batches of ~${BATCH_SIZE}`);

phase('Extract trade reviews');
const batchPrompts = batches.map((batch, idx) => {
  const msgBlock = batch.map((m, j) =>
    `--- MSG ${idx * BATCH_SIZE + j + 1} ---
Author: ${m.author}
Channel: ${m.channel}
Timestamp: ${m.timestamp || m.ts}
Content: ${(m.content || '').slice(0, 600)}
`).join('\n');

  return `${EXTRACT_PROMPT}\n\nMESSAGES:\n${msgBlock}`;
});

const results = await parallel(
  batchPrompts.map((prompt, i) => () =>
    agent(prompt, {
      label: `batch-${i + 1}/${batches.length}`,
      schema: EXTRACT_SCHEMA,
    })
  )
);

/* Aggregate */
let allReviews = [];
for (const r of results) {
  if (r && r.tradeReviews) {
    allReviews = allReviews.concat(r.tradeReviews);
  }
}

log(`\n=== EXTRACTION COMPLETE ===`);
log(`Total structured trade reviews: ${allReviews.length}`);

/* Summary stats */
const good = allReviews.filter(r => r.verdict === 'good');
const bad = allReviews.filter(r => r.verdict === 'bad');
const mixed = allReviews.filter(r => r.verdict === 'mixed');
log(`Good: ${good.length}, Bad: ${bad.length}, Mixed: ${mixed.length}`);

/* By ticker */
const byTicker = {};
for (const r of allReviews) {
  const t = r.ticker.toUpperCase();
  if (!byTicker[t]) byTicker[t] = { good: 0, bad: 0, mixed: 0, reviews: [] };
  byTicker[t][r.verdict]++;
  byTicker[t].reviews.push(r);
}

log('\nTop tickers by review count:');
const tickerList = Object.entries(byTicker)
  .filter(([k]) => k !== 'N/A')
  .sort((a, b) => (b[1].good + b[1].bad + b[1].mixed) - (a[1].good + a[1].bad + a[1].mixed))
  .slice(0, 20);
for (const [t, v] of tickerList) {
  log(`  ${t}: ${v.good}G / ${v.bad}B / ${v.mixed}M total=${v.good + v.bad + v.mixed}`);
}

return {
  total: allReviews.length,
  byVerdict: { good: good.length, bad: bad.length, mixed: mixed.length },
  tickers: Object.fromEntries(tickerList.map(([t, v]) => [t, { good: v.good, bad: v.bad, mixed: v.mixed, count: v.good + v.bad + v.mixed }])),
  reviews: allReviews,
};
