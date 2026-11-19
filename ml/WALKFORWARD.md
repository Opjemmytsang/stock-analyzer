# XAU/USD multi-year walk-forward + HK$500 paper simulation

## Inputs
Download Dukascopy 15-minute **bid and ask** candles for 2022–2026:
```bash
bash ml/download_history.sh
python -m pip install -r ml/requirements.txt
python ml/walkforward.py --data ml/data --profile ig_international_spot_gold_1usd
```
Outputs: `ml/artifacts/walkforward/report.json`, `predictions.csv`, `paper_trades.csv`.

**This is a research implementation, not verified trading performance.** Model trains only on earlier years, with 5-bar embargo, and tests one future calendar year at a time. Thresholds 0.58/0.42 are fixed *before* seeing new data; tuning them on test years invalidates the claimed holdout. The script currently evaluates 2024 onward and treats 2026 as another fold, NOT a sealed final untouched holdout. To claim an untouched 2026 holdout, freeze all parameters using only 2022–2025 then run 2026 once.

Bid/ask historical candles provide an observed spread on entry and exit, not an assumed constant spread. Add a slippage allowance per side. Broker profiles are **indicative** and must be confirmed against the actual client entity, platform, margin tier and live spread. Missing critical contract specifications cause rejection. Funding is zero unless explicitly configured; that is not evidence that a broker charges zero. A four-bar hold is assumed to last one hour, so funding should usually be zero if no overnight cutoff is crossed, but real financing is platform-specific.

**Important risk-engine limitation:** position eligibility uses a volatility-based *risk proxy*, not an executable stop. There is no intrabar stop, stop gap/slippage, margin close-out, guaranteed-stop charge, account liquidation or full mark-to-market equity engine. Do not describe this as a full realistic broker backtest or use it for live orders.

### Data QA and audit
Verify Dukascopy feed terms, time coverage, bid/ask alignment, market closures, 15-minute timestamps, candle validity, and abnormal spreads before trusting results. GitHub Actions is not automatically enabled here; the download and training commands must be executed in a network-enabled runner. Do not commit proprietary raw market data or model artifacts without verifying redistribution rights.

### Sources
- https://www.dukascopy-node.app/config/cli
- https://help.oanda.com/bvi/zh-tw/faqs/minimum-trade-size.htm
- https://www.ig.com/en/commodities/markets-commodities/gold?siteId=igm
- https://www.ig.com/en/help-and-support/articles/692056-what-are-ig-s-commodities-metatrader-product-details
