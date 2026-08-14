# Lead-Lag و زنجیره‌ی پامپ مطابق منظور حمید

## Trigger

هر ارز که در Rolling 15M حداقل 5% رشد کند یا Return Z-score غیرعادی داشته باشد، یک `LEADER_PUMP_EVENT` می‌سازد.

## تحلیل درست مثال XRP

1. تمام پامپ‌های تاریخی XRP را با تعریف ثابت و بدون Cherry-pick پیدا کن.
2. برای هر رویداد، وضعیت قبل/حین پامپ را ذخیره کن: شکل چارت، RSI/MACD/MFI/ADX، Volume، BTC، USDT.D، OI/Funding، خبر، Session و Regime.
3. در پنجره‌های 0–1h، 1–3h، 3–6h، 6–12h و 12–24h تمام ارزهایی را که حرکت معنادار داشته‌اند پیدا کن.
4. برای هر Follower محاسبه کن:
   - تعداد رویدادهای Leader
   - تعداد Follow
   - conditional probability
   - baseline probability
   - Lift = conditional / baseline
   - median lag و IQR
   - MFE/MAE و حجم ورود
   - ثبات در Regime/سال/Session
   - sector/network/layer/narrative relation
   - confidence interval و multiple-testing correction
5. نتیجه را با یک پامپ دیگر یا دو نمونه محدود نکن؛ همه‌ی داده‌ی معتبر را استفاده کن.

## Watch و Signal

- تکرار در دو رویداد = `RESEARCH_WATCH`.
- برای `PUMP_PROBABLE` نیاز به sample کافی، Lift مثبت، lag پایدار و current-regime similarity است.
- برای Signal واقعی، Follower باید volume ورود، Strategy setup، BTC/USDT.D alignment، liquidity و Risk approval داشته باشد.

## Runtime

- پس از Pump Event یک 24h follower clock ایجاد می‌شود.
- Watchlist هر بار با Tick/Volume update می‌شود.
- به محض activation، Symbol مستقیم وارد Full Re-analysis می‌شود.
- پیام «از چرخه عقب افتادیم» ممنوع است؛ State از لحظه‌ی Leader Event persist می‌شود.

## مقابله با خطا

- confounderهای BTC-wide pump، خبر مشترک، sector rally و listing را ثبت کن.
- Survivorship bias و symbol migration را کنترل کن.
- Resultها را بر اساس historical universe همان تاریخ بساز.
- دو همبستگی تصادفی Rule تولید نمی‌کنند.
