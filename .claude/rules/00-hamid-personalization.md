# شخصی‌سازی قطعی پروژه برای حمید

این فایل مشخصات پایدار روش کار و ترجیحات حمید را برای تمام نشست‌ها، ایجنت‌ها و تغییرات پروژه ثبت می‌کند.

## هویت پروژه

- نام مالک محصول: **حمید**
- نام سیستم: **AuraLiam369 / LIAM Trading Intelligence OS**
- برند تصویر و کانال: **Trade_osuli**
- زبان گزارش به کاربر: فارسی، مستقیم، کوتاه و شفاف؛ اصطلاح تازه با یک توضیح یک‌خطی.
- نقش Claude Code/Fable 5: سازنده، پژوهشگر، ممیز و نگهدارنده‌ی سیستم؛ نه حلقه‌ی ۲۴ساعته‌ی بازار.
- حلقه‌ی زنده‌ی بازار: سرویس‌های محلی و پایدار Python.

## ترتیب غیرقابل حذف تحلیل

1. USDT.D مستقل
2. BTC.D و Macro/TOTAL/TOTAL2/TOTAL3/OTHERS/ETH.D در صورت نیاز
3. BTC کامل
4. ارز هدف: 4H → 1H → 15M → 5M
5. Liquidity/Derivatives
6. Strategy Registry
7. Historical Analog + سابقه‌ی همان ارز
8. Lead-Lag/Pump Chain در صورت وجود رویداد
9. Risk
10. Signal Committee
11. Snapshot/Telegram
12. Post-Trade + Memory

## روش ترسیم و ساختار

- در 4H و 1H حداقل ۲۰۰ کندل بررسی شود.
- Pivotها، سقف/کف‌ها، حمایت/مقاومت‌ها، Trendline و Channel با واکنش‌های معتبر استخراج شوند.
- خط معتبر حذف نمی‌شود؛ وضعیت آن به ACTIVE/BROKEN/FLIPPED/HISTORICAL تغییر می‌کند.
- ترجیح حمید خطی است که دست‌کم سه واکنش معتبر داشته باشد؛ استثنا فقط در Strategy نسخه‌دار.
- برخورد Wick و پذیرش Body جدا ثبت شود.
- 4H جهت و محدوده‌ی راهبردی؛ 1H ساختار عملیاتی؛ 15M ستاپ؛ 5M تریگر ورود.
- یک CHoCH داخلی در پولبک به‌تنهایی تغییر روند نیست.

## SMC و نقدینگی

- Order Block فقط «آخرین کندل مخالف» نیست؛ باید Displacement، BOS/MSS، موقعیت HTF، FVG/Liquidity و Freshness بررسی شود.
- FVG/OB مصرف‌شده، تضعیف‌شده یا Invalid نباید Fresh نمایش داده شود.
- قیمت ممکن است ساعت‌ها بین دو OB مخالف بچرخد و چند پولبک فریبنده بسازد؛ در این حالت NO_TRADE_ROTATION معتبر است.
- حجم برای حمید مهم‌ترین تأیید است.
- CoinGlass/Order Book/OI/Funding/Liquidation به‌عنوان لایه‌ی نقدینگی بررسی می‌شود، نه تریگر مستقل.

## اندیکاتورهای شخصی‌سازی‌شده از «ورژن دو»

- RSI: واگرایی معمولی و مخفی؛ در روند با ساختار و سطح.
- ADX: زیر 20 رنج/ضعیف، 20–40 قابل معامله، 40–60 قوی، بالاتر از 60 بسیار قوی؛ جهت را تعیین نمی‌کند.
- Stochastic: در بازار رنج اولویت بیشتری از RSI دارد.
- CPR: محدوده‌ی ماهانه روی تایم روزانه، نسخه‌دار و تست‌شده.
- EMA/SMA: شکست و Ribbon در چرخش/روند، نه سیگنال تنها.
- Bollinger Bands: استفاده‌ی محدود؛ خروج کندل در S/R یا BB روی RSI فقط یک تیک اولیه.
- Alligator: در موج/روند برای Overextension، نه تریگر تنها.
- Ichimoku + Fibonacci: زمان/موقعیت چرخش، کراس و Kumo در ساختار HTF.
- MACD: کراس/هیستوگرام/واگرایی؛ قانون «MACD 30M + عبور RSI 15M از Midline» در Registry نسخه‌دار.
- Gaussian Channel و Bull Market Support Band: فقط در هفتگی برای تأیید چرخش/روند.
- MFI، IBS، ATR، VWAP و DMI طبق Strategy استفاده می‌شوند.

## استراتژی‌ها

- S1
- S2
- Liam S
- IBS + Pullback Plus
- ONE-IDM Wick 15
- هر Strategy باید ID، Version، Hard Gates، Entry، Invalidation، SL، TP، RR، Allowed/Forbidden Regime و Golden Fixtures داشته باشد.
- حمید عمدتاً Pullback Trader در جهت روند است؛ معامله‌ی خلاف روند فقط با نقض معتبر و Strategy مستقل تست‌شده.

## Universe و صرافی

- Top-200 جهانی برای Research، Lead-Lag، Catalyst و Historical Study.
- سیگنال اجرایی فقط برای نمادی که در صرافی هدف—در وضعیت فعلی Bitunix—واقعاً قابل معامله و دارای نقدشوندگی کافی است.
- Stablecoin، Wrapped duplicate و Symbol ambiguity باید جدا مدیریت شوند.

## خروجی سیگنال

- هر نماد به‌محض کامل‌شدن شروط خودش ارسال شود؛ پایان چرخه‌ی ۳۰ثانیه‌ای یا جمع‌شدن سیگنال‌های دیگر انتظار ایجاد نمی‌کند.
- تصویر چارت: خطوط/کانال معتبر، S/R، OB/FVG، Entry/SL/TP، مسیر سناریویی و Watermark کم‌رنگ Trade_osuli.
- هر Signal یک شناسه‌ی انسانی و یکتا دارد.
- نتیجه‌ی همان Signal باید در Telegram به پیام اصلی Reply شود.
- گزارش فارسی شامل جهت، Entry، SL، TP، RR، Strategy Version، دلیل، invalidation، BTC/USDT.D، حجم/نقدینگی و هشدارهای ضروری است.

## یادگیری

- هر Paper و Live Signal یک Snapshot تغییرناپذیر پیش از ورود دارد.
- Review در زمان نتیجه، سپس 1h/6h/24h انجام می‌شود.
- یک معامله فقط Episode می‌سازد؛ Lesson مشترک بعد از تکرار، شواهد و آزمایش ارتقا می‌گیرد.
- آموخته‌ها با Symbol/Timeframe/Regime/Strategy Version ذخیره می‌شوند.
- هیچ ایجنتی بدون Memory Curator و مسیر Validation منطق Production را تغییر نمی‌دهد.

## مدیریت ریسک و اختیار نهایی

- LIVE_EXECUTION در این نسخه خاموش است؛ سیستم Paper، Replay، Shadow و Live Signal تولید می‌کند.
- Leverage بالاتر از 15x بدون تأیید صریح حمید مجاز نیست.
- تصمیم نهایی معامله با حمید است.
- Secret/API Token در Frontend، Prompt، Git یا Log قرار نمی‌گیرد.
