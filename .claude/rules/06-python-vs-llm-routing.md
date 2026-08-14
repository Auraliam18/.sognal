# تقسیم کار Python و LLM

## همیشه Python/کد قطعی

- WebSocket/REST ingestion، candle building، indicators، pivots، trendline candidates، channels، S/R، BOS/CHoCH، FVG/OB candidates
- order book/OI/funding/liquidation math، event study، lead-lag، analog search، backtest/replay، risk، MFE/MAE
- cache/state/queue/idempotency، chart rendering، Telegram delivery، metrics/tests

## فقط در صورت نیاز LLM/Agent

- Ambiguity review، source verification، research synthesis، pattern interpretation با uncertainty
- conflict resolution، post-trade causal narrative، improvement hypothesis، Persian explanation

## ممنوع

- فراخوانی LLM برای هر Tick یا هر Symbol در Heartbeat 30s
- جایگزین کردن مقدار عددی Engine با حدس Agent
- تغییر مستقیم Strategy Production از خروجی تحقیق
