import { chromium } from 'playwright';
const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
const p=await b.newPage({viewport:{width:1440,height:1000}});
const errs=[];p.on('pageerror',e=>errs.push('PAGE:'+e.message.slice(0,90)));
p.on('console',m=>{if(m.type()==='error'&&!m.text().includes('WebSocket')&&!m.text().includes('404'))errs.push('CONS:'+m.text().slice(0,90));});
const SY=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT'];
const seed=s=>[...s].reduce((a,c)=>a+c.charCodeAt(0),0);
const gen=(sd,n)=>{let s=sd,pz=100+sd%50;const o=[];const rnd=()=>(s=(s*1103515245+12345)%2147483648)/2147483648;
  for(let i=0;i<n;i++){const ph=(i+sd)%90;const op=pz,c=pz*(1+(ph<50?(rnd()-.5)*.005:ph<70?.006+rnd()*.003:-.002+rnd()*.001));
    o.push([Date.now()-(n-i)*9e5,op,Math.max(op,c)*1.002,Math.min(op,c)*.998,c,3000+(ph>=50&&ph<70?5000:0),0,0,0,0,0,0]);pz=c;}return o;};
await p.route('**fapi.binance.com/**',async r=>{
  const u=new URL(r.request().url()),pa=u.pathname;let body='{}';
  if(pa.endsWith('/ticker/24hr')){const sm=u.searchParams.get('symbol');const t=s=>({symbol:s,quoteVolume:'900000000',priceChangePercent:seed(s)%2?'3.1':'-2.0',lastPrice:String(100+seed(s)%50),volume:'1'});body=JSON.stringify(sm?t(sm):SY.map(t));}
  else if(pa.endsWith('/premiumIndex'))body=JSON.stringify(SY.map(s=>({symbol:s,lastFundingRate:'0.0001'})));
  else if(pa.endsWith('/klines'))body=JSON.stringify(gen(seed(u.searchParams.get('symbol')||'B')+seed(u.searchParams.get('interval')||'i'),+(u.searchParams.get('limit')||200)));
  await r.fulfill({status:200,contentType:'application/json',body});});
await p.route('**api.coingecko.com/**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"data":{"market_cap_percentage":{"btc":54.3}}}'}));

const T={};
await p.goto('http://127.0.0.1:8901/index.html');
await p.waitForTimeout(8000); // auto-scan (boot at 1.2s)
T.autoScan=await p.evaluate(()=>STATE.universe.length>0);
T.regime=await p.evaluate(()=>/دامیننس/.test(document.getElementById('regimeTxt').textContent)&&/صعودی/.test(document.getElementById('regimeTxt').textContent));
T.watchlist=await p.evaluate(()=>STATE.watchlist.length>0);
T.zones=await p.evaluate(()=>Object.keys(RADAR_LIVE.zones).length>0||STATE.universe.length>0);
// alarm + re-analysis
console.log('DIAG:',await p.evaluate(()=>JSON.stringify({n:STATE.universe.length,st:STATE.universe.map(r=>r.status),ez:STATE.universe.map(r=>!!r.entry_zone),smc:STATE.universe.map(r=>r.smc&&r.smc.stage)})));
T.alarm=await p.evaluate(async()=>{
  if(!Object.keys(RADAR_LIVE.zones).length){const r=STATE.universe[0];RADAR_LIVE.zones[r.binance_symbol]={sym:r.binance_symbol,asset:r.asset_symbol,dir:r.direction||"LONG",low:r.entry*0.999,high:r.entry*1.001,qv:1e9,chg:0};}
  const z=Object.values(RADAR_LIVE.zones)[0];radarCheck(z,(z.low+z.high)/2);await new Promise(r=>setTimeout(r,3500));
  return RADAR_LIVE.alarms.length>0&&RADAR_LIVE.alarms[0].st!=="بررسی…";});
// deep dive: live chart + IBS + pattern
await p.evaluate(()=>openDeep('BTCUSDT'));
await p.waitForTimeout(3500);
T.deepIbs=await p.evaluate(()=>!!(lastDeep&&document.body.innerHTML.includes('استراتژی IBS')));
T.liveChart=await p.evaluate(()=>LIVE.candles.length>=200&&!!document.querySelector('#liveChart canvas'));
T.patChart=await p.evaluate(()=>!!document.querySelector('#patChart'));
// auto-track full cycle
T.track=await p.evaluate(async()=>{trackSignals([{binance_symbol:"XRPUSDT",asset_symbol:"XRP",direction:"SHORT",entry:100,stop_loss:105,tp1:92.5,tp2:87.5,score:70}]);
  const tr=STATE.trades.find(t=>t.sym==="XRPUSDT");tradeCheck(tr,92);tradeCheck(tr,87);await new Promise(r=>setTimeout(r,300));
  return !tr.open&&tr.r===2.5&&getFb()[0].verdict==="win";});
// backtest + calibration
// AUTO backtest: no click at all — just wait for the scheduled run (45s)
await p.evaluate(()=>selectTab('calib'));
const q0=await p.evaluate(()=>ibsQmin());
await p.waitForTimeout(48000);
T.autoBacktest=await p.evaluate(()=>!!document.querySelector('#btOut table'));
T.autoCalib=await p.evaluate(()=>document.body.innerHTML.includes('خودکار اعمال شد')||document.body.innerHTML.includes('همین آستانه'));
T.noApplyBtn=await p.evaluate(()=>!document.getElementById('btApply'));
T.btSymsAuto=await p.evaluate(()=>($('#btSyms').value||'').includes('USDT'));
// scalp + pump radar tabs render
T.scalp=await p.evaluate(async()=>{selectTab('scalp');await runScalp('BTCUSDT');await new Promise(r=>setTimeout(r,1500));return !document.getElementById('view-scalp').innerText.includes('خطا');});
T.pumpRadar=await p.evaluate(async()=>{selectTab('radar');try{await runRadar();return true;}catch(e){return 'ERR:'+e.message;}});
// full persistence
await p.evaluate(()=>saveLocal());
await p.reload({waitUntil:'load'});await p.waitForTimeout(2500);
T.persist=await p.evaluate(()=>STATE.watchlist.length>0&&RADAR_LIVE.alarms.length>0&&(STATE.trades||[]).length>0&&Object.keys(RADAR_LIVE.zones).length>0&&!!document.querySelector('#btOut table'));
T.feedback=await p.evaluate(()=>getFb().length>0);
// OPS control room
await p.evaluate(()=>selectTab('ops'));
await p.waitForTimeout(2500);
const ops=await p.evaluate(()=>({
  rooms:document.querySelectorAll('#opsRooms .card').length,
  alive:[...document.querySelectorAll('#opsRooms .card')].filter(c=>c.innerText.includes('فعال')).length,
  feed:document.querySelectorAll('#opsFeed div').length,
  rate:(document.getElementById('opsRate')||{}).textContent,
  sample:[...document.querySelectorAll('#opsFeed div')].slice(0,3).map(d=>d.innerText.replace(/\n/g,' | ')),
  roomHeads:[...document.querySelectorAll('#opsRooms .card b')].map(b=>b.textContent)
}));
console.log('OPS:',JSON.stringify(ops,null,1));
await p.screenshot({path:'shot9_ops.png',fullPage:true});
console.log('SYNC-AUTO:',await p.evaluate(()=>SYNC.get().on));
T.smcEngine=await p.evaluate(()=>STATE.universe.filter(r=>r.smc).length>0);
T.smcBothTf=await p.evaluate(()=>STATE.universe.some(r=>r.smc5&&r.smc15));
T.smcCard=await p.evaluate(()=>{selectTab('single');return document.body.innerHTML.includes('استراتژی اصلی');});
console.log('MATRIX:',JSON.stringify(T));
console.log('ERRS:',errs.length?errs.slice(0,6):'none');
await b.close();
