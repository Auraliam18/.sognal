# معماری پایش لحظه‌ای و Heartbeat سی‌ثانیه‌ای

- Market Feed پیوسته و رویدادمحور است؛ ۳۰ ثانیه فقط Heartbeat/Sweep برای اطمینان از پوشش تمام Top-200 است.
- هر Symbol یک Actor/Mailbox منطقی و State مستقل دارد.
- انجین‌های قطعی Python به‌صورت Incremental و Concurrent کار می‌کنند.
- HTF Structure فقط در Candle Close، Pivot Change یا Lifecycle Event محاسبه‌ی مجدد می‌شود؛ در هر ۳۰ ثانیه کل ۲۰۰ کندل دوباره محاسبه نمی‌شود.
- وقتی یک Symbol تمام Hard Gateها را Pass کرد، `SIGNAL_READY` همان لحظه منتشر می‌شود؛ Global Barrier، Batch Buffer یا انتظار پایان اسکن ممنوع است.
- LLM روی Tick، Candle یا هر Symbol در هر ۳۰ ثانیه فراخوانی نمی‌شود. ایجنت استدلالی فقط برای Ambiguity، Research، Conflict و Postmortem فعال می‌شود.
- Priority: Tier 2 approaching setup > Tier 1 anomaly/watch > Tier 0 universe maintenance.
- SLO هدف: data ingest p95<1s؛ candidate evaluation p95<10s؛ Telegram enqueue p95<500ms، با اندازه‌گیری واقعی و بدون ادعای صفر تأخیر.
- GitHub Actions حلقه‌ی بازار نیست؛ Runtime محلی Python/Docker است.
