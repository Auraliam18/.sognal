# ورک‌فلو حرفه‌ای پایش Top-200 و ارسال فوری

## اصل اصلاحی

چرخه‌ی ۵ دقیقه‌ای حذف می‌شود. بازار از WebSocket پیوسته دریافت می‌شود و هر ۳۰ ثانیه فقط بررسی می‌کنیم هیچ Symbol یا Worker از پوشش خارج نشده است.

## مدل اجرا

```text
Continuous WebSocket
  → per-symbol actor/mailbox
  → incremental feature updates
  → parallel deterministic engines
  → candidate state
  → only missing expensive evidence
  → Risk + Signal Committee
  → SIGNAL_READY
  → chart renderer + transactional outbox
  → Telegram immediately
```

هیچ `await all_symbols_finished()` در مسیر Signal وجود ندارد.

## تقسیم بار

### Tier 0 — 200 ارز
Ticker/1m/returns/volume/volatility/freshness. 4H/1H cached.

### Tier 1 — 40 تا 60 ارز
نزدیک سطح، volume spike، pump/lead-lag، catalyst، strategy proximity؛ 15M/5M، trade/depth سبک.

### Tier 2 — 10 تا 20 ارز
تحلیل کامل، CoinGlass، analog، risk simulation و chart-ready state.

## محاسبه‌ی Incremental

- RSI/MACD/MFI/ATR با state قبلی update می‌شوند.
- Trendline/SR/OB HTF فقط با candle close یا pivot/zone event update می‌شوند.
- فاصله تا خطوط و zoneها با آخرین قیمت update می‌شود.
- Backfill فقط برای gap؛ نه هر sweep.

## Concurrency بدون تداخل

- Symbol partition و lock per symbol.
- Single writer per state domain.
- NATS/Redis Streams برای event؛ PostgreSQL transaction برای truth؛ Redis فقط hot state/lock.
- Idempotency key و event sequence.
- Dead-letter queue برای packet ناقص/failed.

## اولویت و Preemption

`SIGNAL_READY > APPROACHING > PUMP/CATALYST > Tier1 > Tier0 > REPLAY/RESEARCH`.

Replay/Research هنگام فشار Live متوقف و بعد Resume می‌شود.

## معیار پذیرش

- تمام ۲۰۰ نماد در هر heartbeat دارای `last_seen` و `last_analyzed` باشند.
- هیچ سیگنال بیش از زمان SLO در Candidate نماند.
- تست اثبات کند Symbol اول قبل از پایان تحلیل Symbol دویستم ارسال می‌شود.
- Batch Telegram path حذف یا فقط برای گزارش دوره‌ای استفاده شود؛ نه Signal.
