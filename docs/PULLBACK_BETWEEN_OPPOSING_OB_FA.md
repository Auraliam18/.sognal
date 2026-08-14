# اسکیل تشخیص چرخش و پولبک فریبنده بین دو Order Block مخالف

## مسئله

قیمت می‌تواند در یک تایم‌فریم میان یک Bearish OB بالا و Bullish OB پایین بارها حرکت کند. هر حرکت داخلی ممکن است شبیه Pullback/CHoCH باشد و تریدر را قبل از حرکت اصلی وارد کند.

## قانون مهم

«معمولاً چند دقیقه/ساعت طول می‌کشد» پاسخ ثابتی ندارد. مدت باید برای هر Symbol، Timeframe، Regime، Session، Volatility و نوع OB به‌صورت آماری آموخته شود.

## State Machine

1. `ROTATION` — قیمت داخل Range دو OB پذیرفته شده است.
2. `LIQUIDITY_BUILD` — Equal highs/lows، repeated stops یا OI/liquidity در مرزها انباشته می‌شود.
3. `FAKE_PULLBACK` — micro BOS/CHoCH بدون HTF acceptance و بدون displacement کافی.
4. `ACCEPTANCE` — body close و dwell معتبر نزدیک/داخل zone.
5. `DISPLACEMENT_READY` — sweep + expansion + volume/order-flow confirmation.
6. `BREAKOUT_CONFIRMED` — close خارج Range + meaningful BOS + retest/hold یا Strategy trigger.
7. `INVALIDATED` — دو zone یا thesis اعتبار خود را از دست داده‌اند.

## Featureهای اجباری

- range_age_bars و wall_clock_duration
- touch_count و time_between_touches برای هر OB
- mitigation_depth، wick/body penetration، close location
- false_break_count و internal CHoCH count
- ATR compression/expansion و realized volatility
- volume profile/relative volume، MFI، RSI/MACD/ADX
- FVG create/fill، displacement ATR multiple
- OI/funding/liquidations/order-flow imbalance
- BTC/USDT.D direction و HTF trend
- session/time-of-day و catalyst window

## تخمین زمان حرکت اصلی

برای هر کلاس `symbol × timeframe × regime × OB-pair-type` توزیع زیر ذخیره شود:

- median و quantiles زمان تا breakout
- survival curve: احتمال باقی‌ماندن در rotation بعد از n کندل
- hazard: احتمال breakout در کندل بعد با توجه به ماندگاری فعلی
- conditional results after 1/2/3/... touches

خروجی به‌جای قطعیت:

```text
rotation_age = 19 bars
historical median = 24 bars
P(break within next 4 bars | current state) = ...
confidence = ... based on N and regime similarity
```

## مجوز حرکت اصلی

ترجیحاً ترکیب:

- liquidity sweep در یک سمت
- displacement واقعی و FVG
- meaningful BOS/MSS، نه micro noise
- volume/OFI/OI confirmation
- HTF alignment
- close/acceptance خارج range
- retest/hold یا Pullback Plus trigger

تا قبل از آن خروجی `NO_TRADE_ROTATION` یا Watch Alert است.

## چهار تصویر حمید

چهار تصویر ذکرشده در پیام فعلی ضمیمه نشده‌اند. تا زمان دریافت:

- هیچ عددی از روی آن تصاویر حدس زده نمی‌شود.
- Thresholdهای image-specific با وضعیت `UNCALIBRATED` می‌مانند.
- پس از Upload، هر تصویر با توضیح فارسی حمید به Golden Fixture تبدیل می‌شود: خطوط/OBها، fake pullbackها، حرکت اصلی، تعداد کندل و invalidation.
- تست Engine باید Annotation مرجع حمید را بازتولید کند.
