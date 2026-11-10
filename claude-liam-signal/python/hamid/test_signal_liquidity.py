import unittest
from unittest.mock import patch

from hamid import signal_liquidity as liq


class LiquidityPolicyTests(unittest.TestCase):
    def setUp(self):
        self.directory = [{"symbol": f"C{i:02}USDT", "quote": "USDT", "symbolStatus": "OPEN"}
                          for i in range(1, 52)]
        self.tickers = [{"symbol": r["symbol"], "quoteVol": str(100-i), "baseVol": str(i)}
                        for i, r in enumerate(self.directory)]
        self.book = {"asks": [["100.001", "100"]], "bids": [["99.999", "100"]]}
        self.ranking = {"at": liq.now_ms(), "members": liq._rank(self.directory, self.tickers)}

    def test_universe(self):
        self.directory.append({"symbol": "CLOSEDUSDT", "quote": "USDT", "symbolStatus": "CLOSED"})
        self.tickers.append({"symbol": "CLOSEDUSDT", "quoteVol": "99999"})
        ranked = liq._rank(self.directory, list(reversed(self.tickers)))
        self.assertEqual(len(ranked), 50)
        self.assertEqual(ranked["C50USDT"]["rank"], 50)
        self.assertEqual(ranked["C49USDT"]["rank"], 49)
        self.assertNotIn("C51USDT", ranked)
        self.assertNotIn("CLOSEDUSDT", ranked)
        self.assertEqual(liq.prioritize(["C51USDT", "C01USDT"], 51, self.ranking)[-1], "C51USDT")

    def test_incomplete_volume(self):
        with self.assertRaises(ValueError):
            liq._rank(self.directory, self.tickers[:-1])
        self.tickers[-1]["quoteVol"] = "NaN"
        with self.assertRaises(ValueError):
            liq._rank(self.directory, self.tickers)

    def test_boundary_and_book(self):
        signal = {"symbol": "C50USDT", "notional_usd": 2000}
        with patch.object(liq, "_get", return_value=(self.book, liq.now_ms())) as fetch:
            self.assertFalse(liq.assess(dict(signal, symbol="C51USDT"), self.ranking)["ok"])
            self.assertFalse(liq.assess(signal, dict(self.ranking, at=1))["ok"])
            fetch.assert_not_called()
            self.assertTrue(liq.assess(signal, self.ranking)["ok"])
            for book, why in [
                (dict(self.book, bids=[["99.999", "1"]]), "insufficient_depth"),
                (dict(self.book, bids=[["100.01", "100"]]), "crossed_depth"),
                (dict(self.book, bids=[["99.999", "1"], ["99.9", "99"]]), "slippage_limit"),
                (dict(self.book, asks=[["101", "100"]]), "slippage_limit"),
            ]:
                fetch.return_value = book, liq.now_ms()
                self.assertEqual(liq.assess(signal, self.ranking)["reason"], why)
            fetch.side_effect = ValueError("stale_depth")
            self.assertEqual(liq.assess(signal, self.ranking)["reason"], "stale_depth")


if __name__ == "__main__":
    unittest.main()
