import { chromium } from 'playwright';
const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
const errs=[];
// Case 1: Binance completely unreachable — the geo-block case
const p1=await b.newPage();
p1.on('pageerror',e=>errs.push(e.message.slice(0,110)));
await p1.route('**fapi*.binance.com/**',r=>r.abort());
await p1.goto('http://127.0.0.1:8901/index.html');
await p1.waitForTimeout(12000);
console.log('BLOCKED:',JSON.stringify(await p1.evaluate(()=>({
  verdict:(document.querySelector('#whyBox div[style*="font-weight:700"]')||{}).textContent,
  net:{ok:DIAG.net.ok,fail:DIAG.net.fail},
  mentionsVpn:document.getElementById('whyBox').innerText.includes('VPN')}))));
await p1.close();
// Case 2: data flows but nothing has set up yet
const p2=await b.newPage();
const SY=['AUSDT','BUSDT','CUSDT'];
const gen=n=>{let p=100;const o=[];for(let i=0;i<n;i++){const c=p*(1+(Math.sin(i/9)*0.0008));o.push([Date.now()-(n-i)*9e5,p,Math.max(p,c)*1.0005,Math.min(p,c)*0.9995,c,900,0,0,0,0,0,0]);p=c;}return o;};
await p2.route('**fapi*.binance.com/**',async r=>{
  const u=new URL(r.request().url()),pa=u.pathname;let body='{}';
  if(pa.endsWith('/ticker/24hr')){const sm=u.searchParams.get('symbol');const t=s=>({symbol:s,quoteVolume:'9e8',priceChangePercent:'0.2',lastPrice:'100',volume:'1'});body=JSON.stringify(sm?t(sm):SY.map(t));}
  else if(pa.endsWith('/premiumIndex'))body=JSON.stringify(SY.map(s=>({symbol:s,lastFundingRate:'0.0001'})));
  else if(pa.endsWith('/klines'))body=JSON.stringify(gen(+(u.searchParams.get('limit')||200)));
  else if(pa.endsWith('/ticker/price'))body=JSON.stringify(SY.map(s=>({symbol:s,price:'100'})));
  await r.fulfill({status:200,contentType:'application/json',body});});
await p2.route('**api.coingecko.com/**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"data":{"market_cap_percentage":{"btc":54,"usdt":5}}}'}));
await p2.goto('http://127.0.0.1:8901/index.html');
await p2.waitForTimeout(14000);
console.log('FLAT-MARKET:',JSON.stringify(await p2.evaluate(()=>({
  verdict:(document.querySelector('#whyBox div[style*="font-weight:700"]')||{}).textContent,
  detail:(document.querySelector('#whyBox .muted')||{}).innerText,
  net:{ok:DIAG.net.ok,fail:DIAG.net.fail}}))));
console.log('ERRS:',errs.length?errs.slice(0,3):'none');
await b.close();
