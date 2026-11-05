"""Read-only baseline for comparing monitored production data with test evidence."""
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'claude-liam-signal/python'))
from hamid import conformance

out=ROOT/'audit-results'
out.mkdir(exist_ok=True)
report=conformance.check()
report['sha']=os.environ.get('GITHUB_SHA')
report['kind']='production checkout observation; independent of offline test pass/fail'
report['contracts']={p.name:('empty' if not p.read_text(encoding='utf-8').strip() else 'present')
                     for p in sorted((ROOT/'runtime/contracts').glob('*.json'))}
report['coverage_limits']=[
    'A fresh engine data binding is not proof of an independently running LLM agent.',
    'Historical full decision packets (dominance, news, committee, 5m execution) are not complete enough for end-to-end replay.',
    'Current-universe component backtests are not a historical Top-200 walk-forward study.',
    'Actual order placement and real Telegram messages are intentionally not exercised.',
    'Existing historical ledgers are preserved; corrected scoring applies prospectively.'
]
(out/'monitored-baseline.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'conformance_ok':report['ok'],'violations':report['violations'],
                  'empty_contracts':[k for k,v in report['contracts'].items() if v=='empty']},ensure_ascii=False))
