"""Regression cases derived from the monitored paper and delivery ledgers; no network."""
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from hamid import paper, position_state as state, trend_gate
import telegram


class MonitoredRecovery(unittest.TestCase):
    row = dict(sym="XUSDT", dir="LONG", opened=10000, entry=100., sl=95., tp1=110.,
               tp2=115., why={"stage":"second"}, filled=None)

    def test_exact_and_idempotent_reconciliation(self):
        p=self.row
        remaining=[dict(p, opened=10001),dict(p, why={"stage":"v2"}),dict(p, tp1=105.),
                   dict(p, tp2=None),dict(p, sl=97.),dict(p, why={})]
        history=[dict(p, closed=11000, outcome="stop")]
        self.assertEqual(state.reconcile([p,*remaining],history),remaining)
        self.assertEqual(state.reconcile(remaining,history),remaining)
        self.assertEqual(state.reconcile([p],[dict(p, closed=11000)]),[p])

    def test_three_way_close_wins_and_preserves_additions_and_fill(self):
        p=self.row
        new=dict(p,opened=10002)
        other=dict(p,opened=10003)
        self.assertEqual(state.merge_open([p],[new],[p,other]),[new,other])
        self.assertEqual(state.merge_open([p],[dict(p,filled=10005)],[p])[0]["filled"],10005)
        with self.assertRaises(ValueError):
            state.merge_open([], [p], [dict(p, why={"stage":"second","other":1})])

    def test_inconsistent_outcomes_and_repeats_do_not_train(self):
        from hamid.settled_evidence import consistent
        p=dict(self.row,closed=20000,filled=10010,outcome="stop",R=-1)
        q=dict(p,opened=10001)
        rows=[p,dict(p,closed=33000),q,dict(q,outcome="target",R=2),dict(p,entry=94),dict(p,why={})]
        self.assertEqual(consistent(rows),[p])

    def test_one_read_per_symbol_and_no_duplicate_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            with patch.multiple(paper, OPEN=path/"open.jsonl", CLOSED=path/"closed.jsonl"), patch.object(paper,"_equity"), patch.object(paper,"_candles_since",return_value=[]) as read, patch.object(paper.time,"time",return_value=11):
                p=self.row
                opened=[p,dict(p,opened=10001),dict(p,opened=10002)]
                closed=[dict(p,closed=11000,outcome="stop")]
                paper._write(paper.OPEN,opened);paper._write(paper.CLOSED,closed)
                self.assertEqual(paper.mark(),(2,0))
                read.assert_called_once_with("XUSDT",10001)
                self.assertEqual(paper._read(paper.CLOSED),closed)

    def test_no_invalid_levels(self):
        for side,sl,tp in [("LONG",99,101),("SHORT",101,99)]:
            self.assertTrue(state.geometry(side,100,sl,tp))
            self.assertFalse(state.geometry(side,100,tp,sl))
        for bad in (None,float("nan"),float("inf"),True,-1,100):
            self.assertFalse(state.geometry("LONG",100,bad,110))

    def test_seeded_bootstrap_matches_original_draws(self):
        a=list(range(19));b=[x/7 for x in range(21)]
        da=[i%4 for i in a];db=[i%3 for i in range(len(b))]
        def draw(v,days):
            groups={}
            for x,d in zip(v,days):groups.setdefault(d,[]).append(x)
            out=[]
            while len(out)<len(v):out.extend(random.choice(list(groups.values())))
            return sum(out[:len(v)])/len(v)
        random.seed(27)
        expected=sorted(draw(a,da)-draw(b,db) for _ in range(200))
        random.seed(27);lo,hi=paper._boot_diff(a,b,200,.05,da,db)
        self.assertAlmostEqual(lo,expected[5],places=12);self.assertAlmostEqual(hi,expected[195],places=12)

    def test_watch_never_enters_execution_outbox(self):
        with tempfile.TemporaryDirectory() as d, patch.object(telegram,"TGLOG",Path(d)/"log.json"),patch("hamid.execution_gate.push") as push:
            telegram._log_final(dict(kind="watch_alert",sym="XUSDT",tg_msg_id=95))
            push.assert_not_called()
            self.assertEqual(json.loads(telegram.TGLOG.read_text(encoding="utf8"))["sent"][0]["tg_msg_id"],95)

    def test_no_btc_or_stale_macro_blocks_alt(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);now=99000000
            dom={"generated":now,"usdt_dominance":6.3,"structure":{"regime":"RANGE"}}
            (d/"dominance.json").write_text(json.dumps(dom))
            with self.assertRaises(FileNotFoundError):telegram.decision_context("XUSDT",d,now)
            (d/"btc-patterns.json").write_text(json.dumps({"generated":now,"btc":{"4h":[],"1h":[]}}))
            self.assertEqual(telegram.decision_context("XUSDT",d,now)["btc_at"],now)
            with self.assertRaises(ValueError):telegram.decision_context("XUSDT",d,now+3600001)

    def test_htf_stale_gap_insufficient(self):
        from hamid.test_trend_gate import kget_for
        fetch=kget_for("up","up")
        for transform in (lambda rows:rows[-100:],lambda rows:rows[:-1],
                          lambda rows:rows[:-10]+rows[-9:]):
            self.assertFalse(trend_gate.assess("XUSDT","LONG",lambda s,t,n:transform(fetch(s,t,n)))["ok"])


if __name__ == "__main__":
    unittest.main()
