/* Worker: replays history for a slice of symbols and returns settled trades.
   One of these runs per core, so a training pass over 80 symbols finishes in
   a quarter of the time and leaves the main loop free to keep watching. */
const {parentPort,workerData}=require("worker_threads");
const B=require("./binance");
const E=require("./engine");

/* Pure: given candles, return the trades the live engine would have taken and
   how each one actually resolved. Separated from fetching so it can be tested. */
function replay(cd,tf,asset){
  if(!cd||cd.length<260)return[];
  const out=[];let open=null,last=-99;
  for(let i=240;i<cd.length;i++){
    const bar=cd[i];
    if(open){
      const L=open.dir==="LONG";
      const hitSL=L?bar.l<=open.sl:bar.h>=open.sl;
      const hitT1=L?bar.h>=open.tp1:bar.l<=open.tp1;
      const hitT2=open.tp2!=null&&(L?bar.h>=open.tp2:bar.l<=open.tp2);
      let r=null;
      if(!open.t1&&hitSL)r=-1;
      else{
        if(hitT1&&!open.t1){open.t1=true;open.sl=open.entry;}
        if(open.t1){ if(hitT2)r=open.R2; else if(hitSL)r=open.R1; }
      }
      if(r==null&&i-open.i>96)r=open.t1?open.R1:0;
      if(r!=null){out.push({feat:open.feat,r,asset,dir:open.dir,tf});open=null;}
      if(open)continue;
    }
    if(i-last<6)continue;
    let s=null;
    try{s=E.smcSetup(cd.slice(0,i+1),{tf,asset});}catch(e){continue;}
    if(!s||s.stage!=="SIGNAL"||!s.tp1)continue;
    const risk=Math.abs(s.entry-s.sl);
    if(!risk||risk/s.entry<0.0008)continue;
    const R1=Math.min(Math.abs(s.tp1-s.entry)/risk,6);
    const R2=s.tp2!=null?Math.min(Math.abs(s.tp2-s.entry)/risk,10):R1;
    if(R1<1)continue;
    last=i;
    open={i,dir:s.dir,entry:s.entry,sl:s.sl,tp1:s.tp1,tp2:s.tp2,R1,R2,t1:false,feat:E.confFeat(s,null)};
  }
  return out;
}
async function replaySymbol(sym,tf,limit){
  let cd;
  try{cd=await B.klines(sym,tf,limit);}catch(e){return[];}
  return replay(cd,tf,sym.replace("USDT",""));
}

if(parentPort)(async()=>{
  const {symbols,days}=workerData;
  const tfs=[["15m",Math.min(1500,days*96)],["5m",Math.min(1500,days*288)]];
  let all=[];
  for(const sym of symbols){
    for(const[tf,limit]of tfs)all=all.concat(await replaySymbol(sym,tf,limit));
    parentPort.postMessage({progress:1});
  }
  parentPort.postMessage({done:true,trades:all});
})().catch(e=>parentPort.postMessage({done:true,trades:[],error:String(e.message||e)}));

module.exports={replay,replaySymbol};
