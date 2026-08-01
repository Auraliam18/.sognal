/* Opens the standalone file the way the artifact will: from disk, with no
   network at all. If it needs anything it cannot reach, this is where it shows. */
import { chromium } from "playwright";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
function chrome(){ for(const d of readdirSync("/opt/pw-browsers"))
  for(const b of ["chrome-linux/chrome","chrome-linux/headless_shell"]){
    const f=join("/opt/pw-browsers",d,b); if(existsSync(f)) return f; } }
const br = await chromium.launch({ headless:true, executablePath: chrome() });
const ctx = await br.newContext({ viewport:{width:1500,height:1300}, offline:true });
const pg = await ctx.newPage();
const errs=[], failed=[];
pg.on("pageerror", e=>errs.push(String(e).slice(0,180)));
pg.on("requestfailed", r=>failed.push(r.url().slice(0,90)));
await pg.goto("file://" + process.argv[2], { waitUntil:"domcontentloaded" });
await pg.waitForTimeout(9000);
const r = await pg.evaluate(()=>{
  const b=document.querySelector("#whyBox");
  const heads=[...(b?b.querySelectorAll(".box h3"):[])].map(h=>h.textContent.trim());
  return { version:(document.querySelector("#ver")||{}).textContent,
           banner:(document.body.innerText.match(/عکس لحظه‌ای[^\n]{0,90}/)||[""])[0],
           signalCards: heads.filter(h=>h.startsWith("🚨")).length,
           tabs:[...(b?b.querySelectorAll("button"):[])].map(x=>x.textContent.trim().replace(/\s+/g," ")),
           learning:(document.body.innerText.match(/اتاق یادگیری[^\n]{0,60}/)||[""])[0] };
});
console.log("version      :", (r.version||"").trim());
console.log("banner       :", r.banner);
console.log("signal cards :", r.signalCards);
console.log("tabs         :", r.tabs.join("  |  "));
console.log("learning     :", r.learning || "(none on first card)");
console.log("page errors  :", errs.length); errs.slice(0,5).forEach(e=>console.log("   ✗ "+e));
console.log("failed reqs  :", failed.length); [...new Set(failed)].slice(0,5).forEach(u=>console.log("   ✗ "+u));
await pg.screenshot({ path: process.argv[3], fullPage:false });
await br.close();
process.exit(errs.length || r.signalCards===0 ? 1 : 0);
