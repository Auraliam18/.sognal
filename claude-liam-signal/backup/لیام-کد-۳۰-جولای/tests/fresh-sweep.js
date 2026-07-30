const {simulate}=require('./sim.js');const H=require('./harness.js');
const bars=process.argv[2], from=+process.argv[3], to=+process.argv[4];
const E=H.loadEngine({'ob.brk<=200':'ob.brk<='+bars});
let all=[];
for(let s=from;s<to;s++)all=all.concat(H.evaluate(E,simulate(s*1013+7,1500)));
process.stdout.write(JSON.stringify(all.map(t=>({w:t.win?1:0,R:+t.R.toFixed(3)}))));
