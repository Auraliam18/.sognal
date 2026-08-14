# ماتریس شکاف — سیستم یادگیری دائمی در برابر وضعیت مخزن

تاریخ: ۱۴ اوت ۲۰۲۶ · مبنا: `config/engine_learning_registry.yaml` نسخهٔ 1.0
مأموریت اول سند `prompts/CONTINUOUS_LEARNING_FA.txt`، بند A تا C.

## آنچه از قبل بود و دست نخورد

| جزء | کجا | نگاشت به سند |
|---|---|---|
| حافظهٔ تجربی ۴لایه | `brain/memory/` (lessons.json + README) | لایهٔ ۲ — جدا از canonical جدید می‌ماند |
| ایندکس یادگیری آماری | `brain/learning/` (experiences/positive/negative) | خوراک آیندهٔ E20/E21 |
| تحقیق ایزوله | `brain/research/order-block/` | الگوی اولیهٔ همین ساختار — با چرخهٔ اجباری |
| دفترهای آزمایش | `brain/paper/` (پولبک اول، inducement، تمرین) | مصداق «فرضیه در دفتر جدا» |
| قواعد منبع | `config/source_policy.yaml` (بستهٔ v2.1) | مکمل Tier ۱..۵ رجیستری |
| زمان‌بندی تحقیق | `config/research_schedule.yaml` (بستهٔ v2.1) | مکمل cadence هر انجین |
| ماشین بونفرونی شبانه | `paper.reasons()` | همان روح «Multiple-testing کنترل شود» |

## شکاف‌هایی که فاز ۱ بست

| شکاف | راه‌حل | آزمون |
|---|---|---|
| رجیستری یادگیری ۲۶ انجین نبود | `config/engine_learning_registry.yaml` (سند حمید، بدون تغییر) | لود ۲۶ انجین، ۹ پله |
| پایپ‌لاین اجباری دانش نبود | `research/claim_registry.py` — پرش ممنوع، evidence اجباری، Tier 5 فقط سرنخ | ۱۱ آزمون |
| دروازهٔ E21 نبود | `research/memory_promotion.py` — فقط E21؛ CI بدون صفر؛ کف نمونه ۳۰؛ SUPERSEDE بدون حذف | ۸ آزمون |
| مانیتور منبع نبود | `research/source_monitor.py` — هش/ETag/backoff؛ فقط تغییر واقعی → DISCOVERED | ۷ آزمون |
| حافظهٔ خصوصی هر انجین نبود | `brain/memory/private/{Exx}/` | ۱ آزمون |
| حافظهٔ مرجع نسخه‌دار نبود | `brain/memory/canonical/lessons.jsonl` (append-only) | با دروازه |
| حلقهٔ دانشِ جدا از عملیات نبود | `.github/workflows/knowledge-loop.yml` — روزانه، بدون LLM | خودآزمایی در ورک‌فلو |
| پروتکل کتاب نبود | `brain/knowledge/books/README.md` — فقط نسخهٔ قانونی حمید؛ فقط کارت دانشی | — |

## شکاف‌های باز (فازهای بعد، به ترتیب سند)

1. **G) بقیهٔ ۲۱ انجین** — ساختار research/private برای E01, E03..E17, E19,
   E20, E22, E24, E25 (الگو حاضر است؛ افزودن هر انجین چند دقیقه است).
2. **کتاب‌ها** — منتظر نسخه‌های قانونی حمید؛ تا آن موقع کتابخانه خالی
   می‌ماند و فقط Source Monitor فعال است.
3. **experiment_router** — اتصال خودکار HYPOTHESIS به `backtest.py`/دفترهای
   paper موجود (الان دستی است: ایجنت claim را می‌خواند و آزمایش ثبت می‌کند).
4. **fetcherهای تخصصی** — RSS/GitHub Release/arXiv listing به‌جای هش کل صفحه
   (هش کل صفحه برای شروع درست است ولی نویز تغییرات بی‌ربط را دارد).
5. **Shadow namespace** — دفتر SHADOW_VALIDATED هنوز مصداق اجرایی ندارد.
6. **E20 خودکار** — پیوند postmortemهای موجود (`cases.py`) به evidence_ids.

## ریسک‌ها و برگشت

- **ریسک**: هش کل صفحه ممکن است با تغییرات جزئی (تاریخ/تبلیغ) DISCOVERED
  نویزی بسازد → دفع: استخراج Claim فقط با ایجنت و quota؛ fetcher تخصصی در
  فاز بعد.
- **ریسک**: schedule فقط روی شاخهٔ پیش‌فرض کار می‌کند → تا مرج PR #46،
  حلقهٔ دانش فقط دستی اجرا می‌شود.
- **برگشت**: کل فاز ۱ افزودنی است — حذف پوشهٔ `research/` در python و
  `knowledge-loop.yml` سیستم را دقیقاً به قبل برمی‌گرداند. هیچ فایل
  تولیدی (engine/cycle/paper/telegram/panel) دست نخورده است.
