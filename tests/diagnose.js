const {simulate}=require('./sim.js');const H=require('./harness.js');
const E=H.loadEngine();
// instrument: walk many markets and count where setups die
const R={none:0,watch:0,pullback1:0,armed:0,signal:0,blocked:{}};
for(let s=1;s<=150;s++){
  const cd=simulate(s*1013+7,900);
  for(let i=300;i<cd.length;i+=5){
    const x=E.smcSetup(cd.slice(0,i+1),{tf:'15m'});
    if(!x){R.none++;continue;}
    R[x.stage==='SIGNAL'?'signal':x.stage==='ARMED'?'armed':x.stage==='PULLBACK_1'?'pullback1':'watch']++;
    if(x.skip)R.blocked[x.skip.split('—')[0].trim()]=(R.blocked[x.skip.split('—')[0].trim()]||0)+1;
  }
}
const tot=R.none+R.watch+R.pullback1+R.armed+R.signal;
console.log('از',tot,'بار بررسی:');
const pc=n=>(n/tot*100).toFixed(1)+'%';
console.log('  هیچ ساختاری نبود      :',R.none,pc(R.none));
console.log('  ساختار بود، پولبک نه   :',R.watch,pc(R.watch));
console.log('  پولبک اول              :',R.pullback1,pc(R.pullback1));
console.log('  آماده (داخل باکس)      :',R.armed,pc(R.armed));
console.log('  سیگنال                 :',R.signal,pc(R.signal));
console.log('دلایل رد شدن در آخرین مرحله:');
for(const [k,v] of Object.entries(R.blocked).sort((a,b)=>b[1]-a[1]))console.log('   ',k,v);
