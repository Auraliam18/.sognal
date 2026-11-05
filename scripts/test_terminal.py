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
            feeds = {k: {"generated": 1, "path": k, "state": "fresh", "data": data}
                     for k, data in [("radar", radar), ("delivery", {"sent": sent})]}
            return {e["id"]: e["own_state"] for e in
                    b.engine_packets(b.ROOT, feeds, {"available": True, "source": "fixture"}, 1)}
        packet = {"universe_n": 30, "coins": [], "recommendation": [], "verdict": None}
        result = own(packet, [{"kind": "trade_signal", "tg_msg_id": 8}])
        self.assertEqual((result["E12"], result["E25"]), ("fresh", "partial"))
        result = own(dict(packet, universe_n=0), [{"kind": "watch_alert", "tg_msg_id": 8}])
        self.assertEqual((result["E12"], result["E25"]), ("partial", "fresh"))

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
