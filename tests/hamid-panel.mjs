/* آیا بخش «روش خود حمید» در پنل واقعاً رندر می‌شود؟
 *
 * The cycle has been writing signals/hamid-latest.json for a while and nothing
 * displayed it. A file Hamid cannot see is not a result — he does not read code
 * or JSON — so this opens the real panel in a real browser, serves the real
 * published file, and checks the section appears with the numbers in it.
 *
 * It also checks the honest bit is present. The card shows entries and targets,
 * and without the measured record beside them the panel reads as a promise.
 *
 *   node tests/hamid-panel.mjs
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
  try { const b = await readFile(join(ROOT, p === "/" ? "index.html" : p));
    res.writeHead(200,{ "content-type": T[extname(p)]||"application/octet-stream" }); res.end(b);
  } catch { res.writeHead(404).end("nf"); }
});
await new Promise(r=>server.listen(0,"127.0.0.1",r));
const url = `http://127.0.0.1:${server.address().port}/index.html`;

function chrome(){ for(const d of readdirSync("/opt/pw-browsers"))
  for(const b of ["chrome-linux/chrome","chrome-linux/headless_shell"]){
    const f=join("/opt/pw-browsers",d,b); if(existsSync(f)) return f; } }
const br = await chromium.launch({ headless:true, executablePath: chrome() });
const pg = await br.newPage({ viewport:{ width:1400, height:1100 } });
const errors=[]; pg.on("pageerror",e=>errors.push(String(e).slice(0,160)));

await pg.goto(url,{waitUntil:"domcontentloaded"});
// the section fetches after 3s and renderWhy paints every 5s
await pg.waitForTimeout(11000);

const txt = await pg.evaluate(()=>document.body.innerText);
const has = s => txt.includes(s);

const checks = [
  ["بخش روش حمید نمایش داده می‌شود", has("روش خود حمید")],
  ["ترتیب تایم‌فریم‌ها نوشته شده", has("۴ساعته → ۱ساعته → ۱۵دقیقه")],
  ["تعداد ارزهای خوانده‌شده", /\d+ ارز خوانده شد/.test(txt)],
  ["رکورد اندازه‌گیری‌شده کنار سیگنال است", has("۴۶٫۵٪") && has("۰٫۱۸۴R")],
  ["صادقانه می‌گوید لبه ثابت نشده", has("بازهٔ اطمینان صفر را در بر می‌گیرد")],
  ["اردر بلاک و واکنش سطح نشان داده شده", has("اردر بلاک") && has("واکنش")],
  ["فاصلهٔ استاپ نمایش داده می‌شود", has("فاصلهٔ استاپ")],
  ["خطای صفحه ندارد", errors.length===0],
];
let bad=0;
console.log("\nپنل — بخش روش حمید\n" + "─".repeat(56));
for(const [n,ok] of checks){ console.log(`  ${ok?"✓":"✗"} ${n}`); if(!ok) bad++; }
if(errors.length) errors.slice(0,3).forEach(e=>console.log("    "+e));

await pg.screenshot({ path: join(ROOT,"claude-liam-signal/screenshots/panel-hamid.png"), fullPage:true });
console.log(`\nاسکرین‌شات: claude-liam-signal/screenshots/panel-hamid.png`);
console.log(bad?`\n${bad} ایراد`:"\nهمه درست است");
await br.close(); server.close();
process.exit(bad?1:0);
