import { chromium } from 'playwright';
const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
const p=await b.newPage({viewport:{width:1440,height:1200}});
const errs=[];p.on('pageerror',e=>errs.push(e.message.slice(0,120)));
const SY=Array.from({length:14},(_,i)=>`P${i}USDT`);
const seed=s=>[...s].reduce((a,c)=>a+c.charCodeAt(0),0);
const gen=(sd,n)=>{let s=sd,p=50+sd%150;const o=[];const rnd=()=>(s=(s*1103515245+12345)%2147483648)/2147483648;
  for(let i=0;i<n;i++){const ph=(i+sd)%130;let d;
    if(ph<48)d=-0.004+rnd()*0.0018;else if(ph<62)d=0.009+rnd()*0.002;
    else if(ph<76)d=-0.012-rnd()*0.003;else if(ph<88)d=0.011+rnd()*0.002;
    else if(ph<98)d=-0.010;else if(ph<112)d=0.010;else d=-0.013;
    const op=p,c=p*(1+d);o.push([Date.now()-(n-i)*9e5,op,Math.max(op,c)*(1+rnd()*0.003),Math.min(op,c)*(1-rnd()*0.003),c,4000,0,0,0,0,0,0]);p=c;}
  return o;};
await p.route('**api.telegram.org/**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"ok":true}'}));
await p.route('**fapi*.binance.com/**',async r=>{
  const u=new URL(r.request().url()),pa=u.pathname;let body='{}';
  if(pa.endsWith('/ticker/24hr')){const sm=u.searchParams.get('symbol');const t=s=>({symbol:s,quoteVolume:'9e8',priceChangePercent:'-2',lastPrice:String(50+seed(s)%150),volume:'1'});body=JSON.stringify(sm?t(sm):SY.map(t));}
  else if(pa.endsWith('/ticker/price'))body=JSON.stringify(SY.map(s=>({symbol:s,price:String((50+seed(s)%150)*0.97)})));
  else if(pa.endsWith('/premiumIndex'))body=JSON.stringify(SY.map(s=>({symbol:s,lastFundingRate:'0.0001'})));
  else if(pa.includes('/openInterestHist'))body=JSON.stringify([{sumOpenInterest:'1000'},{sumOpenInterest:'1010'}]);
  else if(pa.includes('LongShort')||pa.includes('longshort'))body=JSON.stringify([{longShortRatio:'1.1',buySellRatio:'1.0'}]);
  else if(pa.endsWith('/klines'))body=JSON.stringify(gen(seed(u.searchParams.get('symbol')||'B')+seed(u.searchParams.get('interval')||'i'),+(u.searchParams.get('limit')||200)));
  await r.fulfill({status:200,contentType:'application/json',body});});
await p.route('**api.coingecko.com/**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"data":{"market_cap_percentage":{"btc":54,"usdt":5}}}'}));
await p.goto('http://127.0.0.1:8901/index.html');
await p.waitForTimeout(15000);

// drive evaluations directly, as closed candles would
const r=await p.evaluate(async()=>{
  const before={paper:PAPER.trades.length,sig:STATE.signals.length};
  const syms=(STATE.universe||[]).map(u=>u.binance_symbol);
  for(const sym of syms)for(const tf of ["5m","15m"]){
    const k=sym+"|"+tf;
    if(!WATCHER.buf[k]){try{WATCHER.buf[k]=await fetchKlines(sym,tf,300);}catch(e){continue;}}
    watcherEvaluate(sym,tf);
  }
  await new Promise(r=>setTimeout(r,600));
  const stages={};let rrs=[];
  for(const sym of syms)for(const tf of ['5m','15m']){
    const buf=WATCHER.buf[sym+'|'+tf];if(!buf)continue;
    let x=null;try{x=smcSetup(buf,{tf,asset:sym.replace('USDT','')});}catch(e){}
    const k=x?x.stage:'NONE';stages[k]=(stages[k]||0)+1;
    if(x&&x.rr)rrs.push(+x.rr.toFixed(2));
  }
  return{before,paperOpened:PAPER.trades.length,signals:STATE.signals.length,
    evals:WATCHER.evals,symbols:syms.length,stages,rrSample:rrs.slice(0,8)};
});
console.log('OPENED:',JSON.stringify(r));

// settle them against a moved price, and confirm the learning room absorbed it
const s=await p.evaluate(async()=>{
  const n0=confN(),c0=CASES.count();
  for(const t of PAPER.trades)if(t.open){
    paperCheck(t,t.dir==="LONG"?t.tp1*1.001:t.tp1*0.999);   // reach the first target
    if(t.open)paperCheck(t,t.dir==="LONG"?t.sl*0.999:t.sl*1.001);
  }
  await new Promise(r=>setTimeout(r,400));
  const st=paperStats();
  return{...st,learnedBefore:n0,learnedAfter:confN(),casesBefore:c0,casesAfter:CASES.count()};
});
console.log('SETTLED:',JSON.stringify(s));

// the learning room's answer, and the supervisor's use of it
const g=await p.evaluate(()=>{
  const sym=(STATE.universe[0]||{}).binance_symbol||"P0USDT";
  const feat={bias:1,rr:0.3,depth:0.4,fvg:1,level:0,channel:1,visits2:0,btc:0,ibs:0,ext:0,intel:0,usdtd:0};
  const q=askLearningRoom(sym,feat,"LONG");
  const v=supervisorApproves(sym,{dir:"LONG",rr:2,depth:40,visits:1,tf:"15m",fvg:true,level:null,channel:null,tpExt:false});
  return{pool:q.pool,coin:q.coin,similar:q.similar&&{n:q.similar.n,hit:q.similar.hit,ev:q.similar.ev},
    approved:v.ok,why:v.why};
});
console.log('LEARNING ROOM:',JSON.stringify(g,null,1));
await p.evaluate(()=>selectTab('paper'));
await p.waitForTimeout(1200);
await p.screenshot({path:'shot15_paper.png',fullPage:true});
console.log('ERRS:',errs.length?errs.slice(0,3):'none');
await b.close();
