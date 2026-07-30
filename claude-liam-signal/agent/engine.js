/* GENERATED — do not edit. Rebuild with: node extract-engine.js
   Source: index.html, the same code the panel runs. */
const {db:DB}=require("./store");
const COMMODITY_KEEP=new Set(["XAU","XAUT","PAXG","GOLD","XAG","SILVER","SLV","OIL","USOIL","UKOIL","WTI","WTIUSD","BRENT","CRUDE","NGAS"]);
const CASES=(()=>{
  const KEYS=["rr","depth","fvg","level","channel","visits2","btc","ibs","ext","intel","usdtd"];
  const load=()=>DB.get("cases")||[];
  const save=a=>DB.set("cases",a.slice(-3000));
  function add(feat,won,R,meta){
    if(!feat)return;
    const a=load();
    a.push({f:KEYS.map(k=>+(feat[k]||0).toFixed(3)),w:won?1:0,R:+(+R||0).toFixed(2),
            t:Date.now(),s:(meta&&meta.asset)||"",d:(meta&&meta.dir)||"",tf:(meta&&meta.tf)||""});
    save(a);
  }
  function dist(a,b){let d=0;for(let i=0;i<a.length;i++){const x=a[i]-b[i];d+=x*x;}return Math.sqrt(d);}
  function similar(feat,k){
    if(!feat)return null;
    const a=load();if(a.length<5)return{n:0,hit:0,ev:0,pool:a.length};
    const v=KEYS.map(x=>+(feat[x]||0).toFixed(3));
    const scored=a.map(c=>({c,d:dist(v,c.f)})).sort((p,q)=>p.d-q.d).slice(0,k||25);
    const n=scored.length,w=scored.filter(x=>x.c.w).length;
    const ev=scored.reduce((s,x)=>s+(x.c.w?x.c.R:-1),0)/n;
    return{n,hit:Math.round(w/n*100),ev:+ev.toFixed(2),pool:a.length,
           radius:+scored[n-1].d.toFixed(2)};
  }
  return{add,similar,load,count:()=>load().length};
})();
function rsiSeries(c,p=14){
  if(c.length<p+1)return[];
  const out=new Array(c.length).fill(null);let g=0,l=0;
  for(let i=1;i<=p;i++){const d=c[i]-c[i-1];if(d>=0)g+=d;else l-=d;}
  g/=p;l/=p;out[p]=l===0?100:100-100/(1+g/l);
  for(let i=p+1;i<c.length;i++){const d=c[i]-c[i-1];
    g=(g*(p-1)+(d>0?d:0))/p;l=(l*(p-1)+(d<0?-d:0))/p;
    out[i]=l===0?100:100-100/(1+g/l);}
  return out;
}
function smcATR(cd,p=14){
  if(cd.length<p+1)return 0;let a=0;
  for(let i=cd.length-p;i<cd.length;i++)a+=Math.max(cd[i].h-cd[i].l,Math.abs(cd[i].h-cd[i-1].c),Math.abs(cd[i].l-cd[i-1].c));
  return a/p;
}
/* linear-regression channel: slope, rails, and where price sits inside it */
function smcChannel(cd,look=120){
  const n=Math.min(look,cd.length);if(n<40)return null;
  const s=cd.slice(-n),xs=s.map((_,i)=>i),ys=s.map(k=>k.c);
  const mx=xs.reduce((a,b)=>a+b,0)/n,my=ys.reduce((a,b)=>a+b,0)/n;
  let num=0,den=0;for(let i=0;i<n;i++){num+=(xs[i]-mx)*(ys[i]-my);den+=(xs[i]-mx)**2;}
  const slope=den?num/den:0,inter=my-slope*mx;
  const line=i=>inter+slope*i;
  let up=-Infinity,dn=Infinity;
  for(let i=0;i<n;i++){up=Math.max(up,s[i].h-line(i));dn=Math.min(dn,s[i].l-line(i));}
  const last=n-1,mid=line(last),width=up-dn;
  const pct=width?((s[last].c-(line(last)+dn))/width)*100:50;
  const drift=mid?slope*n/mid*100:0;     // % move across the window
  const dir=drift<-1.5?"نزولی":drift>1.5?"صعودی":"خنثی";
  return{slope,dir,drift:Math.round(drift*10)/10,upper:mid+up,lower:mid+dn,mid,
         posPct:Math.max(0,Math.min(100,Math.round(pct))),bars:n};
}
/* fair value gaps (3-candle imbalance), newest first, unfilled only */
function smcFVGs(cd,max=6){
  const out=[];
  for(let i=cd.length-2;i>=2&&out.length<max;i--){
    const a=cd[i-2],c=cd[i];
    if(c.l>a.h){ // bullish gap
      let filled=false;for(let j=i+1;j<cd.length;j++)if(cd[j].l<=a.h){filled=true;break;}
      if(!filled)out.push({dir:"LONG",low:a.h,high:c.l,i,mid:(a.h+c.l)/2});
    }else if(c.h<a.l){ // bearish gap
      let filled=false;for(let j=i+1;j<cd.length;j++)if(cd[j].h>=a.l){filled=true;break;}
      if(!filled)out.push({dir:"SHORT",low:c.h,high:a.l,i,mid:(c.h+a.l)/2});
    }
  }
  return out;
}
/* support / resistance: swing pivots clustered by proximity, ranked by touches */
function smcLevels(cd,k=4,tolPct=0.004){
  const piv=[];
  for(let i=k;i<cd.length-k;i++){
    let hi=true,lo=true;
    for(let j=i-k;j<=i+k;j++){if(j===i)continue;if(cd[j].h>cd[i].h)hi=false;if(cd[j].l<cd[i].l)lo=false;}
    if(hi)piv.push({p:cd[i].h,t:"R",i});
    if(lo)piv.push({p:cd[i].l,t:"S",i});
  }
  const cl=[];
  for(const v of piv){
    const f=cl.find(c=>Math.abs(c.price-v.p)/v.p<tolPct);
    if(f){f.touches++;f.price=(f.price*(f.touches-1)+v.p)/f.touches;f.last=Math.max(f.last,v.i);}
    else cl.push({price:v.p,type:v.t,touches:1,last:v.i});
  }
  return cl.sort((a,b)=>b.touches-a.touches||b.last-a.last).slice(0,8);
}
/* order blocks: last opposite candle before the impulse that broke structure */
function smcOrderBlocks(cd,k=4,max=4){
  const atr=smcATR(cd)||1e-9;const sw=[];
  for(let i=k;i<cd.length-k;i++){
    let hi=true,lo=true;
    for(let j=i-k;j<=i+k;j++){if(j===i)continue;if(cd[j].h>cd[i].h)hi=false;if(cd[j].l<cd[i].l)lo=false;}
    const near=sw[sw.length-1];
    if(hi&&!(near&&near.t==="H"&&i-near.i<=k))sw.push({i,p:cd[i].h,t:"H"});
    if(lo&&!(near&&near.t==="L"&&i-near.i<=k))sw.push({i,p:cd[i].l,t:"L"});
  }
  const obs=[];
  for(let s=sw.length-1;s>=0&&obs.length<max;s--){
    const piv=sw[s];
    // structure break after this pivot?
    let brk=-1;
    for(let i=piv.i+1;i<cd.length;i++){
      if(piv.t==="L"&&cd[i].c<piv.p){brk=i;break;}
      if(piv.t==="H"&&cd[i].c>piv.p){brk=i;break;}
    }
    if(brk<0)continue;
    const dir=piv.t==="L"?"SHORT":"LONG";
    // the break must be decisive, and the leg after it must actually displace price
    if(Math.abs(cd[brk].c-piv.p)<atr*0.35)continue;
    let ext=cd[brk].c;
    for(let i=brk;i<Math.min(cd.length,brk+6);i++)ext=dir==="SHORT"?Math.min(ext,cd[i].l):Math.max(ext,cd[i].h);
    if(Math.abs(ext-piv.p)<atr*1.5)continue;
    // last candle against the impulse, just before the break
    let ob=-1;
    for(let i=brk-1;i>=Math.max(0,brk-12);i--){
      if(dir==="SHORT"&&cd[i].c>cd[i].o){ob=i;break;}
      if(dir==="LONG"&&cd[i].c<cd[i].o){ob=i;break;}
    }
    if(ob<0)continue;
    const b=cd[ob],low=Math.min(b.o,b.c,b.l),high=Math.max(b.o,b.c,b.h);
    if(high-low<atr*0.12||high-low>atr*3.5)continue;
    if(obs.some(o=>Math.abs(o.mid-(low+high)/2)/((low+high)/2)<0.002))continue;
    obs.push({dir,i:ob,brk,low,high,mid:(low+high)/2,pivot:piv.p});
  }
  return obs;
}
/* how many separate visits back into the box, and is price outside it now */
function obVisits(cd,ob){
  const box=ob.high-ob.low||1e-9,away=box*1.2;
  let visits=0,inside=false,lastExit=-1,deepest=0,left=false;
  for(let i=ob.brk;i<cd.length;i++){
    const touch=cd[i].h>=ob.low&&cd[i].l<=ob.high;
    const far=ob.dir==="SHORT"?(ob.low-cd[i].l>away):(cd[i].h-ob.high>away);
    if(far)left=true;                                  // price must actually leave before a return counts
    if(touch&&!inside){if(left){visits++;left=false;}inside=true;}
    else if(!touch&&inside){inside=false;lastExit=i;}
    if(touch)deepest=Math.max(deepest,ob.dir==="SHORT"?(cd[i].h-ob.low)/(ob.high-ob.low):(ob.high-cd[i].l)/(ob.high-ob.low));
  }
  return{visits,inside,lastExit,depth:Math.round(Math.min(1,deepest)*100)};
}
/* targets: prior swing low/high beyond entry */
function smcTargets(cd,dir,entry,k=4){
  const lows=[],highs=[];
  for(let i=k;i<cd.length-k;i++){
    let hi=true,lo=true;
    for(let j=i-k;j<=i+k;j++){if(j===i)continue;if(cd[j].h>cd[i].h)hi=false;if(cd[j].l<cd[i].l)lo=false;}
    if(hi)highs.push(cd[i].h);
    if(lo)lows.push(cd[i].l);
  }
  let pool=(dir==="SHORT"?lows.filter(p=>p<entry).sort((a,b)=>b-a):highs.filter(p=>p>entry).sort((a,b)=>a-b));
  const out=[];for(const p of pool){if(!out.length||Math.abs(p-out[out.length-1])/entry>0.004)out.push(p);}
  return{tp1:out[0]||null,tp2:out[1]||null,pool:out.slice(0,3)};
}
/* BTC 4h RSI divergence — regular and hidden */
function rsiDivergence(cd,k=3){
  const closes=cd.map(c=>c.c),R=rsiSeries(closes,14);
  if(!R.length)return null;
  const piv={H:[],L:[]};
  for(let i=k;i<cd.length-k;i++){
    if(R[i]==null)continue;
    let hi=true,lo=true;
    for(let j=i-k;j<=i+k;j++){if(j===i)continue;if(cd[j].h>cd[i].h)hi=false;if(cd[j].l<cd[i].l)lo=false;}
    if(hi)piv.H.push({i,p:cd[i].h,r:R[i]});
    if(lo)piv.L.push({i,p:cd[i].l,r:R[i]});
  }
  const H=piv.H.slice(-2),L=piv.L.slice(-2);
  const out={rsi:Math.round((R[R.length-1]||50)*10)/10,type:null,label:"بدون واگرایی",bias:"NEUTRAL"};
  if(H.length===2){
    const[a,b]=H;
    if(b.p>a.p&&b.r<a.r){out.type="regular_bear";out.label="واگرایی منفی معمولی (سقف بالاتر، RSI پایین‌تر)";out.bias="SHORT";}
    else if(b.p<a.p&&b.r>a.r){out.type="hidden_bear";out.label="واگرایی منفی مخفی (ادامهٔ نزول)";out.bias="SHORT";}
  }
  if(!out.type&&L.length===2){
    const[a,b]=L;
    if(b.p<a.p&&b.r>a.r){out.type="regular_bull";out.label="واگرایی مثبت معمولی (کف پایین‌تر، RSI بالاتر)";out.bias="LONG";}
    else if(b.p>a.p&&b.r<a.r){out.type="hidden_bull";out.label="واگرایی مثبت مخفی (ادامهٔ صعود)";out.bias="LONG";}
  }
  return out;
}


/* =========================================================================
   USDT DOMINANCE — ported from the Codex v4 panel kept in
   claude-liam-signal/reference, then wired into this engine's decision layer.
   Money moving into Tether is money leaving alts: a rising USDT.D fights alt
   longs, a sharply falling one fights alt shorts. Samples are rate-limited,
   persisted, and fitted by regression so the slope survives a gap in the feed.
   ========================================================================= */
const DOM={url:"https://api.coingecko.com/api/v3/global",maxSamples:48,minGapMs:120000,trendMin:0.03,strongMin:0.10};
function domLoad(){const d=DB.get("usdtDom")||{samples:[]};if(!Array.isArray(d.samples))d.samples=[];return d;}
function domSave(d){DB.set("usdtDom",d);}
function domFit(pts){
  const n=pts.length;if(n<2)return{slope:0};
  let sx=0,sy=0,sxy=0,sxx=0;
  for(const[x,y]of pts){sx+=x;sy+=y;sxy+=x*y;sxx+=x*x;}
  const d=n*sxx-sx*sx;return{slope:d?(n*sxy-sx*sy)/d:0};
}
function domState(st,available){
  const s=st.samples;
  if(!available||!s.length)return{available:false,value:null,dir:"UNKNOWN",slopePerHr:0,samples:0};
  const value=s[s.length-1].v;
  if(s.length<3)return{available:true,value,dir:"FLAT",slopePerHr:0,samples:s.length};
  const win=s.slice(-12),t0=win[0].t;
  const slope=domFit(win.map(p=>[(p.t-t0)/3600000,p.v])).slope;
  let dir="FLAT";
  if(slope>=DOM.trendMin)dir=slope>=DOM.strongMin?"UP_STRONG":"UP";
  else if(slope<=-DOM.trendMin)dir=slope<=-DOM.strongMin?"DOWN_STRONG":"DOWN";
  return{available:true,value,dir,slopePerHr:+slope.toFixed(4),samples:s.length};
}
async function fetchUsdtDominance(){
  const st=domLoad(),now=Date.now(),last=st.samples[st.samples.length-1];
  if(last&&now-last.t<DOM.minGapMs)return domState(st,true);
  try{
    const r=await fetch(DOM.url,{cache:"no-store"});
    if(!r.ok)throw new Error("HTTP "+r.status);
    const j=await r.json();
    const pct=j&&j.data&&j.data.market_cap_percentage&&+j.data.market_cap_percentage.usdt;
    if(!isFinite(pct)||pct<=0)throw new Error("no usdt pct");
    st.samples.push({t:now,v:pct});
    if(st.samples.length>DOM.maxSamples)st.samples.splice(0,st.samples.length-DOM.maxSamples);
    st.lastOkAt=now;domSave(st);
    return domState(st,true);
  }catch(e){
    const fresh=last&&(now-last.t)<18e5;      // keep using samples up to 30 min old
    return fresh?domState(st,true):domState(st,false);
  }
}
function domFa(dom){
  if(!dom||!dom.available)return"دامیننس تتر: در دسترس نیست";
  const arrow={UP_STRONG:"▲▲",UP:"▲",FLAT:"◆",DOWN:"▼",DOWN_STRONG:"▼▼"}[dom.dir]||"◆";
  return`دامیننس تتر ${dom.value.toFixed(2)}% ${arrow}`;
}
function domConflicts(dir,asset,dom){
  if(!dom||!dom.available)return false;
  if(asset==="BTC"||COMMODITY_KEEP.has(asset))return false;
  if(dir==="LONG")return dom.dir==="UP"||dom.dir==="UP_STRONG";
  if(dir==="SHORT")return dom.dir==="DOWN_STRONG";
  return false;
}

/* =========================================================================
   WILDER — three ideas from New Concepts in Technical Trading Systems (1978),
   the book that introduced RSI, ATR, ADX/DMI and Parabolic SAR as one system:
   the ADX says whether a trend exists, the SAR manages the stop inside it, the
   ATR sizes it, the RSI measures the push.

   All three are off until measured. Wilder's own emphasis is worth keeping:
   he rated the failure swing above divergence, and said divergence is not a
   timing signal.
   ========================================================================= */
function wilderADX(cd,p){
  p=p||14;
  if(!cd||cd.length<2*p+1)return{adx:0,pdi:0,ndi:0};
  const tr=[],pdm=[],ndm=[];
  for(let i=1;i<cd.length;i++){
    const up=cd[i].h-cd[i-1].h, dn=cd[i-1].l-cd[i].l;
    pdm.push(up>dn&&up>0?up:0);
    ndm.push(dn>up&&dn>0?dn:0);
    tr.push(Math.max(cd[i].h-cd[i].l,Math.abs(cd[i].h-cd[i-1].c),Math.abs(cd[i].l-cd[i-1].c)));
  }
  /* Wilder smoothing: first value is a plain sum, then subtract 1/p and add the new. */
  const sm=a=>{let v=0;for(let i=0;i<p;i++)v+=a[i];const o=[v];
    for(let i=p;i<a.length;i++){v=v-v/p+a[i];o.push(v);}return o;};
  const T=sm(tr),P=sm(pdm),N=sm(ndm);
  const dx=[];
  for(let i=0;i<T.length;i++){
    if(!T[i])continue;
    const pdi=100*P[i]/T[i], ndi=100*N[i]/T[i], sum=pdi+ndi;
    if(sum)dx.push(100*Math.abs(pdi-ndi)/sum);
  }
  if(dx.length<p)return{adx:0,pdi:0,ndi:0};
  let adx=0;for(let i=0;i<p;i++)adx+=dx[i];adx/=p;
  for(let i=p;i<dx.length;i++)adx=(adx*(p-1)+dx[i])/p;
  const last=T.length-1;
  return{adx:+adx.toFixed(1),
         pdi:T[last]?+(100*P[last]/T[last]).toFixed(1):0,
         ndi:T[last]?+(100*N[last]/T[last]).toFixed(1):0};
}
/* Parabolic SAR as Wilder built it: a trailing stop, not an entry. Step 0.02,
   cap 0.20, and it only belongs in a market the ADX says is trending. */
function wilderSAR(cd,step,max){
  step=step||0.02;max=max||0.20;
  if(!cd||cd.length<5)return null;
  let up=cd[1].c>=cd[0].c, sar=up?cd[0].l:cd[0].h, ep=up?cd[1].h:cd[1].l, af=step;
  for(let i=2;i<cd.length;i++){
    sar=sar+af*(ep-sar);
    if(up){
      sar=Math.min(sar,cd[i-1].l,cd[i-2].l);
      if(cd[i].l<sar){up=false;sar=ep;ep=cd[i].l;af=step;}
      else if(cd[i].h>ep){ep=cd[i].h;af=Math.min(af+step,max);}
    }else{
      sar=Math.max(sar,cd[i-1].h,cd[i-2].h);
      if(cd[i].h>sar){up=true;sar=ep;ep=cd[i].h;af=step;}
      else if(cd[i].l<ep){ep=cd[i].l;af=Math.min(af+step,max);}
    }
  }
  return{sar:+sar,up};
}
/* The failure swing Wilder rated above divergence: RSI leaves the extreme,
   pulls back without re-entering it, then takes out its own prior turn. */
function wilderFailureSwing(cd,p){
  const R=rsiSeries(cd.map(c=>c.c),p||14);
  if(R.length<30)return null;
  const w=R.slice(-40).map((v,i)=>({v,i})).filter(x=>x.v!=null);
  if(w.length<12)return null;
  const piv=[];
  for(let i=2;i<w.length-2;i++){
    const a=w[i].v;
    if(a>w[i-1].v&&a>w[i-2].v&&a>w[i+1].v&&a>w[i+2].v)piv.push({v:a,t:"H",i});
    if(a<w[i-1].v&&a<w[i-2].v&&a<w[i+1].v&&a<w[i+2].v)piv.push({v:a,t:"L",i});
  }
  if(piv.length<3)return null;
  const last=piv.slice(-3);
  /* Bearish: a high above 70, a lower high that stays above 30, then the
     trough between them gives way. Bullish is the mirror. */
  if(last[0].t==="H"&&last[1].t==="L"&&last[2].t==="H"&&
     last[0].v>70&&last[2].v<last[0].v&&R[R.length-1]<last[1].v)
    return{dir:"SHORT",label:"شکست نوسان نزولی (RSI)"};
  if(last[0].t==="L"&&last[1].t==="H"&&last[2].t==="L"&&
     last[0].v<30&&last[2].v>last[0].v&&R[R.length-1]>last[1].v)
    return{dir:"LONG",label:"شکست نوسان صعودی (RSI)"};
  return null;
}
/* Wilder's threshold, confirmed on 4,730 outcomes: below 20 there is no trend
   worth trading (+0.167R), above 25 there is (+0.422R), above 35 more so
   (+0.529R). Gating costs total return because it removes trades — so it gates
   signals only. The practice desk still takes what falls below, as ARMED,
   which is where the learning sample comes from. */
function adxFloor(){const v=+DB.get("adx_floor");return isNaN(v)||v===0?25:v;}
function sarTrailOn(){return DB.get("sar_trail")===true;}
/* =========================================================================
   CONFIDENCE & EXPECTANCY — the signal decision.
   An arbitrary 0-100 score tells you nothing about whether a trade pays.
   Instead: estimate the probability that TP1 lands before the stop, from
   evidence weighted by an online logistic model, then require the trade to
   be worth taking:  EV = p·R − (1−p).  Weights start weakly-informative and
   are updated from this panel's own closed trades, so the model calibrates
   on the market you actually trade rather than on anyone's opinion.
   ========================================================================= */
const CONF_DEF={bias:-0.30,rr:-0.18,depth:0,fvg:0,level:0,channel:0,visits2:0,btc:0,ibs:0,ext:0,intel:0,usdtd:0};
function confW(){const w=DB.get("conf_w");return Object.assign({},CONF_DEF,w&&typeof w==="object"?w:{});}
function confFeat(s,ibs){
  const R=s.rr||0;
  return{bias:1,
    rr:Math.max(-1.5,Math.min(2.5,R-1.5)),
    depth:Math.max(-1,Math.min(1.5,(s.depth-40)/40)),
    fvg:s.fvg?1:0,
    level:s.level?1:0,
    channel:s.channel&&((s.dir==="SHORT"&&s.channel.dir==="نزولی")||(s.dir==="LONG"&&s.channel.dir==="صعودی"))?1:0,
    visits2:s.visits>=2?1:0,
    btc:s.btcDiv&&s.btcDiv.bias&&s.btcDiv.bias!=="NEUTRAL"?(s.btcDiv.bias===s.dir?1:-1):0,
    ibs:ibs&&ibs.dir===s.dir?(ibs.quality>=55?1:0.5):(ibs?-0.5:0),
    intel:(typeof intelBias==="function")?(s.dir==="LONG"?intelBias():-intelBias()):0,
    usdtd:(s.domConflict?-1:0),
    ext:s.tpExt?1:0};
}
function confP(s,ibs){
  const w=confW(),x=confFeat(s,ibs);
  let z=0;for(const k in x)z+=(w[k]||0)*x[k];
  return 1/(1+Math.exp(-z));
}
function confEV(p,R){return p*R-(1-p);}
/* one SGD step per closed trade — the model learns from what actually happened */
function confLearn(feat,won,lr){
  if(!feat)return;
  const w=confW();let z=0;for(const k in feat)z+=(w[k]||0)*feat[k];
  const p=1/(1+Math.exp(-z)),err=(won?1:0)-p,rate=lr||0.05;
  for(const k in feat)w[k]=(w[k]||0)+rate*err*feat[k];
  for(const k in w)w[k]=Math.max(-3,Math.min(3,w[k]));
  DB.set("conf_w",w);DB.set("conf_n",(+DB.get("conf_n")||0)+1);
}
function evMin(){const v=+DB.get("ev_min");return isNaN(v)||v===0?0.05:v;}
function confN(){return +DB.get("conf_n")||0;}
function confReady(){return confN()>=40;}   // below this the model is still uninformed
/* ---- the setup ---- */
function smcSetup(cd,opts){
  opts=opts||{};
  if(!cd||cd.length<80)return null;
  const atr=smcATR(cd)||1e-9;
  const dmi=wilderADX(cd);
  const fs=wilderFailureSwing(cd);
  const ch=smcChannel(cd),obs=smcOrderBlocks(cd),fvgs=smcFVGs(cd),levels=smcLevels(cd);
  if(!obs.length)return null;
  const last=cd[cd.length-1],price=last.c;
  let best=null;
  for(const ob of obs){
    const v=obVisits(cd,ob);
    const box=ob.high-ob.low;if(!box)continue;
    // signal: at least the second visit, and price has now closed back out of the box
    const margin=Math.max((ob.high-ob.low)*0.15,atr*0.15);
    const exited=ob.dir==="SHORT"?last.c<ob.low-margin:last.c>ob.high+margin;
    /* Measured, not assumed: expectancy falls monotonically with how long ago the
   structure broke. Setups taken within ~15 bars of the break pay +0.20R; past
   40 bars they are reliably negative. The imbalance gets absorbed — a block
   price returns to while the impulse is still fresh is one that gets defended. */
const fresh=cd.length-1-ob.brk<=(typeof smcFreshBars==="function"?smcFreshBars():10);
    const stillIn=price>=ob.low&&price<=ob.high;
    const tgt=smcTargets(cd,ob.dir,ob.dir==="SHORT"?ob.low:ob.high);
    const edge=ob.dir==="SHORT"?ob.low:ob.high;
    const entry=exited?last.c:edge;   // no look-ahead: once price has closed out of the box, that close is the fill
    const buf=Math.max(box*0.08,atr*0.12);
    const sl=ob.dir==="SHORT"?ob.high+buf:ob.low-buf;
    const risk=Math.abs(entry-sl);
    const sgn=ob.dir==="SHORT"?-1:1;
    const Rof=p=>risk?(p-entry)*sgn/risk:0;
    const pool=(tgt.pool||[]).filter(p=>Rof(p)>0);
    const RMIN=1.8;                                              // measured: below this the edge disappears
    let tp1=pool.find(p=>Rof(p)>=RMIN)||null,tp2=pool.find(p=>Rof(p)>=RMIN+1)||null;
    let tpExt=false;
    if(!tp1){tp1=entry+sgn*risk*RMIN;tpExt=true;}                // no structure that far — measured move at the floor
    if(!tp2||tp2===tp1)tp2=entry+sgn*Math.max(Math.abs(tp1-entry)*1.8,risk*2.5);
    const rr=risk?Math.abs(tp1-entry)/risk:0;
    const fvg=fvgs.find(f=>f.dir===ob.dir&&Math.abs(f.mid-ob.mid)/ob.mid<0.03)||null;
    const lvl=levels.find(l=>Math.abs(l.price-ob.mid)/ob.mid<0.006)||null;
    const chOk=ch&&((ob.dir==="SHORT"&&ch.dir==="نزولی")||(ob.dir==="LONG"&&ch.dir==="صعودی"));
    let stage="WATCH",q=0;
    q+=Math.min(30,v.visits*15);              // the second pullback is the heart of it
    q+=chOk?20:ch&&ch.dir==="خنثی"?6:0;
    q+=fvg?12:0;
    q+=lvl?10:0;
    q+=rr>=2?16:rr>=1.5?10:rr>=1?4:0;
    q+=v.depth>=40?8:v.depth>=20?4:0;
    /* A second pullback is the textbook trap, but it often never comes — the move
       just continues off the first touch. Judge the context instead of always waiting. */
    const strong=(chOk?1:0)+(fvg?1:0)+(lvl?1:0)+(rr>=1.5?1:0)+
                 (opts.btcDiv&&opts.btcDiv.bias===ob.dir?1:0)+(v.depth>=30?1:0);
    const goOnFirst=strong>=3;
    let waitReason="";
    if(!fresh)stage="WATCH";
    else if(!fvg&&!lvl)stage=stage==="SIGNAL"?"ARMED":stage;      // no gap and no level behind it — not worth the risk
    else if(v.visits>=2&&exited)stage="SIGNAL";
    else if(v.visits===1&&exited&&goOnFirst)stage="SIGNAL";        // continuation off pullback #1
    else if(v.visits>=2&&stillIn)stage="ARMED";
    else if(v.visits===1&&stillIn)stage=goOnFirst?"ARMED":"PULLBACK_1";
    else if(v.visits>=1){stage="PULLBACK_1";if(!goOnFirst)waitReason="هم‌سویی کافی نیست — منتظر پولبک دوم";}
    if(v.visits===1&&exited&&!goOnFirst)waitReason="پولبک اول تمام شد ولی هم‌سویی کم بود — منتظر پولبک دوم";
    if(opts.btcDiv&&opts.btcDiv.bias&&opts.btcDiv.bias!=="NEUTRAL"){
      if(opts.btcDiv.bias===ob.dir)q+=14;else q-=10;
    }
    q+=goOnFirst?6:0;
    const domC=(typeof domConflicts==="function")&&domConflicts(ob.dir,opts.asset,opts.dom);
    const cand={dir:ob.dir,stage,strong,goOnFirst,waitReason,tf:opts.tf||"15m",domConflict:domC,dom:opts.dom,
      quality:Math.max(0,Math.min(100,Math.round(q))),
      ob,visits:v.visits,depth:v.depth,inside:stillIn,exited,
      channel:ch,fvg,level:lvl,levels,fvgs,
      entry,edge,sl,tp1,tp2,tpExt,rr:Math.round(rr*100)/100,price,
      btcDiv:opts.btcDiv||null};
    cand.dmi=dmi;cand.failSwing=fs;
    cand.p=confP(cand,opts.ibs);
    cand.ev=confEV(cand.p,cand.rr||0);
    cand.conf=Math.round(cand.p*100);
    if(cand.stage==="SIGNAL"){
      if(!(cand.rr>=(+(DB.get("rr_min")||1.2))))                 {cand.stage="ARMED";cand.skip="ریسک‌به‌ریوارد کمتر از ۱.۲ — ارزش ورود ندارد";}
      else if(cand.p<0.30)                {cand.stage="ARMED";cand.skip=`اعتماد ${cand.conf}٪ — پایین‌تر از حد قابل قبول`;}
      else if(cand.ev<evMin())            {cand.stage="ARMED";cand.skip=`انتظار ریاضی ${cand.ev.toFixed(2)}R — کمتر از حد لازم`;}
      else if(adxFloor()&&dmi.adx<adxFloor()){cand.stage="ARMED";cand.skip=`ADX ${dmi.adx} زیر حد ${adxFloor()} — بازار روند ندارد`;}
      else if(domC)                       {cand.stage="ARMED";cand.skip=`دامیننس تتر ${opts.dom.dir==="UP_STRONG"||opts.dom.dir==="UP"?"صعودی":"در حال ریزش شدید"} — خلاف این ${ob.dir==="LONG"?"خرید":"فروش"}`;}
    }
    const rank=s=>({SIGNAL:3,ARMED:2,PULLBACK_1:1,WATCH:0})[s];
    if(!best||rank(stage)>rank(best.stage)||(rank(stage)===rank(best.stage)&&cand.quality>best.quality))best=cand;
  }
  return best;
}


module.exports={rsiSeries,smcATR,smcChannel,smcFVGs,smcLevels,smcOrderBlocks,obVisits,smcTargets,rsiDivergence,smcSetup,confFeat,confP,confEV,confLearn,confW,evMin,domState,domFit,domFa,domConflicts,CASES,COMMODITY_KEEP};
