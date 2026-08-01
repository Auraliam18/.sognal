/* Opens the panel in a real Chromium, the way Hamid opens it, and reports what
   it actually does — console errors, which rooms come up, whether the engine
   renders a setup card with every chip on it.

   Two things are worth knowing before reading the output. First, the panel is
   served over http rather than opened as a file, because a service worker will
   not register on file://. Second, on a network that cannot reach the exchange
   the panel has nothing live to chart; that is not a fault, and the panel says
   so itself through its own diagnosis. To prove the rendering path regardless,
   a setup built from simulated candles is injected and screenshotted.

     node tests/live-panel.mjs [--headed] [--seconds 20] */
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { existsSync, readdirSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const SHOTS = join(ROOT, "claude-liam-signal", "screenshots");
const args = process.argv.slice(2);
const headed = args.includes("--headed");
const seconds = +(args[args.indexOf("--seconds") + 1] || 20) || 20;

const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".json": "application/json", ".png": "image/png", ".webmanifest": "application/manifest+json",
  ".css": "text/css", ".svg": "image/svg+xml" };

const missing = new Set();
const server = createServer(async (req, res) => {
  const p = decodeURIComponent(req.url.split("?")[0]);
  const file = join(ROOT, p === "/" ? "index.html" : p);
  if (!file.startsWith(ROOT)) { res.writeHead(403).end(); return; }
  try {
    const body = await readFile(file);
    res.writeHead(200, { "content-type": TYPES[extname(file)] || "application/octet-stream" });
    res.end(body);
  } catch {
    /* /api/* is the cloud backend, which a static serve does not have; the panel
       is meant to fall back to local storage there, so it is not a missing file. */
    if (!p.startsWith("/api/")) missing.add(p);
    res.writeHead(404).end("not found");
  }
});
await new Promise(r => server.listen(0, "127.0.0.1", r));
const url = `http://127.0.0.1:${server.address().port}/index.html`;
console.log(`serving the panel at ${url}`);

/* Chromium is already on the machine; find it rather than downloading one. */
function chromePath() {
  const roots = ["/opt/pw-browsers", process.env.PLAYWRIGHT_BROWSERS_PATH].filter(Boolean);
  for (const root of roots) {
    for (const d of existsSync(root) ? readdirSync(root) : []) {
      for (const bin of ["chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const f = join(root, d, bin);
        if (existsSync(f)) return f;
      }
    }
  }
  return undefined;                     // let Playwright fall back to its own
}
const browser = await chromium.launch({ headless: !headed, executablePath: chromePath() });
const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });

const errors = [], warnings = [];
page.on("console", m => {
  if (m.type() === "error") errors.push(m.text().slice(0, 200));
  if (m.type() === "warning") warnings.push(m.text().slice(0, 160));
});
page.on("pageerror", e => errors.push("PAGE: " + String(e).slice(0, 200)));

await page.goto(url, { waitUntil: "domcontentloaded" });
console.log(`title: ${await page.title()}`);
console.log(`version: ${(await page.locator("#ver").innerText().catch(() => "—")).trim()}`);

console.log(`running for ${seconds}s…`);
await page.waitForTimeout(seconds * 1000);

/* What the panel believes about itself. */
const state = await page.evaluate(() => {
  const g = n => (typeof window[n] === "function" ? window[n] : null);
  const rooms = [...document.querySelectorAll("[data-room], .room")].length;
  const lights = {};
  document.querySelectorAll(".dot,.light,[class*=led]").forEach(el => {
    const k = (el.className || "").toString().split(/\s+/).slice(-1)[0];
    lights[k] = (lights[k] || 0) + 1;
  });
  return {
    rooms, lights,
    watchlist: (window.WATCH && window.WATCH.length) || (window.CURST && CURST.watch && CURST.watch.length) || 0,
    paper: g("paperStats") ? paperStats() : null,
    diagnosis: (document.body.innerText.match(/تشخیص[^\n]{0,140}/) || [null])[0],
    engine: ["smcSetup", "roomToRun", "liquidityPools", "inducementSwept", "structureIsThin",
             "wilderADX", "wilderSAR", "askLearningRoom", "supervisorApproves"]
             .filter(n => typeof window[n] === "function"),
  };
});
console.log(`engine functions present: ${state.engine.join(", ")}`);
console.log(`rooms rendered: ${state.rooms}   watchlist: ${state.watchlist}`);
if (state.paper) console.log(`paper desk: ${JSON.stringify(state.paper)}`);
if (state.diagnosis) console.log(`panel's own diagnosis: ${state.diagnosis.trim()}`);

/* The rendering path, proven on candles that do not need the network. */
const { simulate } = createRequire(import.meta.url)("./sim.js");
const probeCandles = simulate(20260730, 900).map((c, i) => ({ ...c, t: 1750000000000 + i * 900000 }));

const card = await page.evaluate((cd) => {
  for (let i = cd.length - 1; i >= 320; i--) {
    const s = smcSetup(cd.slice(0, i + 1), { tf: "15m", asset: "TEST" });
    if (!s || !s.ob) continue;
    const host = document.createElement("div");
    host.id = "live-panel-probe";
    host.style.cssText = "position:fixed;inset:40px;overflow:auto;z-index:99999;background:#0e141c;padding:18px;border-radius:12px;border:1px solid #22303f";
    host.innerHTML = smcCardHTML({ smc: s });
    if (!host.innerHTML) continue;
    document.body.appendChild(host);
    return {
      stage: s.stage, dir: s.dir, rr: s.rr, conf: s.conf, ev: s.ev,
      room: s.room, swept: !!s.swept, thin: s.thin, adx: s.dmi && s.dmi.adx,
      skip: s.skip || null,
      chips: [...host.querySelectorAll(".chip")].map(c => c.textContent.trim()),
    };
  }
  return null;
}, probeCandles);
if (card) {
  console.log("\nsetup rendered from simulated candles (the network is not involved):");
  console.log(`  ${card.dir} ${card.stage}  rr=${card.rr}  conf=${card.conf}%  ev=${(card.ev ?? 0).toFixed(2)}R  adx=${card.adx}`);
  console.log(`  room: ${card.room ? card.room.r + "× to " + (card.room.blocker || "nothing") : "—"}`);
  console.log(`  inducement swept: ${card.swept}   inside ${card.thin && card.thin.insideRatio}  vol ${card.thin && card.thin.volRatio}`);
  if (card.skip) console.log(`  held back because: ${card.skip}`);
  console.log(`  chips on the card (${card.chips.length}):`);
  card.chips.forEach(c => console.log(`    · ${c}`));
} else console.log("\nno setup formed on the probe candles");

await page.screenshot({ path: join(SHOTS, "panel-live.png"), fullPage: false });
await page.evaluate(() => document.getElementById("live-panel-probe")?.remove());
await page.screenshot({ path: join(SHOTS, "panel-live-full.png"), fullPage: true });
console.log(`\nscreenshots: claude-liam-signal/screenshots/panel-live.png and panel-live-full.png`);

/* Cross-origin failures are the exchange being unreachable and say nothing about
   the panel. Missing files of our own are a real fault and are named separately. */
const ourFault = errors.filter(e => !/ERR_TUNNEL|ERR_NAME_NOT_RESOLVED|ERR_CONNECTION|Failed to fetch|ERR_PROXY/.test(e));
console.log(`\nunreachable-network errors (expected where the exchange is blocked): ${errors.length - ourFault.length}`);
console.log(`missing files of our own: ${missing.size}${missing.size ? " → " + [...missing].join(", ") : ""}`);
console.log(`other console errors: ${ourFault.length}`);
ourFault.slice(0, 10).forEach(e => console.log("  ✗ " + e));
if (warnings.length) console.log(`console warnings: ${warnings.length} (first: ${warnings[0]})`);

await browser.close();
server.close();
/* A blocked exchange is the network's doing, not the panel's; a missing file or
   a thrown script is ours, and only those fail the check. */
process.exit(missing.size || ourFault.some(e => e.startsWith("PAGE:")) ? 1 : 0);
