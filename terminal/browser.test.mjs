// Run by GitHub Actions. Fixtures stay in memory and are never deployed.
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {spawn} from 'node:child_process';
const server=spawn('python',['-m','http.server','8765','--bind','127.0.0.1'],{stdio:'ignore'});
let browser;
try {
  for(let i=0;i<40;i++){try{if((await fetch('http://127.0.0.1:8765/terminal/')).ok)break;}catch{}await new Promise(r=>setTimeout(r,250));}
  browser=await chromium.launch();
  const page=await browser.newPage({viewport:{width:1440,height:1000},serviceWorkers:'block'}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const snapshot=JSON.parse(await fs.readFile('terminal/data/snapshot.json','utf8'));
  snapshot.feeds.scan.data.signals = [{sym:'TSLABUSDT'}, {sym:'CAPUSDT'}];
  snapshot.feeds.hamid.data.quote_book={markets:{
    BTCUSDT:'OKX swap', TSLABUSDT:'Binance spot', CAPUSDT:'MEXC spot'
  }};
  const trade={sym:'TESTUSDT',book:'hamid',dir:'LONG',entry:100,sl:99,tp1:102,R:2,outcome:'tp',closed:Date.now(),mode:'paper'};
  snapshot.ledger.available=true;snapshot.ledger.records=1;snapshot.ledger.pages=[{url:'history/0000000000000000.json',count:1,books:['hamid'],symbols:['TESTUSDT']}];
  await page.route('**/data/snapshot.json',r=>r.fulfill({json:snapshot}));
  await page.route('**/history/0000000000000000.json',r=>r.fulfill({json:[trade]}));
  const candles=Array.from({length:200},(_,i)=>[1700000000000+i*3600000,'100','103','98',String(100+i/100),'1000']);
  await page.route('https://www.okx.com/api/v5/market/candles?**',r=>r.fulfill({json:{code:'0',data:candles.slice().reverse()}}));
  await page.route('https://www.okx.com/api/v5/market/tickers?**',r=>r.fulfill({json:{code:'0',data:[{instId:'BTC-USDT-SWAP',last:'65432.123',ts:String(Date.now())}]}}));
  await page.route('https://api.bitget.com/**',r=>r.fulfill({json:{code:'00000',data:[]}}));
  await page.route('https://liam-market-quotes.phoenix-hamid-2026.workers.dev/**',r=>r.fulfill({json:{
    quotes:[{symbol:'CAPUSDT', price:0.01234, at:Date.now(), venue:'MEXC spot'},
      {symbol:'BTCUSDT',price:70000,at:Date.now(),venue:'Bitunix futures'}]
  }}));
  await page.routeWebSocket(/wss:\/\//,ws=>ws.close());
  await page.route('https://data-api.binance.vision/**',r=>r.fulfill({json:candles}));
  await page.route('https://data-api.binance.vision/api/v3/ticker/24hr?**',r=>r.fulfill({json:[
    {symbol:'TSLABUSDT',lastPrice:'234.56',closeTime:Date.now()},
    {symbol:'CAPUSDT',lastPrice:'789',closeTime:Date.now()}
  ]}));
  await page.goto('http://127.0.0.1:8765/terminal/');
  await page.locator('.metric').first().waitFor();
  for(const route of ['signals','agents','learning','strategy','health','market','history','overview']) {
    await page.locator(`nav a[data-view="${route}"]`).click();
    await page.locator(`nav a[data-view="${route}"].active`).waitFor();
    assert.equal(await page.locator('.error-box').count(),0,route);
    if(route==='signals') {
      await page.locator('[data-market-quote="TSLABUSDT"]').first().getByText('234.56',{exact:true}).waitFor();
      await page.locator('[data-market-quote="CAPUSDT"]').first().getByText('0.01234',{exact:true}).waitFor();
    }
    if(route==='agents')assert.equal(await page.locator('.agent-card').count(),26);
    if(route==='market'){
      await page.locator('#chart canvas').first().waitFor();
      await page.locator('#chart-quote').getByText('65,432.123',{exact:true}).waitFor();
    }
    if(route==='history'){
      await page.locator('#history-table').getByText('TEST',{exact:false}).first().waitFor();
      const download=page.waitForEvent('download');await page.locator('#history-export').click();assert.ok((await download).suggestedFilename().endsWith('.csv'));
    }
  }
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'mobile page overflow');
  await page.screenshot({path:'terminal-mobile.png',fullPage:true});
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:'terminal-desktop.png',fullPage:true});
  await page.route('**/data/snapshot.json',r=>r.fulfill({status:503,body:'unavailable'}));
  await page.locator('#refresh').click();await page.locator('#connection.error').waitFor();
  assert.ok(await page.locator('.metric').count()>0,'previous snapshot remains visible with error');
  await page.reload();await page.getByText('داده‌های پنل دریافت نشد.',{exact:true}).waitFor();
  assert.equal(await page.locator('.metric').count(),0,'no fabricated data on initial failure');
  assert.deepEqual(errors,[]);
  console.log('PASS: 8 routes, 26 bindings, chart, history, export, mobile layout, cached and initial failures');
  // A visitor of the classic panel can already have its root worker active.
  // Reproduce a cache-poisoned snapshot response, then verify scope takeover.
  await fs.writeFile('terminal-legacy-test-sw.js', `self.addEventListener('install',()=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));self.addEventListener('fetch',e=>{if(e.request.url.includes('snapshot.json'))e.respondWith(new Response('{"stale_legacy_cache":true}',{headers:{'Content-Type':'application/json'}}));});`);
  const migration=await browser.newPage();
  await migration.goto('http://127.0.0.1:8765/terminal/lib.mjs');
  await migration.evaluate(async()=>{await navigator.serviceWorker.register('/terminal-legacy-test-sw.js',{scope:'/'});await navigator.serviceWorker.ready;});
  await migration.waitForFunction(()=>!!navigator.serviceWorker.controller);
  await migration.goto('http://127.0.0.1:8765/terminal/');
  await migration.waitForFunction(()=>navigator.serviceWorker.controller?.scriptURL.endsWith('/terminal/sw.js'));
  await migration.locator('.metric').first().waitFor();
  assert.equal(await migration.locator('#connection.error').count(),0);
  const swData=await migration.evaluate(async()=>await (await fetch('data/snapshot.json')).json());
  assert.equal(swData.schema_version,1);
  assert.equal(swData.stale_legacy_cache,undefined);
  console.log('PASS: classic root service-worker migration and uncached terminal snapshot');
  await fs.rm('terminal-legacy-test-sw.js');
} finally {await browser?.close();server.kill();}
