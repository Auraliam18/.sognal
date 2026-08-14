# قرارداد تصویر سیگنال و Reply نتیجه در Telegram

## Chart

- 16:9 یا 4:3 خوانا، بدون اشغال بی‌دلیل فضا.
- 4H/1H context در inset یا خطوط مرجع؛ 15M/5M execution واضح.
- فقط خطوط معتبر و zoneهای مرتبط نزدیک قیمت؛ خطوط تاریخی کم‌رنگ یا قابل toggle.
- Entry، SL، TP1/TP2/TP3، RR، invalidation و مسیر احتمالی.
- watermark `Trade_osuli` با opacity حدود 0.05–0.10، پشت داده و دور از نقاط مهم.
- Signal ID و timestamp/source freshness روی تصویر.

## Telegram database mapping

```text
signal_id
chat_id
telegram_message_id
chart_hash
sent_at
status
last_update_message_id
```

ارسال `sendPhoto` باید Message برگشتی را ذخیره کند. Result/Update از `reply_parameters: {message_id: original_message_id}` استفاده کند.

## Outbox

Transaction ایجاد Signal و Outbox row همزمان؛ Worker یکتا ارسال می‌کند؛ retry با همان idempotency key؛ duplicate send ممنوع.
