"""The actual cycle must request 4h candles and fail closed on thin history."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from hamid import cycle


class TimeframeContract(unittest.TestCase):
    def test_real_timeframes_closed_bars_and_immediate_delivery(self):
        calls, seen, order = [], [], []
        now=1_800_000_000_000
        def candles(sym, tf, n):
            step={'4h':14_400_000,'1h':3_600_000,'15m':900_000}[tf]
            calls.append((sym,tf,n))
            if sym == 'BUSDT' and tf in ('1h','15m') and n==300:
                raise RuntimeError("preferred window unavailable")
            start=now//step*step
            count=80 if sym=='THINUSDT' and tf=='4h' else n
            return [[start-i*step,100,101,99,100,1] for i in reversed(range(count))]
        def read(sym,c4,c1,c15):
            seen.append((sym,c4,c1,c15))
            order.append(('read',sym))
            return SimpleNamespace(setup={'dir':'LONG','entry':100,'sl':99,'tp1':103,'waiting':False}, position_1h=None, trend_4h='up', blocks=[])
        with patch.object(cycle.sources,'klines',side_effect=candles), \
             patch.object(cycle.time,'time',return_value=now/1000), \
             patch.object(cycle.brain,'room_log'), patch.object(cycle.brain,'room_save'), \
             patch.object(cycle.research,'global_market',side_effect=RuntimeError('offline')), \
             patch.object(cycle,'market_first',return_value={}), patch.object(cycle,'read',side_effect=read), \
             patch.object(cycle,'money_flow',return_value=[]):
            cycle.run_active(['AUSDT','BUSDT','THINUSDT'],on_ready=lambda sym,r:order.append(('send',sym)))
        self.assertIn(('BTCUSDT','4h',201),calls)
        self.assertIn(('BUSDT','1h',201),calls)
        self.assertIn(('BUSDT','15m',61),calls)
        self.assertNotIn(('THINUSDT','1h',201),calls)
        self.assertEqual([r[0] for r in seen],['AUSDT','BUSDT'])
        for _,c4,c1,c15 in seen:
            self.assertGreaterEqual(len(c4),200)
            self.assertEqual(c4[-1]['t']-c4[-2]['t'],14_400_000)
            for bars,step in ((c4,14_400_000),(c1,3_600_000),(c15,900_000)):
                self.assertLessEqual(bars[-1]['t']+step,now)
        self.assertLess(order.index(('send','AUSDT')),order.index(('read','BUSDT')))


if __name__=='__main__':
    unittest.main()
