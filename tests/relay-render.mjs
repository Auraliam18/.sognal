/* Proves the relay path: panel blind to the exchange -> reads signals/latest.json
   -> renders the cards. The scan file here is a stand-in built from simulator
   candles; only the rendering is under test, never the numbers. */
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { existsSync, readdirSync } from "node:fs";
import { extname, join } from "node:path";

import { fileURLToPath } from "node:url";
const ROOT = fileURLToPath(new URL("..", import.meta.url));
const OVERLAY = process.argv[2];
const TYPES = { ".html":"text/html; charset=utf-8", ".js":"text/javascript; charset=utf-8",
  ".json":"application/json", ".png":"image/png", ".webmanifest":"application/manifest+json" };
const server = createServer(async (req,res)=>{
  const p = decodeURIComponent(req.url.split("?")[0]);
  for (const base of [OVERLAY, ROOT]) {
    const f = join(base, p === "/" ? "index.html" : p);
    try { const b = await readFile(f);
      res.writeHead(200,{ "content-type": TYPES[extname(f)]||"application/octet-stream" });
      return res.end(b);
    } catch {}
  }
  res.writeHead(404).end("not found");
});
await new Promise(r=>server.listen(0,"127.0.0.1",r));
const url = `http://127.0.0.1:${server.address().port}/index.html`;

function chromePath(){
  for (const root of ["/opt/pw-browsers"]) for (const d of readdirSync(root))
    for (const bin of ["chrome-linux/chrome","chrome-linux/headless_shell"]) {
      const f = join(root,d,bin); if (existsSync(f)) return f;
    }
}
const browser = await chromium.launch({ headless:true, executablePath: chromePath() });
const page = await browser.newPage({ viewport:{ width:1500, height:1150 } });
const errs=[]; page.on("pageerror",e=>errs.push(String(e).slice(0,200)));
await page.goto(url,{ waitUntil:"domcontentloaded" });

/* Make the panel believe its own feed is dead, which is the real condition. */
await page.evaluate(()=>{ DIAG.net.fail = 9; DIAG.net.lastOk = 0; DIAG.net.lastErr = "Failed to fetch"; });
await page.waitForTimeout(9000);
await page.evaluate(()=>{ relayTick(); });
await page.waitForFunction(()=>window.RELAY && RELAY.data, null, { timeout: 15000 }).catch(()=>{});
await page.evaluate(()=>renderWhy());
await page.waitForTimeout(600);

/* RELAY is a top-level `const`, so it is not a property of window and cannot be
   read from here. Judge by what the panel actually rendered instead — which is
   the thing under test anyway. */
const seen = await page.evaluate(()=>{
  const box = document.querySelector("#whyBox");
  const cards = [...box.querySelectorAll(".box h3")].map(h=>h.textContent.trim());
  return { headings: cards,
           signalCards: cards.filter(h=>h.startsWith("🚨")).length,
           relayHeader: cards.some(h=>h.includes("اسکن از راه دور")),
           chips: [...box.querySelectorAll(".chip")].map(c=>c.textContent.trim()).slice(0,10),
           levels: [...box.querySelectorAll(".lvls div")].map(d=>d.textContent.trim()).slice(0,4) };
});
console.log("relay header rendered:", seen.relayHeader, "| signal cards:", seen.signalCards);
console.log("headings:"); seen.headings.forEach(h=>console.log("   "+h));
console.log("chips on first card:"); seen.chips.forEach(c=>console.log("   · "+c));
console.log("levels:"); seen.levels.forEach(l=>console.log("   · "+l));
await page.screenshot({ path: join(ROOT,"claude-liam-signal","screenshots","panel-relay.png") });
console.log("page errors:", errs.length); errs.forEach(e=>console.log("  ✗ "+e));
await browser.close(); server.close();
/* The relay is only useful if it actually reached the card. */
const ok = seen.relayHeader && seen.signalCards > 0 && errs.length === 0;
console.log(ok ? "\nrelay path works" : "\nrelay path FAILED");
process.exit(ok ? 0 : 1);
