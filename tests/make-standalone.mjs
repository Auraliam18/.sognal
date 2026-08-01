/* Builds a single self-contained copy of the panel that opens from one click.

   The deployed panel lives on GitHub Pages and fetches its chart library and its
   scan file as separate requests. That is right for a hosted page and wrong for
   a link you just want to open: a strict content policy blocks outside requests,
   and a repository link shows source rather than a running page.

   So this inlines everything the panel needs — the chart library, and the newest
   scan with its signals already in place — into one file with no external
   requests left. What it cannot inline is the exchange: live prices need a
   network the page will not have, so the snapshot says plainly, at the top, that
   it is a snapshot and when it was taken. A page that looks live but is frozen
   would be worse than one that admits it.

     node tests/make-standalone.mjs [out.html]
*/
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const out = process.argv[2] || join(ROOT, "panel-standalone.html");

let html = readFileSync(join(ROOT, "index.html"), "utf8");

/* 1 — the chart library, inlined so no request is needed for it */
const lib = readFileSync(join(ROOT, "lightweight-charts.js"), "utf8");
html = html.replace('<script src="./lightweight-charts.js"></script>',
  `<script>${lib}</script>`);

/* 2 — the scan, inlined. The panel normally fetches this only once it decides
   its own feed is dead; here it is handed over at load and the fetch is turned
   into a no-op so nothing races it. */
const scanPath = join(ROOT, "signals", "latest.json");
if (!existsSync(scanPath)) {
  console.error("no signals/latest.json — run the scan first");
  process.exit(1);
}
const scan = JSON.parse(readFileSync(scanPath, "utf8"));
const ageMin = Math.round((Date.now() - scan.generated) / 60000);

const inject = `
<script>
/* Snapshot data, baked in at build time. */
(function(){
  const DATA = ${JSON.stringify(scan)};
  function seed(){
    if (typeof RELAY === "undefined") return setTimeout(seed, 60);
    RELAY.data = DATA; RELAY.at = Date.now(); RELAY.err = null; RELAY.tried = 1;
    /* The live fetch has nothing to reach here, so stop it rather than let it
       fail on a loop and write errors into the rooms. */
    if (typeof relayFetch === "function") window.relayFetch = async () => {};
    if (typeof relayTick === "function") window.relayTick = () => {};
    /* Make the panel show the relay: it only does so when it believes its own
       feed is down, which in a snapshot it genuinely is. */
    if (typeof DIAG !== "undefined" && DIAG.net) {
      DIAG.net.fail = Math.max(DIAG.net.fail || 0, 1);
      DIAG.net.lastErr = "این یک عکس لحظه‌ای است — اتصال زنده ندارد";
    }
    if (typeof renderWhy === "function") renderWhy();
  }
  seed();
})();
</script>`;
html = html.replace("</body>", inject + "\n</body>");
if (!html.includes(inject)) html += inject;      // no </body> in this file? append

/* 3 — say what this is, before anything else on the page */
const banner = `
<div style="background:#1d2836;border-bottom:1px solid #2b3a4d;padding:9px 16px;
  font-family:'Segoe UI',Tahoma,sans-serif;font-size:12.5px;color:#c8d4e3;direction:rtl">
  <b style="color:#f0a92e">عکس لحظه‌ای</b> — اسکن
  <b>${scan.generatedText}</b> (${ageMin} دقیقه پیش) ·
  <b>${scan.counts.SIGNAL}</b> سیگنال روی <b>${scan.series}</b> سری.
  قیمت‌ها در همین لحظه ثابت‌اند و به‌روز نمی‌شوند —
  برای نسخهٔ زنده پنل را از GitHub Pages باز کن.
</div>`;
html = html.replace(/(<body[^>]*>)/i, `$1${banner}`);
if (!html.includes(banner)) html = banner + html;

writeFileSync(out, html);
const kb = (Buffer.byteLength(html) / 1024).toFixed(0);
console.log(`wrote ${out} — ${kb} KB, no external requests`);
console.log(`scan ${scan.generatedText} (${ageMin} min old), ${scan.counts.SIGNAL} signals`);
console.log(`per strategy: ${JSON.stringify(scan.per_strategy && Object.fromEntries(
  Object.entries(scan.per_strategy).map(([k, v]) => [k, v.signals])))}`);

/* A leftover external reference would silently break under a strict policy. */
const leftovers = [...html.matchAll(/(?:src|href)\s*=\s*["'](https?:\/\/[^"']+|\.\/[^"']+)["']/g)]
  .map(m => m[1])
  .filter(u => !u.startsWith("data:") && !/\.(png|webmanifest|ico)$/.test(u));
if (leftovers.length) {
  console.log(`\nstill referenced externally (will not load): ${[...new Set(leftovers)].join(", ")}`);
} else {
  console.log("no external script or style references remain");
}
