"""Walk-forward XAU model + conservative paper execution, research only.
Input: pairs of Dukascopy CSVs with timestamp,open,high,low,close.
Use actual bid/ask opens and closes; stops/targets evaluated on bid/ask OHLC.
"""
import argparse, glob, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, brier_score_loss

HORIZON=4
FEATURES=["r1","r4","r8","vol8","vol24","range","body","ma8","ma24","hour_sin","hour_cos"]
def load(directory):
    pairs=[]
    for bp in sorted(glob.glob(str(Path(directory)/"xauusd_m15_bid_*.csv"))):
        apath=bp.replace("_bid_","_ask_")
        if not Path(apath).exists():raise ValueError("Missing ask pair: "+apath)
        def read(p,side):
            df=pd.read_csv(p)
            df.columns=[c.strip().lower() for c in df.columns]
            if "timestamp" not in df and "time" in df:df=df.rename(columns={"time":"timestamp"})
            if "timestamp" not in df:raise ValueError("Missing timestamp in "+p)
            t=pd.to_numeric(df.timestamp,errors="coerce")
            df["time"]=pd.to_datetime(t,unit="ms",utc=True) if t.notna().all() else pd.to_datetime(df.timestamp,utc=True,errors="raise")
            df=df[["time","open","high","low","close"]].copy()
            for c in ["open","high","low","close"]:df[c]=pd.to_numeric(df[c],errors="raise")
            if df.time.duplicated().any() or not df.time.is_monotonic_increasing:raise ValueError("Duplicate or unordered timestamps: "+p)
            return df.rename(columns={c:c+"_"+side for c in ["open","high","low","close"]})
        b=read(bp,"bid");a=read(apath,"ask")
        merged=b.merge(a,on="time",how="inner",validate="one_to_one")
        if len(merged)<len(b)*.95 or len(merged)<len(a)*.95:raise ValueError("Bid/ask timestamp coverage below 95%: "+bp)
        pairs.append(merged)
    if not pairs:raise ValueError("No bid/ask CSV pairs in "+directory)
    df=pd.concat(pairs,ignore_index=True).sort_values("time")
    if df.time.duplicated().any():raise ValueError("Overlapping input years")
    for side in ["bid","ask"]:
        o,h,l,c=[df[f"{x}_{side}"] for x in ["open","high","low","close"]]
        if ((h<o)|(h<c)|(l>o)|(l>c)|(l<=0)|~np.isfinite(c)).any():raise ValueError("Invalid OHLC: "+side)
    if (df.open_ask<df.open_bid).any() or (df.close_ask<df.close_bid).any():raise ValueError("Negative bid/ask spread")
    df["gap"]=df.time.diff().ne(pd.Timedelta(minutes=15)).cumsum()
    mid=(df.close_bid+df.close_ask)/2
    df["r1"]=mid.pct_change();df["r4"]=mid.pct_change(4);df["r8"]=mid.pct_change(8)
    df["vol8"]=df.r1.rolling(8).std();df["vol24"]=df.r1.rolling(24).std()
    df["range"]=(df.high_bid-df.low_bid)/mid
    df["body"]=(df.close_bid-df.open_bid)/df.open_bid
    df["ma8"]=mid/mid.rolling(8).mean()-1;df["ma24"]=mid/mid.rolling(24).mean()-1
    hour=df.time.dt.hour+df.time.dt.minute/60
    df["hour_sin"]=np.sin(2*np.pi*hour/24);df["hour_cos"]=np.cos(2*np.pi*hour/24)
    # Classification uses NEXT OPEN -> fourth future CLOSE, not same-bar future information.
    df["y"]=((df.close_bid.shift(-4)+df.close_ask.shift(-4))/2 > (df.open_bid.shift(-1)+df.open_ask.shift(-1))/2).astype(int)
    df["rowid"]=np.arange(len(df))
    valid=(df.gap==df.gap.shift(24))&(df.gap==df.gap.shift(-4))&df[FEATURES].notna().all(axis=1)&df.time.lt(pd.Timestamp("2027-01-01",tz="UTC"))
    return df,df.loc[valid].copy()
def main():
    p=argparse.ArgumentParser();p.add_argument("--data",default="ml/data");p.add_argument("--output",default="ml/artifacts/walkforward")
    p.add_argument("--broker",default="ml/broker_profiles.json");p.add_argument("--profile",default="ig_international_spot_gold_1usd")
    p.add_argument("--capital-hkd",type=float,default=500);p.add_argument("--usd-hkd",type=float,default=7.8)
    p.add_argument("--risk",type=float,default=.02);p.add_argument("--slippage-usd",type=float,default=.2)
    p.add_argument("--financing-usd-per-oz-day",type=float,default=None)
    args=p.parse_args()
    if min(args.capital_hkd,args.usd_hkd,args.risk)<=0 or args.slippage_usd<0:raise ValueError("Invalid simulation parameters")
    profiles=json.loads(Path(args.broker).read_text())["profiles"];profile=next(x for x in profiles if x["id"]==args.profile)
    required=["min_contracts","contract_oz","margin_rate","commission_usd_per_contract_side"]
    if any(profile.get(k) is None for k in required):raise ValueError("Broker specification incomplete: "+str(required))
    df,valid=load(args.data);out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    years=sorted(valid.time.dt.year.unique());preds=[];folds=[]
    for year in years:
        if year<2024:continue
        # Rolling expanding window; 5-bar embargo before test year; no training on test year.
        test=valid[valid.time.dt.year==year];train=valid[valid.rowid<test.rowid.iloc[0]-5]
        if len(train)<1500 or len(test)<200:continue
        if train.y.nunique()<2:continue
        model=HistGradientBoostingClassifier(max_iter=120,max_leaf_nodes=15,l2_regularization=5,learning_rate=.05,random_state=42)
        model.fit(train[FEATURES],train.y);pr=model.predict_proba(test[FEATURES])[:,1]
        baseline=float(train.y.mean())
        folds.append({"year":int(year),"train_samples":len(train),"test_samples":len(test),"accuracy":float(accuracy_score(test.y,pr>=.5)),"brier":float(brier_score_loss(test.y,pr)),"baseline_brier":float(brier_score_loss(test.y,np.full(len(test),baseline)))})
        for rid,prob in zip(test.rowid,pr):preds.append({"rowid":int(rid),"time":str(df.loc[rid,"time"]),"prob_up":float(prob),"year":int(year)})
    if not folds:raise ValueError("Insufficient historical data for walk-forward folds")
    predictions=pd.DataFrame(preds).sort_values("rowid");predictions.to_csv(out/"predictions.csv",index=False)
    # Chronological, non-overlapping, fixed four-bar exits. No stop/target assumed for this baseline.
    equity=args.capital_hkd;peak=equity;maxdd=0;trades=[];blocked=0;wait=0;last_exit=-1
    oz_min=profile["min_contracts"]*profile["contract_oz"]
    if oz_min<=0:raise ValueError("Invalid minimum size")
    for row in predictions.itertuples(index=False):
        i=row.rowid
        if i<=last_exit:continue
        side=1 if row.prob_up>=.58 else -1 if row.prob_up<=.42 else 0
        if not side:wait+=1;continue
        entry=float(df.loc[i+1,"open_ask" if side==1 else "open_bid"])
        exitprice=float(df.loc[i+4,"close_bid" if side==1 else "close_ask"])
        # Risk proxy based on historical 24-bar volatility; NOT an actual protective stop.
        volatility=float(df.loc[i,"vol24"])
        stop_distance=max(1.5,entry*volatility*2)
        margin=entry*oz_min*profile["margin_rate"]*args.usd_hkd
        commission=2*profile["commission_usd_per_contract_side"]*profile["min_contracts"]*args.usd_hkd
        maxloss_proxy=(stop_distance+2*args.slippage_usd)*oz_min*args.usd_hkd+commission
        if margin>equity or maxloss_proxy>equity*args.risk:
            blocked+=1;continue
        days=1/24
        funding_rate=args.financing_usd_per_oz_day if args.financing_usd_per_oz_day is not None else profile.get("financing_usd_per_oz_day")
        if funding_rate is None:funding_rate=0
        pnl=((exitprice-entry)*side-2*args.slippage_usd-funding_rate*days)*oz_min*args.usd_hkd-commission
        equity+=pnl;peak=max(peak,equity);maxdd=max(maxdd,(peak-equity)/peak)
        trades.append({"time":row.time,"year":row.year,"side":"BUY" if side==1 else "SELL","prob_up":row.prob_up,"oz":oz_min,"entry":entry,"exit":exitprice,"pnl_hkd":pnl,"equity_hkd":equity})
        last_exit=i+4
        if equity<=0:break
    pd.DataFrame(trades,columns=["time","year","side","prob_up","oz","entry","exit","pnl_hkd","equity_hkd"]).to_csv(out/"paper_trades.csv",index=False)
    report={"folds":folds,"paper":{"initial_hkd":args.capital_hkd,"final_hkd":equity,"trades":len(trades),"blocked":blocked,"wait":wait,"max_drawdown":maxdd,"win_rate":sum(t["pnl_hkd"]>0 for t in trades)/len(trades) if trades else None},"broker_profile":profile,"simulation":{"risk_proxy":"24-bar volatility sizing proxy; NO executable stop order","slippage_usd_per_side":args.slippage_usd,"financing_usd_per_oz_day":funding_rate,"usd_hkd":args.usd_hkd},"limitations":["Broker product may not be available in Hong Kong","Broker spread and margin are indicative and may vary","No intrabar stop-out or liquidation engine","No independent final holdout after threshold selection","No verified broker execution or live trading"]}
    (out/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8");print(json.dumps(report,indent=2))
if __name__=="__main__":main()
