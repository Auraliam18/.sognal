/* آیا پنل واقعاً از یک منبع به منبع بعدی می‌رود؟
 *
 * The whole point of eight sources is that no single one going down takes the
 * panel with it. That only holds if the fallback actually runs, so this blocks
 * them one at a time in the browser and checks the panel keeps getting candles
 * — and remembers which source finally answered.
 */
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { existsSync, readdirSync } from "node:fs";
import { extname, join } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = fileURLToPath(new URL("..", import.meta.url));
const T = { ".html":"text/html; charset=utf-8", ".js":"text/javascript; charset=utf-8",
  ".json":"application/json", ".png":"image/png", ".webmanifest":"application/manifest+json" };
const server = createServer(async (req,res)=>{
  const p = decodeURIComponent(req.url.split("?")[0]);
  try { const b = await readFile(join(ROOT, p==="/"?"index.html":p));
    res.writeHead(200,{ "content-type": T[extname(p)]||"application/octet-stream" }); res.end(b);
  } catch { res.writeHead(404).end("nf"); }
});
await new Promise(r=>server.listen(0,"127.0.0.1",r));
function chrome(){ for(const d of readdirSync("/opt/pw-browsers"))
  for(const b of ["chrome-linux/chrome","chrome-linux/headless_shell"]){
    const f=join("/opt/pw-browsers",d,b); if(existsSync(f)) return f; } }

/* One recorded reply per exchange, served from a fake network so the test does
   not depend on any of them being up right now. */
const REPLY = {
  "fapi.bitunix.com":         ()=>JSON.stringify({data:mk("bitunix")}),
  "api.nobitex.ir":           ()=>JSON.stringify(mk("udf")),
  "api.wallex.ir":            ()=>JSON.stringify(mk("udf")),
  "api.tabdeal.org":          ()=>JSON.stringify(mk("udf")),
  "api.mexc.com":             ()=>JSON.stringify(mk("binance")),
  "open-api.bingx.com":       ()=>JSON.stringify({data:mk("bingx")}),
  "api-cloud.bitmart.com":    ()=>JSON.stringify({data:mk("bitmart")}),
  "api.huobi.pro":            ()=>JSON.stringify({data:mk("htx")}),
  "api.kucoin.com":           ()=>JSON.stringify({data:mk("kucoin")}),
  "www.okx.com":              ()=>JSON.stringify({data:mk("okx")}),
  "api.bitget.com":           ()=>JSON.stringify({data:mk("bitget")}),
  "api.gateio.ws":            ()=>JSON.stringify(mk("gate")),
  "api.coinex.com":           ()=>JSON.stringify({data:mk("coinex")}),
  "api.exchange.coinbase.com":()=>JSON.stringify(mk("coinbase")),
  "api.binance.com":          ()=>JSON.stringify(mk("binance")),
};
function mk(kind){
  const rows=[]; const udf={s:"ok",t:[],o:[],h:[],l:[],c:[],v:[]};
  let t=1785500000000, p=63000;
  for(let i=0;i<60;i++){
    const o=p, c=p*(1+(i%7-3)*0.0004), h=Math.max(o,c)*1.0006, l=Math.min(o,c)*0.9994;
    if(kind==="bitunix") rows.push({time:t,open:""+o,high:""+h,low:""+l,close:""+c,quoteVol:"10",baseVol:"630000"});
    else if(kind==="udf"){udf.t.push(t/1000);udf.o.push(o);udf.h.push(h);udf.l.push(l);udf.c.push(c);udf.v.push(10);}
    else if(kind==="kucoin")   rows.push([""+(t/1000),""+o,""+c,""+h,""+l,"10","630000"]);
    else if(kind==="okx")      rows.push([""+t,""+o,""+h,""+l,""+c,"10","630000"]);
    else if(kind==="bingx")    rows.push([t,o,h,l,c,10,t+899999]);
    else if(kind==="bitmart")  rows.push([""+(t/1000),""+o,""+h,""+l,""+c,"10","630000"]);
    else if(kind==="htx")      rows.push({id:t/1000,open:o,high:h,low:l,close:c,amount:10});
    else if(kind==="bitget")   rows.push([""+t,""+o,""+h,""+l,""+c,"10","630000"]);
    else if(kind==="gate")     rows.push([""+(t/1000),"630000",""+c,""+h,""+l,""+o,"10"]);
    else if(kind==="coinex")   rows.push({created_at:t,open:""+o,high:""+h,low:""+l,close:""+c,volume:"10"});
    else if(kind==="coinbase") rows.push([t/1000,l,h,o,c,10]);
    else rows.push([t,""+o,""+h,""+l,""+c,"10",t+899999]);
    p=c; t+=900000;
  }
  if(kind==="udf") return udf;
  // the ones that really return newest-first
  if(["kucoin","okx","bingx","htx","coinbase","bitunix"].includes(kind)) rows.reverse();
  return rows;
}
const br = await chromium.launch({ headless:true, executablePath: chrome() });
const hosts = Object.keys(REPLY);
let failed = 0;
console.log("\nهر بار یک منبع بیشتر قطع می‌شود — پنل باید همچنان کندل بگیرد:\n");
for (let blocked = 0; blocked < hosts.length; blocked++) {
  const down = new Set(hosts.slice(0, blocked));
  const ctx = await br.newContext();
  await ctx.route("**://**", async route => {
    const u = new URL(route.request().url());
    if (u.hostname === "127.0.0.1") return route.continue();
    if (down.has(u.hostname)) return route.abort();
    const body = REPLY[u.hostname];
    if (body) return route.fulfill({ status:200, contentType:"application/json", body: body() });
    return route.abort();
  });
  const pg = await ctx.newPage();
  await pg.goto(`http://127.0.0.1:${server.address().port}/index.html`, { waitUntil:"domcontentloaded" });
  await pg.waitForTimeout(1200);
  const r = await pg.evaluate(async ()=>{
    try { const cd = await fetchKlinesAny("BTCUSDT","15m",60);
      return { n: cd.length, src: DB.get("source_ok"),
               ordered: cd[0].t < cd[cd.length-1].t, sane: cd.every(k=>k.h>=k.l && k.c>0) };
    } catch(e){ return { error: String(e.message||e) }; }
  });
  await ctx.close();
  const label = blocked===0 ? "هیچ‌کدام قطع نیست" : `${blocked} منبع اول قطع`;
  if (r.error) { console.log(`  ✗ ${label.padEnd(22)} ${r.error}`); failed++; }
  else if (!r.n || !r.ordered || !r.sane) { console.log(`  ✗ ${label.padEnd(22)} دادهٔ خراب`); failed++; }
  else console.log(`  ✓ ${label.padEnd(22)} ${r.n} کندل از ${r.src}`);
}
/* And with every source down it must fail loudly, not return something. */
const ctx = await br.newContext();
await ctx.route("**://**", r => new URL(r.request().url()).hostname==="127.0.0.1" ? r.continue() : r.abort());
const pg = await ctx.newPage();
await pg.goto(`http://127.0.0.1:${server.address().port}/index.html`,{waitUntil:"domcontentloaded"});
await pg.waitForTimeout(1200);
const dead = await pg.evaluate(async ()=>{ try { await fetchKlinesAny("BTCUSDT","15m",60); return "returned data"; }
  catch(e){ return "threw: "+(e.message||e); } });
await ctx.close();
const ok = dead.startsWith("threw");
console.log(`\n  ${ok?"✓":"✗"} با قطع همهٔ منابع: ${dead}`);
if (!ok) failed++;
await br.close(); server.close();
console.log(`\n${failed?`${failed} ایراد`:"جایگزینی منابع درست کار می‌کند"}`);
process.exit(failed?1:0);
