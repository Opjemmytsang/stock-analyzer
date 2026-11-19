"""Fail-closed AUTO PAPER historical replay. Never sends broker orders.

Requires bid/ask CSV data, trains models only on previously known labeled bars.
This is a chronological paper *replay*, not a live market-data connection.
"""
import argparse, json
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from ml.walkforward import load, FEATURES
from ml.execution import simulate

def run(data, output, capital_hkd=500, usd_hkd=7.8, min_oz=.01,
        margin_rate=.05, funding_long=.1, funding_short=.1,
        commission_usd_per_oz_side=0, slippage_usd=.2,
        risk_fraction=.02, daily_loss_fraction=.04,
        max_drawdown_fraction=.15, threshold=.58, retrain_every=500):
    if not 0.5<threshold<1:raise ValueError("Threshold must exceed 0.5")
    if min(capital_hkd,usd_hkd,min_oz,margin_rate,risk_fraction,daily_loss_fraction,max_drawdown_fraction,retrain_every)<=0:
        raise ValueError("Invalid configuration")
    if min(funding_long,funding_short,commission_usd_per_oz_side,slippage_usd)<0:
        raise ValueError("Costs cannot be negative")
    df,valid=load(data)
    valid=valid.reset_index(drop=True)
    if len(valid)<1800:raise ValueError("Need at least 1800 valid completed training and test samples")
    # No model fitted on the replay's evaluation period. Refit on previous fully
    # labeled samples, with 5-row embargo. Each signal is at bar close.
    first=1500; model=None;last_fit=-999999;cash=float(capital_hkd)
    peak=cash;day_start=cash;day=None;trades=[];events=[];blocked=0
    last_exit_row=-1;halted=False;bars=df.to_dict("records")
    for k in range(first,len(valid)):
        signal=valid.iloc[k];i=int(signal.rowid)
        today=signal.time.date().isoformat()
        if day!=today:
            day=today;day_start=cash
        if cash<=0 or cash<=capital_hkd*(1-max_drawdown_fraction):
            halted=True
        if halted:
            events.append({"time":str(signal.time),"event":"GLOBAL_KILL_SWITCH"})
            break
        if cash<=day_start*(1-daily_loss_fraction):
            continue
        if i<=last_exit_row:continue
        if model is None or k-last_fit>=retrain_every:
            # Samples with outcome horizon reaching current signal are embargoed.
            train=valid.iloc[:k]
            train=train[train.rowid<=i-5]
            if len(train)<1200 or train.y.nunique()<2:continue
            model=HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=15,
                                                  l2_regularization=5,learning_rate=.05,
                                                  random_state=42)
            model.fit(train[FEATURES],train.y)
            last_fit=k
        probability=float(model.predict_proba(signal[FEATURES].to_frame().T)[0,1])
        side=1 if probability>=threshold else -1 if probability<=1-threshold else 0
        if not side:continue
        entry_i=i+1
        if entry_i+3>=len(bars):break
        # No trading across market closure: execution and exit bars must be contiguous.
        if any(bars[j]["time"]-bars[j-1]["time"]!=__import__("datetime").timedelta(minutes=15)
               for j in range(entry_i,entry_i+4)):
            continue
        entry=float(df.loc[entry_i,"open_ask" if side==1 else "open_bid"])
        stop_distance=max(1.5,entry*float(signal.vol24)*2)
        margin=entry*min_oz*usd_hkd*margin_rate
        loss_budget=(stop_distance+2*slippage_usd)*min_oz*usd_hkd+2*commission_usd_per_oz_side*min_oz*usd_hkd
        if margin>cash or loss_budget>cash*risk_fraction:
            blocked+=1;continue
        result=simulate(bars,side=side,entry_index=entry_i,oz=min_oz,initial_hkd=cash,
                        usd_hkd=usd_hkd,margin_rate=margin_rate,
                        stop_distance=stop_distance,
                        commission_usd_per_oz_side=commission_usd_per_oz_side,
                        slippage_usd=slippage_usd,
                        financing_long_usd_per_oz_day=funding_long,
                        financing_short_usd_per_oz_day=funding_short,
                        max_bars=4)
        cash=result["equity_hkd"];peak=max(peak,cash)
        last_exit_row=result["exit_index"]
        trades.append({"signal_time":str(signal.time),"prob_up":probability,
                       "side":"BUY" if side==1 else "SELL",**result})
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    report={"mode":"HISTORICAL_PAPER_REPLAY_ONLY","broker_orders_enabled":False,
            "initial_hkd":capital_hkd,"final_hkd":cash,"trades":len(trades),
            "blocked_risk_or_margin":blocked,"halted":halted,
            "max_drawdown_fraction":max_drawdown_fraction,
            "daily_loss_fraction":daily_loss_fraction,
            "parameters":{"min_oz":min_oz,"margin_rate":margin_rate,
                          "funding_long_usd_per_oz_day":funding_long,
                          "funding_short_usd_per_oz_day":funding_short,
                          "commission_usd_per_oz_side":commission_usd_per_oz_side,
                          "slippage_usd":slippage_usd,
                          "usd_hkd":usd_hkd,"probability_threshold":threshold},
            "limitations":["Historical replay only, not live execution or live feed",
                           "Indicative contract inputs, not verified broker pricing",
                           "OHLC stop and margin liquidation are conservative approximations",
                           "Historical funding and exchange rates assumed fixed",
                           "Model thresholds are research assumptions, not proven profitable"]}
    (output/"report.json").write_text(json.dumps(report,indent=2,default=str))
    (output/"trades.json").write_text(json.dumps(trades,indent=2,default=str))
    (output/"events.json").write_text(json.dumps(events,indent=2,default=str))
    print(json.dumps(report,indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--data",default="ml/data")
    p.add_argument("--output",default="ml/artifacts/auto_paper")
    p.add_argument("--capital-hkd",type=float,default=500)
    p.add_argument("--min-oz",type=float,default=.01)
    p.add_argument("--margin-rate",type=float,default=.05)
    p.add_argument("--funding-long",type=float,required=True)
    p.add_argument("--funding-short",type=float,required=True)
    p.add_argument("--commission-per-oz-side",type=float,default=0)
    p.add_argument("--slippage",type=float,default=.2)
    a=p.parse_args()
    run(a.data,a.output,capital_hkd=a.capital_hkd,min_oz=a.min_oz,
        margin_rate=a.margin_rate,funding_long=a.funding_long,
        funding_short=a.funding_short,
        commission_usd_per_oz_side=a.commission_per_oz_side,slippage_usd=a.slippage)
