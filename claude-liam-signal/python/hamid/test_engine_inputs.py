import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from hamid import contract_history as ch, engine_inputs as ei, paper
import telegram


class Inputs(unittest.TestCase):
    def test_closed_pages_and_local_aggregation(self):
        dt=ch.STEP["4h"]; end=dt*1000
        def read(sym,tf,cursor,n):
            step=ch.STEP[tf]
            return [[t,2,1 if t==end-3*dt and tf=="4h" else 3,1,2,1,t] for t in range(cursor-step,cursor-(n+1)*step,-step)]
        rows=ch.closed("ONEUSDT","4h",201,end+31,read)
        self.assertEqual([r[0] for r in rows],list(range(end-201*dt,end,dt)))
        self.assertEqual(rows[-3][2:6],[3,1,2,4])
        with self.assertRaises(ValueError):
            ch.closed("ONEUSDT","4h",201,end,lambda *args: read(*args)[1:])

    def test_observed_liquidations_not_stale_or_estimates(self):
        row=dict(time=10000,contract="BTC_USDT",order_size="-2",fill_price="20")
        get=lambda _: [row,dict(row,time=6000),dict(row,fill_price="nan"),dict(row,order_size=0)]
        result=ei.liquidations(get,10005)
        self.assertEqual(len(result["events"]),1)
        self.assertEqual(result["at"],10000000)

    def test_primary_reserves_capacity_and_legacy_fails_closed(self):
        setup=dict(symbol="AAAUSDT",dir="LONG",entry=100,sl=85,tp1=120,tp2=150,waiting=False)
        with tempfile.TemporaryDirectory() as d, patch.object(paper,"OPEN",Path(d)/"open.jsonl"), patch.object(paper,"_equity",return_value={"balance":1265.63}), patch.object(paper.brain,"room_log"), patch.object(paper,"_append_gatelog"):
            setups=[dict(setup,symbol=s+"USDT") for s in ("AAA","BBB","CCC","DDD")]
            self.assertEqual(paper.open_from(setups,{}),3)
            rows=paper._read(paper.OPEN)
            self.assertTrue(all(r["risk_usd"]>0 and r["sized_at"] for r in rows))
            self.assertLessEqual(sum(r["notional_usd"] for r in rows),1265.63*.2)
            paper._append(paper.OPEN,dict(sym="OLDUSDT",entry=5,why={"stage":"second"}))
            self.assertIsNone(ei.portfolio(paper._read(paper.OPEN),1265.63,1)["open_exposure_usd"])
            self.assertEqual(paper.open_from([dict(setup,symbol="NEWUSDT")],{}),0)
    def test_keep_trade_after_watch_burst(self):
        now=int(time.time()*1000)
        observed={"kind":"trade_signal","tg_msg_id":8,"signal_id":"S-"+"a"*20,"at":now}
        rows=[{"kind":"watch_alert","at":now}]*45+[observed,dict(observed,at=now-3600001)]
        self.assertEqual(telegram.retained_receipts(rows)[40:],[observed])


if __name__ == "__main__": unittest.main()
