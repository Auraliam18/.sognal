"""Small deterministic contract fixtures. Never fetch candles or alter the books."""
import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_terminal as b


class TerminalContract(unittest.TestCase):
    def test_observed_no_pick_and_unlinked_delivery_have_different_health(self):
        def own(radar, sent):
            feeds = {k: {"generated": 1700000000000, "path": k, "state": "fresh", "data": data}
                     for k, data in [("radar", radar), ("delivery", {"sent": sent})]}
            return {e["id"]: e["own_state"] for e in
                    b.engine_packets(b.ROOT, feeds, {"available": True, "source": "fixture"}, 1700000000000)}
        packet = {"universe_n": 30, "coins": [], "recommendation": [], "verdict": None}
        result = own(packet, [{"kind": "trade_signal", "tg_msg_id": 8}])
        self.assertEqual((result["E12"], result["E25"]), ("fresh", "partial"))
        result = own(dict(packet, universe_n=0), [{"kind": "watch_alert", "tg_msg_id": 8}])
        self.assertEqual((result["E12"], result["E25"]), ("partial", "partial"))
        receipt = {"kind":"trade_signal", "tg_msg_id":8, "at":1700000000000, "signal_id":"S-"+"a"*20}
        self.assertEqual(own(packet, [receipt, {"at":1}])["E25"], "fresh")
        self.assertEqual(own(packet, [dict(receipt, at=1600000000000)])["E25"], "stale")
        self.assertEqual(own(packet, [dict(receipt, at=1800000000000)])["E25"], "clock_error")
        self.assertEqual(own(packet, [receipt, receipt])["E25"], "partial")
        self.assertEqual(own(packet, [])["E25"], "partial")

    def test_role_checks_distinguish_review_coverage_and_legacy_receipts(self):
        from role_evidence import inspect, delivery, history_ok, positioned
        def inspect_role(role, packet):
            return inspect(role, packet, lessons={}, reconciliation={}, risk={}, portfolio={})
        review = {"at":1700000000000, "closed":2,"books":{"alarm":{"n":2}},"verdict":"reviewed"}
        packet = {"review":review, "coverage":{"complete":False}}
        _, missing, clock = inspect_role("E20",packet)
        self.assertEqual(missing, [])
        self.assertEqual(clock[0],review["at"])
        review["closed"] = 3
        self.assertTrue(inspect_role("E20",packet)[1])
        self.assertFalse(history_ok({"1h":200,"4h":199,"15m":60}))
        self.assertFalse(positioned({"dir":"LONG","sl":1,"entry":2,"tp1":2,"tp2":3}))
        log = delivery([{"kind":"watch_alert","tg_msg_id":True,"at":1},{"at":1},
                        {"kind":"watch_alert","tg_msg_id":2,"at":1}])
        grouped = delivery([{"kind":"watch_alert","tg_msg_id":8,"at":1,"sym":symbol} for symbol in ("BTC","ETH")])
        self.assertEqual((grouped["watch_receipts"],grouped["watch_rows"],grouped["reused_receipts"]), (1,2,0))
        self.assertEqual((log["trade_receipts"],log["watch_receipts"],log["invalid"],log["legacy_unverified"]), (0,1,1,1))

    def test_order_book_preserves_source_time_and_rejects_crossed_books(self):
        from hamid import intel
        from unittest.mock import patch
        row={"ts":"1700000000000","bids":[["10","4"]],"asks":[["11","1"]]}
        with patch.object(intel,"_json",return_value={"data":[row]}):
            result=intel.order_book()
            self.assertEqual((result["at"],result["imbalance"]), (1700000000000,0.6))
            row["bids"][0][0]="12"
            with self.assertRaises(ValueError):
                intel.order_book()

    def test_radar_recovers_only_with_the_required_closed_bars(self):
        from hamid import ob_intel
        from unittest.mock import patch
        calls = []
        def fetch(symbol, frame, size):
            calls.append((frame,size))
            if size in (61,201):
                return [{"c":1}] * (size-1)
            return []
        with patch.object(ob_intel,"analyze",return_value=[]):
            self.assertEqual(set(ob_intel.radar_for("FIXTURE",fetch)["observed_frames"]), {"15m","1h","4h"})
        self.assertEqual(len(calls),6)

    def test_freshness_never_rebrands_missing_or_future_time(self):
        self.assertEqual(b.freshness(None, 1000000, 60), "unknown")
        self.assertEqual(b.freshness(1, 1000000, 60), "stale")
        self.assertEqual(b.freshness(2000000, 1000000, 60), "clock_error")
        self.assertEqual(b.freshness(999000, 1000000, 60), "fresh")

    def test_books_duplicates_expiries_and_shards(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = root / 'brain/paper/closed.jsonl'
            p.parent.mkdir(parents=True)
            rows = [
                {'sym':'BTCUSDT','why':{'stage':'second'},'R':2,'outcome':'tp','closed':1700000000000},
                {'sym':'BTCUSDT','why':{'stage':'second'},'R':0,'outcome':'expired'},
                {'sym':'ETHUSDT','why':{'stage':'practice'},'R':-1,'outcome':'sl'},
                {'sym':'SOLUSDT','why':{'stage':'sig-ibs'},'R':1,'outcome':'tp'},
                {'sym':'XUSDT','R':4,'outcome':'tp','secret':'never export'},
            ]
            for i,r in enumerate(rows):
                r.update(opened=10000+i,entry=100.,sl=98.,tp1=104.,dir="LONG")
                r.setdefault("why",{"stage":"unknown-fixture"})
            rows.append(rows[0].copy())  # repeated evidence must remain repeated
            p.write_text('\n'.join(json.dumps(r) for r in rows)+'\nnot-json\n',encoding='utf-8')
            result = b.ledger(root,root/'out',1700000000100,2)
            self.assertEqual(result['records'],6)
            self.assertEqual(result['malformed_records'],1)
            self.assertEqual(sum(p['count'] for p in result['pages']),6)
            self.assertTrue(all(len(p['books']) == 1 for p in result['pages']))
            primary_pages=[p for p in result['pages'] if 'hamid' in p['books']]
            self.assertEqual(sum(p['count'] for p in primary_pages),3)
            books={r['book']:r for r in result['books']}
            self.assertEqual(books['hamid']['settled'],1)
            self.assertEqual(result['evidence_counts']['repeat'],1)
            self.assertEqual(books['hamid']['win_pct'],100)
            self.assertEqual(books['practice']['sum_r'],-1)
            self.assertEqual(books['other']['records'],1)
            self.assertNotIn('secret',json.dumps(result))
            # Exercise the sharded representation independently of migration.
            part=b.jsonl_store.parts(p)
            part.mkdir()
            (part/'000001.jsonl').write_text(p.read_text(encoding='utf-8'),encoding='utf-8')
            p.unlink()
            sharded=b.ledger(root,root/'sharded',1700000000100,2)
            self.assertEqual(sharded['records'],6)
            self.assertEqual(sharded['books'],result['books'])

    def test_all_bindings_point_to_existing_implementations(self):
        self.assertEqual(len(b.ENGINE_BINDINGS),26)
        for _,_,module,_,_ in b.ENGINE_BINDINGS:
            if module:
                self.assertTrue((b.ROOT/'claude-liam-signal/python/hamid'/f'{module}.py').is_file(),module)

    def test_missing_ledger_is_not_an_empty_success(self):
        with tempfile.TemporaryDirectory() as d:
            r=b.ledger(Path(d),Path(d)/'out',1700000000100)
            self.assertFalse(r['available'])
            self.assertEqual(r['records'],0)

    def test_built_health_contract(self):
        import jsonschema
        with tempfile.TemporaryDirectory() as d:
            s=b.build(output=Path(d))
            schema=json.loads((b.ROOT/'runtime/contracts/panel_health.schema.json').read_text())
            jsonschema.validate(s['panel_health'],schema)
            self.assertFalse(s['live_execution'])
            self.assertEqual([e['id'] for e in s['engines']],[f'E{i:02d}' for i in range(26)])


if __name__=='__main__': unittest.main()
