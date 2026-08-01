#!/usr/bin/env node
/* claude-liam-signal — the panel's work, running on the laptop.
   No browser tab required: it scans, streams every symbol on 5m and 15m,
   paper-trades what it signals, learns from every close, trains on history
   across all cores, and sends to Telegram. Restarts clean from state.json. */
const os=require("os"),path=require("path");
const {Worker}=require("worker_threads");
const {db}=require("./store");
const B=require("./binance");
const E=require("./engine");
const TG=require("./telegram");

const CFG={
  universe:+(process.env.UNIVERSE||100),
  scanMin:+(process.env.SCAN_MIN||30),
  trainDays:+(process.env.TRAIN_DAYS||4),
  trainTop:+(process.env.TRAIN_TOP||80),
  cores:Math.max(1,Math.min(os.cpus().length,+(process.env.CORES||os.cpus().length))),
  reportMin:+(process.env.REPORT_MIN||5)
};
const S={universe:[],zones:{},trades:db.get("trades")||[],buf:{},subs:[],
         ws:null,ticks:0,evals:0,signals:0,lastScan:0,lastTick:0,started:Date.now(),
         training:false,repairs:0};

const log=(room,msg)=>{
  const line=`[${new Date().toISOString().slice(11,19)}] ${room.padEnd(8)} ${msg}`;
  console.log(line);
  const l=db.get("agent_log")||[];l.unshift({t:Date.now(),room,msg});db.set("agent_log",l.slice(0,400));
};
const fmt=(v)=>v==null?"—":(+v).toPrecision(6).replace(/\.?0+$/,"");

/* ---------- universe ---------- */
async function buildUniverse(){
  const t=await B.tickers();
  return t.filter(x=>x.symbol.endsWith("USDT")&&!/(UP|DOWN|BULL|BEAR)USDT$/.test(x.symbol))
    .map(x=>({sym:x.symbol,asset:x.symbol.replace("USDT",""),qv:+x.quoteVolume,chg:+x.priceChangePercent,last:+x.lastPrice}))
    .sort((a,b)=>b.qv-a.qv).slice(0,CFG.universe);
}

/* ---------- market context ---------- */
async function marketContext(){
  const ctx={};
  try{const k=await B.klines("BTCUSDT","4h",200);ctx.btcDiv=E.rsiDivergence(k);}catch(e){}
  try{
    const st=db.get("usdtDom")||{samples:[]};
    const last=st.samples[st.samples.length-1];
    if(!last||Date.now()-last.t>12e4){
      const r=await fetch("https://api.coingecko.com/api/v3/global");
      const j=await r.json();
      const pct=j&&j.data&&j.data.market_cap_percentage&&+j.data.market_cap_percentage.usdt;
      if(isFinite(pct)&&pct>0){st.samples.push({t:Date.now(),v:pct});st.samples=st.samples.slice(-48);db.set("usdtDom",st);}
    }
    ctx.dom=E.domState(st,!!st.samples.length);
  }catch(e){}
  return ctx;
}

/* ---------- signals ---------- */
async function emit(sym,asset,s,tf){
  const recent=(db.get("recent_sig")||{});
  if(recent[sym]&&Date.now()-recent[sym]<9e5)return;
  recent[sym]=Date.now();db.set("recent_sig",recent);
  S.signals++;
  const feat=E.confFeat(s,null);
  const sim=E.CASES.similar(feat);
  S.trades.unshift({sym,asset,dir:s.dir,tf,entry:s.entry,sl:s.sl,tp1:s.tp1,tp2:s.tp2,
    R1:Math.abs(s.tp1-s.entry)/Math.abs(s.entry-s.sl),
    R2:s.tp2?Math.abs(s.tp2-s.entry)/Math.abs(s.entry-s.sl):null,
    open:true,t1:false,t0:Date.now(),feat,conf:s.conf,ev:s.ev});
  S.trades=S.trades.slice(0,400);db.set("trades",S.trades);
  log("signal",`${s.dir} ${asset} ${tf} entry ${fmt(s.entry)} sl ${fmt(s.sl)} tp ${fmt(s.tp1)} rr ${s.rr} conf ${s.conf}%`);
  await TG.send([`<b>${s.dir==="LONG"?"🟢 خرید (LONG)":"🔴 فروش (SHORT)"} — ${asset}</b>  <code>${tf}</code>`,``,
    `ورود   <code>${fmt(s.entry)}</code>`,`استاپ  <code>${fmt(s.sl)}</code>`,
    `تارگت۱ <code>${fmt(s.tp1)}</code>`,s.tp2?`تارگت۲ <code>${fmt(s.tp2)}</code>`:``,``,
    `ریسک/ریوارد <b>${s.rr}</b> · اعتماد <b>${s.conf}%</b> · انتظار <b>${(s.ev||0).toFixed(2)}R</b>`,
    s.ob?`اردر بلاک <code>${fmt(s.ob.low)} — ${fmt(s.ob.high)}</code>`:``,
    s.channel?`کانال ${s.channel.dir} (${s.channel.drift}%)`:``,
    s.fvg?`FVG هم‌جهت ✓`:``,
    sim&&sim.n>=5?`سابقهٔ مشابه: ${sim.n} مورد · برد ${sim.hit}% · ${sim.ev>0?"+":""}${sim.ev}R`:``,
    ``,`<i>${new Date().toLocaleString("fa-IR")}</i>`].filter(Boolean).join("\n"));
}

function settle(tr,price){
  const L=tr.dir==="LONG";
  const hitSL=L?price<=tr.sl:price>=tr.sl;
  const hitT1=L?price>=tr.tp1:price<=tr.tp1;
  const hitT2=tr.tp2!=null&&(L?price>=tr.tp2:price<=tr.tp2);
  let r=null,why="";
  if(!tr.t1&&hitSL){r=-1;why="استاپ خورد";}
  else{
    if(hitT1&&!tr.t1){tr.t1=true;tr.sl=tr.entry;log("trade",`${tr.asset} TP1 — stop to entry`);}
    if(tr.t1){ if(hitT2){r=tr.R2||tr.R1;why="تارگت ۲ کامل";} else if(hitSL){r=tr.R1;why="برگشت به ورود بعد از TP1";} }
  }
  if(r==null&&Date.now()-tr.t0>288e5){r=tr.t1?tr.R1:0;why="مهلت تمام شد";}
  if(r==null)return false;
  tr.open=false;tr.r=+r.toFixed(2);tr.why=why;
  try{E.confLearn(tr.feat,r>0);E.CASES.add(tr.feat,r>0,r,{asset:tr.asset,dir:tr.dir,tf:tr.tf});}catch(e){}
  db.set("trades",S.trades);
  log("trade",`${r>0?"WIN":"LOSS"} ${tr.asset} ${tr.dir} ${why} ${r>0?"+":""}${tr.r}R`);
  TG.send(`${r>0?"✅":"❌"} <b>${tr.asset} ${tr.dir}</b> — ${why}\nنتیجه <b>${r>0?"+":""}${tr.r}R</b>`);
  return true;
}

/* ---------- scan ---------- */
async function scan(){
  try{
    log("scan","sweep started");
    S.universe=await buildUniverse();
    const ctx=await marketContext();
    db.set("ctx",ctx);
    log("market",`${S.universe.length} symbols${ctx.dom&&ctx.dom.available?" · "+E.domFa(ctx.dom):""}${ctx.btcDiv?" · BTC RSI "+ctx.btcDiv.rsi:""}`);
    S.lastScan=Date.now();
    startStream(S.universe.map(u=>u.sym));
  }catch(e){log("scan","sweep failed: "+e.message);}
}

/* ---------- continuous watch ---------- */
function startStream(syms){
  const tfs=["5m","15m"];
  S.subs=[];
  for(const tf of tfs)for(const s of syms.slice(0,Math.floor(1000/tfs.length)))S.subs.push(s.toLowerCase()+"@kline_"+tf);
  seed(syms,tfs);
  connect();
}
async function seed(syms,tfs){
  let n=0;
  for(const tf of tfs)for(const sym of syms){
    const k=sym+"|"+tf;
    if(S.buf[k]&&S.buf[k].length>=260)continue;
    try{S.buf[k]=await B.klines(sym,tf,300);n++;}catch(e){}
    await B.sleep(60);
  }
  log("watch",`${n} candle series seeded · ${Object.keys(S.buf).length} buffers live`);
}
function connect(){
  if(S.ws||!S.subs.length)return;
  const WebSocket=global.WebSocket;
  const url=B.wsBase+"/stream?streams="+S.subs.join("/");
  let ws;
  try{ws=new WebSocket(url);}catch(e){log("watch","stream failed: "+e.message);return;}
  S.ws=ws;
  ws.onopen=()=>log("watch",`stream connected — ${S.subs.length} channels (${S.subs.length/2} symbols x 2 timeframes)`);
  ws.onmessage=ev=>{
    try{
      const m=JSON.parse(ev.data),k=m&&m.data&&m.data.k;if(!k)return;
      S.ticks++;S.lastTick=Date.now();
      const key=k.s+"|"+k.i,buf=S.buf[key];if(!buf)return;
      const bar={t:k.t,o:+k.o,h:+k.h,l:+k.l,c:+k.c,v:+k.v};
      const last=buf[buf.length-1];
      if(last&&last.t===bar.t)buf[buf.length-1]=bar;else{buf.push(bar);if(buf.length>320)buf.shift();}
      for(const tr of S.trades)if(tr.open&&tr.sym===k.s)settle(tr,bar.c);
      if(k.x)evaluate(k.s,k.i);
    }catch(e){}
  };
  ws.onclose=()=>{S.ws=null;S.repairs++;log("watch","stream dropped — reconnecting");setTimeout(connect,4000);};
  ws.onerror=()=>{try{ws.close();}catch(e){}};
}
function evaluate(sym,tf){
  const buf=S.buf[sym+"|"+tf];
  if(!buf||buf.length<140)return;
  S.evals++;
  const u=S.universe.find(x=>x.sym===sym);
  const ctx=db.get("ctx")||{};
  let s=null;
  try{s=E.smcSetup(buf,{tf,asset:u?u.asset:sym.replace("USDT",""),dom:ctx.dom,btcDiv:ctx.btcDiv});}catch(e){return;}
  if(s&&s.stage==="SIGNAL"&&s.tp1)emit(sym,u?u.asset:sym.replace("USDT",""),s,tf);
}

/* ---------- training across all cores ---------- */
async function train(){
  if(S.training)return;
  S.training=true;
  const syms=(S.universe.length?S.universe:await buildUniverse()).slice(0,CFG.trainTop).map(u=>u.sym);
  const per=Math.ceil(syms.length/CFG.cores);
  const slices=[];for(let i=0;i<syms.length;i+=per)slices.push(syms.slice(i,i+per));
  log("train",`replaying ${CFG.trainDays} days across ${syms.length} symbols on ${slices.length} cores`);
  const t0=Date.now();
  const results=await Promise.all(slices.map(symbols=>new Promise(res=>{
    const w=new Worker(path.join(__dirname,"trainer.js"),{workerData:{symbols,days:CFG.trainDays}});
    const acc=[];
    w.on("message",m=>{if(m.done){res(m.trades||[]);w.terminate();}});
    w.on("error",()=>res([]));
    w.on("exit",()=>res(acc));
  })));
  const trades=results.flat();
  let wins=0,net=0;
  for(const t of trades){
    if(t.r>0)wins++;net+=t.r;
    try{E.confLearn(t.feat,t.r>0);E.CASES.add(t.feat,t.r>0,t.r,{asset:t.asset,dir:t.dir,tf:t.tf});}catch(e){}
  }
  db.set("bf_at",Date.now());db.flushNow();
  const hit=trades.length?Math.round(wins/trades.length*100):0;
  const secs=Math.round((Date.now()-t0)/1000);
  log("train",`${trades.length} positions · win ${hit}% · net ${net>0?"+":""}${net.toFixed(1)}R · ${secs}s on ${slices.length} cores`);
  await TG.send([`📚 <b>دورهٔ آموزش تمام شد</b>`,
    `${trades.length} پوزیشن روی ${syms.length} ارز (${CFG.trainDays} روز)`,
    `برد <b>${hit}%</b> · خالص <b>${net>0?"+":""}${net.toFixed(1)}R</b>`,
    `${secs} ثانیه روی ${slices.length} هسته · حافظهٔ تجربه ${E.CASES.count()} موقعیت`].join("\n"));
  S.training=false;
}

/* ---------- supervisor ---------- */
async function supervise(){
  const now=Date.now();
  if(!S.training&&now-S.lastScan>CFG.scanMin*60000){await scan();}
  if(S.subs.length&&!S.ws){S.repairs++;connect();}
  if(S.subs.length&&S.ws&&now-S.lastTick>120000){S.repairs++;log("sup","stream silent — cycling");try{S.ws.close();}catch(e){}S.ws=null;}
  const open=S.trades.filter(t=>t.open);
  if(open.length&&now-S.lastTick>45000){
    try{
      const px=await B.prices();
      const map={};px.forEach(p=>map[p.symbol]=+p.price);
      for(const tr of open)if(map[tr.sym])settle(tr,map[tr.sym]);
    }catch(e){}
  }
  const bf=db.get("bf_at")||0;
  if(!S.training&&now-bf>864e5&&S.universe.length)train();
}
async function report(){
  const open=S.trades.filter(t=>t.open),closed=S.trades.filter(t=>!t.open);
  const net=closed.reduce((a,t)=>a+(t.r||0),0);
  const up=Math.round((Date.now()-S.started)/60000);
  const lines=[`🛰 <b>گزارش ${CFG.reportMin} دقیقه‌ای</b>`,
    `پایش: ${S.ticks.toLocaleString("en")} کندل · ${S.evals} ارزیابی · ${S.subs.length/2||0} ارز`,
    `سیگنال: ${S.signals} · باز ${open.length} · بسته ${closed.length}${closed.length?` · خالص ${net>0?"+":""}${net.toFixed(1)}R`:""}`,
    `یادگیری: ${db.get("conf_n")||0} نتیجه · ${E.CASES.count()} تجربه`,
    `اتصال: ${S.ws?"برقرار":"در حال تعمیر"} · تعمیر ${S.repairs} · بالا ${up} دقیقه`];
  log("sup",lines.slice(1).join(" | ").replace(/<\/?b>/g,""));
  if(TG.on())await TG.send(lines.join("\n"));
}

/* ---------- boot ---------- */
(async()=>{
  console.log(`claude-liam-signal agent — ${CFG.cores} cores, ${CFG.universe} symbols, scan every ${CFG.scanMin}m`);
  if(!TG.on())console.log("Telegram is not configured: set TG_TOKEN and TG_CHAT to receive signals.");
  await scan();
  setInterval(supervise,15000);
  setInterval(report,CFG.reportMin*60000);
  if(TG.on())await TG.send("🚀 <b>عامل روی لپ‌تاپ راه افتاد</b>\nپایش، ترید کاغذی و یادگیری بدون نیاز به مرورگر ادامه دارد.");
  setTimeout(()=>{if(!S.training)train();},20000);
})();
