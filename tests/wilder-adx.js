/* Wilder held that below ADX 20 there is no trend and signals should be
   ignored. Does that hold for this engine, on this tape? */
const {simulate}=require('/home/user/.sognal/tests/sim.js');
const H=require('/home/user/.sognal/tests/harness.js');
const from=+process.argv[2],to=+process.argv[3];
const E=H.loadEngine();
const out=[];
for(let s=from;s<to;s++){
  const cd=simulate(s*1013+7,1500);
  let open=null,last=-99;
  for(let i=240;i<cd.length;i++){
    const bar=cd[i];
    if(open){
      const L=open.dir==="LONG";
      const sl=L?bar.l<=open.sl:bar.h>=open.sl, t1=L?bar.h>=open.tp1:bar.l<=open.tp1;
      let r=null;
      if(sl)r=-1; else if(t1)r=open.R; else if(i-open.i>96)r=0;
      if(r!=null){out.push({adx:open.adx,pdi:open.pdi,ndi:open.ndi,fs:open.fs,w:r>0?1:0,R:open.R,r});open=null;}
      if(open)continue;
    }
    if(i-last<6)continue;
    let s2=null;try{s2=E.smcSetup(cd.slice(0,i+1),{tf:"15m",asset:"X"});}catch(e){continue;}
    if(!s2||s2.stage!=="SIGNAL"||!s2.tp1)continue;
    const risk=Math.abs(s2.entry-s2.sl);if(!risk||risk/s2.entry<0.0008)continue;
    const R=Math.min(Math.abs(s2.tp1-s2.entry)/risk,6);if(R<1)continue;
    last=i;
    open={i,dir:s2.dir,sl:s2.sl,tp1:s2.tp1,R,
      adx:s2.dmi?s2.dmi.adx:0,pdi:s2.dmi?s2.dmi.pdi:0,ndi:s2.dmi?s2.dmi.ndi:0,
      fs:s2.failSwing?(s2.failSwing.dir===s2.dir?1:-1):0};
  }
}
process.stdout.write(JSON.stringify(out));
