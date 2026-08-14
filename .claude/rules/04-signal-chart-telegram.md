# قرارداد سیگنال، تصویر و Telegram

- Signal ID: `LIAM-<UTC timestamp>-<SYMBOL>-<STRATEGY>-<8hex>`.
- Signal در Outbox تراکنشی ثبت و سپس ارسال شود.
- عکس Chart پیش از Delivery render و hash شود.
- Chart باید OHLCV، Trendline/Channel، 4H/1H S/R، OB/FVG، Entry/SL/TP و مسیر Scenario را نشان دهد.
- Watermark `Trade_osuli` کم‌رنگ، در پس‌زمینه و دور از Entry/SL/TP باشد.
- پاسخ Telegram از `reply_parameters.message_id` با message_id ذخیره‌شده‌ی پیام اصلی استفاده کند.
- هیچ Credential در Caption، Log، Browser یا Frontend قرار نگیرد.
- نتیجه‌ها: TARGET, STOP, INVALIDATED, EXPIRED, NO_FILL, MANUAL_CANCEL؛ همراه با MFE/MAE و Postmortem link.
- ارسال فوری per-symbol؛ Batch ارسال ممنوع.
