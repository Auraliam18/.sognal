import test from 'node:test';
import assert from 'node:assert/strict';
import {escapeHTML,freshness,validateSnapshot,filterRows,historyPages,engineState,csv} from './lib.mjs';
test('missing, old and future data never get a fresh badge',()=>{
  assert.equal(freshness(null),'missing');
  assert.equal(freshness({data:{},ttl:60},1700000000000),'unknown');
  assert.equal(freshness({data:{},generated:1600000000000,ttl:60},1700000000000),'stale');
  assert.equal(freshness({data:{},generated:1800000000000,ttl:60},1700000000000),'clock_error');
});
test('untrusted feed values cannot inject markup or spreadsheet formulas',()=>{
  assert.equal(escapeHTML('<img onerror="bad">'),'&lt;img onerror=&quot;bad&quot;&gt;');
  assert.ok(csv([{sym:'=EVIL()'}]).includes("'=EVIL()"));
});
test('history filtering preserves repeated records and isolates books',()=>{
  const r={sym:'BTCUSDT',book:'hamid'};
  assert.equal(filterRows([r,r,{...r,book:'practice'}],'hamid','btc').length,2);
  assert.equal(historyPages([{books:['hamid'],symbols:['BTCUSDT']},{books:['practice'],symbols:['BTCUSDT']}],'hamid','btc').length,1);
});
test('bad snapshots and archive traversal are rejected',()=>{
  const s={schema_version:1,live_execution:false,generated:1700000000000,feeds:{},ledger:{records:0,pages:[]},engines:Array.from({length:26},(_,i)=>({id:`E${String(i).padStart(2,'0')}`}))};
  assert.equal(validateSnapshot(s),s);
  assert.throws(()=>validateSnapshot({...s,live_execution:true}));
  assert.throws(()=>validateSnapshot({...s,ledger:{records:1,pages:[{count:1,url:'../secret'}]}}));
});
test('stale conformance failures remain stale, not current assertions',()=>{
  assert.equal(engineState({feed:'conformance',missing:[]},{conformance:{data:{ok:false},generated:1600000000000,ttl:60}},{},1700000000000),'stale');
});

test('a newly rendered ledger preserves role gaps and the reconciliation clock',()=>{
  const now=1700000000000, ledger={available:true,computed_at:now};
  const role={feed:'ledger',missing:['reconciliation'],evidence:{},observed_at:now,evidence_ttl:3600};
  assert.equal(engineState(role,{},ledger,now),'partial');
  assert.equal(engineState({...role,missing:[],observed_at:now-4000000},{},ledger,now),'stale');
});
