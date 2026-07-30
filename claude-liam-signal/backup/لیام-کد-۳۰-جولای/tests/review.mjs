import { chromium } from 'playwright';
const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
const p=await b.newPage({viewport:{width:1440,height:1200}});
const errs=[];p.on('pageerror',e=>errs.push(e.message.slice(0,120)));
await p.route('**fapi*.binance.com/**',r=>r.abort());
await p.route('**api.telegram.org/**',r=>r.fulfill({status:200,contentType:'application/json',body:'{"ok":true}'}));
await p.goto('http://127.0.0.1:8901/index.html');
await p.waitForTimeout(4000);

// Seed closed trades where old setups lose badly and fresh ones win — the exact
// pattern the review is supposed to find.
const seeded=await p.evaluate(()=>{
  const mk=(age,r,i)=>({sym:"X"+i,asset:"X"+i,dir:i%2?"LONG":"SHORT",tf:i%3?"15m":"5m",
    entry:100,sl:95,tp1:110,open:false,r,age,visits:1+(i%3),rr:1.4+(i%3),conf:30+(i%40),
    regime:"NEUTRAL",closedAt:Date.now()-1000,
    feat:{bias:1,rr:0.2,depth:0.3,fvg:i%2,level:0,channel:1,visits2:0,btc:0,ibs:0,ext:0,intel:0,usdtd:0}});
  const T=[];
  for(let i=0;i<60;i++)T.push(mk(5,i%3?2.2:-1,i));      // fresh setups: mostly winners
  for(let i=60;i<130;i++)T.push(mk(80,i%5?-1:2.0,i));   // stale setups: mostly losers
  STATE.trades=T;
  return{n:T.length,fresh:smcFreshBars()};
});
console.log('SEEDED:',JSON.stringify(seeded));

const r1=await p.evaluate(()=>{const rep=runReview(false);
  return{n:rep.n,ev:rep.all.ev,
    old:(rep.groups.find(g=>g.title==="سن ستاپ در لحظهٔ سیگنال")||{list:[]}).list.map(x=>`${x.name}: ${x.ev}R ${x.verdict}`),
    acts:(DB.get("review")||{}).acts, fresh:smcFreshBars(), log:tuneLog().length};});
console.log('REVIEW-1:',JSON.stringify(r1,null,1));

// Cycle 2: the change made things WORSE — it must be reverted.
const r2=await p.evaluate(()=>{
  const T=STATE.trades;
  for(let i=0;i<20;i++)T.push({sym:"Y"+i,asset:"Y"+i,dir:"LONG",tf:"15m",entry:100,sl:95,tp1:110,
    open:false,r:-1,age:5,visits:1,rr:2,conf:50,regime:"NEUTRAL",closedAt:Date.now(),
    feat:{bias:1,rr:0.2,depth:0.3,fvg:1,level:0,channel:1,visits2:0,btc:0,ibs:0,ext:0,intel:0,usdtd:0}});
  runReview(false);
  const log=tuneLog();
  return{fresh:smcFreshBars(),graded:log[0]&&log[0].graded,kept:log[0]&&log[0].kept,
    before:log[0]&&log[0].evBefore,after:log[0]&&log[0].evAfter,acts:(DB.get("review")||{}).acts};});
console.log('REVIEW-2 (change hurt → revert):',JSON.stringify(r2,null,1));
const r3=await p.evaluate(()=>{runReview(false);
  return{acts:(DB.get('review')||{}).acts,cool:Object.keys(DB.get('tune_cool')||{}),logLen:tuneLog().length};});
console.log('REVIEW-3 (must not re-apply):',JSON.stringify(r3,null,1));

await p.evaluate(()=>selectTab('paper'));
await p.waitForTimeout(1200);
const ui=await p.evaluate(()=>({
  hasTable:!!document.querySelector('#paperBox table'),
  hasLedger:document.getElementById('paperBox').innerText.includes('دفتر تغییرها'),
  txt:document.getElementById('paperBox').innerText.slice(0,220).replace(/\n+/g,' | ')}));
console.log('UI:',JSON.stringify(ui,null,1));
await p.screenshot({path:'shot14_paper.png',fullPage:true});
console.log('ERRS:',errs.length?errs.slice(0,3):'none');
await b.close();
