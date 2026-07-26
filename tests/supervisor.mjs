import { chromium } from 'playwright';
const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
const p=await b.newPage({viewport:{width:1440,height:1100}});
const errs=[];p.on('pageerror',e=>errs.push(e.message.slice(0,110)));
const SY=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','NEARUSDT'];
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
  else if(pa.endsWith('/klines'))body=JSON.stringify(gen(seed(u.searchParams.get('symbol')||'B')+seed(u.searchParams.get('interval')||'i'),+(u.searchParams.get('limit')||200)));
  await r.fulfill({status:200,contentType:'application/json',body});});
await p.route('**api.coingecko.com/**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"data":{"market_cap_percentage":{"btc":54.3}}}'}));
// A websocket that CANNOT connect — the failure the supervisor must survive
await p.addInitScript(()=>{window.WebSocket=function(){const w={readyState:3,close(){}};setTimeout(()=>w.onerror&&w.onerror(),50);setTimeout(()=>w.onclose&&w.onclose(),80);return w;};});
await p.goto('http://127.0.0.1:8901/index.html');
await p.waitForTimeout(9000);
// force a watched zone + an open paper trade, then let the supervisor cope
await p.evaluate(()=>{
  const r=STATE.universe[0];
  RADAR_LIVE.zones[r.binance_symbol]={sym:r.binance_symbol,asset:r.asset_symbol,dir:'LONG',low:1,high:1e9,qv:1e9,chg:0};
  trackSignals([{binance_symbol:'ETHUSDT',asset_symbol:'ETH',direction:'LONG',entry:100,stop_loss:95,tp1:110,tp2:120,score:70,
    smc:{dir:'LONG',rr:2,depth:50,visits:2,tf:'15m'}}]);
  const t=STATE.trades.find(x=>x.sym==='ETHUSDT');t.feat={bias:1,rr:0.5,depth:0.25,fvg:1,level:0,channel:1,visits2:1,btc:0,ibs:0,ext:0};
});
await p.waitForTimeout(26000);   // supervisor ticks every 5s
const st=await p.evaluate(()=>({
  wsDead:!RADAR_LIVE.ws, polling:SUP.polling, runs:SUP.runs,
  repairs:SUP.repairs.map(r=>r.what), ticks:OPS.ticks,
  health:(SUP.health||[]).map(h=>h.name+':'+(h.ok?'ok':'DOWN')),
  openTrades:(STATE.trades||[]).filter(t=>t.open).length,
}));
console.log('SUPERVISOR:',JSON.stringify(st,null,1));
// now prove learning fires: close the trade via the fallback price path
const learned=await p.evaluate(async()=>{
  const t0=STATE.trades.find(x=>x.sym==='ETHUSDT');
  const closedByFallback={closed:t0&&!t0.open,r:t0&&t0.r,learned:t0&&!!t0.learned};
  const before=confN();
  trackSignals([{binance_symbol:'SOLUSDT',asset_symbol:'SOL',direction:'SHORT',entry:200,stop_loss:210,tp1:180,tp2:170,score:70,
    smc:{dir:'SHORT',rr:2,depth:60,visits:2,tf:'5m'}}]);
  const t=STATE.trades.find(x=>x.sym==='SOLUSDT'&&x.open);
  t.feat={bias:1,rr:0.5,depth:0.5,fvg:1,level:1,channel:1,visits2:1,btc:1,ibs:0,ext:0};
  tradeCheck(t,179); tradeCheck(t,169);
  await new Promise(r=>setTimeout(r,400));
  return{closedByFallback,before,after:confN(),closed:!t.open,r:t.r,
    w:Object.fromEntries(Object.entries(confW()).map(([k,v])=>[k,+v.toFixed(3)]))};
});
console.log('LEARNING:',JSON.stringify(learned));
await p.screenshot({path:'shot11_sup.png',fullPage:true});
console.log('ERRS:',errs.length?errs.slice(0,4):'none');
await b.close();
