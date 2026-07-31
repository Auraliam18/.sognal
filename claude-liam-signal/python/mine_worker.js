/* Mines the past for setups, on both strategies, and records what became of
   each one along with everything that was true at the time.

   Strategy 1 is IBS + Pullback — ibsPullback() in the panel.
   Strategy 2 is the channel / order block engine — smcSetup().

   Both are lifted out of index.html by the same harness the rest of tests/ uses,
   so this mines what the panel actually runs rather than a description of it.

   The point is not the outcome on its own. The outcome alone says a trade won
   or lost; it does not say why, and "why" is the only part that transfers to
   the next trade. So every setup is recorded with the conditions that held when
   it fired — the trend, the structure, the dominance at that moment — and the
   reason is found afterwards, by looking at which conditions keep showing up on
   the winners and which keep showing up on the losers. A reason invented per
   trade would just be a story; a reason that survives a few hundred repetitions
   is a finding.

   Nothing is ever shown a bar it has not reached.

     node mine_worker.js <jobs.json>   → experiences as JSON on stdout */
const fs = require("fs");
const path = require("path");
const H = require(path.join(__dirname, "..", "..", "tests", "harness.js"));

const E = H.loadEngine();
const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

const WINDOW = 400;        // what the panel sees
const WARMUP = 320;
const MAX_BARS = 96;       // 24h on 15m — a setup that has not resolved by then has not
const COOLDOWN = 8;
const FILL_WINDOW = 24;    // 6h on 15m — a pullback that has not come by then is not coming

/* A trade at a price the market never reached is not a trade.

   Both strategies can name an entry away from the current price — a limit at the
   order block edge, waiting for the pullback. Assuming that limit always fills
   is the single most flattering mistake a backtest can make, because the setups
   where price runs away without returning are exactly the ones that would have
   been "right", and counting them hands the strategy every winner it never took.

   Measured on this data it was worth 8.5x: the strategy-1 setups that entered at
   the real market price returned +0.103R, the ones assumed filled at the block
   returned +0.873R.

   So the fill is required. Walk forward from the signal and open only when price
   actually trades through the entry level, inside a window; if it never does,
   there is no trade at all. `waited` is kept because how long a fill took is
   worth knowing later. */
function fill(tr, bars, window) {
  const L = tr.dir === "LONG";
  for (let i = 0; i < Math.min(bars.length, window); i++) {
    const b = bars[i];
    if (L ? b.l <= tr.entry : b.h >= tr.entry) {
      /* The filling bar can also take the stop out. Assume it did — the
         pessimistic reading, and the one that cannot flatter. */
      const stopped = L ? b.l <= tr.sl : b.h >= tr.sl;
      return { at: i, waited: i, stoppedOnFill: stopped };
    }
  }
  return null;
}

/* Manage exactly as the paper desk does: target one moves the stop to entry,
   then target two or the return to entry closes it. A bar that could have hit
   either side is assumed to have hit the losing one. */
function outcome(tr, bars) {
  const L = tr.dir === "LONG";
  let t1 = false, sl = tr.sl;
  for (let i = 0; i < bars.length; i++) {
    const b = bars[i];
    const hitSL = L ? b.l <= sl : b.h >= sl;
    const hitT1 = L ? b.h >= tr.tp1 : b.l <= tr.tp1;
    const hitT2 = tr.tp2 != null && (L ? b.h >= tr.tp2 : b.l <= tr.tp2);
    if (!t1) {
      if (hitSL) return { r: -1, why: "stop", bars: i + 1 };
      if (hitT1) { t1 = true; sl = tr.entry; }
    } else {
      if (L ? b.l <= tr.entry : b.h >= tr.entry) return { r: tr.R1, why: "breakeven", bars: i + 1 };
      if (hitT2) return { r: tr.R2, why: "target2", bars: i + 1 };
    }
  }
  return { r: t1 ? tr.R1 : 0, why: "timeout", bars: bars.length };
}

/* The market at the moment the setup fired, from series aligned by timestamp.
   Stored with the setup because the whole question later is which conditions
   the winners shared. */
function contextAt(ctx, t) {
  const out = {};
  for (const [name, series] of Object.entries(ctx || {})) {
    if (!series || !series.length) continue;
    let lo = 0, hi = series.length - 1, at = -1;
    while (lo <= hi) {                                  // last bar at or before t
      const mid = (lo + hi) >> 1;
      if (series[mid].t <= t) { at = mid; lo = mid + 1; } else hi = mid - 1;
    }
    if (at < 8) continue;
    const now = series[at].c, ago = series[at - 8].c;
    const chg = (now - ago) / ago * 100;
    out[name + "_chg"] = +chg.toFixed(2);
    out[name + "_dir"] = chg > 0.25 ? "UP" : chg < -0.25 ? "DOWN" : "FLAT";
  }
  return out;
}

const out = [];
for (const job of jobs) {
  const cd = job.candles;
  if (!cd || cd.length < WARMUP + 60) continue;
  const ctx = job.context || {};

  for (const strategy of ["ibs", "smc"]) {
    let last = -999;
    const found = { LONG: 0, SHORT: 0 };

    for (let i = WARMUP; i < cd.length - 2; i++) {
      if (i - last < COOLDOWN) continue;
      if (found.LONG >= job.perSide && found.SHORT >= job.perSide) break;

      const view = cd.slice(Math.max(0, i - WINDOW + 1), i + 1);
      let s = null;
      try {
        s = strategy === "smc"
          ? E.smcSetup(view, { tf: job.tf, asset: job.sym })
          : E.ibsPullback(view);
      } catch (e) {
        /* A missing function is a broken harness, not a quiet market. Swallowing
           it once already produced a confident zero for strategy 1 — every IBS
           call was throwing TypeError and the catch reported "no setups found".
           Anything that is not the engine declining is fatal now. */
        if (e instanceof TypeError || e instanceof ReferenceError) {
          console.error(`FATAL: ${strategy} engine is not callable — ${e.message}`);
          process.exit(2);
        }
        continue;
      }
      if (!s || !s.tp1 || !s.dir) continue;

      /* Strategy 1 has no staged lifecycle; quality is its own bar to clear.
         Strategy 2 fires on the close back out of the box. Each is asked for
         what it actually means by "a setup", not a shared invention. */
      const fired = strategy === "smc"
        ? s.stage === "SIGNAL"
        : (s.quality >= 55 && (s.inOB || s.nearOB));
      if (!fired) continue;
      if (found[s.dir] >= job.perSide) continue;

      const risk = Math.abs(s.entry - s.sl);
      if (!risk || risk / s.entry < 0.0008) continue;
      const R1 = Math.min(Math.abs(s.tp1 - s.entry) / risk, 8);
      if (R1 < 0.8) continue;
      const R2 = s.tp2 != null ? Math.min(Math.abs(s.tp2 - s.entry) / risk, 12) : R1;

      const tr = { dir: s.dir, entry: s.entry, sl: s.sl, tp1: s.tp1, tp2: s.tp2, R1, R2 };
      const forward = cd.slice(i + 1, i + 1 + MAX_BARS);
      const f = fill(tr, forward, FILL_WINDOW);
      if (!f) continue;                       // never filled — never a trade

      const res = f.stoppedOnFill
        ? { r: -1, why: "stop", bars: f.waited + 1 }
        : outcome(tr, forward.slice(f.at + 1));
      last = i;
      found[s.dir]++;

      out.push({
        sym: job.sym, tf: job.tf, strategy, dir: s.dir,
        t: cd[i].t, iso: new Date(cd[i].t).toISOString(),
        entry: s.entry, sl: s.sl, tp1: s.tp1, tp2: s.tp2 ?? null,
        rr: +R1.toFixed(2), R2: +R2.toFixed(2),
        r: +res.r.toFixed(3), outcome: res.why, held: res.bars,
        win: res.r > 0 ? 1 : 0,
        waitedToFill: f.waited,          // 0 means it filled on the next bar
        filledAtMarket: s.inOB ? 1 : 0,
        /* conditions at the moment it fired — the raw material for "why" */
        quality: s.quality ?? null,
        conf: s.conf ?? null,
        adx: s.dmi ? s.dmi.adx : null,
        visits: s.visits ?? null,
        depth: s.depth ?? null,
        fvg: s.fvg ? 1 : 0,
        level: s.level ? 1 : 0,
        levelTouches: s.level ? s.level.touches : 0,
        channel: s.channel ? s.channel.dir : null,
        channelAligned: s.channel
          ? ((s.dir === "LONG" && s.channel.dir === "صعودی") ||
             (s.dir === "SHORT" && s.channel.dir === "نزولی")) ? 1 : 0
          : null,
        room: s.room ? s.room.r : null,
        swept: s.swept ? 1 : 0,
        insideRatio: s.thin ? s.thin.insideRatio : null,
        volRatio: s.thin ? s.thin.volRatio : null,
        inOB: s.inOB ? 1 : 0,
        barsAgo: s.barsAgo ?? null,
        choch: s.choch ? 1 : 0,
        ...contextAt(ctx, cd[i].t),
      });
    }
  }
}

process.stdout.write(JSON.stringify(out));
