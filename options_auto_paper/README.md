# stock-analyzer — US Options AUTO PAPER (offline prototype)

**Research only.** The system cannot trade live and does not connect to a broker, OPRA provider, or AI model. The sample CLI `--signal` is a **fixed demonstration score**, not a trained prediction. There is **no verified profitability or historical options backtest**.

## Features
- OCC-standard 100-share long Call/Put contracts; BUY TO OPEN and SELL TO CLOSE only. No short options, margin, live orders or broker credentials.
- Starting virtual cash **USD 63**. Entry at ask + slippage, liquidation at bid − slippage; configurable commissions and per-side fees.
- One contract position at a time; maximum 25% of equity spent on premium including fees; max 20% quoted spread; expiry 2–21 calendar days.
- Simulated 35% stop loss, 75% take profit, 10% daily loss halt and 30% total loss halt, and planned close before expiry. These are assumptions, **not guaranteed fills**.
- Reject invalid, stale, indicative/delayed, expired or nonstandard quotes.
- 12 deterministic unit tests.
- The CSV `feed=opra` flag is only a string claim; the code **cannot authenticate** an actual OPRA source.

## Test
From repository root:
```sh
cd options_auto_paper
python -m unittest discover -s tests -v
```

## Replay (only on properly licensed real quote input)
```sh
cd options_auto_paper
python options_paper.py --quotes /path/to/licensed_opra_quotes.csv --output paper_report.json
```

Required CSV columns: `time,symbol,bid,ask,multiplier,source,feed`; timestamps ISO8601 timezone-aware and strictly increasing. A symbol example is `SPY261127C00600000`. `feed` must be `opra` and multiplier exactly 100. Every held contract needs a fresh quote on each tick. The input must come from an authorized, quality-controlled source; **do not relabel indicative prices as executable OPRA bid/ask**.

## Not yet implemented
1. Authenticated live options chain data and OPRA entitlements; quote-source verification.
2. AI training, Greeks/IV/volatility features, walk-forward validation or automated contract selection.
3. US market session/holiday rules; quotes/depth, liquidity, open interest and survivorship checks.
4. State persistence, restart reconciliation, clock-based scheduler, outage safety, alerting and monitored production deployment.
5. Proper OCC exercise/assignment/expiry handling for forced closure when there is no valid bid.
6. Commission schedule confirmed with a specific broker for Hong Kong residents.
7. Forward paper test with real licensed data and defensible performance metrics.

The `USD 63` budget and 25% premium cap imply a maximum debit of `USD 15.75` per position including all fees. **Many real option contracts cannot qualify; zero trades is an acceptable risk outcome.**

This module is independent of the existing XAU research and OptionRadar files.
