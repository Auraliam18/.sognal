"""Real local Git race: bounded shallow fetch preserves both writers."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import fetch_for_merge
import resolve_brain_conflicts as resolver


class PublishContract(unittest.TestCase):
    def test_racing_shallow_writers_keep_both_commits(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            def git(cwd,*args):
                return subprocess.run(['git',*args],cwd=cwd,check=True,capture_output=True,text=True).stdout.strip()
            origin=root/'origin.git'
            git(root,'init','--bare',str(origin))
            seed=root/'seed'
            git(root,'clone',origin.as_uri(),str(seed))
            git(seed,'config','user.email','audit@example.invalid')
            git(seed,'config','user.name','Audit fixture')
            git(seed,'checkout','-b','main')
            (seed/'base').write_text('base')
            git(seed,'add','.')
            git(seed,'commit','-m','base')
            git(seed,'push','origin','main')
            worker=root/'worker'
            git(root,'clone','--depth=1','--branch','main',origin.as_uri(),str(worker))
            git(worker,'config','user.email','audit@example.invalid')
            git(worker,'config','user.name','Audit fixture')
            (worker/'local').write_text('unpublished result')
            git(worker,'add','.')
            git(worker,'commit','-m','local result')
            (seed/'remote').write_text('other result')
            git(seed,'add','.')
            git(seed,'commit','-m','other result')
            git(seed,'push','origin','main')
            fetch_for_merge.fetch('main',worker)
            git(worker,'merge','--no-edit','origin/main')
            self.assertEqual((worker/'local').read_text(),'unpublished result')
            self.assertEqual((worker/'remote').read_text(),'other result')

    def test_failed_fetch_cannot_be_treated_as_published(self):
        with patch.object(fetch_for_merge.subprocess,'run',side_effect=subprocess.TimeoutExpired('git',180)):
            with self.assertRaises(subprocess.TimeoutExpired):
                fetch_for_merge.fetch('main')

    def test_conflict_snapshot_prefers_actual_newer_timestamp(self):
        with tempfile.TemporaryDirectory() as d, patch.object(resolver,'ROOT',Path(d)):
            target=Path(d)/'signals/latest.json'
            target.parent.mkdir()
            with patch.object(resolver,'_stage',side_effect=lambda stage,path:json.dumps({'generated':100 if stage==2 else 200,'value':stage})):
                resolver.latest_snapshot('signals/latest.json')
            self.assertEqual(json.loads(target.read_text())['value'],3)


if __name__=='__main__':
    unittest.main()
