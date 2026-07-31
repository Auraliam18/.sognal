/* Runs the shipped engine over the newest candles and reports what it says
   right now — one entry per symbol and timeframe that produced a setup.

   Same engine as the panel, lifted out of index.html by the same harness. The
   last candle is dropped before evaluating, because a candle that is still open
   has not closed out of the box yet and the whole strategy turns on that close.

     node scan_worker.js <jobs.json>   → setups as JSON on stdout */
const fs = require("fs");
const path = require("path");
const H = require(path.join(__dirname, "..", "..", "tests", "harness.js"));

const E = H.loadEngine();
const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const WINDOW = 400;

const out = [];
for (const job of jobs) {
  /* Drop the candle still forming: the signal fires on a close, not a tick. */
  const cd = job.candles.slice(0, -1).slice(-WINDOW);
  if (cd.length < 320) continue;

  let s = null;
  try { s = E.smcSetup(cd, { tf: job.tf, asset: job.sym, dom: job.dom || null }); }
  catch (e) { continue; }
  if (!s || !s.ob) continue;

  const risk = Math.abs(s.entry - s.sl);
  if (!risk || risk / s.entry < 0.0008) continue;

  out.push({
    sym: job.sym, tf: job.tf, stage: s.stage, dir: s.dir,
    entry: s.entry, sl: s.sl, tp1: s.tp1, tp2: s.tp2, rr: s.rr,
    price: s.price, conf: s.conf, ev: s.ev, quality: s.quality,
    visits: s.visits, depth: s.depth, exited: !!s.exited, inside: !!s.inside,
    fvg: !!s.fvg, level: s.level ? { type: s.level.type, touches: s.level.touches } : null,
    channel: s.channel ? { dir: s.channel.dir, drift: s.channel.drift, posPct: s.channel.posPct } : null,
    adx: s.dmi ? s.dmi.adx : null,
    room: s.room ? { r: s.room.r, blocker: s.room.blocker } : null,
    swept: s.swept ? { n: s.swept.n } : null,
    thin: s.thin ? { insideRatio: s.thin.insideRatio, volRatio: s.thin.volRatio } : null,
    goOnFirst: !!s.goOnFirst, waitReason: s.waitReason || null, skip: s.skip || null,
    lastClose: cd[cd.length - 1].t,
  });
}

process.stdout.write(JSON.stringify(out));
