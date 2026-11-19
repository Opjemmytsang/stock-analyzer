import unittest
from datetime import datetime
from options_paper import Config,Quote,PaperAccount

def q(time='2026-11-20T15:00:00Z',bid=.10,ask=.12,symbol='SPY261127C00600000',feed='opra'):
    return Quote(time,symbol,bid,ask,100,'fixture',feed)
def t(value):return datetime.fromisoformat(value.replace('Z','+00:00'))
class TestPaper(unittest.TestCase):
    def test_buy_at_ask_mark_bid(self):
        a=PaperAccount();a.open(q(),t('2026-11-20T15:00:00Z'),.8)
        self.assertAlmostEqual(a.cash,63-13.7)
        self.assertAlmostEqual(a.equity,59.3)
    def test_stop(self):
        a=PaperAccount();a.open(q(),t('2026-11-20T15:00:00Z'),.8)
        x=a.update(q('2026-11-20T15:01:00Z',bid=.06,ask=.08),t('2026-11-20T15:01:00Z'))
        self.assertEqual(x['reason'],'DAILY_LOSS_KILL')
    def test_profit(self):
        a=PaperAccount();a.open(q(),t('2026-11-20T15:00:00Z'),.8)
        x=a.update(q('2026-11-20T15:01:00Z',bid=.27,ask=.29),t('2026-11-20T15:01:00Z'))
        self.assertEqual(x['reason'],'TAKE_PROFIT')
    def test_reject_indicative(self):
        with self.assertRaises(ValueError):PaperAccount().open(q(feed='indicative'),t('2026-11-20T15:00:00Z'),.8)
    def test_stale(self):
        with self.assertRaises(ValueError):PaperAccount().open(q(),t('2026-11-20T15:10:00Z'),.8)
    def test_premium_cap(self):
        with self.assertRaises(ValueError):PaperAccount().open(q(bid=.2,ask=.25),t('2026-11-20T15:00:00Z'),.8)
    def test_no_short(self):
        with self.assertRaises(ValueError):PaperAccount().open(q(),t('2026-11-20T15:00:00Z'),.8,qty=-1)
    def test_expiry(self):
        a=PaperAccount();a.open(q(),t('2026-11-20T15:00:00Z'),.8)
        x=a.update(q('2026-11-26T15:00:00Z'),t('2026-11-26T15:00:00Z'))
        self.assertEqual(x['reason'],'EXPIRY_BUFFER')
    def test_cash_limit(self):
        with self.assertRaises(ValueError):PaperAccount(Config(initial_cash=10)).open(q(),t('2026-11-20T15:00:00Z'),.8)
    def test_spread_limit(self):
        with self.assertRaises(ValueError):PaperAccount().open(q(bid=.01,ask=.12),t('2026-11-20T15:00:00Z'),.8)
    def test_no_duplicate_position(self):
        a=PaperAccount();a.open(q(),t('2026-11-20T15:00:00Z'),.8)
        with self.assertRaises(ValueError):a.open(q('2026-11-20T15:01:00Z'),t('2026-11-20T15:01:00Z'),.8)
    def test_expired(self):
        with self.assertRaises(ValueError):q(symbol='SPY261119C00600000').validate(t('2026-11-20T15:00:00Z'))
if __name__=='__main__':unittest.main()
