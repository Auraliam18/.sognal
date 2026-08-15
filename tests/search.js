/* Overnight parameter search, run on hosted runners rather than the laptop.
   The rule that matters: every candidate is fitted on one set of markets and
   judged on markets it has never seen. A configuration that wins in-sample and
   loses out-of-sample is overfitting, and this refuses to adopt it. */
const os=require("os"),fs=require("fs"),path=require("path"),crypto=require("crypto");
const {Worker,isMainThread,parentPort,workerData}=require("worker_threads");
const {simulate}=require("./sim.js");
const H=require("./harness.js");

/* Checkpointing. Ten consecutive nights ran for exactly 5:00:21 and committed
   nothing: the grid does not fit in the timeout, and results only existed in
   memory until the very end, so hitting the wall threw the whole night away.
   Now every finished configuration is written to a cache the moment it lands,
   and the next night resumes from there. The grid completes over several
   nights instead of never.

   The cache is keyed on the engine slice the harness actually executes plus
   the simulator, so a change to either invalidates it. Keying on the whole of
   index.html would invalidate nightly on unrelated panel edits; keying on
   nothing would silently reuse results measured against different code. */
const CACHE=path.join(__dirname,"..","claude-liam-signal","cycles","search-cache.json");
const sha=s=>crypto.createHash("sha256").update(s).digest("hex").slice(0,16);
function engineSlice(){
  const re=/<script[^>]*>([\s\S]*?)<\/script>/g;let m,best="";
  const html=fs.readFileSync(path.join(__dirname,"..","index.html"),"utf8");
  while((m=re.exec(html)))if(m[1].length>best.length)best=m[1];
  return best.slice(best.indexOf("function rsiSeries"),best.indexOf("function smcQmin"));
}
const keyOf=c=>`${c.fresh}|${c.rmin}|${c.decisive}|${c.disp}`;

/* The tunables, with the shipped value first so a null result changes nothing. */
/* First value in each list is what is shipped, so the baseline row always
   exists in the grid and the comparison is against the real engine. Read from
   the engine rather than restated, because restating it is how the baseline
   silently became a different configuration than the one running. */
function shipped(){
  const fs=require("fs"),path=require("path");
  const src=fs.readFileSync(path.join(__dirname,"..","index.html"),"utf8");
  const one=(re,d)=>{const m=src.match(re);return m?+m[1]:d;};
  return{
    fresh:    one(/smcFreshBars\(\):(\d+)\)/,10),
    rmin:     one(/const RMIN=([\d.]+);/,1.8),
    decisive: one(/Math\.abs\(cd\[brk\]\.c-piv\.p\)<atr\*([\d.]+)\)/,0.35),
    disp:     one(/Math\.abs\(ext-piv\.p\)<atr\*([\d.]+)\)/,1.5)
  };
}
const SHIP=shipped();
const uniq=a=>a.filter((v,i)=>a.indexOf(v)===i);
const GRID={
  fresh:    uniq([SHIP.fresh,    8,12,15,20]),
  rmin:     uniq([SHIP.rmin,     1.5,2.2,2.6]),
  decisive: uniq([SHIP.decisive, 0.25,0.5,0.7]),
  disp:     uniq([SHIP.disp,     1.2,1.9,2.3])
};
/* Anchored on unique surrounding code rather than bare numbers, so an edit to
   the engine cannot silently turn the grid into one repeated cell. Every key is
   verified to match before the run starts — the last search reported three
   different thresholds with identical results because two of these had gone
   stale and were replacing nothing. */
const ANCHORS={
  fresh:    /const fresh=cd\.length-1-ob\.brk<=\(typeof smcFreshBars==="function"\?smcFreshBars\(\):\d+\);/,
  rmin:     /const RMIN=[\d.]+;/,
  decisive: /if\(Math\.abs\(cd\[brk\]\.c-piv\.p\)<atr\*[\d.]+\)continue;/,
  disp:     /if\(Math\.abs\(ext-piv\.p\)<atr\*[\d.]+\)continue;/
};
function patch(c){
  return{
    __regex:[
      [ANCHORS.fresh,    `const fresh=cd.length-1-ob.brk<=${c.fresh};`],
      [ANCHORS.rmin,     `const RMIN=${c.rmin};`],
      [ANCHORS.decisive, `if(Math.abs(cd[brk].c-piv.p)<atr*${c.decisive})continue;`],
      [ANCHORS.disp,     `if(Math.abs(ext-piv.p)<atr*${c.disp})continue;`]
    ]
  };
}
function assertAnchors(){
  const fs=require("fs"),path=require("path");
  const src=fs.readFileSync(path.join(__dirname,"..","index.html"),"utf8");
  const missing=Object.entries(ANCHORS).filter(([,re])=>!re.test(src)).map(([k])=>k);
  if(missing.length){
    console.error(`These knobs no longer match the engine: ${missing.join(", ")}.`);
    console.error("Fix the anchors in tests/search.js before trusting a search.");
    process.exit(2);
  }
}
function evaluate(c,from,to){
  const E=H.loadEngine(patch(c));
  const out=[];
  for(let s=from;s<to;s++)
    for(const t of H.evaluate(E,simulate(s*1013+7,1500)))out.push(t.win?t.R:-1);
  return out;
}
const stat=a=>{
  if(!a.length)return{n:0,ev:0,net:0,lo:0};
  const ev=a.reduce((x,y)=>x+y,0)/a.length;
  const o=[];
  for(let b=0;b<300;b++){let s=0;for(let i=0;i<a.length;i++)s+=a[(Math.random()*a.length)|0];o.push(s/a.length);}
  o.sort((p,q)=>p-q);
  return{n:a.length,ev:+ev.toFixed(4),net:+a.reduce((x,y)=>x+y,0).toFixed(0),lo:+o[7].toFixed(4),hi:+o[292].toFixed(4)};
};

if(!isMainThread){
  /* One message per configuration rather than one at the end, so the main
     thread can bank each result as it lands and lose nothing on a stop. */
  for(const c of workerData.configs){
    parentPort.postMessage({key:keyOf(c),c,
      fit:stat(evaluate(c,workerData.fitFrom,workerData.fitTo)),
      test:stat(evaluate(c,workerData.testFrom,workerData.testTo))});
  }
  parentPort.postMessage({done:true});
}else{
  const FIT=+(process.env.FIT||160), TEST=+(process.env.TEST||160);
  const CORES=Math.max(1,Math.min(os.cpus().length,+(process.env.CORES||os.cpus().length)));
  const configs=[];
  for(const fresh of GRID.fresh)for(const rmin of GRID.rmin)
    for(const decisive of GRID.decisive)for(const disp of GRID.disp)
      configs.push({fresh,rmin,decisive,disp});
  const only=+(process.env.LIMIT||0);
  const list=only?configs.slice(0,only):configs;
  assertAnchors();

  /* Budget deliberately below the workflow timeout, so the run stops itself,
     writes, and lets the commit step execute — the step that ten cancelled
     nights never reached. */
  const BUDGET=+(process.env.BUDGET_MIN||270)*60000;
  const fingerprint=sha(engineSlice()+fs.readFileSync(path.join(__dirname,"sim.js"),"utf8"));

  let cache={engine:fingerprint,fit:FIT,test:TEST,results:{}};
  try{
    const prev=JSON.parse(fs.readFileSync(CACHE,"utf8"));
    if(prev.engine===fingerprint&&prev.fit===FIT&&prev.test===TEST){
      cache=prev;
      console.log(`resuming — ${Object.keys(cache.results).length} configurations already measured`);
    }else{
      console.log("cache discarded — engine, simulator or market split changed since it was written");
    }
  }catch{/* first run */}

  const todo=list.filter(c=>!cache.results[keyOf(c)]);
  console.log(`${list.length} configurations · shipped is fresh ${SHIP.fresh}, R ${SHIP.rmin}, decisive ${SHIP.decisive}, disp ${SHIP.disp}`);
  console.log(`fit on markets 1-${FIT}, judged on ${FIT+1}-${FIT+TEST} · ${CORES} cores · ${todo.length} left to measure`);

  const saveCache=()=>{
    fs.mkdirSync(path.dirname(CACHE),{recursive:true});
    fs.writeFileSync(CACHE,JSON.stringify(cache));
  };

  const t0=Date.now();
  const per=Math.ceil(todo.length/CORES),jobs=[];
  for(let i=0;i<CORES;i++){
    const slice=todo.slice(i*per,(i+1)*per);
    if(slice.length)jobs.push({configs:slice,fitFrom:1,fitTo:1+FIT,testFrom:1+FIT,testTo:1+FIT+TEST});
  }

  const workers=[];
  let stopped=false;
  const timer=setTimeout(()=>{
    stopped=true;
    console.log(`budget of ${BUDGET/60000} minutes reached — banking what is measured and stopping`);
    workers.forEach(w=>w.terminate());
  },BUDGET);

  Promise.all(jobs.map(w=>new Promise((res,rej)=>{
    const wk=new Worker(__filename,{workerData:w});
    workers.push(wk);
    wk.on("message",m=>{
      if(m.done){wk.terminate();return res();}
      cache.results[m.key]={c:m.c,fit:m.fit,test:m.test};
      saveCache();
      const n=Object.keys(cache.results).length;
      if(n%10===0)console.log(`  ${n}/${list.length} measured · ${((Date.now()-t0)/60000).toFixed(1)} min`);
    });
    wk.on("error",rej);
    wk.on("exit",()=>res());          // terminate() on budget stop lands here
  }))).then(()=>{
    clearTimeout(timer);
    saveCache();
    const all=list.map(c=>cache.results[keyOf(c)]).filter(Boolean);
    const complete=all.length>=list.length;
    const base=all.find(r=>r.c.fresh===SHIP.fresh&&r.c.rmin===SHIP.rmin&&r.c.decisive===SHIP.decisive&&r.c.disp===SHIP.disp);
    /* Rank on out-of-sample only, and require the interval to clear zero there. */
    const ranked=all.filter(r=>r.test.n>=300&&r.test.lo>0)
                    .sort((a,b)=>b.test.ev-a.test.ev);
    const best=ranked[0]||null;
    const secs=+((Date.now()-t0)/1000).toFixed(1);
    const L=[`# Parameter search — ${new Date().toISOString().slice(0,16).replace("T"," ")} UTC`,``,
      `${all.length} of ${list.length} configurations measured, fitted on ${FIT} markets and judged on ${TEST} the engine never saw. ${secs}s this run.`,``];
    if(!complete)L.push(`> **Partial.** ${list.length-all.length} configurations still unmeasured; the next run resumes from the cache. `+
      `Rankings below cover only what has been measured, so a better configuration may still be unseen — nothing is adopted from a partial grid.`,``);
    if(base)L.push(`**Shipped configuration** — out-of-sample ${base.test.ev>0?"+":""}${base.test.ev}R [${base.test.lo}, ${base.test.hi}] on ${base.test.n} trades.`,``);
    L.push(`| rank | fresh | R min | decisive | displacement | in-sample | out-of-sample | interval | trades |`,
           `|---|---|---|---|---|---|---|---|---|`);
    ranked.slice(0,12).forEach((r,i)=>L.push(
      `| ${i+1} | ${r.c.fresh} | ${r.c.rmin} | ${r.c.decisive} | ${r.c.disp} | ${r.fit.ev>0?"+":""}${r.fit.ev}R | **${r.test.ev>0?"+":""}${r.test.ev}R** | [${r.test.lo}, ${r.test.hi}] | ${r.test.n} |`));
    const gap=r=>+(r.fit.ev-r.test.ev).toFixed(3);
    if(best&&!complete){
      const better=base?best.test.ev-base.test.ev:best.test.ev;
      L.push(``,`## Verdict`,``,
        `Held — the grid is ${all.length}/${list.length} measured. Best so far is fresh ${best.c.fresh}, `+
        `R min ${best.c.rmin}, decisive ${best.c.decisive} ATR, displacement ${best.c.disp} ATR `+
        `(${better>0?"+":""}${better.toFixed(3)}R over shipped, out-of-sample), but a verdict on an `+
        `incomplete grid is a verdict on an arbitrary subset. Nothing is adopted until the grid finishes.`);
    }else if(best){
      const better=base?best.test.ev-base.test.ev:best.test.ev;
      L.push(``,`## Verdict`,``);
      if(base&&better<=0.02){
        L.push(`Nothing beats what is already shipped by a margin worth taking (best is ${better>0?"+":""}${better.toFixed(3)}R over it, out-of-sample). No change.`);
      }else{
        L.push(`Best out-of-sample: fresh ${best.c.fresh}, R min ${best.c.rmin}, decisive ${best.c.decisive} ATR, displacement ${best.c.disp} ATR.`,
          `That is ${better>0?"+":""}${better.toFixed(3)}R per trade over the shipped configuration, on markets neither saw during fitting.`,
          `In-sample minus out-of-sample is ${gap(best)}R — the smaller that gap, the less of the gain is fitting noise.`,``,
          `Adopting it means editing index.html: freshness window, RMIN, and the two ATR thresholds in smcOrderBlocks.`);
      }
    }else L.push(``,`## Verdict`,``,`No configuration cleared zero out-of-sample with enough trades to judge. Nothing to adopt.`);
    const dir=path.join(__dirname,"..","claude-liam-signal","cycles");
    fs.mkdirSync(dir,{recursive:true});
    fs.writeFileSync(path.join(dir,"search-latest.md"),L.join("\n"));
    fs.writeFileSync(path.join(dir,`search-${new Date().toISOString().slice(0,13).replace(/[:T]/g,"-")}.json`),
      JSON.stringify({at:new Date().toISOString(),fit:FIT,test:TEST,base,ranked:ranked.slice(0,20)},null,1));
    console.log(L.join("\n"));
  }).catch(e=>{console.error(e);process.exit(1);});
}
