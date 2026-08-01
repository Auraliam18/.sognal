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
  else if(pa.includes('/openInterestHist'))body=JSON.stringify([{sumOpenInterest:'1000'},{sumOpenInterest:'1080'}]);
  else if(pa.includes('/globalLongShortAccountRatio'))body=JSON.stringify([{longShortRatio:'2.45'}]);
  else if(pa.includes('/takerlongshortRatio'))body=JSON.stringify([{buySellRatio:'0.72'}]);
  else if(pa.endsWith('/klines'))body=JSON.stringify(gen(seed(u.searchParams.get('symbol')||'B')+seed(u.searchParams.get('interval')||'i'),+(u.searchParams.get('limit')||200)));
  await r.fulfill({status:200,contentType:'application/json',body});});
await p.route('**alternative.me/**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"data":[{"value":"81","value_classification":"Extreme Greed"}]}'}));
await p.route('**api.coingecko.com/**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"data":{"market_cap_percentage":{"btc":54.3}}}'}));
await p.goto('http://127.0.0.1:8901/index.html');
await p.waitForTimeout(12000);
await p.evaluate(()=>selectTab('ops'));
await p.waitForTimeout(2000);
// count how many times room cards are actually replaced over 8 seconds
const churn=await p.evaluate(()=>new Promise(res=>{
  let replaced=0, attrs=0, added=0;
  const rooms=document.getElementById('opsRooms'), feed=document.getElementById('opsFeed');
  const first=rooms.firstElementChild;
  const mo=new MutationObserver(ms=>{for(const m of ms){
    if(m.type==='childList'&&m.target===rooms&&m.removedNodes.length)replaced++;
    if(m.type==='childList'&&m.target===feed)added+=m.addedNodes.length;
    if(m.type==='characterData'||m.type==='attributes')attrs++;}});
  mo.observe(rooms,{childList:true,subtree:true,characterData:true,attributes:true});
  mo.observe(feed,{childList:true});
  setTimeout(()=>{mo.disconnect();res({roomsReplaced:replaced,textUpdates:attrs,feedAdded:added,sameNode:document.getElementById('opsRooms').firstElementChild===first});},8000);
}));
console.log('CHURN(8s):',JSON.stringify(churn));
const lights=await p.evaluate(()=>[...document.querySelectorAll('#opsRooms .card')].map(c=>
  c.querySelector('b').textContent+':'+(c.querySelector('.rc-state').textContent.trim())));
console.log('LIGHTS:',JSON.stringify(lights));
await p.screenshot({path:'shot13_ops.png',fullPage:true});
console.log('ERRS:',errs.length?errs.slice(0,3):'none');
await b.close();
