# brain/cases — پرونده‌های معامله (case studies)

هر ستاپ بسته یا باطل‌شدهٔ سیگنال‌گرید یک فایل JSON جدا می‌شود:
`cases/YYYY-MM/<SYM>-<closed_ms>.json` — **فایل یکتا به ازای هر پرونده**،
عمداً: دو ورک‌فلوی هم‌زمان هرگز روی یک فایل نمی‌نویسند (ایمنی همزمانی،
بند ۳۴ منشور). پرونده‌ها append-only هستند: هرگز ویرایش یا حذف نمی‌شوند
(«باخت حذف نمی‌شود، خطا پنهان نمی‌شود»).

## شِما (فیلدها هر جا موجود باشند؛ غایب = UNKNOWN، هرگز جعل نشود)
ts_open, ts_close, symbol, dir, setup_type(stage), regime, entry, sl,
tp1, tp2, outcome, R, R_net, mfe_r, mae_r, held_h, fee_r,
ctx { شرایط لحظهٔ باز شدن: trend_4h, liq, liq_map, relax, memory, ... },
autopsy (کالبدشکافی استاپ: سیستمی/ضعف ستاپ)، lessons (اگر بازبینی درس داد)

نویسنده: `hamid/cases.py` که از settle_books صدا می‌شود. خواننده:
ایجنت post-trade-learning و review_cycle. آمار تجمیعی از اینجا ساخته
می‌شود، نه برعکس — پرونده منبع حقیقت است.
