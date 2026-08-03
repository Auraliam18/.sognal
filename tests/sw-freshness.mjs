/* آیا سرویس‌ورکر نسخهٔ قدیمی را نگه می‌دارد؟
   یک بار پنل قدیمی را باز می‌کنیم تا کش شود، بعد فایل را با نسخهٔ جدید عوض
   می‌کنیم و دوباره باز می‌کنیم — همان کاری که مرورگر حمید می‌کند. */
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile, writeFile } from "node:fs/promises";
import { existsSync, readdirSync } from "node:fs";
import { extname, join } from "node:path";
import { mkdtempSync, copyFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

/* This test edits index.html and sw.js to simulate a deploy, so it must never
   be pointed at the repository itself. Given no directory it makes its own
   throwaway copy — running it plainly should not be able to damage the panel. */
const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DIR = process.argv[2] || (() => {
  const d = mkdtempSync(join(tmpdir(), "sw-fresh-"));
  for (const f of ["index.html","sw.js","manifest.webmanifest","lightweight-charts.js"])
    { try { copyFileSync(join(ROOT,f), join(d,f)); } catch {} }
  return d;
})();
const T = { ".html":"text/html; charset=utf-8", ".js":"text/javascript; charset=utf-8",
  ".json":"application/json", ".png":"image/png", ".webmanifest":"application/manifest+json" };
const server = createServer(async (req,res)=>{
  const p = decodeURIComponent(req.url.split("?")[0]);
  try { const b = await readFile(join(DIR, p==="/"?"index.html":p));
    res.writeHead(200,{ "content-type": T[extname(p)]||"application/octet-stream" }); res.end(b);
  } catch { res.writeHead(404).end("nf"); }
});
await new Promise(r=>server.listen(0,"127.0.0.1",r));
const url = `http://127.0.0.1:${server.address().port}/index.html`;
function chrome(){ for(const d of readdirSync("/opt/pw-browsers"))
  for(const b of ["chrome-linux/chrome","chrome-linux/headless_shell"]){
    const f=join("/opt/pw-browsers",d,b); if(existsSync(f)) return f; } }
const br = await chromium.launch({ headless:true, executablePath: chrome() });
const ctx = await br.newContext();           // one profile, kept across loads
const pg = await ctx.newPage();

await pg.goto(url,{waitUntil:"load"});
await pg.waitForTimeout(3500);
const first = await pg.evaluate(()=>({v:(document.querySelector("#ver")||{}).textContent,
  sw: !!navigator.serviceWorker.controller}));
console.log("بازدید اول :", (first.v||"").trim(), "| سرویس‌ورکر فعال:", first.sw);

// حالا دیپلوی جدید را شبیه‌سازی می‌کنیم
let html = await readFile(join(DIR,"index.html"),"utf8");
await writeFile(join(DIR,"index.html"), html.replace(/cycle v[0-9.]+/, "cycle v99-NEW"));
let sw = await readFile(join(DIR,"sw.js"),"utf8");
await writeFile(join(DIR,"sw.js"), sw.replace(/hsa-shell-v[0-9.]+/,"hsa-shell-v99"));

await pg.goto(url,{waitUntil:"load"});
await pg.waitForTimeout(3500);
const second = await pg.evaluate(()=>((document.querySelector("#ver")||{}).textContent||"").trim());
console.log("بازدید دوم :", second);
await pg.goto(url,{waitUntil:"load"});
await pg.waitForTimeout(3000);
const third = await pg.evaluate(()=>((document.querySelector("#ver")||{}).textContent||"").trim());
console.log("بازدید سوم :", third);

await writeFile(join(DIR,"index.html"), html);
await writeFile(join(DIR,"sw.js"), sw);
const stale = !second.includes("v99");
console.log(stale ? "\n>>> نسخهٔ قدیمی از کش سرو شد — همین مشکل حمید است"
                  : "\n>>> نسخهٔ جدید بلافاصله آمد");
await br.close(); server.close();
process.exit(stale?1:0);
