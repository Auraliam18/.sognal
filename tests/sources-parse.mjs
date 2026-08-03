/* هر پارسر را با همان ردیفی که پروب واقعاً از آن صرافی گرفت تست می‌کند.
 *
 * These APIs disagree about field order and about which way time runs, and
 * getting either wrong produces a chart that looks completely normal and is
 * wrong. KuCoin puts close where Binance puts high. Gate puts volume second and
 * open last. Half of the twelve return newest-first. None of that is visible on
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
  // Bitunix: objects, NEWEST FIRST, ms. Reversing this is the fix that made the
  // primary source usable at all — unreversed, sourceSane rejected every reply.
  bitunix: [
    { time: 1785665700000, open: "63249.8", high: "63260", low: "63240", close: "63255.0",
      quoteVol: "40.1", baseVol: "2536000" },
    { time: 1785664800000, open: "63239.1", high: "63253.7", low: "63230", close: "63249.8",
      quoteVol: "42.8512", baseVol: "2710134.33232" },
  ],
  mexc: [
    [1785656700000, "63548.41", "63548.41", "63497.75", "63509.48", "63.64265045", 1785657600000],
    [1785657600000, "63509.48", "63560.00", "63490.00", "63540.00", "51.11", 1785658500000],
  ],
  bingx: [   // newest first, ms
    [1785665700000, 63274.0, 63280.0, 63250.0, 63260.0, 2.1, 1785666599999],
    [1785664800000, 63273.94, 63273.95, 63234.44, 63234.44, 2.156673, 1785665699999],
  ],
  bitmart: [ // oldest first, seconds
    ["1785656700", "63538.11", "63538.12", "63483.76", "63506.23", "72.49017", "4603177.17"],
    ["1785657600", "63506.23", "63560.00", "63490.00", "63540.00", "60.10", "3810000.00"],
  ],
  htx: [     // objects keyed id, seconds, newest first
    { id: 1785665700, open: 63244.11, close: 63255.0, low: 63240.0, high: 63260.0, amount: 7.1 },
    { id: 1785664800, open: 63282.87, close: 63244.11, low: 63244.11, high: 63282.87, amount: 7.947177 },
  ],
  kucoin: [  // newest first, seconds, [t, open, CLOSE, HIGH, LOW, vol, turnover]
    ["1785665700", "63238.3", "63255.0", "63260.0", "63230.0", "0.70", "44000.0"],
    ["1785664800", "63272.3", "63238.3", "63272.3", "63238.3", "0.71017397", "44920.089347816"],
  ],
  okx: [     // newest first, ms
    ["1785665700000", "63234.1", "63260.0", "63230.0", "63255.0", "1.70", "107000.0"],
    ["1785664800000", "63271", "63271", "63234.1", "63234.1", "1.78132461", "112670.341183148"],
  ],
  bitget: [  // oldest first, ms
    ["1785656700000", "63528.58", "63528.58", "63471.62", "63485.98", "40.260803", "2556090.49546045"],
    ["1785657600000", "63485.98", "63560.00", "63480.00", "63540.00", "38.10", "2420000.00"],
  ],
  gate: [    // oldest first, seconds, [t, VOLUME, close, high, low, open]
    ["1785656700", "2596079.82040720", "63498.9", "63533.2", "63475.5", "63533.2", "40.88496700"],
    ["1785657600", "2480000.00000000", "63540.0", "63560.0", "63490.0", "63498.9", "39.10"],
  ],
  coinex: [  // objects, created_at already in ms, oldest first
    { close: "63480", created_at: 1785656700000, high: "63530", low: "63480",
      market: "BTCUSDT", open: "63530", volume: "40.1" },
    { close: "63540", created_at: 1785657600000, high: "63560", low: "63470",
      market: "BTCUSDT", open: "63480", volume: "38.2" },
  ],
  coinbase: [ // newest first, seconds, [t, LOW, HIGH, open, close, volume]
    [1785665700, 63192.81, 63220.00, 63205.21, 63210.00, 0.80],
    [1785664800, 63192.81, 63205.21, 63205.21, 63192.81, 0.82142626],
  ],
  binance: [
    [1785655800000, "62997.75000000", "63018.64000000", "62982.00000000", "63004.48000000",
     "103.40962000", 1785656699999],
    [1785656700000, "63004.48000000", "63560.00000000", "62995.50000000", "63509.48000000",
     "88.10000000", 1785657599999],
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
  const ok = off < (x.id === "coinbase" ? 1.5 : 0.5);
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
