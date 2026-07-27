const {simulate}=require('./sim.js');const H=require('./harness.js');
const E=H.loadEngine();

// ---------- A) 12-hour equivalent: 100 symbols, last 48 closed 15m bars ----------
const HOURS=12, BARS=HOURS*4;            // 48 bars of 15m
let win=[];
for(let s=1;s<=100;s++){
  const cd=simulate(s*7717+31,1200);
  const full=H.evaluate(E,cd);
  win=win.concat(full.filter(t=>t.i>=cd.length-BARS));   // signals inside the window
}
const st=H.stats(win);
console.log('=== معادل ۱۲ ساعت روی ۱۰۰ بازار ===');
console.log(JSON.stringify(st));
console.log('سیگنال به ازای هر ارز در ۱۲ ساعت:',(win.length/100).toFixed(2));

// ---------- B) categorised breakdown on a large sample ----------
let all=[];
for(let s=1;s<=200;s++)all=all.concat(H.evaluate(E,simulate(s*1013+7,1200)));
const grp=(name,f)=>{const a=all.filter(f);const s=H.stats(a);
  console.log('  '+name.padEnd(26),'n='+String(s.n).padStart(4),'برد '+String(s.hit).padStart(5)+'%','میانگین‌R '+String(s.avgR).padStart(5),'انتظار '+String(s.ev).padStart(6));};
console.log('\n=== دسته‌بندی روی '+all.length+' معامله ===');
grp('همه',()=>true);
grp('لانگ',t=>t.dir==='LONG');
grp('شورت',t=>t.dir==='SHORT');
grp('پولبک اول',t=>t.visits===1);
grp('پولبک دوم یا بیشتر',t=>t.visits>=2);
grp('کانال هم‌جهت',t=>t.chOk);
grp('کانال مخالف/خنثی',t=>!t.chOk);
grp('با FVG',t=>t.fvg);
grp('بدون FVG',t=>!t.fvg);
grp('روی سطح کلیدی',t=>t.lvl);
grp('نفوذ عمیق در باکس ≥۵۰٪',t=>t.depth>=50);
grp('R:R ۱.۲ تا ۲',t=>t.R>=1.2&&t.R<2);
grp('R:R ۲ تا ۳',t=>t.R>=2&&t.R<3);
grp('R:R ≥۳',t=>t.R>=3);

// ---------- C) does the learning transfer? train on half the markets, test on the other half ----------
const feats=all.filter(t=>t.feat);
const mid=Math.floor(feats.length/2);
const train=feats.slice(0,mid), test=feats.slice(mid);
let W=Object.assign({},E.confW());
const pred=(w,f)=>{let z=0;for(const k in f)z+=(w[k]||0)*f[k];return 1/(1+Math.exp(-z));};
for(let ep=0;ep<8;ep++)for(const t of train){const p=pred(W,t.feat),e=(t.win?1:0)-p;
  for(const k in t.feat)W[k]=(W[k]||0)+0.03*e*t.feat[k];}
const auc=(w,g)=>{const P=g.filter(x=>x.win),N=g.filter(x=>!x.win);if(!P.length||!N.length)return NaN;
  let c=0;for(const a of P)for(const b of N){const pa=pred(w,a.feat),pb=pred(w,b.feat);c+=pa>pb?1:pa===pb?0.5:0;}
  return c/(P.length*N.length);};
console.log('\n=== آیا یادگیری قابل انتقال است؟ (آموزش روی نیمی، آزمون روی نیمهٔ دیده‌نشده) ===');
console.log('AUC روی دادهٔ آموزش :',auc(W,train).toFixed(3));
console.log('AUC روی دادهٔ نادیده:',auc(W,test).toFixed(3),'  (۰.۵ = بی‌فایده)');
const evOf=a=>a.length?(a.reduce((s,x)=>s+(x.win?x.R:-1),0)/a.length).toFixed(3):'-';
const hi=test.filter(x=>pred(W,x.feat)>=0.45),lo=test.filter(x=>pred(W,x.feat)<0.45);
console.log('روی دادهٔ نادیده — اعتماد بالا: انتظار',evOf(hi),'n='+hi.length,' | اعتماد پایین: انتظار',evOf(lo),'n='+lo.length);
console.log('وزن‌های آموخته:',JSON.stringify(Object.fromEntries(Object.entries(W).map(([k,v])=>[k,+v.toFixed(3)]))));
