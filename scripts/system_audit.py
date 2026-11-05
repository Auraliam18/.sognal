"""Execute every offline Python module in a separate process; retain evidence.

Run on a disposable Actions checkout with no secrets or write credentials.
The explicitly excluded script sends an actual Telegram pattern message.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PY=ROOT/'claude-liam-signal/python'
OUT=ROOT/'audit-results'
OUT.mkdir(exist_ok=True)
env=dict(os.environ, PYTHONUTF8='1', LIVE_EXECUTION='false', PYTHONPATH=os.pathsep.join([str(PY),str(ROOT)]))
for key in list(env):
    if any(word in key.upper() for word in ('TOKEN','API_KEY','CHAT_ID','SECRET')):
        env.pop(key)
modules=['test_sources', 'test_jsonl_store', 'hamid.selfcheck']
modules += ['hamid.'+p.stem for p in sorted((PY/'hamid').glob('test_*.py')) if p.stem != 'test_signal_pattern']
modules += ['freebuff.'+p.stem for p in sorted((ROOT/'freebuff').glob('test_*.py'))]
results=[]
for module in modules:
    started=time.monotonic()
    try:
        proc=subprocess.run([sys.executable,'-m',module],cwd=PY,env=env,
                            capture_output=True,text=True,encoding='utf-8',timeout=180)
        code, log=proc.returncode, proc.stdout+'\n'+proc.stderr
    except subprocess.TimeoutExpired as e:
        code,log=124,'Timeout after 180 seconds\n'+str(e.stdout or '')+str(e.stderr or '')
    (OUT/(module+'.log')).write_text(log,encoding='utf-8')
    row=dict(module=module,exit_code=code,seconds=round(time.monotonic()-started,2))
    results.append(row)
    print(json.dumps(row),flush=True)
    if code:
        print(log[-5000:],flush=True)
report=dict(generated=int(time.time()*1000),sha=os.environ.get('GITHUB_SHA'),tests=results,
            passed=sum(r['exit_code']==0 for r in results),failed=sum(r['exit_code']!=0 for r in results),
            excluded={'hamid.test_signal_pattern':'Real external message sender; delivery covered by mocked tests'},
            live_execution=False)
(OUT/'tests.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(f"AUDIT: {report['passed']} passed; {report['failed']} failed",flush=True)
sys.exit(bool(report['failed']))
