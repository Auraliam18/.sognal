# قوانین غیرقابل‌مذاکره‌ی ترید و توسعه

1. داده‌ی ناقص/قدیمی/UNKNOWN در فیلد اجباری = NO_SIGNAL.
2. 4H و 1H بر 15M و 5M اولویت دارند؛ Lower TF بدون Evidence قوی HTF را Override نمی‌کند.
3. USDT.D و BTC Context برای هر Alt Signal اجباری‌اند.
4. Volume/Liquidity/Structure از یک Indicator منفرد مهم‌ترند.
5. CHoCH داخلی پولبک به‌تنهایی مجوز Reversal نیست.
6. خطوط، S/R، OB و FVG حذف نمی‌شوند؛ Lifecycle و Role Flip ثبت می‌شود.
7. Strategyها با هم مخلوط نمی‌شوند و هر خروجی Strategy ID/Version دارد.
8. خلاف روند فقط با Strategy Counter-trend مستقل و تست‌شده.
9. Paper، Shadow، Live Signal و Live Execution داده/آمار/حافظه‌ی جدا دارند.
10. LIVE_EXECUTION=false تا فعال‌سازی جداگانه و تأیید انسانی.
11. هیچ Agent نتیجه‌ی یک Agent دیگر را واقعیت تلقی نمی‌کند؛ فقط Evidence Packet معتبر.
12. هیچ تغییر Strategy مستقیم وارد Production نمی‌شود.
13. هر Signal پیش از ارسال Snapshot، Risk approval، Dedupe key و Signal ID دارد.
14. هر نتیجه با Signal ID و Telegram message_id اصلی پیوند دارد.
15. توسعه بدون تست، Source Lineage و Change Log کامل محسوب نمی‌شود.
