/* Walk-forward evaluation: run the engine bar by bar, take the trade it
   proposes, and measure what actually happened (TP1 before SL). */
const fs=require('fs');
function loadEngine(patch){
  const re=/<script[^>]*>([\s\S]*?)<\/script>/g;let m,best="";
  const html=fs.readFileSync(require('path').join(__dirname,'..','index.html'),'utf8');
  while((m=re.exec(html)))if(m[1].length>best.length)best=m[1];
  /* Up to smcQmin rather than to ibsDetectSwings: the IBS engine sits between
     the two, and stopping short of it meant strategy 1 could not be measured at
     all. Everything added is additive — smcSetup is unchanged. */
  let src=best.slice(best.indexOf('function rsiSeries'),best.indexOf('function smcQmin'));
  if(patch&&patch.__regex){
    for(const[re,rep]of patch.__regex){
      if(!re.test(src))throw new Error("patch anchor did not match: "+re);
      src=src.replace(re,rep);
    }
  }else if(patch)for(const[k,v]of Object.entries(patch))src=src.split(k).join(v);
  const shim=`const _M={};const DB={get:k=>_M[k],set:(k,v)=>{_M[k]=v;}};`;
  return (new Function(shim+src+"\nreturn{smcSetup,ibsPullback,ibsDetectSwings,ibsDetectBOS,"+
    "ibsDetectOB,ibsDetectChoch,confLearn,confW,confFeat,confP,confEV,DB};"))();
}
function evaluate(E,cd,opts){
  opts=opts||{};const minQ=opts.minQ==null?0:opts.minQ;
  const trades=[];let open=null,last=-99;
  for(let i=220;i<cd.length;i++){
    const bar=cd[i];
    if(open){
      const L=open.dir==="LONG";
      const sl=L?bar.l<=open.sl:bar.h>=open.sl;
      const tp=L?bar.h>=open.tp1:bar.l<=open.tp1;
      if(sl&&tp){open.win=false;open.r=-1;trades.push(open);open=null;}      // same bar → assume the stop
      else if(sl){open.win=false;open.r=-1;trades.push(open);open=null;}
      else if(tp){open.win=true;open.r=open.R;trades.push(open);open=null;}
      else if(i-open.i>96){open.win=false;open.r=0;open.timeout=true;trades.push(open);open=null;}
      if(open)continue;
    }
    if(i-last<8)continue;
    const s=E.smcSetup(cd.slice(0,i+1),{tf:"sim"});
    if(!s||s.stage!=="SIGNAL"||!s.tp1)continue;
    if(s.quality<minQ)continue;
    const risk=Math.abs(s.entry-s.sl);if(!risk||risk/s.entry<0.0008)continue;
    const R=Math.min(Math.abs(s.tp1-s.entry)/risk,8);
    if(R<0.5)continue;
    last=i;
    open={i,dir:s.dir,sl:s.sl,tp1:s.tp1,R,q:s.quality,p:s.p,ev:s.ev,feat:E.confFeat?E.confFeat(s,null):null,visits:s.visits,strong:s.strong,
          fvg:!!s.fvg,lvl:!!s.level,chOk:s.channel&&((s.dir==="SHORT"&&s.channel.dir==="نزولی")||(s.dir==="LONG"&&s.channel.dir==="صعودی")),
          depth:s.depth,rr:R};
  }
  return trades;
}
function stats(tr){
  if(!tr.length)return{n:0};
  const w=tr.filter(t=>t.win).length;
  const net=tr.reduce((a,t)=>a+t.r,0);
  return{n:tr.length,hit:+(w/tr.length*100).toFixed(1),ev:+(net/tr.length).toFixed(3),net:+net.toFixed(1),
         avgR:+(tr.reduce((a,t)=>a+t.R,0)/tr.length).toFixed(2)};
}
module.exports={loadEngine,evaluate,stats};
