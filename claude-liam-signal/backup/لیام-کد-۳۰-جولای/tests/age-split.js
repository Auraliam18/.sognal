const {simulate}=require('./sim.js');const H=require('./harness.js');
const from=+process.argv[2],to=+process.argv[3];
const E=H.loadEngine({'ob.brk<=200':'ob.brk<=400'});   // wide, so every age is represented
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
      if(sl&&t1)r=-1; else if(sl)r=-1; else if(t1)r=open.R;
      else if(i-open.i>96)r=0;
      if(r!=null){out.push({age:open.age,visits:open.visits,w:r>0?1:0,R:open.R,r});open=null;}
      if(open)continue;
    }
    if(i-last<6)continue;
    let s2=null;try{s2=E.smcSetup(cd.slice(0,i+1),{tf:"15m",asset:"X"});}catch(e){continue;}
    if(!s2||s2.stage!=="SIGNAL"||!s2.tp1)continue;
    const risk=Math.abs(s2.entry-s2.sl);if(!risk||risk/s2.entry<0.0008)continue;
    const R=Math.min(Math.abs(s2.tp1-s2.entry)/risk,6);if(R<1)continue;
    last=i;
    open={i,dir:s2.dir,sl:s2.sl,tp1:s2.tp1,R,age:s2.ob?i-s2.ob.brk:0,visits:s2.visits};
  }
}
process.stdout.write(JSON.stringify(out));
