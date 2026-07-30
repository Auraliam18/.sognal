import { chromium } from 'playwright';
const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
const p=await b.newPage({viewport:{width:1440,height:1200}});
const errs=[];p.on('pageerror',e=>errs.push(e.message.slice(0,110)));
const SY=Array.from({length:20},(_,i)=>`SYM${i}USDT`);
const seed=s=>[...s].reduce((a,c)=>a+c.charCodeAt(0),0);
// realistic structured tape so setups genuinely form
const gen=(sd,n)=>{let s=sd,p=50+sd%150;const o=[];const rnd=()=>(s=(s*1103515245+12345)%2147483648)/2147483648;
  for(let i=0;i<n;i++){const ph=(i+sd)%130;let d;
    if(ph<48)d=-0.004+rnd()*0.0018;else if(ph<62)d=0.009+rnd()*0.002;
    else if(ph<76)d=-0.012-rnd()*0.003;else if(ph<88)d=0.011+rnd()*0.002;
    else if(ph<98)d=-0.010;else if(ph<112)d=0.010;else d=-0.013;
    const op=p,c=p*(1+d);o.push([Date.now()-(n-i)*9e5,op,Math.max(op,c)*(1+rnd()*0.003),Math.min(op,c)*(1-rnd()*0.003),c,4000,0,0,0,0,0,0]);p=c;}
  return o;};
let tgCalls=0;
await p.route('**api.telegram.org/**',r=>{tgCalls++;return r.fulfill({status:200,contentType:'application/json',body:'{"ok":true}'});});
await p.route('**fapi.binance.com/**',async r=>{
  const u=new URL(r.request().url()),pa=u.pathname;let body='{}';
  if(pa.endsWith('/ticker/24hr')){const sm=u.searchParams.get('symbol');const t=s=>({symbol:s,quoteVolume:String(9e8-seed(s)*1e5),priceChangePercent:'-2.0',lastPrice:String(50+seed(s)%150),volume:'1'});body=JSON.stringify(sm?t(sm):SY.map(t));}
  else if(pa.endsWith('/ticker/price'))body=JSON.stringify(SY.map(s=>({symbol:s,price:String(50+seed(s)%150)})));
  else if(pa.endsWith('/premiumIndex'))body=JSON.stringify(SY.map(s=>({symbol:s,lastFundingRate:'0.0001'})));
  else if(pa.includes('/openInterestHist'))body=JSON.stringify([{sumOpenInterest:'1000'},{sumOpenInterest:'1080'}]);
  else if(pa.includes('/globalLongShortAccountRatio'))body=JSON.stringify([{longShortRatio:'2.45'}]);
  else if(pa.includes('/takerlongshortRatio'))body=JSON.stringify([{buySellRatio:'0.72'}]);
  else if(pa.endsWith('/klines'))body=JSON.stringify(gen(seed(u.searchParams.get('symbol')||'B')+seed(u.searchParams.get('interval')||'i'),+(u.searchParams.get('limit')||200)));
  await r.fulfill({status:200,contentType:'application/json',body});});
await p.route('**alternative.me/**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"data":[{"value":"81","value_classification":"Extreme Greed"}]}'}));
await p.route('**api.coingecko.com/**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"data":{"market_cap_percentage":{"btc":54.3,"usdt":5.12}}}'}));
await p.goto('http://127.0.0.1:8901/index.html');
await p.waitForTimeout(3000);
// connect through the banner, exactly as the user will
await p.waitForSelector('#tgSave',{timeout:15000});
await p.fill('#tgTok','111:TESTTOKEN'); await p.fill('#tgChat','999');
await p.click('#tgSave'); await p.waitForTimeout(1500);
console.log('BANNER-CONNECTED:', await p.evaluate(()=>TG.on()));
// prove queued delivery survives an outage
await p.route('**api.telegram.org/**',r=>r.abort());
await p.evaluate(()=>TG.send('outage test'));
await p.waitForTimeout(500);
const q1=await p.evaluate(()=>TG.pending());
await p.unroute('**api.telegram.org/**');
await p.route('**api.telegram.org/**',r=>{tgCalls++;return r.fulfill({status:200,contentType:'application/json',body:'{"ok":true}'});});
await p.evaluate(()=>TG.flush()); await p.waitForTimeout(800);
console.log('QUEUE: held',q1,'-> after retry',await p.evaluate(()=>TG.pending()));
await p.waitForTimeout(9000);
// run the training pass directly and wait for it
await p.evaluate(()=>backfillTrain({days:4,topN:20,target:300}));
await p.waitForTimeout(3000);
const st=await p.evaluate(()=>({
  bfTrades:BF.trades, bfWins:BF.wins, bfNet:+BF.netR.toFixed(1), bfSyms:BF.done,
  learned:confN(), cases:CASES.count(),
  weights:Object.fromEntries(Object.entries(confW()).map(([k,v])=>[k,+v.toFixed(3)])),
  sim:CASES.similar({bias:1,rr:0.5,depth:0.4,fvg:1,level:1,channel:1,visits2:1,btc:0,ibs:0,ext:0,intel:0,usdtd:0})
}));
console.log('TRAIN:',JSON.stringify(st,null,1));
const rpt=await p.evaluate(()=>supReport(true));
console.log('REPORT:',JSON.stringify(rpt,null,1));
console.log('TELEGRAM CALLS:',tgCalls);
console.log('ERRS:',errs.length?errs.slice(0,4):'none');
await b.close();
