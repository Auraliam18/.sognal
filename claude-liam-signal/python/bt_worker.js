/* Replays real candles through the shipped engine, one bar at a time, and
   reports every trade it would have taken.

   The engine is not re-implemented here. It is lifted out of index.html by the
   same harness the rest of tests/ uses, so what this measures is the code that
   actually runs in the panel. Two variants:

     base    — the engine exactly as it ships
     channel — the same engine with the three channel rules made compulsory:
               room to run, an inducement sweep, and structure that is not thin

   Only bars up to and including the current one are ever passed in, so nothing
   can see its own future. Trades are managed the way the paper desk manages
   them: target one moves the stop to entry, then target two or the return to
   entry closes it, and eight hours without either is a timeout.

   Usage: node bt_worker.js <variant> <jobs.json>   → trades as JSON on stdout */
const fs = require("fs");
const path = require("path");
const H = require(path.join(__dirname, "..", "..", "tests", "harness.js"));

const variant = process.argv[2] || "base";
const jobs = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));

/* Re-arming the channel rules for the strict variant. The anchor is the ADX
   gate, which sits at the end of the chain and has not moved. */
const CHANNEL_GATES =
  'else if(thin.thin){cand.stage="ARMED";cand.skip="thin";}\n' +
  '      else if(room.r<1.5){cand.stage="ARMED";cand.skip="no room";}\n' +
  '      else if(!swept){cand.stage="ARMED";cand.skip="no inducement";}\n' +
  "      ";

const E = H.loadEngine(
  variant === "channel"
    ? { __regex: [[/else if\(adxFloor\(\)&&dmi\.adx<adxFloor\(\)\)\{/, CHANNEL_GATES + "else if(adxFloor()&&dmi.adx<adxFloor()){"]] }
    : undefined
);

const WINDOW = 400;          // the panel never sees more history than this
const WARMUP = 300;          // enough bars behind the first decision
const TIMEOUT_MS = 288e5;    // eight hours, as on the paper desk
const COOLDOWN = 6;          // bars between entries on one symbol

/* One bar's worth of management, ordered pessimistically: when a bar could have
   hit either side, assume it hit the losing one first. */
function step(tr, bar) {
  const L = tr.dir === "LONG";
  const hitSL = L ? bar.l <= tr.sl : bar.h >= tr.sl;
  const hitT1 = L ? bar.h >= tr.tp1 : bar.l <= tr.tp1;
  const hitT2 = tr.tp2 != null && (L ? bar.h >= tr.tp2 : bar.l <= tr.tp2);
  if (!tr.t1) {
    if (hitSL) return { r: -1, why: "stop" };
    if (hitT1) { tr.t1 = true; tr.sl = tr.entry; }
    return null;
  }
  if (L ? bar.l <= tr.entry : bar.h >= tr.entry) return { r: tr.R1, why: "breakeven" };
  if (hitT2) return { r: tr.R2, why: "target2" };
  return null;
}

const out = [];
for (const job of jobs) {
  const cd = job.candles;
  if (!cd || cd.length < WARMUP + 40) continue;
  let open = null, lastEntry = -999;

  for (let i = WARMUP; i < cd.length; i++) {
    const bar = cd[i];

    if (open) {
      const done = step(open, bar);
      const timedOut = !done && bar.t - open.t0 > TIMEOUT_MS;
      if (done || timedOut) {
        const res = done || { r: open.t1 ? open.R1 : 0, why: "timeout" };
        out.push({
          sym: job.sym, tf: job.tf, dir: open.dir, r: +res.r.toFixed(3), why: res.why,
          w: res.r > 0 ? 1 : 0, bars: i - open.i, R: open.R2,
          room: open.room, swept: open.swept, inside: open.inside,
          volr: open.volr, thin: open.thin, adx: open.adx, conf: open.conf,
          openedAt: open.t0, closedAt: bar.t
        });
        open = null;
      } else continue;
    }

    if (i - lastEntry < COOLDOWN) continue;
    const view = cd.slice(Math.max(0, i - WINDOW + 1), i + 1);
    let x = null;
    try { x = E.smcSetup(view, { tf: job.tf, asset: job.sym }); } catch (e) { continue; }
    if (!x || x.stage !== "SIGNAL" || !x.tp1) continue;

    const risk = Math.abs(x.entry - x.sl);
    if (!risk || risk / x.entry < 0.0008) continue;
    const R1 = Math.min(Math.abs(x.tp1 - x.entry) / risk, 8);
    if (R1 < 1) continue;
    const R2 = x.tp2 != null ? Math.min(Math.abs(x.tp2 - x.entry) / risk, 12) : R1;

    lastEntry = i;
    open = {
      i, t0: bar.t, dir: x.dir, entry: x.entry, sl: x.sl, tp1: x.tp1, tp2: x.tp2,
      R1, R2, t1: false,
      room: x.room ? x.room.r : null, swept: x.swept ? 1 : 0,
      inside: x.thin ? x.thin.insideRatio : null, volr: x.thin ? x.thin.volRatio : null,
      thin: x.thin && x.thin.thin ? 1 : 0, adx: x.dmi ? x.dmi.adx : null,
      conf: x.conf != null ? x.conf : null
    };
  }
}

process.stdout.write(JSON.stringify(out));
