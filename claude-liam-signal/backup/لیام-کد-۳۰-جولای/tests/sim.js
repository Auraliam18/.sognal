/* Regime-switching market simulator with volatility clustering.
   Not a toy: GARCH-like vol, trend/range/reversal regimes, fat tails,
   and realistic intrabar ranges — so a strategy cannot look good by luck. */
function mulberry(seed){let a=seed>>>0;return()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}
function gauss(r){let u=0,v=0;while(!u)u=r();while(!v)v=r();return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);}
function simulate(seed,n){
  const r=mulberry(seed);
  let price=50+r()*200, vol=0.004, drift=0, regime="range", left=40+Math.floor(r()*80);
  const cd=[];
  for(let i=0;i<n;i++){
    if(--left<=0){
      const x=r();
      regime=x<0.42?"trend":x<0.72?"range":x<0.88?"pullback":"shock";
      drift=regime==="trend"?(r()<0.5?-1:1)*(0.0012+r()*0.002)
           :regime==="pullback"?(r()<0.5?-1:1)*0.0006
           :regime==="shock"?(r()<0.5?-1:1)*0.006:0;
      left=regime==="shock"?4+Math.floor(r()*8):35+Math.floor(r()*90);
    }
    // GARCH(1,1)-ish volatility with clustering
    const shock=gauss(r);
    vol=Math.sqrt(0.000002+0.08*(vol*shock)**2+0.90*vol*vol);
    vol=Math.min(Math.max(vol,0.0015),0.05);
    const ret=drift+vol*(Math.abs(shock)>2.5?shock*1.6:shock);   // fat tails
    const o=price,c=price*(1+ret);
    const wick=vol*(0.4+r()*1.4);
    const h=Math.max(o,c)*(1+wick*r()),l=Math.min(o,c)*(1-wick*r());
    cd.push({t:i*9e5,o,h,l,c,v:1000*(1+r()*4)*(regime==="shock"?3:1)});
    price=c;
  }
  return cd;
}
module.exports={simulate};
