import { chromium } from 'playwright';
const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
const p=await b.newPage({viewport:{width:1440,height:1200}});
const errs=[];p.on('pageerror',e=>errs.push(e.message.slice(0,110)));
const SY=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','NEARUSDT','ADAUSDT'];
const seed=s=>[...s].reduce((a,c)=>a+c.charCodeAt(0),0);
const gen=(sd,n)=>{let s=sd,p=100+sd%50;const o=[];const rnd=()=>(s=(s*1103515245+12345)%2147483648)/2147483648;
  for(let i=0;i<n;i++){const ph=(i+sd)%110;let d;
    if(ph<45)d=-0.005+rnd()*0.002;else if(ph<60)d=0.010;else if(ph<72)d=-0.013;
    else if(ph<82)d=0.012;else if(ph<90)d=-0.011;else if(ph<98)d=0.011;else d=-0.014;
    const op=p,c=p*(1+d);o.push([Date.now()-(n-i)*9e5,op,Math.max(op,c)*1.002,Math.min(op,c)*0.998,c,4000,0,0,0,0,0,0]);p=c;}
  return o;};
await p.route('**fapi.binance.com/**',async r=>{
  const u=new URL(r.request().url()),pa=u.pathname;let body='{}';
  if(pa.endsWith('/ticker/24hr')){const sm=u.searchParams.get('symbol');const t=s=>({symbol:s,quoteVolume:'900000000',priceChangePercent:'-3.0',lastPrice:String(100+seed(s)%50),volume:'1'});body=JSON.stringify(sm?t(sm):SY.map(t));}
  else if(pa.endsWith('/ticker/price'))body=JSON.stringify(SY.map(s=>({symbol:s,price:String(100+seed(s)%50)})));
  else if(pa.endsWith('/premiumIndex'))body=JSON.stringify(SY.map(s=>({symbol:s,lastFundingRate:'0.0001'})));
  else if(pa.includes('/openInterestHist'))body=JSON.stringify([{sumOpenInterest:'1000'},{sumOpenInterest:'1080'}]);
  else if(pa.includes('/globalLongShortAccountRatio'))body=JSON.stringify([{longShortRatio:'2.45'}]);
  else if(pa.includes('/takerlongshortRatio'))body=JSON.stringify([{buySellRatio:'0.72'}]);
  else if(pa.endsWith('/klines'))body=JSON.stringify(gen(seed(u.searchParams.get('symbol')||'B')+seed(u.searchParams.get('interval')||'i'),+(u.searchParams.get('limit')||200)));
  await r.fulfill({status:200,contentType:'application/json',body});});
await p.route('**alternative.me/**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"data":[{"value":"81","value_classification":"Extreme Greed"}]}'}));
await p.route('**api.coingecko.com/**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"data":{"market_cap_percentage":{"btc":54.3}}}'}));
// combined-stream websocket stub: replays closed candles so the watcher must react
await p.addInitScript(({SY})=>{
  const Real=window.WebSocket;
  window.WebSocket=function(url){
    if(!String(url).includes('/stream?streams='))return new Real(url);
    const ws={readyState:1,close(){clearInterval(this._t);}};
    setTimeout(()=>ws.onopen&&ws.onopen(),200);
    let i=0;
    ws._t=setInterval(()=>{
      i++;const s=SY[i%SY.length],tf=i%2?'5m':'15m';
      const base=100+[...s].reduce((a,c)=>a+c.charCodeAt(0),0)%50;
      const c=base*(1-0.02);
      ws.onmessage&&ws.onmessage({data:JSON.stringify({stream:s.toLowerCase()+'@kline_'+tf,
        data:{k:{s,i:tf,t:Date.now(),o:String(base),h:String(base*1.001),l:String(c*0.999),c:String(c),v:'5000',x:true}}})});
    },300);
    return ws;};
},{SY});
await p.goto('http://127.0.0.1:8901/index.html');
await p.waitForTimeout(20000);
const st=await p.evaluate(()=>({
  subs:WATCHER.subs.length, ready:WATCHER.ready, wsUp:!!WATCHER.ws,
  evals:WATCHER.evals, found:WATCHER.found, buffers:Object.keys(WATCHER.buf).length,
  intel:INTEL.snap, bias:intelBias(),
  supRuns:SUP.runs, health:(SUP.health||[]).map(h=>h.name+':'+(h.ok?'ok':'DOWN')),
  signals:STATE.signals.length, trades:(STATE.trades||[]).length
}));
console.log('WATCH:',JSON.stringify(st,null,1));
await p.evaluate(()=>selectTab('ops'));
await p.waitForTimeout(1500);
await p.screenshot({path:'shot12_watch.png',fullPage:true});
console.log('ERRS:',errs.length?errs.slice(0,4):'none');
await b.close();
