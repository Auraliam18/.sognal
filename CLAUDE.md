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
| اعتبار اردر بلاک قبل از ستاپ، استاپ روی سطح، بازپایش OBها | order-block |
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
