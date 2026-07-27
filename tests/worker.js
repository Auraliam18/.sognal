const {simulate}=require('./sim.js');const H=require('./harness.js');
const [from,to,minR]=process.argv.slice(2).map(Number);
const patch=minR?{'>=1.2)||null,':'>='+minR+')||null,'}:null;
const E=H.loadEngine(patch);
const out=[];
for(let s=from;s<to;s++){
  const cd=simulate(s*1013+7,1500);
  for(const t of H.evaluate(E,cd))out.push({w:t.win?1:0,R:+t.R.toFixed(3),d:t.dir==='LONG'?1:0,
    v:t.visits,ch:t.chOk?1:0,f:t.fvg?1:0,l:t.lvl?1:0,dp:t.depth,i:t.i,n:cd.length,feat:t.feat});
}
process.stdout.write(JSON.stringify(out));
