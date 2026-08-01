/* Runs the shipped engine over the newest candles and reports what it says
   right now — one entry per symbol and timeframe that produced a setup.

   Same engine as the panel, lifted out of index.html by the same harness. The
   last candle is dropped before evaluating, because a candle that is still open
   has not closed out of the box yet and the whole strategy turns on that close.

   Both strategies are asked, on the same candles, and each carries its own name
   through to the panel and to Telegram — so a signal always says which strategy
   produced it and the two can be judged apart rather than as one blur.

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

  /* ── strategy 2: channel + order block ─────────────────────────────────── */
  let s = null;
  try { s = E.smcSetup(cd, { tf: job.tf, asset: job.sym, dom: job.dom || null }); }
  catch (e) {
    if (e instanceof TypeError || e instanceof ReferenceError) {
      console.error(`FATAL: smc engine not callable — ${e.message}`);
      process.exit(2);
    }
  }

  /* ── strategy 1: IBS + pullback ────────────────────────────────────────── */
  let ibs = null;
  try { ibs = E.ibsPullback(cd); }
  catch (e) {
    if (e instanceof TypeError || e instanceof ReferenceError) {
      console.error(`FATAL: ibs engine not callable — ${e.message}`);
      process.exit(2);
    }
  }
  if (ibs && ibs.tp1 && ibs.dir) {
    const r = Math.abs(ibs.entry - ibs.sl);
    if (r && r / ibs.entry >= 0.0008) {
      /* Strategy 1 has no staged lifecycle. Quality is its bar, and price has to
         be at the block — the same condition the miner measured it on, so the
         live signal and the stored history mean the same thing. */
      const fired = ibs.quality >= 55 && (ibs.inOB || ibs.nearOB);
      out.push({
        strategy: "ibs", strategyName: "IBS + پولبک",
        sym: job.sym, tf: job.tf,
        stage: fired ? "SIGNAL" : ibs.quality >= 45 ? "ARMED" : "WATCH",
        dir: ibs.dir, entry: ibs.entry, sl: ibs.sl, tp1: ibs.tp1, tp2: ibs.tp2,
        rr: +(Math.abs(ibs.tp1 - ibs.entry) / r).toFixed(2),
        price: ibs.cur, conf: null, ev: null, quality: ibs.quality,
        visits: null, depth: null, exited: false, inside: !!ibs.inOB,
        fvg: false, level: null, channel: null, adx: null, room: null, swept: null,
        thin: null, goOnFirst: false,
        waitReason: fired ? null : (ibs.inOB || ibs.nearOB ? "کیفیت کافی نیست" : "قیمت هنوز به باکس نرسیده"),
        skip: null, lastClose: cd[cd.length - 1].t,
        ob: ibs.ob ? { low: ibs.ob.low, high: ibs.ob.high } : null,
        choch: ibs.choch ? 1 : 0, barsAgo: ibs.barsAgo ?? null,
        inOB: ibs.inOB ? 1 : 0, nearOB: ibs.nearOB ? 1 : 0,
        candles: cd.slice(-120),
      });
    }
  }

  if (!s || !s.ob) continue;

  const risk = Math.abs(s.entry - s.sl);
  if (!risk || risk / s.entry < 0.0008) continue;

  out.push({
    strategy: "smc", strategyName: "کانال + اردر بلاک",
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
    /* The box itself, so the chart can draw what the price has to close out of. */
    ob: s.ob ? { low: s.ob.low, high: s.ob.high } : null,
    /* Enough tail to draw the setup without carrying 400 bars per symbol. */
    candles: cd.slice(-120),
  });
}

process.stdout.write(JSON.stringify(out));
