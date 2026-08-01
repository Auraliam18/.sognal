/* Strategy evaluation: walk-forward over simulated markets.
   node tests/evaluate.js   → trades, hit rate, average R, expectancy, net R */
const {simulate}=require('./sim.js');const H=require('./harness.js');
const E=H.loadEngine();
let all=[];for(let s=1;s<=40;s++)all=all.concat(H.evaluate(E,simulate(s*1013+7,1200)));
console.log('walk-forward:',JSON.stringify(H.stats(all)));
function walk(seed,n){let s=seed,p=100;const r=()=>(s=(s*1103515245+12345)%2147483648)/2147483648;const cd=[];
 for(let i=0;i<n;i++){const o=p,c=p*(1+(r()-0.5)*0.006);cd.push({o,c,h:Math.max(o,c)*(1+r()*0.002),l:Math.min(o,c)*(1-r()*0.002)});p=c;}return cd;}
let sig=0;for(let k=0;k<400;k++){const x=E.smcSetup(walk(k*7919+13,240),{tf:'15m'});if(x&&x.stage==='SIGNAL')sig++;}
console.log('fire rate on structureless noise:',(sig/4).toFixed(1)+'%');
