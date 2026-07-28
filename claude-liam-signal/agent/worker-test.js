/* Proves the worker pool itself: spawn one per core, hand each a slice, and
   confirm every worker reports back. Uses generated candles, no network. */
const os=require("os"),path=require("path"),{Worker}=require("worker_threads");
const cores=Math.min(os.cpus().length,4);
const slices=Array.from({length:cores},(_,i)=>[`W${i}A`,`W${i}B`]);
const t0=Date.now();
Promise.all(slices.map((symbols,i)=>new Promise(done=>{
  const w=new Worker(path.join(__dirname,"worker-probe.js"),{workerData:{symbols,id:i}});
  w.on("message",m=>{done(m);w.terminate();});
  w.on("error",e=>done({error:e.message}));
}))).then(r=>{
  const ok=r.filter(x=>x&&x.trades!=null).length;
  console.log(`workers: ${ok}/${cores} reported · ${r.reduce((a,x)=>a+(x.trades||0),0)} positions · ${((Date.now()-t0)/1000).toFixed(1)}s`);
  r.forEach(x=>x.error&&console.log("  error:",x.error));
});
