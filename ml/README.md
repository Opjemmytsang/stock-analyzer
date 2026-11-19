# XAU AI Prediction Engine v2 — research only

This is **actual supervised machine learning**, not an LLM pretending to predict prices. It trains a HistGradientBoostingClassifier on a user-provided **real, licensed** XAU/USD 15-minute OHLC CSV.

## Run

```bash
python -m pip install -r ml/requirements.txt
python ml/train.py --csv /path/to/real_xau_15m.csv --output ml/artifacts
```

CSV columns: `time,open,high,low,close`, ISO 8601 UTC timestamps, chronological order, at least 1,500 rows. Never use fabricated/demo bars to claim prediction accuracy. Output: `model.joblib`, `report.json`, `test_predictions.csv`.

## Methodology

Predicts whether price at the close of the fourth future 15-minute bar exceeds next-bar opening price by more than an assumed spread. Features use only historical/current completed bars. Train/validation/test split 60/20/20 chronological with a five-row embargo. Features: returns, ranges, volatility, moving average gaps, and UTC time of day. Baseline is a constant prior model. Compare test Brier score to baseline and inspect accuracy, balanced accuracy, ROC AUC and log loss.

**Important:** Current output is **research-only** and not a BUY/SELL execution recommendation. A probability of 0.6 is not proof of a 60% realized win rate. No model calibration, walk-forward validation, transaction-cost-adjusted trade simulation, retraining schedule, or live data feed yet. No broker integration. Do not use real funds.

The existing `xau-lab.html` is a separate rule-based paper backtester and does **not** currently load this model. `test_predictions.csv` can be reviewed offline; model integration requires a vetted backend and data feed.

## Next gates
1. Validate data quality, session gaps, timestamps, licensing and feed consistency.
2. Add walk-forward training and out-of-sample probability calibration.
3. Evaluate BUY/SELL/WAIT thresholds with costs, slippage, financing and lot-size constraints, using a second untouched test period.
4. Run prospective paper trading and monitor calibration drift before considering any execution integration.
