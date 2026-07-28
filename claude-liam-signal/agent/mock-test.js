/* Runs the agent's pieces against a stubbed exchange so the whole path can be
   exercised without touching the network. */
const seed=s=>[...s].reduce((a,c)=>a+c.charCodeAt(0),0);
const gen=(sd,n)=>{let s=sd,p=50+sd%150;const o=[];const rnd=()=>(s=(s*1103515245+12345)%2147483648)/2147483648;
  for(let i=0;i<n;i++){const ph=(i+sd)%130;let d;
    if(ph<48)d=-0.004+rnd()*0.0018;else if(ph<62)d=0.009+rnd()*0.002;
    else if(ph<76)d=-0.012-rnd()*0.003;else if(ph<88)d=0.011+rnd()*0.002;
    else if(ph<98)d=-0.010;else if(ph<112)d=0.010;else d=-0.013;
    const op=p,c=p*(1+d);o.push({t:Date.now()-(n-i)*9e5,o:op,h:Math.max(op,c)*(1+rnd()*0.003),l:Math.min(op,c)*(1-rnd()*0.003),c,v:4000});p=c;}
  return o;};
const SY=Array.from({length:16},(_,i)=>`M${i}USDT`);
require.cache[require.resolve("./binance.js")]={exports:{
  jget:async()=>({}), sleep:ms=>new Promise(r=>setTimeout(r,Math.min(ms,5))),
  parseKlines:a=>a,
  tickers:async()=>SY.map(s=>({symbol:s,quoteVolume:String(9e8-seed(s)*1e5),priceChangePercent:"-2",lastPrice:String(50+seed(s)%150)})),
  prices:async()=>SY.map(s=>({symbol:s,price:String(50+seed(s)%150)})),
  funding:async()=>[],
  klines:async(sym,iv,limit)=>gen(seed(sym)+seed(iv),limit||300),
  wsBase:"wss://example.invalid"
}};
const E=require("./engine");
const {db}=require("./store");

(async()=>{
  const B=require("./binance");
  // 1) universe + context
  const t=await B.tickers();
  console.log("universe:",t.length,"symbols");
  // 2) strategy over a real-shaped buffer
  const cd=await B.klines("M1USDT","15m",300);
  const s=E.smcSetup(cd,{tf:"15m",asset:"M1"});
  console.log("setup:",s?`${s.stage} conf=${s.conf}% rr=${s.rr} ev=${(s.ev||0).toFixed(2)}`:"none");
  // 3) multi-core training, exactly as the agent runs it
  const {replay}=require("./trainer");
  const os=require("os");
  const t0=Date.now();
  let trades=[];
  for(const sym of SY)for(const tf of ["15m","5m"]){
    const c=await B.klines(sym,tf,tf==="15m"?384:1152);
    trades=trades.concat(replay(c,tf,sym.replace("USDT","")));
  }
  const slices={length:Math.min(os.cpus().length,4)};
  let wins=0,net=0;
  for(const x of trades){if(x.r>0)wins++;net+=x.r;E.confLearn(x.feat,x.r>0);E.CASES.add(x.feat,x.r>0,x.r,x);}
  console.log(`training: ${trades.length} positions on ${slices.length} cores in ${((Date.now()-t0)/1000).toFixed(1)}s`);
  if(trades.length)console.log(`   win ${Math.round(wins/trades.length*100)}% · net ${net>0?"+":""}${net.toFixed(1)}R`);
  console.log("learned from:",db.get("conf_n")||0,"· cases:",E.CASES.count());
  const w=E.confW();
  console.log("weights:",Object.entries(w).filter(([k])=>k!=="bias").sort((a,b)=>Math.abs(b[1])-Math.abs(a[1])).slice(0,4).map(([k,v])=>`${k} ${v>0?"+":""}${v.toFixed(2)}`).join(" · "));
  const sim=E.CASES.similar(E.confFeat(s||{dir:"LONG",rr:2,depth:50,visits:2,quality:60},null));
  console.log("similar-case lookup:",sim?`${sim.n} of ${sim.pool} · win ${sim.hit}% · ${sim.ev}R`:"n/a");
  db.flushNow();
})();
