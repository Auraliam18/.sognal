/* Gate-by-gate funnel: how many candidates reach each check and how many die
   there. Instruments a copy of the engine rather than guessing from outside. */
const fs=require("fs"),path=require("path");
let src=fs.readFileSync(path.join(__dirname,"engine.js"),"utf8");

// count every rejection point inside smcOrderBlocks and smcSetup
const marks=[
  ['if(brk<0)continue;',                              'no structure break after pivot'],
  ['if(Math.abs(cd[brk].c-piv.p)<atr*0.5)continue;',  'break not decisive (<0.5 ATR)'],
  ['if(Math.abs(ext-piv.p)<atr*1.5)continue;',        'no displacement leg (<1.5 ATR)'],
  ['if(ob<0)continue;',                               'no opposite candle before impulse'],
  ['if(high-low<atr*0.12||high-low>atr*3.5)continue;','block body outside 0.12-3.5 ATR'],
];
marks.forEach(([code,label],i)=>{
  src=src.split(code).join(`{G("${label}");continue;}`.replace('continue;}',`continue;}`).replace('{G','if(true===false){}G')
    );
});
// simpler: rewrite with explicit counters
src=fs.readFileSync(path.join(__dirname,"engine.js"),"utf8");
src=src.replace('if(brk<0)continue;','if(brk<0){G("۱ شکست ساختار بعد از پیوت پیدا نشد");continue;}');
src=src.replace('if(Math.abs(cd[brk].c-piv.p)<atr*0.5)continue;','if(Math.abs(cd[brk].c-piv.p)<atr*0.5){G("۲ شکست قاطع نبود (کمتر از ۰.۵ ATR)");continue;}');
src=src.replace('if(Math.abs(ext-piv.p)<atr*1.5)continue;','if(Math.abs(ext-piv.p)<atr*1.5){G("۳ پای حرکتی واقعی نداشت (کمتر از ۱.۵ ATR)");continue;}');
src=src.replace('if(ob<0)continue;','if(ob<0){G("۴ کندل مخالف قبل از حرکت نبود");continue;}');
src=src.replace('if(high-low<atr*0.12||high-low>atr*3.5)continue;','if(high-low<atr*0.12||high-low>atr*3.5){G("۵ اندازهٔ باکس نامعقول");continue;}');
src=src.replace('const box=ob.high-ob.low;if(!box)continue;','const box=ob.high-ob.low;if(!box){G("۶ باکس صفر");continue;}');
src=src.replace('if(!fresh)stage="WATCH";','if(!fresh){G("۷ ستاپ کهنه شده (بیش از ۷۰ کندل)");stage="WATCH";}');
src=src.replace('else if(!fvg&&!lvl)stage=stage==="SIGNAL"?"ARMED":stage;',
                'else if(!fvg&&!lvl){if(stage==="SIGNAL")G("۸ نه FVG هم‌جهت داشت نه سطح کلیدی");stage=stage==="SIGNAL"?"ARMED":stage;}');
src=src.replace('{cand.stage="ARMED";cand.skip=`ریسک‌به‌ریوارد کمتر از ۱.۲ — ارزش ورود ندارد`;}',
                '{G("۹ ریسک‌به‌ریوارد زیر ۱.۲");cand.stage="ARMED";cand.skip="rr";}');
src=src.replace('{cand.stage="ARMED";cand.skip=`اعتماد ${cand.conf}٪ — پایین‌تر از حد قابل قبول`;}',
                '{G("۱۰ اعتماد زیر ۳۰٪");cand.stage="ARMED";cand.skip="p";}');
src=src.replace('{cand.stage="ARMED";cand.skip=`انتظار ریاضی ${cand.ev.toFixed(2)}R — کمتر از حد لازم`;}',
                '{G("۱۱ انتظار ریاضی زیر حد");cand.stage="ARMED";cand.skip="ev";}');
src=src.replace(/\{cand\.stage="ARMED";cand\.skip=`دامیننس تتر[^`]*`;\}/,
                '{G("۱۲ دامیننس تتر خلاف جهت");cand.stage="ARMED";cand.skip="dom";}');
src=src.replace('const {db:DB}=require("./store");',
  'const {db:DB}=require("./store");\nconst GATES={};function G(k){GATES[k]=(GATES[k]||0)+1;}\n');
src=src.replace(/module\.exports=\{/,'module.exports={GATES,');
fs.writeFileSync(path.join(__dirname,"engine-instr.js"),src);

const E=require("./engine-instr.js");
function tape(seed,n,vol){
  let s=seed;const rnd=()=>(s=(s*1103515245+12345)%2147483648)/2147483648;
  const g=()=>{let u=0,v=0;while(!u)u=rnd();while(!v)v=rnd();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);};
  const cd=[];let p=100,drift=0,left=0;
  for(let i=0;i<n;i++){
    if(--left<=0){drift=(rnd()<0.5?-1:1)*1.2*vol;left=30+Math.floor(rnd()*70);}
    const o=p,c=p*(1+drift+vol*g()),w=vol*(0.3+rnd());
    cd.push({t:i*9e5,o,c,h:Math.max(o,c)*(1+w*rnd()),l:Math.min(o,c)*(1-w*rnd()),v:1000});p=c;
  }
  return cd;
}
let checks=0,sig=0,armed=0,pull=0,watch=0,nosetup=0;
for(let k=0;k<60;k++){
  const cd=tape(k*7919+13,900,0.003);
  for(let i=300;i<cd.length;i+=10){
    checks++;
    const s=E.smcSetup(cd.slice(0,i+1),{tf:"15m",asset:"X"});
    if(!s)nosetup++;
    else if(s.stage==="SIGNAL")sig++;else if(s.stage==="ARMED")armed++;
    else if(s.stage==="PULLBACK_1")pull++;else watch++;
  }
}
console.log(`از ${checks} بررسی روی ۶۰ بازار با نوسان واقعی:\n`);
console.log(`  سیگنال شد            ${String(sig).padStart(6)}  ${(sig/checks*100).toFixed(1)}%`);
console.log(`  آماده (داخل باکس)    ${String(armed).padStart(6)}  ${(armed/checks*100).toFixed(1)}%`);
console.log(`  پولبک اول            ${String(pull).padStart(6)}  ${(pull/checks*100).toFixed(1)}%`);
console.log(`  ساختار بدون پولبک    ${String(watch).padStart(6)}  ${(watch/checks*100).toFixed(1)}%`);
console.log(`  هیچ اردر بلاکی نبود  ${String(nosetup).padStart(6)}  ${(nosetup/checks*100).toFixed(1)}%\n`);
console.log("موانع، به ترتیب فراوانی:");
Object.entries(E.GATES).sort((a,b)=>b[1]-a[1]).forEach(([k,v])=>
  console.log(`  ${k.padEnd(45)} ${String(v).padStart(8)}`));
