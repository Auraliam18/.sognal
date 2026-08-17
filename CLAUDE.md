# Working agreement

## Standing instruction — do not wait to be asked

On every task, use the available connectors and plugins according to what each
is actually good at. This is not something Hamid should have to repeat.

| | what it carries |
|---|---|
| **GitHub Actions** | All heavy compute. Paper-trading cycles, parameter searches, deploys. Never the laptop. |
| **Notion** | The comparable record. One row per cycle with expectancy, interval, verdict, and the change made. |
| **Google Drive** | Durable archive of reports, so numbers outlive any machine. |
| **Gmail** | Digests as drafts. Never send from Hamid's account without being asked. |
| **Google Calendar** | The cadence, made visible. |
| **Telegram** | Live delivery from the panel: signals, outcomes, room reports. |
| **n8n** | Orchestration between the above, so the pipeline runs without a session open. |
| **Canva** | Only when something genuinely needs to be a graphic. Inventing work for a tool is not using it. |

If a connector's token has expired, say so plainly and carry on with the rest.

## What must not change

The strategy, the rooms, the supervisor, the two-hourly review with **one
controlled change per cycle** graded on the cycle after, and the rule that a
finding is only acted on once its confidence interval clears zero. Connectors
carry the work; they do not decide anything.

## How results are reported

Every number comes from a measurement that can be re-run. `tests/` holds the
simulator, harness, cycle runner, parameter search, gate funnel and age split.
A number without a way to reproduce it does not get reported.

State plainly whether a figure comes from simulated markets or live candles.
The simulator has volatility clustering, fat tails and regime switching, and it
tests whether the engine has an edge against a hard model — not whether it
makes money on the real tape.

That distinction turned out to matter more than it sounded. Measured on
30 July 2026, the simulator said 45% win and +0.283R where 3,931 trades on real
candles said 22.7% and +0.069R. So a simulator number is never a performance
claim. It is only ever "this rule moved expectancy by X against the same
simulator". Performance claims come from `python/backtest.py`, on real klines.

## Corrections

When a previous conclusion turns out to be wrong, say so directly and show the
measurement that overturned it. Two have already been corrected this way: a
freshness window widened on the strength of a friendly tape, and a claim that
the second pullback carried no advantage.

## Repository layout

- `index.html` — the panel. One file, no build step.
- `sw.js` — service worker. Bump `CACHE` on every deploy.
- `tests/` — simulator, harness, and every measurement script.
- `claude-liam-signal/` — reference material, work plan, cycle reports.
- `claude-liam-signal/agent/` — the standalone Node agent. `engine.js` is
  generated from `index.html`; rerun `extract-engine.js` after engine changes.
- `claude-liam-signal/n8n/` — importable orchestration workflows.

Deploys go to both `claude/hamid-signal-agent-smc-dkot7v` and `gh-pages`.

## LIAM — ارکستراتور و زیرایجنت‌ها

قانون اساسی: `claude-liam-signal/LIAM-CHARTER.md` (verbatim — تغییر فقط با
دستور صریح حمید) · نگاشت وضعیت: `LIAM-STATUS.md` · قوانین عملیاتی:
`.claude/rules/trading-core.md` و `.claude/rules/ibs-pullback-plus.md`.

**ایجنت اصلی ارکستراتور است، نه همه‌کاره.** در هر رویداد مهم بپرس: چه
عوض شد؟ چرا مهم است؟ کدام فرضیه اثر می‌گیرد؟ چه اطلاعاتی کم است؟ کدام
متخصص سریع‌تر جوابش را دارد؟ ستاپ فعالی باطل می‌شود؟ فرصت تازه‌ای ساخته
می‌شود؟ تحقیق لازم است؟ چه چیزی باید به خاطر سپرده شود؟ — بعد به
زیرایجنت مناسب در `.claude/agents/` واگذار کن؛ هر ایجنت را فقط وقتی صدا
بزن که رویداد لازمش کرده، نه مکانیکی در هر چرخه:

| رویداد | زیرایجنت |
|---|---|
| «قیمت کجاست؟» / اعتبار ستاپ | market-structure |
| قبل از سیگنال اصلی، ویک بزرگ | liquidity |
| حرکت ناگهانی BTC، سیگنال پراطمینان | macro-dominance |
| پامپ/دامپ معنادار، همبستگی غیرمنتظره | lead-lag |
| تسویه، استاپ، شکست تکرارشونده | post-trade-learning |
| ۳+ شکستِ همان الگو، رفتار بی‌توضیح | research (فقط پرسش-محور) |
| تأیید لحظهٔ ورود | execution |
| اعتبار اردر بلاک قبل از ستاپ، استاپ روی سطح، بازپایش OBها، رویداد OB_APPROACHING/BREAKER_DETECTED از `signals/ob-radar.json` | order-block |
| دادهٔ مشکوک/ناسازگار | data-quality |

**قانون پیش‌فرض هر انجین/ایجنت جدید (دستور حمید، ۱۳ اوت)**: یادگیری
دائمی از روز اول فعال است — خروجی‌هایش روی پروندهٔ معامله ثبت می‌شود،
ماشین بونفرونی شبانه سهمش را از نتیجه می‌سنجد، و درس‌هایش با memory به
حافظهٔ دائمی می‌رود. انجینی که ردپای قابل‌سنجش نگذارد، ناقص تحویل شده.

**حافظه**: قبل از تحلیل مهم بخوان، بعد از نتیجهٔ معنادار بنویس — فقط دانش
قابل‌استفادهٔ مجدد (`brain/memory/README.md`؛ چهار لایهٔ جدا: قوانین هسته
/ یادگیری تجربی / فرضیهٔ آزمایشی / تحقیق). پرونده‌های معامله در
`brain/cases/` (فایل یکتا، append-only). تحقیق در `brain/research/`
(ایزوله از تولید؛ چرخهٔ اجباری در README همان پوشه).

**ایمنی وضعیت مشترک**: دو ورک‌فلو هم‌زمان روی یک فایل ننویسند — الگوهای
موجود: reapply ضدتصادم، فایل یکتای case، اجتماع (union) برای لاگ/درس/
تاریخچه، concurrency group در ورک‌فلوها. وضعیت تولیدشدهٔ runtime
(signals/, brain/) از دانش سورس‌کنترل‌شده (rules/, python/) جداست.

## بستهٔ مهارت‌های v2.1 (نصب ۱۴ اوت — سند حمید)

بستهٔ `AuraLiam369_Claude_Fable5_Skills_Package_v2_1` در ریشه نصب شده است.
اسناد مرجعش: `AuraLiam369_Trading_Agent_Master_Spec_FA_v2.1.md` ·
`.claude/rules/00..06-*.md` · `config/engine_registry.yaml` · `docs/*_FA.md`.
پرامپت اجرا: `prompts/CLAUDE_FABLE5_APPLY_NOW_FA.txt` (مرحله ۰ = فقط Audit).

- **مرز معماری**: کلود کد سازنده/ممیز است، نه اسکنر ۲۴/۷. حلقهٔ زندهٔ
  هدفِ v2.1 با سرویس Python اجرا می‌شود؛ GitHub Actions به CI/بک‌فیل/گزارش
  برمی‌گردد. تا وقتی آن سرویس مستقر نشده، چرخهٔ فعلی Actions همان مرجع
  عملیاتی است — هیچ‌چیزِ کارکرده قبل از جایگزینِ اثبات‌شده خاموش نمی‌شود.
- **دو خانوادهٔ زیرایجنت**: ۹ ایجنت دامنهٔ رویدادمحور بالا (عملیاتی) سر
  جایشان‌اند؛ ۲۶ ایجنت `e00..e25` متخصص read-only ممیزی/ساخت‌اند که
  فقط `ENGINE_REVIEW_PACKET` برمی‌گردانند و هیچ فایل مشترکی را ویرایش
  نمی‌کنند — نوشتن فقط با ایجنت اصلی (سریالی).
- **قوانین جدید ۰۰–۰۶ مکمل `trading-core.md`اند نه جایگزین**؛ اگر جایی
  اختلاف بود، منشور LIAM و دستور صریح حمید حاکم است.
- **LIVE_EXECUTION=false** می‌ماند؛ فقط Backtest/Replay/Paper/Live-Signal.
- بعد از هر تغییر: `python scripts/validate_skill_package.py` (هوک Stop
  هم خودش اجرایش می‌کند).

## قانون خواندن پیش از پاسخ (دستور حمید، ۱۶ اوت)

قبل از هر پاسخ یا شروع هر کار، اول گفتگوهای قبلی خوانده می‌شود — از جمله
دو صفحهٔ چتِ پین‌شده و نتیجه‌گیری‌های انتهای هر بحث. جواب باید بر پایهٔ
آخرین نتیجه‌گیری باشد، نه حافظهٔ مبهم از وسط بحث. تکرار حرف قبلاً
گفته‌شده، پرسیدن چیزی که قبلاً جواب داده شده، یا قاطی کردن دو موضوع =
نشانهٔ نخواندن، و نقض همین قانون. اگر چیزی در چت با وضعیت فعلی کد
نمی‌خواند، اول همان اختلاف گزارش می‌شود.

## هویت مخزن — تک‌پنل (دستور حمید، ۱۷ اوت؛ جایگزین بند هویت ۱۶ اوت)

- حمید: «تنها پنلی هستی که من در گیت‌هاب auraliam18 دارم» — پنل دیگر
  (لیام تریدر ۹ / چت دیگر) به **مخزن جدای خودش** رفت. جدایی دو پنل حالا
  با جدایی مخزن‌هاست، نه با دو برند داخل یک مخزن.
- نام پنل و **برند همهٔ سیگنال‌های ارسالی این مخزن: «aura liam mAx»**
  (`telegram.PANEL_NAME` تنها منبع است — سرِ پیام `telegram.BRAND`،
  پیشوند شناسه `telegram.PANEL_CODE` = `ALM`). تغییر برند فقط از همان‌جا.
- تاریخچهٔ بند قبلی برای سابقه: ۱۶ اوت که هر دو پنل در یک مخزن بودند،
  برند این فایل «لیام تریدر ۹» بود و پنل aura با env جدا می‌شد.
- کتابخانهٔ دائمی ایجنت‌ها: `brain/library/` — ورود مطلب فقط پس از
  راستی‌آزمایی (اسکیمای README همان پوشه)؛ حلقهٔ شبانه از قفسه می‌خواند
  و برداشت هر انجین در `brain/research/` ثبت می‌شود.

## آستانهٔ پول واقعی — بیت‌یونیکس (دستور حمید، ۱۶ اوت)

**LIVE_EXECUTION همچنان false** — فعال‌سازی فقط با تأیید صریح و جداگانهٔ
حمید، و فقط بعد از برآورده شدن پیش‌نیازهای زیر (از کتابخانهٔ درس‌های
ربات‌تریدری، `brain/library/`، همه VERIFIED):

1. **دروازهٔ کارمزد پیش از هر پوزیشن** — `hamid/fees.py`: RR باید خالص از
   کارمزد+لغزش از حد بگذرد. اعداد راستی‌آزمایی‌شده (۱۶ اوت): Bitunix
   فیوچرز VIP0 میکر ۰.۰۲٪ / تیکر ۰.۰۶٪؛ تیکر دو سر + لغزش = ~۰.۱۵٪ —
   منطبق با قانون تریل. میکر بودن مزیت است؛ استاپ تنگ سهم کارمزد از R را
   چند برابر می‌کند (دام اسکالپ).
2. **ارزهای صفر-کارمزد**: لیست فقط از منبع رسمی صرافی (وضعیت فعلی:
   UNVERIFIED در `config/fees.json`)؛ بعد از تأیید، اولویت تحلیل با
   آن‌هاست. ارزهای وابسته به ساعت بازار امریکا جدا مدیریت می‌شوند.
3. **کیل‌سوییچ چندماشه** قبل از لایو: سقف ضرر تجمعی + نرخ غیرعادی سفارش +
   انحراف قیمت + dead-man's switch؛ فعال‌شدن = لغو سفارش‌ها، بستن
   پوزیشن‌ها، آلارم ثانیه‌ای.
4. **سقف سخت سایز**: استراتژی حق تعیین سایز بی‌سقف ندارد؛ ۱–۵٪ بر ترید،
   سقف اکسپوژر کل، سایز معکوس نوسان.
5. **گذار مرحله‌ای**: عدد پیپر سقف خوش‌بینانه است (فیل کامل/بی‌لغزش)؛
   لایو فقط بعد از دورهٔ پایدار پیپر با همین دروازه‌ها.
6. **Reconciliation**: در فاز لایو، پوزیشن‌های واقعی صرافی دوره‌ای با
   دفترها تطبیق داده می‌شوند؛ بی‌خبری = رفتار امن، نه فرضِ فیل.

## امضای پنل روی هر پیام (دستور حمید، ۱۶ اوت)

دو پنل جدا (لیام تریدر ۹ / AuraLiam Max) = دو استراتژی جدا. هر پیام
تلگرام — سیگنال، رسید، آلارم — باید امضای پنل فرستنده را داشته باشد تا
حمید بداند از کدام پنل آمده. این‌جا: `telegram.PANEL_NAME` («لیام تریدر
۹»). رسید TradingView برند را از فیلد `panel` خود آلارم می‌گیرد؛ آلارم
بی‌امضا صریح «بدون امضای پنل» می‌خورد — امضا حدس زده نمی‌شود. در JSON
آلارم‌های TradingView این پنل همیشه `"panel":"لیام تریدر ۹"` بگذار.

## قانون رفع قطعی (دستور حمید، ۱۷ اوت)

حمید گزارش «یک مشکل پیدا شد» نمی‌خواهد؛ سیستمِ درست‌کار می‌خواهد.
از این پس:

1. هیچ مشکلی «گزارش» نمی‌شود مگر همراه با: رفعِ ریشه‌ای + محافظ دائمی
   (تست/پاسبان) که برگشتش را ناممکن کند + اثبات اجراشده. مشکلِ بسته فقط
   یک خط در گزارش است، نه تیتر.
2. مشکل تکراری از یک کلاس = شکست محافظ قبلی؛ اول محافظ تعمیر می‌شود.
3. کد جدید بدون تستِ همراه تحویل نمی‌شود — عیبِ کدِ تازه باید در همان
   نشستِ ساختنش بمیرد، نه در بازرسی بعدی.
4. گزارش‌ها با «چه چیزی کار می‌کند و چه اعدادی داد» شروع می‌شوند؛
   خرابی‌های بسته‌شده در انتها، یک‌خطی.

## دروازهٔ روند در گلوگاه ارسال (دستور حمید، ۱۷ اوت)

مشاهدهٔ حمید: «چارت کاملاً صعودی ولی سیگنال شورت صادر شده و برعکس.»
از این پس در گلوگاه ارسال (telegram.send_signals) و شلیک دفتر انتظار:

- **هر دو تایم بالا (۴س و ۱س) خلاف جهت سیگنال → وتوی مطلق.** هیچ امتیاز
  و استثنایی عبور نمی‌دهد (اجرای سختِ قانون ۲).
- **یک تایم بالا خلاف → «خلاف روند»**: فقط با تمام تأییدیه‌ها می‌گذرد
  (inOB + سوییپ + CHoCH + FVG + کیفیت ≥۷۰) و پیام برچسب «⚠️ خلاف روند»
  با فهرست تأییدیه‌ها می‌گیرد؛ یک غایب = NO_SIGNAL.
- دادهٔ روند ناموجود = NO_SIGNAL (قانون ۱)، نه عبور کور.
- فرستنده trend4/trend1 را روی لاگ می‌نویسد؛ پاسبان C6 هر ارسالِ
  دورزننده را تخلف high می‌گیرد.
- پیاده‌سازی: hamid/trend_gate.py · محافظ: test_trend_gate (۷ آزمون) +
  C6 پاسبان.
