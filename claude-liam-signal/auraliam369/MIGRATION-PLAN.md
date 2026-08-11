# AuraLiam369 — Migration Plan مرحله‌ای (بدون Big-bang، طبق خود سند)

قید حاکم: انجین تلگرام دست نمی‌خورد (دستور صریح حمید) و هیچ Phase بدون
تست وارد بعدی نمی‌شود. هر مرحله کوچک و برگشت‌پذیر؛ بک‌آپ:
شاخهٔ claude/backup-2026-08-12-pre-auraliam369.

## نگاشت Registry سند → کد موجود (که دوباره ساخته نشود)
E01=universe.py(جدید) · E02=sources+watchdog+medic · E03/E04=dominance.py(نصفه)
E06=btc در cycle+btc_move_cause · E07=structure.py · E08=engine(OB)+liquidity
E09=analyze_pump.rsi+_atr+IBS موتور · E10=liqmap+intel(OI/funding)
E11=registry.yaml+scan+cycle · E12=lagcorr+pump_radar · E13=best_match/react_similarity
E14=intel+discovery · E15=alarms · E16=گیت‌ها+veto+premortem · E17=premortem(کمیته)
E18=backtest.py+paper.py · E19=trail ladder در paper.mark · E20=stop_reason+autopsy+cases
E21=memory+قانون CI (Curator) · E22=review_cycle+open-questions · E23=medic+watchdog
E24=دیده‌بان پنل · E25=telegram.py (SENT=dedup؛ دست نمی‌خورد)

## Phase 1 — Data Foundation (شروع‌شده)
- [x] UniverseSnapshot روزانهٔ Top-200: فیلتر استیبل/رپد، ثبت venue،
      دیف لیست/دی‌لیست، فایل یکتای روزانه (ضد survivorship bias) — hamid/universe.py
- [ ] freshness_ms در خروجی‌های اصلی (سبک؛ چرخهٔ بعد)
- [ ] namespace جداتر آمار paper (equity per-book جدا از headline)

## Phase 2 — Macro (USDT.D/BTC.D ساختاری)
ساختار ۴س/۱س خود USDT.D و BTC.D با همان structure.py روی سری خودساخته؛
خروجی BULLISH/BEARISH/RANGE/TRANSITION/UNSAFE. (اولویت بعد از Phase 1)

## Phase 3 — Lifecycle سطوح (§8)
جدول خطوط/S/R/FVG/OB با status (ACTIVE/BROKEN/FLIPPED/MITIGATED/…)
در brain/levels/ فایل-به-ارز؛ بدون حذف فیزیکی. بزرگ‌ترین ارزش تحلیلی.

## Phase 4 — State Machine یکپارچه + Failure Taxonomy (§13)
برچسب ۱۱حالته روی آلارم/ستاپ + taxonomy روی کالبدشکافی موجود.

## Phase 5 — Lead-Lag آماری کامل (§10)
Lift/Baseline/FDR + کنترل بتای BTC روی دفتر pump-history موجود.

## Phase 6 — Walk-forward + Replay (§14)
روی backtest.py موجود؛ split زمانی purged.

## ⛔ نیازمند تصمیم حمید (سرور)
Timescale/Redis/NATS/LangGraph/FastAPI/WebSocket دائمی/SLO ثانیه‌ای —
بدون یک سرور همیشه-روشن ممکن نیست (لپ‌تاپ طبق دستور قبلی حذف است).
گزینه: VPS ارزان (~۵$/ماه) یا ماندن روی معماری فعلی با کادنس ۵ دقیقه.
تا آن تصمیم، معادل‌های فعلی رسماً «کافی و اندازه‌گیری‌شده» اعلام می‌شوند.
