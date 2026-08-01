/* Worker used by worker-test: exercises the same replay path on generated
   candles so the pool can be verified without the exchange. */
const {parentPort,workerData}=require("worker_threads");
const {replay}=require("./trainer");
const gen=(sd,n)=>{let s=sd,p=50+sd%150;const o=[];const rnd=()=>(s=(s*1103515245+12345)%2147483648)/2147483648;
  for(let i=0;i<n;i++){const ph=(i+sd)%130;let d;
    if(ph<48)d=-0.004+rnd()*0.0018;else if(ph<62)d=0.009+rnd()*0.002;
    else if(ph<76)d=-0.012-rnd()*0.003;else if(ph<88)d=0.011+rnd()*0.002;
    else if(ph<98)d=-0.010;else if(ph<112)d=0.010;else d=-0.013;
    const op=p,c=p*(1+d);
    o.push({t:i*9e5,o:op,h:Math.max(op,c)*(1+rnd()*0.003),l:Math.min(op,c)*(1-rnd()*0.003),c,v:4000});p=c;}
  return o;};
let n=0;
for(const sym of workerData.symbols)
  for(const tf of ["15m","5m"])
    n+=replay(gen([...sym].reduce((a,c)=>a+c.charCodeAt(0),0)+workerData.id*31,900),tf,sym).length;
parentPort.postMessage({id:workerData.id,trades:n});
