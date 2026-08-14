# یادگیری فوری پس از Paper و Live Signal

## Snapshot پیش از Signal

تمام Engine packetها، Chart features، source/freshness، Strategy version، Entry/SL/TP، BTC/USDT.D، Liquidity، News و دلایل رد/قبول Immutable ذخیره می‌شوند.

## Review horizons

- `IMMEDIATE`: هنگام Target/Stop/Invalidation/Expiry/No-fill
- `1H`: آیا Stop زودرس بود یا thesis سریع شکست؟
- `6H`: حرکت جایگزین و MFE/MAE
- `24H`: outcome کامل و missed-follow-through

## Factor audit

برای هر عامل:

- expected_state
- actual_state_at_entry
- state_before_result
- held / weakened / contradicted / missing
- causal relevance estimate
- evidence link

عوامل اجباری: USDT.D، BTC/BTC.D/Macro، HTF structure، Trendline/SR، OB/FVG، volume، liquidity/OI/funding، indicators، strategy gates، analog، news، execution timing.

## Failure taxonomy

- HTF_CONFLICT
- INTERNAL_CHOCH_TRAP
- OB_CONSUMED
- LIQUIDITY_HUNT_TOO_CLOSE
- LATE_ENTRY
- NO_VOLUME_CONFIRMATION
- BTC_USDTD_REGIME_SHIFT
- NEWS_SHOCK
- DATA_STALE
- FALSE_BREAKOUT
- RANGE_ROTATION
- RISK_OR_EXECUTION_ERROR

## Lesson confidence

یک Outcome فقط Episode است. Lesson شامل sample_size، wins/losses، regimes و confidence interval می‌شود. تکرار Evidence اعتبار را بالا می‌برد؛ تناقض اعتبار را پایین می‌آورد.

## Promotion

`EPISODE → CANDIDATE_LESSON → BACKTESTED → PAPER_VALIDATED → SHADOW_VALIDATED → CANONICAL`.

هیچ Agent حق ندارد وزن/Threshold Production را مستقیم تغییر دهد.
