# امنیت و مرز Live Execution

- این Package فقط Backtest/Replay/Paper/Shadow/Live Signal را مجاز می‌داند.
- `LIVE_EXECUTION` باید `false` بماند.
- Secretها فقط در Backend secret store یا environment امن؛ نه Git، Prompt، HTML، localStorage یا Log.
- عملیات مخرب مانند force-push، reset --hard، حذف بازگشتی یا overwrite داده‌ی Runtime بدون Backup و تأیید صریح ممنوع است.
- یک Writer برای Telegram، یک Writer برای هر State domain، Transaction + Idempotency + Lock.
- تغییرات در Branch جدا، با تست و Diff review انجام شوند.
- داده‌ی Runtime داخل Git commit نمی‌شود.
