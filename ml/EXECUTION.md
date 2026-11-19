# Execution risk engine v2
The research engine in `ml/execution.py` is now wired into `ml/walkforward.py`.

- **Stop-loss:** executed at bid for long / ask for short; each 15-minute candle checks open gaps and adverse high/low. Stops can fill worse than the stop price after a gap. Configurable adverse slippage is applied on entry and exit.
- **Margin closeout:** marks positions at adverse executable intrabar quotes, checks remaining equity against a configurable fraction of opening required margin (default 50%) and zero equity. Margin liquidation takes priority over stop in ambiguous OHLC bars. This is a conservative approximation, not a broker-specific liquidation algorithm.
- **Financing:** explicit long/short daily USD-per-ounce inputs in the engine; applies charges when crossing a UTC rollover hour, with a configurable weekday multiplier (example Wednesday triple). Negative balances are retained. Broker policy, triple-day, DST and funding rate changes MUST be verified.
- **Fees:** entry/exit commission, bid/ask spread and slippage included.
- **Tests:** `python -m unittest ml.test_execution -v` includes gap stop, intrabar stop, margin closeout, short ask stop, commissions/slippage, funding and triple rollover.

## Running
```bash
python -m pip install -r ml/requirements.txt
python -m unittest ml.test_execution -v
bash ml/download_history.sh
python ml/walkforward.py --data ml/data --financing-usd-per-oz-day 0.10
```
The 0.10 USD/oz/day value above is **illustrative only**, not a verified broker charge. The CLI deliberately refuses to run without explicit funding terms rather than assume financing is free.

## Important limitations
- Candle OHLC does not reveal exact intrabar event ordering; the engine takes conservative priority when margin and stop are both touched.
- The engine currently applies the same CLI funding rate to both directions, despite the standalone engine supporting distinct rates. A real broker may pay or charge different amounts on longs/shorts, and funding may be a percentage of notional rather than a fixed amount.
- It uses a **fixed initial margin** threshold rather than broker-specific dynamic margin tiers or intraday liquidation practices.
- Funding is charged at a single UTC rollover hour and fixed weekday schedule; this is **not sufficient** for a claim of complete real-broker financing costs until actual terms, DST and historical rates are verified.
- No intra-candle price path, margin call notification, order-book liquidity, market closures, guaranteed-stop premiums, financing history, currency conversion fees or variable contract rules.
- Neither live trading nor historical broker equivalence is established; do not use real money based on this model.
