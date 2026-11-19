"""US long-options paper simulator. NO BROKER ORDER ROUTING. Python stdlib only."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import argparse, csv, json, math, re

CONTRACT = re.compile(r'^([A-Z]{1,6})(\d{6})([CP])(\d{8})$')

def contract_info(symbol: str):
    m=CONTRACT.fullmatch(symbol)
    if not m: raise ValueError('Expected standard OCC option symbol, e.g. SPY261120C00600000')
    root, expiry, kind, strike=m.groups()
    return root, datetime.strptime(expiry,'%y%m%d').date(),kind,int(strike)/1000

def timestamp(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError('Quote timestamp must include timezone')
    return dt.astimezone(timezone.utc)

@dataclass(frozen=True)
class Quote:
    time: str
    symbol: str
    bid: float
    ask: float
    multiplier: int=100
    source: str='unknown'
    feed: str='unknown'
    def validate(self, now: Optional[datetime]=None, max_age_seconds=90):
        _,expiry,_,_=contract_info(self.symbol)
        t=timestamp(self.time)
        if expiry<t.date(): raise ValueError('Expired option')
        if not all(math.isfinite(v) for v in (self.bid,self.ask)) or not 0<=self.bid<=self.ask or self.ask<=0:
            raise ValueError('Invalid executable bid/ask')
        if self.multiplier!=100: raise ValueError('Nonstandard contract multiplier: unsupported')
        if self.feed!='opra': raise ValueError('Indicative/delayed/unknown feed not executable-quality')
        if not self.source: raise ValueError('Missing data source')
        if now is not None:
            if now.tzinfo is None: raise ValueError('now must be timezone-aware')
            age=(now.astimezone(timezone.utc)-t).total_seconds()
            if age < -5 or age > max_age_seconds: raise ValueError('Stale/future quote')
        return t

@dataclass
class Config:
    initial_cash:float=63.0
    fee_per_contract_side:float=.65
    extra_fee_per_contract_side:float=.05
    entry_slippage_per_share:float=.01
    exit_slippage_per_share:float=.01
    max_premium_fraction:float=.25
    max_daily_loss_fraction:float=.10
    max_total_loss_fraction:float=.30
    max_spread_fraction:float=.20
    stop_loss_fraction:float=.35
    take_profit_fraction:float=.75
    min_days_to_expiry:int=2
    max_days_to_expiry:int=21
    close_before_expiry_days:int=1
    max_quote_age_seconds:int=90
    def validate(self):
        if self.initial_cash<=0 or any(v<0 or not math.isfinite(v) for v in asdict(self).values()):
            raise ValueError('Invalid config')
        if not 0<self.max_premium_fraction<=1 or not 0<self.max_daily_loss_fraction<=1 or not 0<self.max_total_loss_fraction<=1:
            raise ValueError('Invalid risk fractions')
        if not 0<self.stop_loss_fraction<1 or self.take_profit_fraction<=0:
            raise ValueError('Invalid exits')
        if self.min_days_to_expiry<self.close_before_expiry_days:
            raise ValueError('Expiry buffer must not exceed minimum DTE')

class PaperAccount:
    def __init__(self, config:Config=None):
        self.config=config or Config()
        self.config.validate()
        self.cash=self.config.initial_cash
        self.position=None
        self.history=[]
        self.day_start={}
        self.halted=False

    @property
    def equity(self):
        return self.cash + (self.position['mark_value'] if self.position else 0)

    def _fee(self,qty):
        return qty*(self.config.fee_per_contract_side+self.config.extra_fee_per_contract_side)

    def _limits(self,now):
        day=now.date().isoformat()
        self.day_start.setdefault(day,self.equity)
        if self.equity <= self.config.initial_cash*(1-self.config.max_total_loss_fraction):
            self.halted=True
        if self.equity <= self.day_start[day]*(1-self.config.max_daily_loss_fraction):
            self.halted=True
        if self.halted:
            raise ValueError('Kill switch: loss limit breached')

    def open(self,quote:Quote,now:datetime,signal:float,qty:int=1):
        quote.validate(now,self.config.max_quote_age_seconds)
        self._limits(now)
        if self.position: raise ValueError('One position at a time')
        if not 0<=signal<=1 or not math.isfinite(signal): raise ValueError('Invalid signal')
        if signal<.65: raise ValueError('Signal below threshold')
        if not isinstance(qty,int) or qty<1: raise ValueError('Whole contracts only')
        _,expiry,_,_=contract_info(quote.symbol)
        dte=(expiry-now.date()).days
        if not self.config.min_days_to_expiry<=dte<=self.config.max_days_to_expiry: raise ValueError('Expiry filter')
        if (quote.ask-quote.bid)/quote.ask>self.config.max_spread_fraction: raise ValueError('Spread too wide')
        premium=(quote.ask+self.config.entry_slippage_per_share)*quote.multiplier*qty
        debit=premium+self._fee(qty)
        if debit>self.cash: raise ValueError('Insufficient cash')
        if debit>self.equity*self.config.max_premium_fraction: raise ValueError('Premium risk limit')
        self.cash-=debit
        self.position={'symbol':quote.symbol,'qty':qty,'expiry':expiry.isoformat(),
                       'entry_time':now.isoformat(),'entry_debit':debit,'entry_ask':quote.ask,
                       'mark_value':quote.bid*quote.multiplier*qty,'last_bid':quote.bid,
                       'last_time':now.isoformat(),'multiplier':quote.multiplier}
        self.history.append({'event':'OPEN','time':now.isoformat(),'symbol':quote.symbol,
                             'qty':qty,'debit':round(debit,2),'signal':signal})
        return self.history[-1]

    def update(self,quote:Quote,now:datetime):
        quote.validate(now,self.config.max_quote_age_seconds)
        if not self.position or quote.symbol!=self.position['symbol']: raise ValueError('No matching position')
        p=self.position
        p['mark_value']=quote.bid*p['multiplier']*p['qty']
        p['last_bid']=quote.bid
        p['last_time']=now.isoformat()
        net_exit=max(0,quote.bid-self.config.exit_slippage_per_share)*p['multiplier']*p['qty']-self._fee(p['qty'])
        pnl_fraction=(net_exit-p['entry_debit'])/p['entry_debit']
        _,expiry,_,_=contract_info(quote.symbol)
        reason=None
        if now.date()>=expiry-timedelta(days=self.config.close_before_expiry_days): reason='EXPIRY_BUFFER'
        elif pnl_fraction<=-self.config.stop_loss_fraction: reason='STOP_LOSS'
        elif pnl_fraction>=self.config.take_profit_fraction: reason='TAKE_PROFIT'
        if self.equity<=self.config.initial_cash*(1-self.config.max_total_loss_fraction): reason='TOTAL_LOSS_KILL'
        day=now.date().isoformat()
        self.day_start.setdefault(day,self.equity)
        if self.equity<=self.day_start[day]*(1-self.config.max_daily_loss_fraction): reason='DAILY_LOSS_KILL'
        if reason:return self.close(quote,now,reason)
        return {'event':'HOLD','equity':round(self.equity,2),'pnl_fraction':round(pnl_fraction,4)}

    def close(self,quote:Quote,now:datetime,reason='MANUAL'):
        quote.validate(now,self.config.max_quote_age_seconds)
        if not self.position or quote.symbol!=self.position['symbol']: raise ValueError('No matching position')
        p=self.position
        proceeds=max(0,quote.bid-self.config.exit_slippage_per_share)*p['multiplier']*p['qty']-self._fee(p['qty'])
        proceeds=max(0,proceeds)
        self.cash+=proceeds
        event={'event':'CLOSE','time':now.isoformat(),'symbol':quote.symbol,'reason':reason,
               'proceeds':round(proceeds,2),'pnl':round(proceeds-p['entry_debit'],2),
               'cash':round(self.cash,2)}
        self.history.append(event)
        self.position=None
        try:self._limits(now)
        except ValueError:pass
        return event

    def snapshot(self):
        return {'cash':round(self.cash,2),'equity':round(self.equity,2),
                'position':self.position,'halted':self.halted,'history':self.history}

def load_quotes(path):
    with open(path,newline='',encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            yield Quote(time=row['time'],symbol=row['symbol'],
                        bid=float(row['bid']),ask=float(row['ask']),
                        multiplier=int(row.get('multiplier') or 100),
                        source=row.get('source',''),feed=row.get('feed',''))

def replay(path,config:Config,signal=.75):
    account=PaperAccount(config)
    last=None
    for q in load_quotes(path):
        now=timestamp(q.time)
        if last is not None and now<=last: raise ValueError('Quotes must be strictly chronological')
        last=now
        if account.position:
            if q.symbol!=account.position['symbol']:
                raise ValueError('Feed must include held contract quote on each tick')
            account.update(q,now)
        elif not account.halted:
            try: account.open(q,now,signal)
            except ValueError: pass
    return account.snapshot()

def main():
    parser=argparse.ArgumentParser(description='Offline-only US options paper replay')
    parser.add_argument('--quotes',required=True,help='CSV containing REAL sourced OPRA bid/ask snapshots, never synthetic or indicative')
    parser.add_argument('--output',default='options_paper_report.json')
    parser.add_argument('--initial-cash',type=float,default=63)
    parser.add_argument('--signal',type=float,default=.75,help='DEMO constant signal; NOT an AI model')
    args=parser.parse_args()
    result=replay(args.quotes,Config(initial_cash=args.initial_cash),args.signal)
    Path(args.output).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'equity':result['equity'],'events':len(result['history']),
                      'halted':result['halted'],'open_position':bool(result['position'])},indent=2))
if __name__=='__main__':main()
