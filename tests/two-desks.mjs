/* The two desks must actually filter, and each must report its own measured
   expectancy — a tab that shows the same list twice is worse than no tab. */
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
const br = await chromium.launch({ headless:true, executablePath: chrome() });
const pg = await br.newPage({ viewport:{width:1500,height:1250} });
const errs=[]; pg.on("pageerror",e=>errs.push(String(e).slice(0,180)));
await pg.goto(`http://127.0.0.1:${server.address().port}/index.html`,{waitUntil:"domcontentloaded"});
await pg.evaluate(()=>{ DIAG.net.fail=9; DIAG.net.lastOk=0; DIAG.net.lastErr="Failed to fetch"; });
await pg.waitForTimeout(7000);
await pg.evaluate(()=>relayTick());
await pg.waitForTimeout(2500);
for (const desk of ["all","smc","ibs"]) {
  await pg.evaluate(k=>{ RELAY.only=k; renderWhy(); }, desk);
  await pg.waitForTimeout(300);
  const r = await pg.evaluate(()=>{
    const b=document.querySelector("#whyBox");
    const cards=[...b.querySelectorAll(".box h3")].map(h=>h.textContent.trim());
    return { signalCards: cards.filter(h=>h.startsWith("🚨")).length,
             tabs: [...b.querySelectorAll("button")].map(x=>x.textContent.trim().replace(/\s+/g," ")),
             measured: (b.textContent.match(/اندازه‌گیری روی[^\n]{0,120}/)||[""])[0].trim().slice(0,110) };
  });
  console.log(`\n[${desk}] signal cards: ${r.signalCards}`);
  if (desk==="all") console.log(`  tabs: ${r.tabs.join("  |  ")}`);
  if (r.measured) console.log(`  ${r.measured}`);
}
await pg.evaluate(()=>{ RELAY.only="smc"; renderWhy(); });
await pg.screenshot({ path: join(ROOT,"claude-liam-signal","screenshots","panel-two-desks.png") });
console.log(`\npage errors: ${errs.length}`); errs.forEach(e=>console.log("  ✗ "+e));
await br.close(); server.close();
process.exit(errs.length?1:0);
