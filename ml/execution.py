"""Conservative OHLC bid/ask paper execution. No real broker connectivity."""
from datetime import timedelta
import math

def simulate(bars, *, side, entry_index, oz, initial_hkd, usd_hkd, margin_rate,
             stop_distance, commission_usd_per_oz_side, slippage_usd,
             financing_long_usd_per_oz_day, financing_short_usd_per_oz_day,
             rollover_hour_utc=22, rollover_weekday_multiplier=None,
             margin_closeout_fraction=0.5, max_bars=4):
    """Bars: chronological list of dicts with time (UTC pandas Timestamp), bid/ask OHLC.
    Stop executes at adverse executable quote, with gap and slippage. Margin closeout
    uses adverse intrabar mark, before stop if both touched (conservative).
    Returns closed-trade record, or raises for invalid/unsupported terms.
    """
    if side not in (1,-1) or oz<=0 or initial_hkd<=0 or usd_hkd<=0 or margin_rate<=0:
        raise ValueError("Invalid trade or margin parameters")
    if not 0<margin_closeout_fraction<=1 or max_bars<1:
        raise ValueError("Invalid closeout or holding period")
    if min(stop_distance,commission_usd_per_oz_side,slippage_usd,
           financing_long_usd_per_oz_day,financing_short_usd_per_oz_day)<0:
        raise ValueError("Costs and stop distance must be nonnegative")
    if not 0<=rollover_hour_utc<=23:raise ValueError("Invalid rollover hour")
    mult=rollover_weekday_multiplier or {0:1,1:1,2:3,3:1,4:1,5:1,6:1}
    if set(mult)!=set(range(7)) or any(v<0 for v in mult.values()):
        raise ValueError("Invalid rollover schedule")
    if entry_index<0 or entry_index>=len(bars):raise ValueError("Invalid entry index")
    bar=bars[entry_index]
    def q(x,k):return float(x[k])
    entry_quote=q(bar,"open_ask" if side==1 else "open_bid")
    entry=entry_quote+side*slippage_usd
    stop=entry-side*stop_distance
    entry_fee=commission_usd_per_oz_side*oz*usd_hkd
    cash=initial_hkd-entry_fee
    margin=entry_quote*oz*usd_hkd*margin_rate
    if cash<margin:raise ValueError("Insufficient initial margin")
    funding=0.0;rollovers=0;peak=initial_hkd;maxdd=0.0
    prev_time=bar["time"]
    def floating(price):return (price-entry)*side*oz*usd_hkd
    def closeout_equity(price):return cash+floating(price)-commission_usd_per_oz_side*oz*usd_hkd
    def check_rollover(start,end):
        nonlocal funding,rollovers,cash
        # Charge each rollover crossing, with explicit weekday multipliers.
        day=start.normalize()
        while day<=end.normalize():
            tick=day+timedelta(hours=rollover_hour_utc)
            if start<tick<=end:
                rate=financing_long_usd_per_oz_day if side==1 else financing_short_usd_per_oz_day
                cost=rate*oz*usd_hkd*mult[tick.weekday()]
                funding+=cost;cash-=cost;rollovers+=1
            day+=timedelta(days=1)
    for i in range(entry_index,min(len(bars),entry_index+max_bars)):
        candle=bars[i]
        time=candle["time"]
        if i>entry_index:check_rollover(prev_time,time)
        prev_time=time
        op=q(candle,"open_bid" if side==1 else "open_ask")
        lo=q(candle,"low_bid" if side==1 else "high_ask")
        cl=q(candle,"close_bid" if side==1 else "close_ask")
        # Open is immediately observable, including adverse gaps. Evaluate closeout
        # first, then protective stop, and assume worst-case closeout when ambiguous.
        exit_quote=None;reason=None
        def breached(price):
            eq=closeout_equity(price)
            return eq<=margin*margin_closeout_fraction or eq<=0
        if breached(op):
            exit_quote=op;reason="margin_closeout_gap"
        elif (side==1 and op<=stop) or (side==-1 and op>=stop):
            exit_quote=op;reason="stop_gap"
        elif breached(lo):
            exit_quote=lo;reason="margin_closeout_intrabar"
        elif (side==1 and lo<=stop) or (side==-1 and lo>=stop):
            exit_quote=stop;reason="stop_intrabar"
        elif i==min(len(bars),entry_index+max_bars)-1:
            exit_quote=cl;reason="time_exit"
        if exit_quote is not None:
            exit_price=exit_quote-side*slippage_usd
            exit_fee=commission_usd_per_oz_side*oz*usd_hkd
            pnl=(exit_price-entry)*side*oz*usd_hkd-entry_fee-exit_fee-funding
            end_equity=initial_hkd+pnl
            # Negative balance remains visible; never silently floor losses to zero.
            maxdd=max(maxdd,(peak-end_equity)/peak)
            return {"reason":reason,"entry":entry,"exit":exit_price,"stop":stop,
                    "entry_index":entry_index,"exit_index":i,"bars_held":i-entry_index+1,
                    "financing_hkd":funding,"rollovers":rollovers,
                    "commission_hkd":entry_fee+exit_fee,"slippage_usd_per_side":slippage_usd,
                    "pnl_hkd":pnl,"equity_hkd":end_equity,"max_drawdown":maxdd,
                    "margin_hkd":margin}
        marked=closeout_equity(cl)
        maxdd=max(maxdd,(peak-marked)/peak)
    raise RuntimeError("No bars to exit position")
