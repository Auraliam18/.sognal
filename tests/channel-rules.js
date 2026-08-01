/* Each rule from the channel summary, measured on its own before any of them is
   allowed to gate anything.

   The four rules under test:
     1. room to run     — distance to the nearest opposing zone, in risk units
     2. inducement      — was resting liquidity swept before the block formed
     3. false structure — inside candles that nobody defended
     4. thin volume     — participation well below the local average

   The engine is loaded as it ships. That is deliberate: the room and thin rules
   are computed and shown on the card but do not gate, so every candidate they
   would have downgraded is still observed here and can be scored. If either is
   ever promoted to a gate, strip it in loadEngine before measuring, or this
   becomes a measurement of the filter rather than of the rule.

     node tests/channel-rules.js <from> <to> [out.json]
     node tests/channel-rules-agg.js                      # aggregates the shards

   Sharding across cores, four at a time:
     for i in 0 1 2 3; do node tests/channel-rules.js $((i*130)) $(((i+1)*130)) \
       tests/.data/ch_$i.json & done; wait */
const path=require("path");
const fs=require("fs");
const {simulate}=require(path.join(__dirname,"sim.js"));
const H=require(path.join(__dirname,"harness.js"));

const from=+process.argv[2]||0, to=+process.argv[3]||130;
const outPath=process.argv[4];

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
      if(r!=null){out.push({room:open.room,swept:open.swept,inside:open.inside,
        volr:open.volr,thin:open.thin,adx:open.adx,w:r>0?1:0,R:open.R,r});open=null;}
      if(open)continue;
    }
    if(i-last<6)continue;
    let x=null;try{x=E.smcSetup(cd.slice(0,i+1),{tf:"15m",asset:"X"});}catch(e){continue;}
    if(!x||x.stage!=="SIGNAL"||!x.tp1)continue;
    const risk=Math.abs(x.entry-x.sl);if(!risk||risk/x.entry<0.0008)continue;
    const R=Math.min(Math.abs(x.tp1-x.entry)/risk,6);if(R<1)continue;
    last=i;
    open={i,dir:x.dir,sl:x.sl,tp1:x.tp1,R,
      room:x.room?x.room.r:99, swept:x.swept?1:0,
      inside:x.thin?x.thin.insideRatio:0, volr:x.thin?x.thin.volRatio:1,
      thin:x.thin&&x.thin.thin?1:0, adx:x.dmi?x.dmi.adx:0};
  }
}

const json=JSON.stringify(out);
if(outPath){
  fs.mkdirSync(path.dirname(outPath),{recursive:true});
  fs.writeFileSync(outPath,json);
  console.error(`${out.length} trades → ${outPath}`);
}else process.stdout.write(json);
