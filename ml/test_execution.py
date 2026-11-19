import unittest
import pandas as pd
from ml.execution import simulate

BASE=dict(side=1,entry_index=0,oz=1,initial_hkd=500,usd_hkd=1,margin_rate=.05,
          stop_distance=5,commission_usd_per_oz_side=0,slippage_usd=0,
          financing_long_usd_per_oz_day=0,financing_short_usd_per_oz_day=0,
          max_bars=3)
def bar(time, bid_open=100,bid_high=102,bid_low=99,bid_close=100,spread=1):
    d={"time":pd.Timestamp(time,tz="UTC")}
    for name,val in [("open",bid_open),("high",bid_high),("low",bid_low),("close",bid_close)]:
        d[name+"_bid"]=val;d[name+"_ask"]=val+spread
    return d
class TestExecution(unittest.TestCase):
    def test_stop_intrabar(self):
        bars=[bar("2026-01-05 10:00",bid_low=94),bar("2026-01-05 10:15")]
        x=simulate(bars,**BASE)
        self.assertEqual(x["reason"],"stop_intrabar")
        self.assertEqual(x["exit"],96)
    def test_gap_stop(self):
        bars=[bar("2026-01-05 10:00"),bar("2026-01-05 10:15",bid_open=90,bid_low=89)]
        x=simulate(bars,**BASE)
        self.assertEqual(x["reason"],"stop_gap")
        self.assertEqual(x["exit"],90)
    def test_margin_closeout(self):
        args={**BASE,"initial_hkd":20,"margin_rate":.1,"stop_distance":40}
        x=simulate([bar("2026-01-05 10:00",bid_low=82)],**args)
        self.assertEqual(x["reason"],"margin_closeout_intrabar")
    def test_financing_rollover(self):
        args={**BASE,"financing_long_usd_per_oz_day":2,"max_bars":2}
        bars=[bar("2026-01-05 21:45"),bar("2026-01-05 22:00")]
        x=simulate(bars,**args)
        self.assertEqual(x["rollovers"],1)
        self.assertEqual(x["financing_hkd"],2)
    def test_triple_rollover(self):
        args={**BASE,"financing_long_usd_per_oz_day":2,"max_bars":2}
        bars=[bar("2026-01-07 21:45"),bar("2026-01-07 22:00")]
        x=simulate(bars,**args)
        self.assertEqual(x["financing_hkd"],6)
    def test_short_stop_ask(self):
        args={**BASE,"side":-1}
        bars=[bar("2026-01-05 10:00",bid_high=108)]
        x=simulate(bars,**args)
        self.assertEqual(x["reason"],"stop_intrabar")
        self.assertEqual(x["exit"],104)
    def test_commission_and_slippage(self):
        args={**BASE,"commission_usd_per_oz_side":1,"slippage_usd":.2,"max_bars":1}
        x=simulate([bar("2026-01-05 10:00")],**args)
        self.assertAlmostEqual(x["pnl_hkd"],-3.4)
    def test_reject_insufficient_margin(self):
        with self.assertRaises(ValueError):
            simulate([bar("2026-01-05 10:00")],**{**BASE,"initial_hkd":1})
if __name__=="__main__":unittest.main()
