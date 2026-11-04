import json
from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import jsonl_store as store


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'paper' / 'closed.jsonl'
        self.path.parent.mkdir()

    def write(self, rows):
        self.path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n'
                                    for r in rows), encoding='utf-8')

    def counts(self):
        return Counter(json.dumps(r, sort_keys=True) for r in store.read(self.path))

    def test_migration_preserves_multiplicity_unicode_and_malformed(self):
        rows = [{'closed': 3, 'sym': 'آزمون'}, {'closed': 1}, {'closed': 1}]
        self.write(rows)
        with self.path.open('ab') as f:
            f.write(b'{torn\n')
        before = Counter(store.lines(self.path))
        store.migrate(self.path, force=True)
        self.assertEqual(before, Counter(store.lines(self.path)))
        self.assertEqual(3, len(store.read(self.path)))
        self.assertEqual(b'', self.path.read_bytes())
        self.assertEqual([rows[0]], store.read(self.path, 1))

    def test_old_job_overlap_and_interrupted_migration_retry(self):
        rows = [{'closed': 1}, {'closed': 1}, {'closed': 2}]
        self.write(rows)
        store.migrate(self.path, force=True)
        self.write(rows + [{'closed': 3}])
        self.assertEqual(4, len(store.read(self.path)))
        store.migrate(self.path)
        self.assertEqual(4, len(store.read(self.path)))
        self.assertFalse(store.migrate(self.path))

    def test_rollover_bounds_every_part_and_preserves_new_duplicates(self):
        row = {'closed': 1, 'sym': 'x' * 25}
        self.write([row])
        with patch.object(store, 'PART_BYTES', 100), patch.object(store, 'ROTATE_BYTES', 1):
            for _ in range(12):
                store.append(self.path, row)
            self.assertTrue(all(p.stat().st_size <= 100
                                for p in store.parts(self.path).glob('*.jsonl')))
        self.assertEqual(13, len(store.read(self.path)))

    def test_oversize_record_keeps_original(self):
        self.write([{'data': 'x' * 100}])
        original = self.path.read_bytes()
        with patch.object(store, 'PART_BYTES', 20):
            with self.assertRaises(ValueError):
                store.migrate(self.path, force=True)
        self.assertEqual(original, self.path.read_bytes())

    def test_small_and_mutable_files_keep_legacy_layout(self):
        self.path = self.path.with_name('open.jsonl')
        with patch.object(store, 'ROTATE_BYTES', 1):
            store.append(self.path, {'t': 1})
        self.assertFalse(store.parts(self.path).exists())
        self.assertEqual([{'t': 1}], store.read(self.path))

    def test_all_consumers_see_migrated_history(self):
        from hamid import paper, classify, improve
        import brain
        rows = [{'closed': 1, 'R': 1, 'outcome': 'win'},
                {'closed': 2, 'R': None, 'outcome': 'expired'}]
        self.write(rows)
        store.migrate(self.path, force=True)
        self.assertEqual(rows, brain.read(self.path))
        self.assertEqual(rows, paper._read(self.path))
        self.assertEqual(rows[:1], classify.load(self.path))
        with patch.object(improve, 'CLOSED', self.path):
            self.assertEqual(rows[:1], improve._rows())


if __name__ == '__main__':
    unittest.main()
