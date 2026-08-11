# AuraLiam369 — Gap Matrix (Phase 0 Audit، ۱۲ اوت ۲۰۲۶)

سند مرجع: دو فایل آپلودی حمید. وضعیت: ✅ هست · 🟡 نصفه · ❌ نیست ·
⛔ با زیرساخت فعلی ناممکن (نیازمند سرور دائمی).

## حقیقت زیرساختی که سند باید با آن روبه‌رو شود
Runtime فعلی: GitHub Actions (رایگان) + gh-pages + آینهٔ Supabase.
**هیچ سرور دائمی‌ای وجود ندارد.** Postgres/TimescaleDB، Redis، NATS،
ClickHouse، FastAPI ماندگار، WebSocket دائمی و LangGraph همگی «پردازهٔ
همیشه-روشن» می‌خواهند — روی Actions نمی‌ایستند (سقف job، شبکهٔ ناپایدار،
بدون دیسک ماندگار). خود سند هم می‌گوید «GitHub Actions رانتایم لحظه‌ای
بازار نیست» (§قوانین-۷) — درست است، ولی جایگزینش سرور است که نداریم.
حمید هم دستور دائمی داده: اتکا به لپ‌تاپ ممنوع. نتیجه: بخش‌های ⛔ فقط
با اجارهٔ یک VPS/سرویس ابری فعال می‌شوند — تصمیمش با حمید.

## نگاشت بخش‌های اصلی
| § | موضوع | وضعیت | جزئیات |
|---|---|---|---|
| 1 | حالت‌های رسمی | 🟡 | BACKTEST/PAPER/LIVE_SIGNAL داریم؛ REPLAY تاریخی و SHADOW_LIVE ❌؛ LIVE_EXECUTION عمداً خاموش ✅ |
| 2 | ۲۰ قانون غیرقابل‌مذاکره | 🟡 | ۱۴ مورد برقرار (dedup/outbox-مانند SENT، no-fabrication، NO_TRADE، snapshot ctx، دلیل ردها، secrets)؛ نقض‌ها: state تولیدی در گیت commit می‌شود (قانون ۶ — در معماری فعلی اجتناب‌ناپذیر، چون گیت تنها دیسک ماندگار ماست)، Event Bus/DB نداریم (قانون ۵) |
| 3 | تفکیک انجین/ایجنت | ✅ | محاسبات همه پایتون قطعی؛ LLM فقط در جلسه‌ها |
| 4 | پشتهٔ فنی (Timescale/NATS/Redis/ClickHouse/LangGraph) | ⛔ | سرور نداریم؛ معادل‌های فعلی: گیت=DB ماندگار، فایل یکتا=lock، SENT=dedup |
| 5 | پایش ۲۰۰ ارز سه‌سطحی | 🟡→ | امروز Top-100 چرخان؛ **Phase 1 همین کامیت: UniverseSnapshot روزانهٔ Top-200 با فیلتر استیبل/رپد + ثبت لیست/دی‌لیست** (universe.py)؛ Tier-1/2 داده‌های عمقی (orderbook/OI دقیق) ❌ |
| 6 | Registry ۲۶ انجین | 🟡 | ~۱۶ معادل واقعی داریم (نگاشت در MIGRATION-PLAN)؛ Committee/Supervisor دوگانه 🟡 (premortem+veto+medic نقش‌ها را پوشش می‌دهد ولی تفکیک رسمی نیست) |
| 7 | فرآیند مرجع USDT.D/BTC.D/BTC/Alt | 🟡 | Alt کامل؛ BTC کامل؛ USDT.D فقط دلتا+رویداد (ساختار ۴س/۱س خودش ❌)؛ BTC.D فقط سری+دلتا |
| 8 | Lifecycle خطوط/S/R/FVG/OB | ❌ | مهم‌ترین شکاف قابل‌اجرا؛ الان سطح‌ها stateless محاسبه می‌شوند |
| 9 | Strategy Registry | ✅ | strategies/registry.yaml همین کامیت — از کد واقعی، S1/S2/LiamS صادقانه NOT_IN_CODE |
| 10 | Lead-Lag با Lift/Baseline | 🟡 | lagcorr (r با تأخیر، ضدمعکوس) + follower_lags + دفتر ماندگار داریم؛ Lift/Baseline/FDR و کنترل بتای BTC در نسخهٔ event-study ❌ |
| 11 | Historical Analog | 🟡 | best_match و react_similarity (شباهت چارت) داریم؛ Analog چندبعدی با Feature کامل ❌ |
| 12 | ۶ لایهٔ حافظه | 🟡 | معادل‌ها: raw=کش کندل+گیت، feature=signals/*.json، episodic=cases/closed.jsonl، private≈اتاق‌ها، canonical=lessons+history-stats با قانون CI (همان Curator)، catalyst=تقویم intel؛ تفکیک رسمی‌تر ممکن |
| 13 | State Machine ۱۱حالته + Failure Taxonomy | 🟡 | معادل‌های پراکنده؛ برچسب یکپارچه و taxonomy رسمی ❌ (در STATUS هم اولویت ۱ بود) |
| 14 | Paper/Replay/Backtest | 🟡 | Paper دائمی ✅، backtest واقعی ✅ (fee/slippage/no-lookahead تست‌شده)؛ Walk-forward و Replay تاریخی ❌ |
| 15 | Risk با Veto | 🟡 | veto تجربه + premortem + سقف‌ها ✅؛ Exposure/Correlation-cluster و Stop=Invalidation+HuntBuffer فرمول‌بندی ❌؛ **Trailing ساختاری**: نردبان ⅓/⅔ حمید پیاده است (دستور صریح خودش)؛ trail-پشت-BOS آینده |
| 16 | News/Catalyst چندمنبعه | 🟡 | شکار خبر+TV+تقویم+دسته‌بندی ✅؛ Ainvest/X رسمی/unlock-calendar ❌ |
| 17-18 | Workflow مرجع + Packetها | 🟡 | جریان واقعی همین است (دیاگرام≈جریان ما)؛ Packetهای رسمی JSON schema ❌ |
| 19 | پنل ۱۹ تب + Contract Agent | 🟡 | ۱۳ تب زنده + دیده‌بان (freshness/health) ≈ Contract سبک؛ تب‌های USDT.D/BTC.D/Analog جدا ❌ |
| 20 | SLO/WebSocket sharding | ⛔ | بدون سرور، وب‌سوکت دائمی ممکن نیست؛ SLO فعلی: کادنس ۵د زنجیره‌ای اندازه‌گیری‌شده |
| 21 | ضد Race | ✅ | تک‌نویسندهٔ منطقی + فایل یکتا + union + concurrency group + reapply — مستند در CLAUDE.md |
| 22 | بیکار نبودن ایجنت‌ها | ✅ | کرون‌های بک‌تست/سرچ/مدیک/گزارش شبانه همین‌اند |
| 23 | تست‌ها | 🟡 | ~۹۰ آزمون آفلاین + CI هر اجرا ✅؛ Golden Fixtures تأییدشدهٔ حمید و Chaos ❌ |
| 24 | Phaseها | ✅ | این سند = Phase 0 تمام؛ Phase 1 شروع شد (Universe) |
| 25 | پرامپت مادر | ✅ | در claude-liam-signal/auraliam369/ نگهداری می‌شود؛ با منشور LIAM هم‌خانواده است (تعارضی ندیدم — LIAM رفتار تحلیلی، این سند معماری اجرایی) |

## سه نقض/ریسک مهم که سند درست می‌گوید و ما داریم
1. state تولیدی در گیت (قانون ۶) — بدون سرور چاره نداریم؛ ریسکش با
   anti-collision مهار شده ولی حجم ریپو رشد می‌کند.
2. آمار paper چند دفتر دارد ولی در یک فایل equity است — namespace
   جداتر بهتر است (قانون ۱۳ سند).
3. Universe تا امروز snapshot روزانهٔ آرشیوی نداشت (§5) — از همین
   کامیت دارد.
