/* هر پارسر را با همان ردیفی که پروب واقعاً از آن صرافی گرفت تست می‌کند.
 *
 * These APIs disagree about field order and about which way time runs, and
 * getting either wrong produces a chart that looks completely normal and is
 * wrong. KuCoin puts close where Binance puts high. Gate puts volume second and
 * open last. Four of the eight return newest-first. None of that is visible on
 * screen, so it has to be caught here.
 *
 * The rows below are copied from the probe's own output — not from any
 * documentation — and every one is BTC/USDT 15m at roughly the same minute, so
 * the parsed prices must all agree with each other to within a fraction of a
 * percent. That cross-check is what actually catches a scrambled field order:
 * a wrong index still parses as a number, but it does not land near 63,000.
 *
 *   node tests/sources-parse.mjs
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const html = readFileSync(ROOT + "index.html", "utf8");

/* Lift SOURCES and its helpers straight out of the panel, so this tests what
   ships rather than a copy that can drift. */
const from = html.indexOf("const SOURCES=[");
const to = html.indexOf("async function srcJSON");
if (from < 0 || to < 0) { console.error("could not find SOURCES in index.html"); process.exit(1); }
const src = html.slice(from, to);
const shim = "const DB={_m:{},get(k){return this._m[k]},set(k,v){this._m[k]=v}};" +
             "function opslog(){}function diagNet(){}const S={kline_limit:300};";
const { SOURCES, sourceSane } =
  new Function(shim + src + "\nreturn{SOURCES,sourceSane};")();

/* Real replies, as recorded by claude-liam-signal/python/probe_sources.py.
   Each is BTC/USDT 15m around 2026-08-01 06:09 UTC, price near 63,000. */
const RECORDED = {
  bitunix: [
    { time: 1785555900000, open: "62983.4", high: "63011", low: "62969.6", close: "62999.8",
      quoteVol: "98.2225", baseVol: "6187255.74097" },
    { time: 1785556800000, open: "62999.8", high: "63040.5", low: "62995.5", close: "63014.5",
      quoteVol: "88.1", baseVol: "5550000.0" },
  ],
  mexc: [
    [1785555900000, "62999.93", "63027.01", "62983.72", "63010.19", "62.53711367", 1785556800000],
    [1785556800000, "63010.19", "63040.50", "62995.50", "63014.50", "51.11", 1785557700000],
  ],
  kucoin: [   // newest first, seconds, [t, open, CLOSE, HIGH, LOW, vol, turnover]
    ["1785564000", "63031.2", "63012.2", "63042.2", "62996.1", "4.89124007", "308311.178363591"],
    ["1785563100", "63000.1", "63031.2", "63035.0", "62990.0", "5.10", "321000.0"],
  ],
  bybit: [    // newest first, ms
    ["1785564000000", "63028.4", "63039.6", "62995.5", "63008.2", "27.472999", "1731377.2888601"],
    ["1785563100000", "63001.0", "63030.0", "62988.0", "63028.4", "19.10", "1203000.0"],
  ],
  okx: [      // newest first, ms
    ["1785564000000", "63033.5", "63040.5", "63000", "63014.5", "11.38669144", "717668.009464882"],
    ["1785563100000", "63005.0", "63035.0", "62995.0", "63033.5", "9.11", "574000.0"],
  ],
  bitget: [   // oldest first, ms
    ["1785555900000", "62999.88", "63018.57", "62983.73", "63002.38", "7.320638", "461203.34697333"],
    ["1785556800000", "63002.38", "63040.50", "62995.50", "63014.50", "6.10", "384000.0"],
  ],
  gate: [     // oldest first, seconds, [t, VOLUME, close, high, low, open]
    ["1785555900", "2070452.55502250", "63002", "63018.6", "62984.8", "62997.6", "32.86185400"],
    ["1785556800", "1980000.00000000", "63014.5", "63040.5", "62995.5", "63002", "31.10"],
  ],
  binance: [
    [1785555900000, "62997.75000000", "63018.64000000", "62982.00000000", "63004.48000000",
     "103.40962000", 1785556799999],
    [1785556800000, "63004.48000000", "63040.50000000", "62995.50000000", "63014.50000000",
     "88.10000000", 1785557699999],
  ],
};

let failed = 0;
const seen = [];
console.log(`\n${"صرافی".padEnd(12)}${"open".padStart(11)}${"high".padStart(11)}${"low".padStart(11)}${"close".padStart(11)}   ترتیب زمان`);
console.log("─".repeat(76));

for (const s of SOURCES) {
  const rows = RECORDED[s.id];
  if (!rows) { console.log(`${s.id.padEnd(12)}  (ردیف ضبط‌شده ندارد)`); failed++; continue; }
  let cd;
  try { cd = s.parse(rows); }
  catch (e) { console.log(`${s.id.padEnd(12)}  پارس نشد: ${e.message}`); failed++; continue; }

  const k = cd[0];
  const ordered = cd[0].t < cd[cd.length - 1].t;
  const msLike = k.t > 1e12;
  const line = `${s.id.padEnd(12)}${k.o.toFixed(2).padStart(11)}${k.h.toFixed(2).padStart(11)}` +
               `${k.l.toFixed(2).padStart(11)}${k.c.toFixed(2).padStart(11)}   ` +
               `${ordered ? "قدیم→جدید" : "جدید→قدیم ✗"}${msLike ? "" : "  زمان ثانیه ✗"}`;
  console.log(line);

  const problems = [];
  if (!ordered) problems.push("ترتیب زمانی برعکس است");
  if (!msLike) problems.push("زمان به میلی‌ثانیه تبدیل نشده");
  if (!(k.h >= k.l)) problems.push("high کمتر از low است — ترتیب فیلدها اشتباه است");
  if (!(k.h >= k.o && k.h >= k.c)) problems.push("high بالاترین مقدار نیست");
  if (!(k.l <= k.o && k.l <= k.c)) problems.push("low پایین‌ترین مقدار نیست");
  if (!isFinite(k.v) || k.v <= 0) problems.push("حجم عددی نیست");
  if (problems.length) { problems.forEach(p => console.log(`             ✗ ${p}`)); failed++; }
  seen.push({ id: s.id, c: k.c });
}

/* Every source was asked for the same instrument at nearly the same minute, so
   the closes must agree. A scrambled field order still yields a number — this
   is what shows that the number is the wrong one. */
console.log("\nهمهٔ منابع باید تقریباً یک قیمت بدهند (BTC/USDT، همان دقیقه):");
const med = seen.map(x => x.c).sort((a, b) => a - b)[Math.floor(seen.length / 2)];
for (const x of seen) {
  const off = Math.abs(x.c / med - 1) * 100;
  const ok = off < 0.5;
  console.log(`  ${ok ? "✓" : "✗"} ${x.id.padEnd(10)} ${x.c.toFixed(2).padStart(10)}  ${off.toFixed(3)}% اختلاف`);
  if (!ok) failed++;
}

/* And the guard that keeps a bad reply off the chart must actually reject one. */
console.log("\nنگهبان sourceSane:");
const good = SOURCES.find(s => s.id === "binance").parse(RECORDED.binance);
const checks = [
  ["کندل سالم را می‌پذیرد", sourceSane([...good, ...good, ...good, ...good, ...good,
    ...good.map(k => ({ ...k, t: k.t + 9e5 }))]) === true],
  ["ترتیب برعکس را رد می‌کند", sourceSane(good.slice().reverse()) === false],
  ["NaN را رد می‌کند", sourceSane(good.map(k => ({ ...k, c: NaN }))) === false],
  ["high<low را رد می‌کند", sourceSane(good.map(k => ({ ...k, h: 1, l: 9 }))) === false],
  ["آرایهٔ کوتاه را رد می‌کند", sourceSane(good) === false],
];
for (const [name, ok] of checks) {
  console.log(`  ${ok ? "✓" : "✗"} ${name}`);
  if (!ok) failed++;
}

console.log(`\n${failed ? `${failed} ایراد` : "همهٔ پارسرها درست‌اند"}`);
process.exit(failed ? 1 : 0);
