# AUTO PAPER: safe first stage

**Status:** historical automatic paper replay only. This does NOT connect to live XAU quotes, a broker, MetaTrader 5 or an exchange, and cannot place live orders. No API credentials are used or needed.

## Run

```bash
python -m pip install -r ml/requirements.txt
python -m unittest ml.test_execution -v
bash ml/download_history.sh
python -m ml.auto_paper --data ml/data --capital-hkd 500 \
  --funding-long 0.10 --funding-short 0.10 \
  --min-oz 0.01 --margin-rate 0.05
```

**All values above for minimum size, margin and financing are placeholders**, NOT a quotation from a verified Hong Kong broker. The program requires explicit long and short financing assumptions and refuses to start without them. Outputs `ml/artifacts/auto_paper/report.json`, `trades.json`, and `events.json`.

The replay runs a rolling supervised HistGradientBoosting model. Each new decision only trains on prior historical labeled candles with a five-bar embargo. A signal is made on candle close; hypothetical entry is next candle open. Each paper trade checks stop, margin closeout and funding through `ml.execution`. No overlapping trades, 2% estimated risk per trade, 4% daily realized loss pause, 15% starting-equity drawdown kill switch. Daily pause does not retroactively cancel an existing position; it stops subsequent entries.

**Known limitations:**
- It is a backtest-style replay, not persistent 24/7 forward paper trading. A real 15-minute feed, persistent state, reconciliation and supervised scheduler are required next.
- It is not proof of a profitable strategy or broker-accurate execution.
- Funding, margin, leverage, spread, FX and minimum size must be verified against the actual Hong Kong resident account. OHLC cannot resolve exact intrabar sequence.
- GitHub Actions must run successfully and artifacts must be inspected before calling it validated.
- The code cannot and must not send live orders. Keep any future live adapter behind an explicit opt-in and independent risk validation.

## Broker investigation (official)
- OANDA Global Markets lists Hong Kong as an eligible application jurisdiction and has MT5 demo accounts, 0.001 minimum gold CFD lot and no minimum standard account deposit.
- **OANDA Global Markets explicitly does not provide API token access for live OR demo accounts.** Do not reuse OANDA US v20 API instructions for Hong Kong.
- MT5 Expert Advisors are a potential automation path, subject to broker-specific permissions and verified contract specification.
- IBKR disallows Hong Kong residents from gold CFDs and its London XAUUSD product.

Official:
https://help.oanda.com/bvi/en/faqs/eligible-ogm-countries-bvi.htm
https://help.oanda.com/bvi/en/faqs/minimum-trade-size.htm
https://help.oanda.com/bvi/en/faqs/oanda-log-in-support-bvi.htm
https://www.interactivebrokers.com/support/faq/content/trade-cfds-through-interactive-brokers-35791967
