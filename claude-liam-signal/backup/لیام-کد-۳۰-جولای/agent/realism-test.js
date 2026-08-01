/* Real 15m crypto candles move a few tenths of a percent, not the percent-plus
   swings the earlier tapes used. This asks whether the filters survive that. */
const E=require("./engine");
const {replay}=require("./trainer");

function tape(seed,n,volPct,trendStrength){
  let s=seed;const rnd=()=>(s=(s*1103515245+12345)%2147483648)/2147483648;
  const g=()=>{let u=0,v=0;while(!u)u=rnd();while(!v)v=rnd();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);};
  const cd=[];let p=100,drift=0,left=0;
  for(let i=0;i<n;i++){
    if(--left<=0){drift=(rnd()<0.5?-1:1)*trendStrength*volPct;left=30+Math.floor(rnd()*70);}
    const ret=drift+volPct*g();
    const o=p,c=p*(1+ret);
    const wick=volPct*(0.3+rnd());
    cd.push({t:i*9e5,o,c,h:Math.max(o,c)*(1+wick*rnd()),l:Math.min(o,c)*(1-wick*rnd()),v:1000});
    p=c;
  }
  return cd;
}
const rows=[];
for(const[label,vol]of[["آرام مثل BTC (0.15%)",0.0015],["معمولی (0.3%)",0.003],["پرنوسان آلت (0.6%)",0.006],["تست قبلی من (1.2%)",0.012]]){
  let sig=0,armed=0,pull=0,watch=0,none=0,trades=0,wins=0,net=0;
  for(let k=0;k<40;k++){
    const cd=tape(k*7919+13,900,vol,1.2);
    for(let i=300;i<cd.length;i+=15){
      const s=E.smcSetup(cd.slice(0,i+1),{tf:"15m",asset:"X"});
      if(!s){none++;continue;}
      if(s.stage==="SIGNAL")sig++;else if(s.stage==="ARMED")armed++;
      else if(s.stage==="PULLBACK_1")pull++;else watch++;
    }
    const t=replay(cd,"15m","X");
    trades+=t.length;t.forEach(x=>{if(x.r>0)wins++;net+=x.r;});
  }
  const tot=sig+armed+pull+watch+none;
  rows.push({label,sig,pct:(sig/tot*100).toFixed(1)+"%",armed,pull,trades,
    win:trades?Math.round(wins/trades*100)+"%":"—",net:trades?(net/trades).toFixed(3):"—"});
}
console.log("نوسان کندل        | سیگنال | درصد  | آماده | پولبک۱ | معامله | برد  | انتظار");
rows.forEach(r=>console.log(
  r.label.padEnd(20),String(r.sig).padStart(6),String(r.pct).padStart(7),
  String(r.armed).padStart(6),String(r.pull).padStart(7),String(r.trades).padStart(8),
  String(r.win).padStart(5),String(r.net).padStart(8)));
