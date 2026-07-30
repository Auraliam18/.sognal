/* Binance access with the manners the exchange asks for: a shared rate budget,
   retry on 429/418 with the wait it names, and a mirror fallback. */
const HOSTS=["https://fapi.binance.com","https://fapi1.binance.com","https://fapi2.binance.com"];
let host=0, tokens=1000, lastRefill=Date.now();
function budget(){
  const now=Date.now();
  if(now-lastRefill>60000){tokens=1000;lastRefill=now;}
  return tokens>0;
}
async function jget(pathname,weight){
  weight=weight||1;
  for(let attempt=0;attempt<5;attempt++){
    while(!budget())await sleep(1000);
    tokens-=weight;
    try{
      const r=await fetch(HOSTS[host]+pathname,{headers:{"User-Agent":"claude-liam-signal/1"}});
      if(r.status===429||r.status===418){
        const wait=+(r.headers.get("retry-after")||5)*1000;
        tokens=0;await sleep(wait);continue;
      }
      if(r.status>=500){host=(host+1)%HOSTS.length;await sleep(500);continue;}
      if(!r.ok)throw new Error("HTTP "+r.status+" "+pathname);
      return await r.json();
    }catch(e){
      if(attempt===4)throw e;
      host=(host+1)%HOSTS.length;
      await sleep(400*(attempt+1));
    }
  }
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const parseKlines=a=>a.map(k=>({t:+k[0],o:+k[1],h:+k[2],l:+k[3],c:+k[4],v:+k[5]}));
module.exports={
  jget,sleep,parseKlines,
  tickers:()=>jget("/fapi/v1/ticker/24hr",40),
  prices:()=>jget("/fapi/v1/ticker/price",2),
  funding:()=>jget("/fapi/v1/premiumIndex",10),
  klines:(sym,iv,limit)=>jget(`/fapi/v1/klines?symbol=${sym}&interval=${iv}&limit=${limit||300}`,5).then(parseKlines),
  wsBase:"wss://fstream.binance.com"
};
