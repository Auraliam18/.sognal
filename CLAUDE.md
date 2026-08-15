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

## پیش از هر کار — بازرسی اجباری (دستور حمید، ۱۵ اوت)

این بند بعد از یک شکست واقعی نوشته شد: در یک جلسه، موتور IBS از صفر
بازنویسی شد در حالی که `index.html` v21.29 و بستهٔ
`claude-liam-signal/python/hamid/` (۶۶ ماژول) همان کار را کامل‌تر
انجام می‌دادند، و `.claude/rules/ibs-pullback-plus.md` از قبل استراتژی
را مکتوب کرده بود. علت: هیچ‌کدام خوانده نشده بودند. کپی محلی روی یک
برنچ کهنه بود و همان جلوی چشم فرض شد که «همهٔ سیستم» است.

**قبل از نوشتن حتی یک خط کد:**

1. `git fetch origin --prune` — کپی محلی همیشه مشکوک است. برنچ پیش‌فرض
   (`main`) مرجع است، نه برنچ کاری.
2. این‌ها را بخوان: `CLAUDE.md` · `00_READ_ME_FIRST_FA.md` ·
   `.claude/rules/` · `claude-liam-signal/LIAM-CHARTER.md`.
3. بگرد ببین همین قابلیت از قبل هست:
   `git grep -i "<اسم قابلیت>" origin/main` روی `python/hamid/` و
   `index.html`. اگر هست، همان را گسترش بده — نسخهٔ موازی نساز.
4. هر برنچ را جدا نگاه کن. دو برنچ می‌توانند دو دنیای متفاوت باشند.

**قبل از هر کار برگشت‌ناپذیر — بکاپ، بدون استثنا:**

برنچ بکاپ بساز و روی remote پوش کن (کانتینر موقتی است، بکاپ محلی بکاپ
نیست): `git branch backup/<ref>-$(date -u +%Y%m%d-%H%M%S) <ref>` سپس
`git push -u origin <آن برنچ>`. مصداق «برگشت‌ناپذیر»: بازنویسی فایل،
force-push، merge با تعارض، حذف، تغییر برنچ منتشرشده.

**تعارض = توقف، نه انتخاب.** اگر دو نسخه از یک فایل وجود دارد، هیچ‌کدام
دور انداخته نمی‌شود. هر دو نگه داشته می‌شوند و تصمیم با حمید است. قبل از
بازنویسی، دو طرف را با عدد مقایسه کن (خط، تاریخ کامیت، قابلیت‌ها) — نه
با حدس. «جلوی دستم بود» دلیل نیست.

**هشدار پیش از خطا، نه گزارش پس از آن.** اگر دستور حمید به چیزی منجر
می‌شود که کار موجود را خراب می‌کند یا با قوانین بالا تناقض دارد، همان
لحظه گفته می‌شود — قبل از اجرا. «نزدیک بود گند بزنم» بعد از کار،
شکست است نه شفافیت.

**کد جدید علیه قوانین ممیزی می‌شود، نه علیه حافظهٔ من.** پیاده‌سازی هر
استراتژی قبل از تحویل با `.claude/rules/` تطبیق داده می‌شود. کدی که
قانون سخت را نقض کند (مثل ورود روی پولبک ۱) تحویل نمی‌شود؛ اگر منتشر
شده، سیگنال ورودش فوراً غیرفعال می‌شود.

**یادگیری دائمی پیش‌فرض است.** هر انجین/ایجنت جدید از روز اول: ثبت روی
پروندهٔ معامله، پیپر تریدینگ، سنجش شبانه، و درس‌نویسی در حافظه. انجینی
که ردپای قابل‌سنجش نگذارد، ناقص تحویل شده.

## غیرقابل مذاکره — تحویل و لایو بودن (دستور حمید، ۱۵ اوت)

**۱. ارسال لحظه‌ای، نه دسته‌ای.** هر ارز که در حین پایش شرایط سیگنال را
پیدا کرد، همان لحظه هم به پنل و هم به تلگرام می‌رود. منتظر پایان چرخه
نمی‌ماند تا چند سیگنال با هم بروند. (وضعیت سنجیده‌شده ۱۵ اوت: مسیر
موجود همین کار را می‌کند — چرخهٔ حمید و اسکن زنده در لحظهٔ تولد سیگنال
`telegram.py` را صدا می‌زنند، ضدتکرار با `signals/sent.json`؛ میانهٔ
فاصلهٔ ارسال ۹ دقیقه، تک‌به‌تک.)

**۲. سیگنالِ حاصل از یادگیری باید علامت و توضیح داشته باشد.** اگر سیگنال
به‌خاطر تغییر استراتژی بر پایهٔ یادگیری/تجربه/مطالعه صادر شده، کنارش
علامت می‌خورد و دلیلش نوشته می‌شود — با ارجاع به شاهد. نمونهٔ خواستهٔ
حمید: «این استراتژی روی این ارز همیشه روی پولبک سوم رخ می‌داد؛ صبر کردم
بعد از پولبک سوم به اردر بلاک برسد و سیگنال کردم، چون در تغییرات قبلی
روی همین ارز نتیجهٔ خوبی گرفته بودم.» بدون این توضیح، سیگنالِ یادگیری
ناقص تحویل شده است.

**۳. هر منبع دادهٔ زنده باید جایگزین آماده داشته باشد.** اگر منبعی از کار
افتاد، بلافاصله به منبع بعدی سوییچ می‌شود و تا رفع مشکل روی همان می‌ماند،
و برگشت به منبع اصلی خودکار است. قطعی منبع = رویداد گزارش‌شدنی، نه
شکست بی‌صدا.

**۴. تحلیل دوباره از منبع زنده، بلافاصله.** انجین بعد از پایش و تحلیل
همه‌جانبهٔ ارزها، فوراً از محل دادهٔ زنده دوباره تحلیل می‌کند و نتیجه را
به‌صورت دائمی به انجین بعدی می‌دهد.

**۵. مهلت رسیدن داده تعریف‌شده است.** برای هر انجین یک پنجرهٔ زمانی
مشخص تعریف می‌شود؛ اگر داده در آن پنجره نرسید یعنی مشکلی هست و همان
لحظه گزارش می‌شود.

**۶. آلارم مشترک روی همهٔ انجین‌ها.** هر وقفه در روند عادی — حتی ثانیه‌ای —
آلارم خودکار می‌دهد و عیب‌یابی خودکار شروع می‌شود.

**۷. تأیید حمید یعنی جایگزینی فوری.** هر وقت حمید دربارهٔ استراتژی، ستاپ
یا هر بهینه‌سازی صحبت کرد و بعد از تغییر نظرش مثبت بود، بلافاصله بررسی
می‌شود که نسخهٔ قبلی جایگزین شود — نه اینکه کنار هم بمانند.
