/* One paper-trading cycle, reduced to a report. Runs on whatever machine will
   have it — a GitHub runner costs nothing and leaves the laptop alone. Writes
   both a machine-readable record and a page a person can read. */
const os=require("os"),fs=require("fs"),path=require("path");
const {Worker,isMainThread,parentPort,workerData}=require("worker_threads");
const {simulate}=require("./sim.js");
const H=require("./harness.js");

if(!isMainThread){
  const E=H.loadEngine();
  let out=[];
  for(let s=workerData.from;s<workerData.to;s++){
    for(const t of H.evaluate(E,simulate(s*1013+7,1500)))
      out.push({w:t.win?1:0,R:+t.R.toFixed(3),d:t.dir==="LONG"?1:0,v:t.visits,
                ch:t.chOk?1:0,f:t.fvg?1:0,l:t.lvl?1:0,dp:t.depth});
  }
  parentPort.postMessage(out);
}else{
  const CORES=Math.max(1,Math.min(os.cpus().length,+(process.env.CORES||os.cpus().length)));
  const MARKETS=+(process.env.MARKETS||600);
  const per=Math.ceil(MARKETS/CORES);
  const jobs=[];
  for(let i=0;i<CORES;i++)jobs.push({from:1+i*per,to:1+Math.min(MARKETS,(i+1)*per)});
  const t0=Date.now();
  Promise.all(jobs.map(w=>new Promise((res,rej)=>{
    const wk=new Worker(__filename,{workerData:w});
    wk.on("message",m=>{res(m);wk.terminate();});
    wk.on("error",rej);
  }))).then(parts=>{
    const a=parts.flat();
    const ev=g=>g.length?g.reduce((s,x)=>s+(x.w?x.R:-1),0)/g.length:0;
    const ci=(g,B=400)=>{
      if(g.length<25)return null;
      const n=g.length,o=[];
      for(let b=0;b<B;b++){let s=0;for(let i=0;i<n;i++){const x=g[(Math.random()*n)|0];s+=x.w?x.R:-1;}o.push(s/n);}
      o.sort((p,q)=>p-q);return[+o[Math.floor(B*.025)].toFixed(3),+o[Math.floor(B*.975)].toFixed(3)];
    };
    const slice=(name,g)=>{
      if(!g.length)return null;
      const c=ci(g);
      return{name,n:g.length,hit:Math.round(g.filter(x=>x.w).length/g.length*100),
        avgR:+(g.reduce((s,x)=>s+x.R,0)/g.length).toFixed(2),ev:+ev(g).toFixed(3),ci:c,
        verdict:!c?"inconclusive (small)":c[0]>0?"positive":c[1]<0?"negative":"inconclusive"};
    };
    const groups=[
      {title:"direction",list:[slice("long",a.filter(x=>x.d===1)),slice("short",a.filter(x=>x.d===0))]},
      {title:"pullbacks",list:[slice("first",a.filter(x=>x.v===1)),slice("second",a.filter(x=>x.v===2)),slice("third+",a.filter(x=>x.v>=3))]},
      {title:"evidence",list:[slice("with FVG",a.filter(x=>x.f===1)),slice("without FVG",a.filter(x=>x.f===0)),
        slice("at key level",a.filter(x=>x.l===1)),slice("with channel",a.filter(x=>x.ch===1)),slice("against channel",a.filter(x=>x.ch===0))]},
      {title:"risk-reward",list:[slice("under 2R",a.filter(x=>x.R<2)),slice("2-3R",a.filter(x=>x.R>=2&&x.R<3)),slice("3R+",a.filter(x=>x.R>=3))]},
      {title:"penetration",list:[slice("under 50%",a.filter(x=>x.dp<50)),slice("50%+",a.filter(x=>x.dp>=50))]}
    ].map(g=>({...g,list:g.list.filter(Boolean)}));
    const all=slice("all",a);
    const rep={at:new Date().toISOString(),markets:MARKETS,cores:CORES,
      seconds:+((Date.now()-t0)/1000).toFixed(1),all,groups};

    const dir=path.join(__dirname,"..","claude-liam-signal","cycles");
    fs.mkdirSync(dir,{recursive:true});
    const stamp=rep.at.slice(0,16).replace(/[:T]/g,"-");
    fs.writeFileSync(path.join(dir,`${stamp}.json`),JSON.stringify(rep,null,1));

    const L=[`# Paper trading cycle — ${rep.at.replace("T"," ").slice(0,16)} UTC`,``,
      `${all.n} trades across ${MARKETS} simulated markets, ${CORES} cores, ${rep.seconds}s.`,``,
      `**Overall: ${all.hit}% win, ${all.avgR} average R, ${all.ev > 0 ? "+" : ""}${all.ev}R expectancy** [${all.ci[0]}, ${all.ci[1]}] — ${all.verdict}`,``,
      `| slice | trades | win | avg R | expectancy | 95% interval | verdict |`,
      `|---|---|---|---|---|---|---|`];
    for(const g of groups)for(const x of g.list)
      L.push(`| ${g.title} · ${x.name} | ${x.n} | ${x.hit}% | ${x.avgR} | ${x.ev>0?"+":""}${x.ev}R | ${x.ci?`[${x.ci[0]}, ${x.ci[1]}]`:"—"} | ${x.verdict} |`);
    const neg=groups.flatMap(g=>g.list).filter(x=>x.verdict==="negative");
    L.push(``,neg.length
      ? `## Action\n\nNegative slices found: ${neg.map(x=>`${x.name} (${x.ev}R)`).join(", ")}. One change is warranted; the panel applies it on its next review and grades it on the cycle after.`
      : `## Action\n\nNo slice is significantly negative. No change is warranted — a finding needs its interval to clear zero before it is acted on.`);
    fs.writeFileSync(path.join(dir,"latest.md"),L.join("\n"));
    console.log(L.slice(0,6).join("\n"));
    console.log(`\nwrote claude-liam-signal/cycles/${stamp}.json and latest.md`);
  }).catch(e=>{console.error(e);process.exit(1);});
}
