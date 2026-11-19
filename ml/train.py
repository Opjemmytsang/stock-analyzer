"""Train a real (non-synthetic) XAU direction classifier with chronological holdout."""
import argparse, json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.dummy import DummyClassifier

FEATURES = ["ret1","ret2","ret4","ret8","range1","body","vol8","vol24","ma8gap","ma24gap","hour_sin","hour_cos"]
HORIZON=4
def prepare(path, spread):
    df=pd.read_csv(path)
    required={"time","open","high","low","close"}
    if not required.issubset(df): raise ValueError("Missing CSV fields: "+str(required-set(df)))
    df["time"]=pd.to_datetime(df.time,utc=True,errors="raise")
    if df.time.isna().any() or df.time.duplicated().any() or not df.time.is_monotonic_increasing: raise ValueError("Time must be unique and ascending")
    for c in ("open","high","low","close"): df[c]=pd.to_numeric(df[c],errors="raise")
    if not np.isfinite(df[["open","high","low","close"]].to_numpy()).all() or (df[["open","high","low","close"]] <=0).any().any(): raise ValueError("Nonpositive or invalid prices")
    if ((df.high < df[["open","close"]].max(axis=1)) | (df.low > df[["open","close"]].min(axis=1))).any(): raise ValueError("Invalid OHLC")
    if len(df)<1500: raise ValueError("At least 1500 bars required")
    delta=df.time.diff().dropna()
    expected=pd.Timedelta(minutes=15)
    # Do not silently interpolate missing or weekend bars. Drop feature windows crossing gaps.
    seg=delta.ne(expected).cumsum()
    df["segment"]=pd.concat([pd.Series([0]),seg],ignore_index=True).cumsum().to_numpy()
    close=df.close
    df["ret1"]=close.pct_change(1);df["ret2"]=close.pct_change(2);df["ret4"]=close.pct_change(4);df["ret8"]=close.pct_change(8)
    df["range1"]=(df.high-df.low)/close
    df["body"]=(df.close-df.open)/df.open
    df["vol8"]=df.ret1.rolling(8).std();df["vol24"]=df.ret1.rolling(24).std()
    df["ma8gap"]=close/close.rolling(8).mean()-1
    df["ma24gap"]=close/close.rolling(24).mean()-1
    hour=df.time.dt.hour+df.time.dt.minute/60
    df["hour_sin"]=np.sin(2*np.pi*hour/24);df["hour_cos"]=np.cos(2*np.pi*hour/24)
    # Entry at next bar open; exit after four completed bars at the close.
    entry=df.open.shift(-1)
    exitprice=df.close.shift(-HORIZON)
    gross=exitprice-entry
    # Direction label, not a claim of profitability. Conservative spread threshold in USD/oz.
    df["target"]=(gross>spread).astype(int)
    df["future_move"]=gross
    segment=df.segment
    valid=(segment==segment.shift(24)) & (segment==segment.shift(-HORIZON))
    out=df.loc[valid & df[FEATURES].notna().all(axis=1) & gross.notna()].copy()
    if len(out)<1000:raise ValueError("Insufficient contiguous 15-minute samples after gap filtering")
    return out
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--csv",required=True)
    ap.add_argument("--output",default="ml/artifacts")
    ap.add_argument("--spread-usd",type=float,default=0.5)
    args=ap.parse_args()
    if args.spread_usd<0:raise ValueError("Spread must be nonnegative")
    df=prepare(args.csv,args.spread_usd)
    # Embargo >= label horizon to avoid overlap leakage.
    n=len(df); a=int(n*.6); b=int(n*.8); gap=HORIZON+1
    train=df.iloc[:a];val=df.iloc[a+gap:b];test=df.iloc[b+gap:]
    if min(len(train),len(val),len(test))<100:raise ValueError("Insufficient split data")
    xtr=train[FEATURES];ytr=train.target
    if ytr.nunique()<2:raise ValueError("Training set has only one class")
    model=HistGradientBoostingClassifier(max_iter=120,max_leaf_nodes=15,l2_regularization=5,learning_rate=.05,random_state=42)
    model.fit(xtr,ytr)
    baseline=DummyClassifier(strategy="prior").fit(xtr,ytr)
    def metrics(part):
        y=part.target.to_numpy();p=model.predict_proba(part[FEATURES])[:,1];q=baseline.predict_proba(part[FEATURES])[:,1]
        return {"n":len(y),"positive_rate":float(np.mean(y)),"accuracy":float(accuracy_score(y,p>=.5)),"balanced_accuracy":float(balanced_accuracy_score(y,p>=.5)),"brier":float(brier_score_loss(y,p)),"baseline_brier":float(brier_score_loss(y,q)),"log_loss":float(log_loss(y,p,labels=[0,1])),"roc_auc":float(roc_auc_score(y,p)) if len(np.unique(y))==2 else None}
    report={"horizon_bars":HORIZON,"bar_minutes":15,"spread_usd":args.spread_usd,"features":FEATURES,"train":metrics(train),"validation":metrics(val),"test":metrics(test),"test_start":str(test.time.iloc[0]),"test_end":str(test.time.iloc[-1]),"limitations":["No fees, financing, execution or live fills","Single chronological holdout; walk-forward not implemented","Predicted probability is not calibrated or verified as trade edge","Do not trade real money"]}
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    joblib.dump({"model":model,"features":FEATURES,"horizon":HORIZON,"spread":args.spread_usd},out/"model.joblib")
    (out/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    # Export test predictions for independent paper-trade evaluation.
    preds=model.predict_proba(test[FEATURES])[:,1]
    pd.DataFrame({"time":test.time.astype(str),"close":test.close,"prob_up":preds,"future_move_usd":test.future_move}).to_csv(out/"test_predictions.csv",index=False)
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
