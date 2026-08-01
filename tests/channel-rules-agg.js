/* Aggregate the four channel rules. Each slice gets expectancy in R and a
   95% bootstrap interval, so a rule is only kept when its interval clears zero. */
const fs=require("fs"),path=require("path");
const DIR=path.join(__dirname,".data");
const D=[0,1,2,3].flatMap(i=>JSON.parse(fs.readFileSync(path.join(DIR,`ch_${i}.json`),"utf8")));
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
function boot(a,n=4000){
  if(a.length<20)return null;
  const m=[];for(let b=0;b<n;b++){let s=0;for(let k=0;k<a.length;k++)s+=a[(Math.random()*a.length)|0];m.push(s/a.length);}
  m.sort((x,y)=>x-y);return[m[(n*0.025)|0],m[(n*0.975)|0]];
}
function line(name,sel){
  const g=D.filter(sel);
  if(!g.length)return `${name.padEnd(30)} —`;
  const rs=g.map(t=>t.r), ci=boot(rs);
  const wr=(100*mean(g.map(t=>t.w))).toFixed(1);
  return `${name.padEnd(30)} n=${String(g.length).padStart(5)}  win=${wr.padStart(5)}%  E=${mean(rs).toFixed(3).padStart(6)}R  ` +
         (ci?`[${ci[0].toFixed(3)}, ${ci[1].toFixed(3)}]${ci[0]>0?"  ✓ above zero":ci[1]<0?"  ✗ below zero":"  — spans zero"}`:"");
}
function diff(name,a,b){
  const A=D.filter(a).map(t=>t.r), B=D.filter(b).map(t=>t.r);
  if(A.length<20||B.length<20)return `${name.padEnd(30)} too few`;
  const n=4000,m=[];
  for(let i=0;i<n;i++){
    let sa=0;for(let k=0;k<A.length;k++)sa+=A[(Math.random()*A.length)|0];
    let sb=0;for(let k=0;k<B.length;k++)sb+=B[(Math.random()*B.length)|0];
    m.push(sa/A.length-sb/B.length);
  }
  m.sort((x,y)=>x-y);
  const lo=m[(n*0.025)|0],hi=m[(n*0.975)|0];
  return `${name.padEnd(30)} Δ=${(mean(A)-mean(B)).toFixed(3).padStart(6)}R  [${lo.toFixed(3)}, ${hi.toFixed(3)}]` +
         (lo>0?"  ✓ real gain":hi<0?"  ✗ real loss":"  — spans zero, do not act");
}

console.log(`\ntrades: ${D.length}   baseline: ${mean(D.map(t=>t.r)).toFixed(3)}R   win ${(100*mean(D.map(t=>t.w))).toFixed(1)}%`);
console.log(`room field present on ${D.filter(t=>t.room!==99).length} of ${D.length}\n`);

console.log("── 1. room to run (distance to opposing supply/demand, in risk units)");
[["room < 1R",t=>t.room<1],["room 1–1.5R",t=>t.room>=1&&t.room<1.5],
 ["room 1.5–3R",t=>t.room>=1.5&&t.room<3],["room ≥ 3R",t=>t.room>=3&&t.room<99],
 ["no blocker found",t=>t.room===99]].forEach(([n,f])=>console.log("  "+line(n,f)));
console.log("  "+diff("≥1.5R vs <1.5R",t=>t.room>=1.5,t=>t.room<1.5));

console.log("\n── 2. inducement swept before entry");
console.log("  "+line("swept",t=>t.swept===1));
console.log("  "+line("not swept",t=>t.swept===0));
console.log("  "+diff("swept vs not",t=>t.swept===1,t=>t.swept===0));

console.log("\n── 3. false structure from inside candles");
[["inside ≤ 30%",t=>t.inside<=0.30],["inside 30–45%",t=>t.inside>0.30&&t.inside<=0.45],
 ["inside > 45%",t=>t.inside>0.45]].forEach(([n,f])=>console.log("  "+line(n,f)));
console.log("  "+diff("inside ≤45% vs >45%",t=>t.inside<=0.45,t=>t.inside>0.45));

console.log("\n── 4. thin volume");
console.log("  "+line("vol ratio < 0.45",t=>t.volr<0.45));
console.log("  "+line("vol ratio ≥ 0.45",t=>t.volr>=0.45));
console.log("  "+diff("vol ≥0.45 vs <0.45",t=>t.volr>=0.45,t=>t.volr<0.45));

console.log("\n── combined thin flag (either condition)");
console.log("  "+line("thin",t=>t.thin===1));
console.log("  "+line("not thin",t=>t.thin===0));
console.log("  "+diff("not thin vs thin",t=>t.thin===0,t=>t.thin===1));
console.log();
