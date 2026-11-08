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

test('exchange quotes expire and malformed or future prices cannot be displayed',async()=>{
  const {marketQuote}=await import('./lib.mjs');
  const t=1700000000000;
  assert.equal(marketQuote('BTCUSDT','1.25',t,'Bitunix futures',t).price,1.25);
  for(const price of [null,true,'','Infinity','0',-1]) assert.equal(marketQuote('BTCUSDT',price,t,'Bitunix futures',t),null);
  for(const at of [t-15001,t+2001,undefined,0]) assert.equal(marketQuote('BTCUSDT','1',at,'OKX swap',t),null);
});

test('MEXC aggregate ticker reads the original exchange time and exact symbol',async()=>{
  const {mexcTickers}=await import('./lib.mjs');
  const sample=Uint8Array.from([48,128,208,149,255,188,49,178,19,18,10,16,10,7,66,84,67,85,83,68,84,18,5,49,46,50,51,52]);
  const ticks=[];mexcTickers(sample.buffer,(...row)=>ticks.push(row));
  assert.deepEqual(ticks,[['BTCUSDT','1.234',1700000000000]]);
  assert.throws(()=>mexcTickers(sample.slice(0,-1).buffer,()=>{}));
});

test('a same-market REST refresh cannot displace a fresh WebSocket trade',async()=>{
  const {livePrices}=await import('./lib.mjs');
  const originalSocket=globalThis.WebSocket, originalFetch=globalThis.fetch;
  const sockets=[], restAt=Math.floor(Date.now()/1000)*1000;
  globalThis.WebSocket=class {static OPEN=1;constructor(url){this.url=url;sockets.push(this);}close(){}};
  globalThis.fetch=async url=>{
    if(String(url).endsWith('/trading_pairs')) return Response.json({code:0,data:[{symbol:'BTCUSDT',symbolStatus:'OPEN',quote:'USDT'}]});
    const bitunix=String(url).includes('fapi.bitunix');
    return Response.json(bitunix?{code:0,data:[{symbol:'BTCUSDT',lastPrice:'100'}]}:[],
      {headers:{date:new Date(restAt).toUTCString()}});
  };
  const feed=livePrices(()=>{},{direct:true});
  try {
    feed.watch(['BTCUSDT','LITUSDT']);
    sockets.find(s=>s.url.includes('bitunix')).onmessage({data:JSON.stringify({
      ch:'tickers',ts:restAt-1000,data:[{s:'BTCUSDT',la:'101'},{s:'LITUSDT',la:'0.57'}]
    })});
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(feed.best('BTCUSDT',restAt).price,101);
    assert.equal(feed.best('LITUSDT',restAt,'Bitunix futures'),null);
    assert.equal(feed.best('BTCUSDT',restAt).transport,'websocket');
    assert.equal(feed.best('BTCUSDT',restAt+14500).transport,'rest');
    assert.equal(feed.best('BTCUSDT',restAt+15001),null);
    feed.watch(['BTCUSDT','LITUSDT'],{BTCUSDT:'MEXC spot'});
    assert.equal(feed.best('BTCUSDT',restAt),null);
    assert.equal(feed.best('BTCUSDT',restAt,'Bitunix futures').price,101);
  } finally {feed.close();globalThis.WebSocket=originalSocket;globalThis.fetch=originalFetch;}
});

test('a stale OKX listing subscribes to live trades despite an obsolete Bitunix ticker',async()=>{
  const {livePrices}=await import('./lib.mjs');
  const originalSocket=globalThis.WebSocket,originalFetch=globalThis.fetch;
  let openSocket;
  const socketReady=new Promise(resolve=>{openSocket=resolve;});
  globalThis.WebSocket=class {
    static OPEN=1;
    constructor(url){if(url.includes('ws.okx.com')) openSocket(this);}
    send(raw){this.subscription=JSON.parse(raw);}
    close(){}
  };
  globalThis.fetch=async url=>{
    const path=String(url);
    if(path.endsWith('/trading_pairs')) return Response.json({code:0,data:[{symbol:'BTCUSDT',symbolStatus:'OPEN',quote:'USDT'}]});
    if(path.includes('fapi.bitunix')) return Response.json({code:0,data:[{symbol:'PUMPUSDT',lastPrice:'0.01613'}]},{headers:{date:new Date().toUTCString()}});
    if(path.includes('www.okx.com')) return Response.json({code:'0',data:[{instId:'PUMP-USDT-SWAP',last:'0.003',ts:Date.now()-60000}]});
    return Response.json([]);
  };
  const feed=livePrices(()=>{},{direct:true});
  let timeout;
  try {
    feed.watch(['PUMPUSDT']);
    const ws=await Promise.race([socketReady,new Promise((_,reject)=>{timeout=setTimeout(()=>reject(Error('no subscription')),3000);})]);
    ws.onopen();
    assert.ok(ws.subscription.args.some(r=>r.instId==='PUMP-USDT-SWAP' && r.channel==='trades'));
    assert.equal(feed.best('PUMPUSDT'),null);
    ws.onmessage({data:JSON.stringify({arg:{channel:'trades'},data:[{instId:'PUMP-USDT-SWAP',px:'0.00367',ts:String(Date.now())}]})});
    assert.equal(feed.best('PUMPUSDT').price,0.00367);
    assert.equal(feed.best('PUMPUSDT').venue,'OKX swap');
  } finally {clearTimeout(timeout);feed.close();globalThis.WebSocket=originalSocket;globalThis.fetch=originalFetch;}
});
