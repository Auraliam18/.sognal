/* Does the 70-bar freshness window throw away good setups, or protect from
   bad ones? Sweep it and measure both signal count and what those signals did. */
const fs=require("fs"),path=require("path");
const base=fs.readFileSync(path.join(__dirname,"engine.js"),"utf8");
function load(bars){
  const src=base.replace("const fresh=cd.length-1-ob.brk<=70;",`const fresh=cd.length-1-ob.brk<=${bars};`);
  const m={exports:{}};
  new Function("module","require","__dirname",src+"\nmodule.exports={smcSetup,confFeat};")
    (m,require,__dirname);
  return m.exports;
}
function tape(seed,n,vol){
  let s=seed;const rnd=()=>(s=(s*1103515245+12345)%2147483648)/2147483648;
  const g=()=>{let u=0,v=0;while(!u)u=rnd();while(!v)v=rnd();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);};
  const cd=[];let p=100,drift=0,left=0;
  for(let i=0;i<n;i++){
    if(--left<=0){drift=(rnd()<0.5?-1:1)*1.2*vol;left=30+Math.floor(rnd()*70);}
    const o=p,c=p*(1+drift+vol*g()),w=vol*(0.3+rnd());
    cd.push({t:i*9e5,o,c,h:Math.max(o,c)*(1+w*rnd()),l:Math.min(o,c)*(1-w*rnd()),v:1000});p=c;
  }
  return cd;
}
function replay(E,cd,tf,asset){
  const out=[];let open=null,last=-99;
  for(let i=240;i<cd.length;i++){
    const bar=cd[i];
    if(open){
      const L=open.dir==="LONG";
      const sl=L?bar.l<=open.sl:bar.h>=open.sl;
      const t1=L?bar.h>=open.tp1:bar.l<=open.tp1;
      const t2=open.tp2!=null&&(L?bar.h>=open.tp2:bar.l<=open.tp2);
      let r=null;
      if(!open.t1&&sl)r=-1;
      else{ if(t1&&!open.t1){open.t1=true;open.sl=open.entry;}
            if(open.t1){ if(t2)r=open.R2; else if(sl)r=open.R1; } }
      if(r==null&&i-open.i>96)r=open.t1?open.R1:0;
      if(r!=null){out.push(r);open=null;}
      if(open)continue;
    }
    if(i-last<6)continue;
    let s=null;try{s=E.smcSetup(cd.slice(0,i+1),{tf,asset});}catch(e){continue;}
    if(!s||s.stage!=="SIGNAL"||!s.tp1)continue;
    const risk=Math.abs(s.entry-s.sl);if(!risk||risk/s.entry<0.0008)continue;
    const R1=Math.min(Math.abs(s.tp1-s.entry)/risk,6),R2=s.tp2!=null?Math.min(Math.abs(s.tp2-s.entry)/risk,10):R1;
    if(R1<1)continue;
    last=i;open={i,dir:s.dir,entry:s.entry,sl:s.sl,tp1:s.tp1,tp2:s.tp2,R1,R2,t1:false};
  }
  return out;
}
const tapes=[];for(let k=0;k<80;k++)tapes.push(tape(k*7919+13,900,0.003));
console.log("پنجرهٔ اعتبار | سیگنال | معامله | برد%  | میانگین R | انتظار | سود کل");
for(const bars of [70,120,200,320]){
  const E=load(bars);
  let sig=0,checks=0;
  for(const cd of tapes.slice(0,30))for(let i=300;i<cd.length;i+=10){
    checks++;const s=E.smcSetup(cd.slice(0,i+1),{tf:"15m",asset:"X"});
    if(s&&s.stage==="SIGNAL")sig++;
  }
  let rs=[];for(const cd of tapes)rs=rs.concat(replay(E,cd,"15m","X"));
  const w=rs.filter(r=>r>0).length,net=rs.reduce((a,b)=>a+b,0);
  console.log(String(bars).padStart(12),
    String(sig).padStart(8),String(rs.length).padStart(8),
    String(rs.length?Math.round(w/rs.length*100):0).padStart(6),
    String(rs.length?(rs.reduce((a,b)=>a+Math.abs(b),0)/rs.length).toFixed(2):"—").padStart(10),
    String(rs.length?(net/rs.length).toFixed(3):"—").padStart(8),
    String(net.toFixed(0)).padStart(8));
}
