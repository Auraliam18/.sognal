"""Adversarial replay, paper parity and health regressions. Offline fixtures."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hamid import backtest, conformance, fees, paper
from hamid.replay_execution import replay, BAR_MS


def bar(i, high=100.2, low=99.8, close=100):
    return dict(t=i*BAR_MS, o=100, h=high, l=low, c=close, v=1)


class ReplayContract(unittest.TestCase):
    setup = dict(dir="LONG", entry=100, sl=99, tp1=103)

    def test_unfilled_and_expiry_are_not_losses(self):
        candles = [bar(i, 105, 104, 104.5) for i in range(96)] + [bar(96)]
        r = replay(candles, self.setup, 0)
        self.assertEqual(r["outcome"], "expired")
        self.assertIsNone(r["R_net"])

    def test_same_bar_stop_wins_and_costs_apply(self):
        r = replay([bar(0, 104, 98)], self.setup, 0)
        self.assertEqual(r["R"], -1)
        self.assertAlmostEqual(r["R_net"], -1-fees.cost_in_r(100,99))

    def test_no_same_bar_trail_lookahead(self):
        r = replay([bar(0), bar(1, 101.2, 99.5), bar(2, 100.4, 99.6)], self.setup, 0)
        self.assertEqual(r["end"], 3*BAR_MS)
        self.assertAlmostEqual(r["R"], .15)

    def test_two_thirds_trailing_and_short_symmetry(self):
        candles = [bar(0), bar(1, 102.2, 99.8), bar(2, 102, 100.8)]
        r = replay(candles, self.setup, 0)
        short = dict(dir="SHORT", entry=100, sl=101, tp1=97)
        mirror = [dict(c, o=200-c["o"], h=200-c["l"], l=200-c["h"], c=200-c["c"]) for c in candles]
        s = replay(mirror, short, 0)
        self.assertAlmostEqual(r["R"], 1)
        self.assertAlmostEqual(s["R_net"], r["R_net"])

    def test_hold_deadline_excludes_later_target(self):
        candles = [bar(i) for i in range(96)] + [bar(96,104,99.8,103)]
        r = replay(candles, self.setup, 0)
        self.assertEqual(r["outcome"], "timeout")
        self.assertEqual(r["R"], 0)

    def test_censored_end_not_fictional_close(self):
        r = replay([bar(0)], self.setup, 0)
        self.assertEqual(r["outcome"], "censored")
        self.assertIsNone(r["R"])

    def test_invalid_geometry_fails(self):
        with self.assertRaises(ValueError):
            replay([bar(0)], dict(self.setup, sl=101), 0)

    def test_closed_htf_at_boundary_and_gaps(self):
        hours = [dict(bar(i), t=i*3_600_000) for i in range(8)]
        self.assertEqual(len(backtest.closed_4h(hours, 8*3_600_000)), 2)
        self.assertEqual(len(backtest.closed_4h(hours, 8*3_600_000-1)), 1)
        self.assertEqual(len(backtest.closed_4h(hours[:2]+hours[3:], 8*3_600_000)), 1)

    def test_bootstrap_reproducible(self):
        self.assertEqual(backtest.boot([1,-1]*12,100), backtest.boot([1,-1]*12,100))

    def test_paginated_adapter_preserves_candle_objects(self):
        import backtest as historical
        series=[bar(0),bar(1)]
        with patch.object(historical,'klines',return_value=series):
            self.assertEqual(backtest.fetch('BTCUSDT',3000),(series,series))

    def paper_result(self, candles, now, **overrides):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.multiple(paper, OPEN=root/'open.jsonl', CLOSED=root/'closed.jsonl', EQUITY=root/'equity.json'), \
                 patch.object(paper, '_candles_since', return_value=candles), \
                 patch.object(paper.time, 'time', return_value=now/1000), \
                 patch.object(paper.brain, 'room_log'), patch.object(paper, '_equity'):
                p = dict(self.setup, sym='BTCUSDT', opened=BAR_MS, filled=None, why={}, **overrides)
                paper._write(paper.OPEN, [p])
                paper.mark()
                return paper._read(paper.CLOSED), paper._read(paper.OPEN)

    def test_paper_replay_trailing_and_fee_parity(self):
        candles = [bar(1), bar(2,101.2,99.8), bar(3,100.3,99.8)]
        closed, _ = self.paper_result(candles, 10*BAR_MS)
        r = replay(candles, self.setup, BAR_MS, symbol='BTCUSDT')
        self.assertEqual(closed[0]['outcome'],r['outcome'])
        self.assertAlmostEqual(closed[0]['R_net'],r['R_net'])

    def test_paper_does_not_fill_after_expiry(self):
        closed, _ = self.paper_result([bar(98)], 110*BAR_MS)
        self.assertEqual(closed[0]['outcome'], 'expired')

    def test_paper_ignores_still_open_candle(self):
        closed, opened = self.paper_result([bar(1,104,98)], BAR_MS+100)
        self.assertEqual(closed, [])
        self.assertEqual(len(opened), 1)

    def test_paper_does_not_take_late_target(self):
        candles = [bar(i) for i in range(1,97)] + [bar(97,104,99.8,103)]
        closed, _ = self.paper_result(candles, 110*BAR_MS)
        self.assertEqual(closed[0]['outcome'],'timeout')
        self.assertEqual(closed[0]['R'],0)

    def test_missing_invalid_future_feed_never_green(self):
        now=1_800_000_000_000
        with tempfile.TemporaryDirectory() as d, patch.object(conformance,'ROOT',Path(d)):
            for value in (None,{}, {'generated':'yesterday'}, {'generated':False}, {'generated':float('nan')}, {'generated':now+120000}):
                with self.subTest(value=value):
                    p=Path(d)/'signals/latest.json'
                    p.parent.mkdir(exist_ok=True)
                    p.write_text(json.dumps(value))
                    report=conformance.check(now)
                    self.assertTrue(any(v['rule']=='C5' and v['sym']=='latest.json' for v in report['violations']))


if __name__ == '__main__':
    unittest.main()
