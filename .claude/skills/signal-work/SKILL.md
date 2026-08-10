---
name: signal-work
description: Working rules for Hamid's trading panel. Load before changing the engine, reporting a number, tuning a threshold, reviewing paper-trading results, or answering "why is there no signal". Covers what to measure, what to refuse, and how to raise signal accuracy toward the 90% target without fooling ourselves.
---

# Working on the signal engine

The goal is signals that land above 90%. Nothing below is a style preference —
each rule exists because breaking it already cost days.

## Measure first, and measure the right thing

Never change a threshold on intuition. The tools are in `tests/`:

```bash
node tests/evaluate.js          # walk-forward over simulated markets
node tests/diagnose.js          # where setups die, gate by gate
node tests/cycle.js             # one full cycle, sharded across cores
node tests/search.js            # parameter sweep, fitted and judged separately
python3 claude-liam-signal/python/screener.py   # which symbols deserve attention now
```

Report expectancy, not win rate. A 98% win rate at 0.74R average is worse than
44% at 1.89R, and the first version of this engine had exactly that profile
because targets were the nearest prior swing.

Always bootstrap a confidence interval. **A finding is only acted on once its
interval clears zero.** This rule has caught two of my own wrong conclusions.

## Sample size is not optional

557 trades gave +0.25R. The same engine over 15,290 trades gave 0.00R. The
first number was noise and I reported it as a result. Before claiming anything,
check the sample is in the thousands, and shard across cores:

```bash
for i in 0 1 2 3; do node tests/worker.js $((1+i*150)) $((1+(i+1)*150)) > /tmp/w$i.json & done; wait
```

## Overfitting has a specific smell

A configuration that wins in-sample and loses out-of-sample is fitting noise.
`tests/search.js` fits on one set of markets and judges on another, ranks only
on the held-out set, and refuses anything whose out-of-sample interval spans
zero. Adopt a candidate only when:

- the out-of-sample interval is entirely above zero,
- the gain over what is shipped is worth taking (> 0.02R, not a rounding),
- and neighbouring cells agree — a lone winning cell in a grid is luck.

I once widened the freshness window to 200 bars on the strength of a trending
tape I had written minutes earlier. The rigorous simulator put it at −0.16R
with the whole interval below zero.

## The simulator is a null test, not a market

It has volatility clustering, fat tails and regime switching, and no order
flow. A strategy that finds edge in it is reading its own noise. Zero there is
the *correct* result for an honest engine. Say plainly which source a number
comes from — simulated or live candles — every single time.

## Two desks, different jobs

**The practice desk** trades the live tape at real prices with no money and no
signal. Its gates are loose on purpose: any structure with a real entry, stop
and target. A strict desk yields a handful of outcomes a day and teaches the
learning room nothing. Everything it settles feeds the confidence model and the
case memory.

**The signal desk** is strict, and before anything goes out the supervisor asks
the learning room about *that coin, that direction, situations like this one*.
Enough negative history vetoes it. Below a dozen trades, say the history is too
thin rather than pretending.

Raising accuracy means growing the practice sample, not tightening the signal
gate until nothing fires. Zero signals is not 100%.

## One change per cycle

Applying several at once makes the next result unreadable — an improvement
names no cause, a regression names nothing to undo. Each review grades the
previous change against trades that closed since, keeps or reverts it, then
makes at most one new change. A reverted change is quarantined; leaving it
eligible produced an oscillation rather than a search.

## What "no signal" actually means

Check in this order, because I wasted days assuming the engine:

1. Is data arriving? Binance geo-blocks some regions and an unreachable host
   looks exactly like a quiet market. The panel says so in a red box.
2. Is the panel deployed and open?
3. Run `node tests/diagnose.js` — it counts where setups die. Last time nothing
   in the decision layer was blocking anything; the engine signalled on 3.6% of
   checks and the problem was that most of those signals should not have been
   taken.

## Reporting

Every number needs a script that reproduces it. Corrections come first and
plainly, with the measurement that overturned the old claim. Never soften a bad
result — Hamid trades this himself and a flattering number is worse than none.

## Standing tools

Per `CLAUDE.md`: Actions carries all heavy compute, Notion the comparable
record, Drive the archive, Gmail drafts only, Telegram live delivery, n8n
orchestration. Use them without being asked. Never put the replay work on the
laptop.

## قوانین اصلی یادگیری و حافظه — از خود حمید، ۱۰ اوت ۲۰۲۶ (عیناً)

۱. **Memory Persistence:** هر تحلیل، نتیجه‌گیری‌ها، الگوها، اشتباهات و
درس‌هایش را ذخیره می‌کند و تحلیل‌های بعدی از آن استفاده می‌کنند.
۲. **Continuous Learning Loop:** بعد از هر تحلیل از نتیجه‌اش یاد بگیر —
سیگنال درست: دلیل موفقیت ثبت؛ اشتباه: علت خطا تحلیل و به دانش اضافه شود.
۳. **Progressive Improvement:** هر تحلیل باید از قبلی هوشمندتر باشد.
هرگز مثل مدل ثابت رفتار نکن.

**رفتار در پنل:** با ظهور هر سیگنال، خودکار تاریخچهٔ همان ارز و مشابه‌ها
(شباهت چارت، ساختار، BOS/CHoCH/FVG/OB/نقدینگی، حجم، احساسات، خبر) بررسی و
بر پایهٔ دانش انباشته تأیید/رد شود؛ شباهت قوی با گذشته **صریح ذکر** شود.

**چرخهٔ همیشگی:** تحلیل → یادگیری → ذخیره در حافظه → استفاده در تحلیل
بعدی → بهبود عملکرد.

پیاده‌سازی: `hamid/memory.py` (دفتر درس‌ها + مشورت قبل از صدور)،
`brain.learn/recall` (حافظهٔ آماری)، هضم بسته‌شده‌ها در هر چرخه، خط 🧠
در پیام تلگرام، جعبهٔ «حافظه و درس‌ها» در تب ایجنت. قید صداقت پابرجاست:
زیر ۸ مورد مشابه فقط ذکر، بدون اثر رتبه؛ وتو با ۱۲+ (ناظر تجربه).

## نقشهٔ نقدینگی (لیکوییدیتی هیت‌مپ) — درس ثابت ایجنت

هیت‌مپ جایی را نشان می‌دهد که استاپ‌ها و لیکوییدها جمع‌اند: بالای سقف‌های
برابر (استاپ شورت‌ها) و زیر کف‌های برابر (استاپ لانگ‌ها). قیمت مثل آهن‌ربا
سمت استخر بزرگ‌تر کشیده می‌شود و بعد از برداشتن نقدینگی اغلب برمی‌گردد
(همان سوییپ ایندوسمنت). تخمین ما از کندل است، نه سرویس پولی:
`hamid/liquidity.py` — خوشهٔ اکسترمم‌های سوینگ در ±۰.۱۵٪ با ۲+ برخورد.
هر چرخه قبل از سیگنال چک می‌شود، جهتش («هم‌جهت/خلاف آهن‌ربا») روی هر
معامله ثبت و در پیام تلگرام (💧) ذکر می‌شود. قانونِ عمل نیست تا وقتی شرط
«نقدینگی هم‌جهت بود» در بک‌تست شبانه بازهٔ اطمینانش را از صفر رد کند.

## چارت اجباری روی هر سیگنال — درس ۱۰ اوت

قانون حمید: سیگنال بی‌چارت نرود. یک بار شکست: ورک‌فلوی چرخه matplotlib
نصب نمی‌کرد، `_tg_chart` بی‌صدا except می‌خورد و fallback متنی می‌رفت —
سیگنال‌ها بدون چارت رسیدند و حمید دید. درس ماندگار: **fallback ساکت،
خطا را از چشم پنهان می‌کند؛ هر مسیر ارسال جدید باید (۱) وابستگی چارت را
در ورک‌فلو نصب کند و (۲) شکست چارت را در لاگ بلند بگوید.** مسیرهای
ارسال و چارتشان: چرخه (`_tg_chart` ۵د + واترمارک)، اسکن (`chart.render`)،
رادار پامپ (`_pick_chart` انتخاب اول)، هشدار ریزش (چارت BTC). سقف کپشن
تلگرام ۱۰۲۴ کاراکتر است — پیام بلندتر: متن جدا + عکس جدا.

## نقشهٔ لیکوییدیشن (سبک kCEX) — liqmap.py

اپ kCEX نقشهٔ لیکوییدیشن دارد ولی API عمومی ندارد؛ معادل بازتولیدپذیرش
از کندل واقعی ساخته شد: حجم هر ساعت × اهرم‌های رایج (۱۰/۲۵/۵۰/۱۰۰×) →
خوشه‌های لیکویید بالا/پایین قیمت + آهن‌ربا. روی کپشن (🗺) و دلایل پیک
رادار. همیشه با برچسب «تخمین از کندل واقعی — دادهٔ مستقیم صرافی نیست».

## تمرین تاریخی — «هزار بار استفاده کن و یاد بگیر»

بک‌تست شبانهٔ backtest.py (کندل واقعی) آمار هر ارز×جهت را به
`brain/history-stats.json` می‌نویسد؛ `memory.history()` قبل از هر سیگنال
آن را کنار تجربهٔ زنده می‌گذارد. کف ۳۰ ریپلی برای ذکر؛ اثر روی رتبه فقط
وقتی CI از صفر رد شود. ریپلی روی تاریخ، ادعای سود زنده نیست — فقط تجربه.

## بازجویی پیش از صدور — قانون حمید (۱۰ اوت)

«قبل از صدور سیگنال نهایی، در ۱۵ دقیقه ببین چه چیزهایی می‌تواند استاپش
کند؛ فقط وقتی دلایل تارگت بیشتر از دلایل استاپ بود صادرش کن.»
پیاده‌سازی: `hamid/premortem.py` در گلوگاه `telegram.send_signals` — همهٔ
مسیرها (چرخه، اسکن، آلارم) از زیرش رد می‌شوند. دلایل شمرده‌شده: استاپ در
برابر ATR ۱۵د، روند ۱۵د، RSI، آهن‌ربای نقدینگی، خوشهٔ لیکویید، تمرین
تاریخی (CI)، دامیننس تتر و رویداد کلانِ ≤۲ساعت، تارگتِ دورتر از ۶×ATR.
حکم سخت: pro > con. ردشده‌ها به دفتر vetoed می‌روند تا خود دروازه نمره
بگیرد — اگر ردشده‌ها بیشترشان تارگت خوردند، دروازه باید شل شود. خطای
زیرساخت (شبکه) جلوی ارسال را نمی‌گیرد: دروازه تحلیل است نه بهانهٔ سکوت.
