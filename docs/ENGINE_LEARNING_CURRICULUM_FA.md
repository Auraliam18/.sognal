# AuraLiam369 — برنامهٔ مطالعه و یادگیری دائمی E00 تا E25

**نسخه:** 1.0  
**تاریخ:** 2026-08-14  
**هدف:** برای هر انجین/ایجنت سه کتاب مرجع، منبع به‌روزرسانی دائمی، موضوع یادگیری، آزمایش Paper و Namespace حافظه تعریف شود.

## قوانین قطعی

1. کتاب‌ها «منبع آموزش» هستند، نه Rule آمادهٔ Production.
2. متن کامل کتاب فقط از نسخه‌ای خوانده شود که حمید به‌طور قانونی تهیه و در اختیار سیستم قرار داده است. دانلود غیرمجاز، دورزدن Paywall و ذخیرهٔ متن کامل کتاب در Memory ممنوع است.
3. از هر کتاب فقط یادداشت، تعریف، Claim، فرمول، Citation و سؤال پژوهشی ذخیره شود؛ نه بازتولید طولانی متن.
4. دو Loop جدا وجود دارد:
   - **Operational Loop:** قیمت و دادهٔ بازار به‌صورت WebSocket/رویدادمحور.
   - **Knowledge Loop:** بررسی Release، مقاله و مستندات در زمان‌بندی روزانه/هفتگی؛ نه فراخوانی LLM روی هر Tick.
5. Python مسئول Fetch، Diff، Hash، Dedup، محاسبه، Backtest و Paper Test است. Agent مسئول تفسیر، ساخت فرضیه، بررسی تعارض و گزارش است.
6. هیچ یافتهٔ جدید مستقیم وارد Strategy زنده نمی‌شود.

## مسیر اجباری ارتقای دانش

```text
DISCOVERED
→ SOURCE_VERIFIED
→ CLAIM_EXTRACTED
→ HYPOTHESIS
→ BACKTESTED
→ WALK_FORWARD_VALIDATED
→ PAPER_VALIDATED
→ SHADOW_VALIDATED
→ PRODUCTION_VALIDATED
```

### معیار Promotion به حافظهٔ مرجع

- منبع اولیه/رسمی یا پژوهش معتبر مشخص باشد.
- کد و دادهٔ آزمایش قابل بازتولید باشد.
- Look-ahead، Survivorship Bias، Fee، Slippage و Funding کنترل شوند.
- برای جست‌وجوهای زیاد، Multiple-testing/FDR کنترل شود.
- Bootstrap Confidence Interval و Effect Size گزارش شوند؛ Win Rate به‌تنهایی کافی نیست.
- نتیجه در Out-of-sample و چند Regime پایدار باشد.
- یک تغییر کنترل‌شده در هر Experiment.
- E21 تنها مرجع Promotion است؛ نسخهٔ قبلی حذف نمی‌شود و `SUPERSEDED` می‌گیرد.

## Schema هر Lesson

```json
{
  "lesson_id": "uuid",
  "engine_id": "E12",
  "scope": "symbol|strategy|market|system",
  "claim": "...",
  "source_url": "...",
  "source_type": "official|peer_reviewed|preprint|aggregator|implementation",
  "retrieved_at": "timestamp",
  "experiment_id": "uuid",
  "dataset_snapshot_id": "uuid",
  "strategy_version": "...",
  "symbol": "...",
  "regime": "...",
  "sample_size": 0,
  "effect_size": 0,
  "confidence_interval": [0, 0],
  "status": "OBSERVATION|RESEARCHED|BACKTESTED|PAPER_VALIDATED|SHADOW_VALIDATED|PRODUCTION_VALIDATED|REJECTED|SUPERSEDED",
  "evidence_ids": [],
  "conflicts": [],
  "expires_at": "timestamp|null"
}
```

---

## E00 — Master Orchestrator / Chief Trader

### سه کتاب مرجع
1. Designing Data-Intensive Applications — Martin Kleppmann
2. Enterprise Integration Patterns — Gregor Hohpe & Bobby Woolf
3. Building Microservices, 2nd Edition — Sam Newman

### منبع پایش دائمی
- **اصلی:** https://docs.langchain.com/oss/python/langgraph/
- **تکمیلی/راستی‌آزمایی:** https://code.claude.com/docs/en/sub-agents

### دقیقاً چه چیزی یاد بگیرد؟
طراحی گراف تصمیم، جداسازی مسئولیت، Handoff، State، Idempotency، Failure Recovery و جلوگیری از Agent همه‌کاره.

### زمان‌بندی
هفتگی و هنگام انتشار Release/Breaking Change

### نحوهٔ استفاده در Paper Trading
شبیه‌سازی Workflowهای چندایجنتی، قطع Worker، اجرای دوباره Event و اثبات نبود Duplicate/State Loss.

### حافظهٔ خصوصی
`agent/E00/orchestrator`

---

## E01 — Universe Engine / Universe Agent

### سه کتاب مرجع
1. Cryptoassets — Chris Burniske & Jack Tatar
2. Advances in Financial Machine Learning — Marcos López de Prado
3. Analysis of Financial Time Series — Ruey S. Tsay

### منبع پایش دائمی
- **اصلی:** https://docs.coingecko.com/docs/market-research
- **تکمیلی/راستی‌آزمایی:** https://coinmarketcap.com/api/documentation/

### دقیقاً چه چیزی یاد بگیرد؟
ساخت Top-200 بدون Survivorship Bias، فیلتر نقدشوندگی، دسته‌بندی Sector/Network/Layer، Listing/Delisting و Symbol Mapping.

### زمان‌بندی
Snapshot روزانه؛ تغییر Listing/Delisting رویدادمحور

### نحوهٔ استفاده در Paper Trading
مقایسه Universeهای مختلف روی Coverage، Slippage، Data Availability و ثبات نتایج بدون تغییر Strategy.

### حافظهٔ خصوصی
`agent/E01/universe`

---

## E02 — Market Data Engine / Data Quality Agent

### سه کتاب مرجع
1. Designing Data-Intensive Applications — Martin Kleppmann
2. Streaming Systems — Tyler Akidau, Slava Chernyak & Reuven Lax
3. Database Internals — Alex Petrov

### منبع پایش دائمی
- **اصلی:** https://www.bitunix.com/api-docs/
- **تکمیلی/راستی‌آزمایی:** https://docs.coingecko.com/

### دقیقاً چه چیزی یاد بگیرد؟
WebSocket، Sequence، Clock Sync، Missing Candle، Out-of-order Event، Backfill، Source Lineage و Freshness.

### زمان‌بندی
مستندات هفتگی؛ Health و Gap Detection پیوسته

### نحوهٔ استفاده در Paper Trading
Chaos Test برای قطع WebSocket، کندل گمشده، Event تکراری، اختلاف منبع و بازسازی دقیق State.

### حافظهٔ خصوصی
`agent/E02/data-quality`

---

## E03 — USDT.D Engine / USDT Dominance Agent

### سه کتاب مرجع
1. Technical Analysis of the Financial Markets — John J. Murphy
2. Trading with Intermarket Analysis — John J. Murphy
3. Analysis of Financial Time Series — Ruey S. Tsay

### منبع پایش دائمی
- **اصلی:** https://www.tradingview.com/markets/cryptocurrencies/dominance/
- **تکمیلی/راستی‌آزمایی:** https://fred.stlouisfed.org/docs/api/fred/

### دقیقاً چه چیزی یاد بگیرد؟
Trendline/Channel، S/R، OB/FVG، الگوها، Regime و رابطه USDT.D با جریان ریسک بازار؛ تحلیل مستقل 4H/1H/15m.

### زمان‌بندی
دانش هفتگی؛ داده و ساختار با بسته‌شدن کندل یا Event مهم

### نحوهٔ استفاده در Paper Trading
Event Study رابطه تغییر USDT.D با BTC/Altها با تفکیک Regime و کنترل زمان انتشار داده‌های کلان.

### حافظهٔ خصوصی
`agent/E03/usdt-dominance`

---

## E04 — BTC.D Engine / BTC Dominance Agent

### سه کتاب مرجع
1. Trading with Intermarket Analysis — John J. Murphy
2. Technical Analysis: The Complete Resource for Financial Market Technicians — Charles D. Kirkpatrick II & Julie R. Dahlquist
3. Analysis of Financial Time Series — Ruey S. Tsay

### منبع پایش دائمی
- **اصلی:** https://www.tradingview.com/markets/cryptocurrencies/dominance/
- **تکمیلی/راستی‌آزمایی:** https://docs.coingecko.com/docs/market-research

### دقیقاً چه چیزی یاد بگیرد؟
جریان سرمایه میان BTC و Altها، الگوهای کلاسیک، شکست/فیک‌اوت و تلاقی BTC.D با TOTAL3/OTHERS.

### زمان‌بندی
دانش هفتگی؛ ساختار با Candle Close و Break Event

### نحوهٔ استفاده در Paper Trading
آزمون اثر Regimeهای BTC.D روی بازده Altها، Breadth و موفقیت Long/Short با کنترل حرکت خود BTC.

### حافظهٔ خصوصی
`agent/E04/btc-dominance`

---

## E05 — Macro Regime Engine / Macro Agent

### سه کتاب مرجع
1. The Economics of Money, Banking, and Financial Markets — Frederic S. Mishkin
2. Trading with Intermarket Analysis — John J. Murphy
3. Forecasting: Principles and Practice — Rob J. Hyndman & George Athanasopoulos

### منبع پایش دائمی
- **اصلی:** https://fred.stlouisfed.org/docs/api/fred/
- **تکمیلی/راستی‌آزمایی:** https://fred.stlouisfed.org/docs/api/fred/alfred.html

### دقیقاً چه چیزی یاد بگیرد؟
Risk-on/Risk-off، نرخ بهره، DXY، نقدینگی کلان، تقویم داده و استفاده از Vintage واقعی برای جلوگیری از Look-ahead.

### زمان‌بندی
تقویم روزانه؛ Research هفتگی؛ Eventهای کلان رویدادمحور

### نحوهٔ استفاده در Paper Trading
Replay با داده Vintage از ALFRED؛ مقایسه تصمیم با اطلاعاتی که واقعاً در همان زمان منتشر شده بود.

### حافظهٔ خصوصی
`agent/E05/macro`

---

## E06 — BTC Analysis Engine / BTC Agent

### سه کتاب مرجع
1. Technical Analysis of the Financial Markets — John J. Murphy
2. Trading and Exchanges: Market Microstructure for Practitioners — Larry Harris
3. Mastering Bitcoin — Andreas M. Antonopoulos

### منبع پایش دائمی
- **اصلی:** https://www.coinbase.com/institutional/research-insights/research
- **تکمیلی/راستی‌آزمایی:** https://coinmetrics.io/insights/state-of-the-network/

### دقیقاً چه چیزی یاد بگیرد؟
ساختار BTC، Liquidity، OI/Funding، On-chain Context، Pullback Plus و نقش BTC به‌عنوان Gate همه Altها.

### زمان‌بندی
Market Data پیوسته؛ Research روزانه/هفتگی

### نحوهٔ استفاده در Paper Trading
بازسازی سناریوهای BTC در 4H/1H/15m/5m و سنجش تأثیر Bias درست/غلط BTC بر سیگنال Altها.

### حافظهٔ خصوصی
`agent/E06/btc`

---

## E07 — Structure Engine / Structure Agent

### سه کتاب مرجع
1. Technical Analysis: The Complete Resource for Financial Market Technicians — Charles D. Kirkpatrick II & Julie R. Dahlquist
2. Technical Analysis of the Financial Markets — John J. Murphy
3. Encyclopedia of Chart Patterns, 3rd Edition — Thomas N. Bulkowski

### منبع پایش دائمی
- **اصلی:** https://cmtassociation.org/education/publications/journal-of-technical-analysis/
- **تکمیلی/راستی‌آزمایی:** https://www.tradingview.com/

### دقیقاً چه چیزی یاد بگیرد؟
Pivot، Trendline معتبر، Channel، S/R Zone، BOS/CHoCH، Role Flip و Pattern Recognition بدون Repaint.

### زمان‌بندی
Journal ماهانه/فصلی؛ Detector با Candle Close و Structure Event

### نحوهٔ استفاده در Paper Trading
Golden Chart Fixtures تأییدشده توسط حمید، Precision/Recall خطوط و الگوها، و آزمون Out-of-sample روی ارز/Regime دیگر.

### حافظهٔ خصوصی
`agent/E07/structure`

---

## E08 — SMC Engine / SMC Agent

### سه کتاب مرجع
1. Trading and Exchanges: Market Microstructure for Practitioners — Larry Harris
2. Market Microstructure Theory — Maureen O’Hara
3. Empirical Market Microstructure — Joel Hasbrouck

### منبع پایش دائمی
- **اصلی:** https://www.cmegroup.com/liquiditytool
- **تکمیلی/راستی‌آزمایی:** https://arxiv.org/list/q-fin.TR/recent

### دقیقاً چه چیزی یاد بگیرد؟
Order Block، FVG، Displacement، Mitigation، Breaker، Liquidity Sweep و Inducement. اصطلاحات ICT/SMC فرضیه‌اند، نه حقیقت آماری.

### زمان‌بندی
Research هفتگی؛ OB/FVG State رویدادمحور

### نحوهٔ استفاده در Paper Trading
ثبت همه OBها با Freshness/Mitigation/Regime و سنجش Reaction Probability، MFE/MAE و زمان واکنش.

### حافظهٔ خصوصی
`agent/E08/smc`

---

## E09 — Indicator Engine / Indicator Agent

### سه کتاب مرجع
1. New Concepts in Technical Trading Systems — J. Welles Wilder Jr.
2. Technical Analysis: The Complete Resource for Financial Market Technicians — Charles D. Kirkpatrick II & Julie R. Dahlquist
3. Evidence-Based Technical Analysis — David R. Aronson

### منبع پایش دائمی
- **اصلی:** https://ta-lib.org/functions/
- **تکمیلی/راستی‌آزمایی:** https://cmtassociation.org/education/publications/journal-of-technical-analysis/

### دقیقاً چه چیزی یاد بگیرد؟
فرمول و Warm-up دقیق RSI/MACD/MFI/ADX/ATR/Stochastic/BB/Moving Averages، واگرایی و جلوگیری از استفاده تک‌اندیکاتوری.

### زمان‌بندی
Release/Formula Review ماهانه؛ محاسبات Incremental

### نحوهٔ استفاده در Paper Trading
Unit Test در برابر TA-Lib، آزمون ارزش افزوده هر Indicator روی Strategy ثابت و کنترل Data Snooping.

### حافظهٔ خصوصی
`agent/E09/indicators`

---

## E10 — Liquidity & Derivatives Engine / Liquidity Agent

### سه کتاب مرجع
1. Trading and Exchanges: Market Microstructure for Practitioners — Larry Harris
2. Market Microstructure Theory — Maureen O’Hara
3. Empirical Market Microstructure — Joel Hasbrouck

### منبع پایش دائمی
- **اصلی:** https://docs.coinglass.com/
- **تکمیلی/راستی‌آزمایی:** https://www.bitunix.com/api-docs/futures/websocket/public/depth%20channel.html

### دقیقاً چه چیزی یاد بگیرد؟
Order Book، Depth، Spread، OI، Funding، Liquidation، Order-flow Imbalance، Stop Hunt و تفکیک داده مستقیم از تخمین.

### زمان‌بندی
Data پیوسته؛ مستندات هفتگی؛ Research ماهانه

### نحوهٔ استفاده در Paper Trading
آزمون Liquidity Magnet، Sweep، OI/Funding Extremes و Stop Buffer با داده Direct و Estimated جدا.

### حافظهٔ خصوصی
`agent/E10/liquidity`

---

## E11 — Strategy Router / Strategy Agents

### سه کتاب مرجع
1. Systematic Trading — Robert Carver
2. Quantitative Trading — Ernest P. Chan
3. Advances in Financial Machine Learning — Marcos López de Prado

### منبع پایش دائمی
- **اصلی:** https://arxiv.org/list/q-fin.TR/recent
- **تکمیلی/راستی‌آزمایی:** https://cmtassociation.org/education/publications/journal-of-technical-analysis/

### دقیقاً چه چیزی یاد بگیرد؟
Registry نسخه‌دار، Hard Gate/Soft Score، انتخاب Strategy مناسب Regime و جلوگیری از تغییر هم‌زمان چند Rule.

### زمان‌بندی
Research هفتگی؛ Registry فقط پس از Promotion

### نحوهٔ استفاده در Paper Trading
هر فرضیه روی یک Strategy Version جدا، Walk-forward، Paper و Shadow؛ مقایسه با Baseline ثابت.

### حافظهٔ خصوصی
`agent/E11/strategy-router`

---

## E12 — Lead-Lag Engine / Relationship Agent

### سه کتاب مرجع
1. Analysis of Financial Time Series — Ruey S. Tsay
2. Time Series Analysis — James D. Hamilton
3. Forecasting: Principles and Practice — Rob J. Hyndman & George Athanasopoulos

### منبع پایش دائمی
- **اصلی:** https://arxiv.org/list/q-fin.ST/recent
- **تکمیلی/راستی‌آزمایی:** https://arxiv.org/list/q-fin.TR/recent

### دقیقاً چه چیزی یاد بگیرد؟
Cross-correlation، Event Study، Conditional Probability، Lift، Lag Distribution، Granger-style tests و کنترل Market Beta/FDR.

### زمان‌بندی
Pump Event رویدادمحور؛ Research هفتگی؛ Backfill شبانه

### نحوهٔ استفاده در Paper Trading
تمام Pumpهای تاریخی Leader، واکنش 0–24h همه Followers، حذف اثر BTC و آزمون Out-of-sample.

### حافظهٔ خصوصی
`agent/E12/lead-lag`

---

## E13 — Historical Analog Engine / Analog Agent

### سه کتاب مرجع
1. Pattern Recognition and Machine Learning — Christopher M. Bishop
2. Analysis of Financial Time Series — Ruey S. Tsay
3. Advances in Financial Machine Learning — Marcos López de Prado

### منبع پایش دائمی
- **اصلی:** https://stumpy.readthedocs.io/en/latest/
- **تکمیلی/راستی‌آزمایی:** https://arxiv.org/list/q-fin.ST/recent

### دقیقاً چه چیزی یاد بگیرد؟
Matrix Profile، Distance Metrics، Feature Similarity، Regime-aware nearest neighbors و جلوگیری از شباهت ظاهری گمراه‌کننده.

### زمان‌بندی
Research ماهانه؛ Index تاریخی Incremental

### نحوهٔ استفاده در Paper Trading
Analog Retrieval را با Outcomeهای مخفی ارزیابی کن؛ Top-k، Calibration و Baseline تصادفی گزارش شود.

### حافظهٔ خصوصی
`agent/E13/analog`

---

## E14 — News & Catalyst Engine / Research Agent

### سه کتاب مرجع
1. The Handbook of News Analytics in Finance — Gautam Mitra & Leela Mitra (eds.)
2. Machine Learning for Trading, Third Edition — Stefan Jansen
3. Cryptoassets — Chris Burniske & Jack Tatar

### منبع پایش دائمی
- **اصلی:** https://coinmarketcap.com/api/documentation/pro-api-reference/content
- **تکمیلی/راستی‌آزمایی:** https://docs.messari.io/api-reference/endpoints/news/news-api

### دقیقاً چه چیزی یاد بگیرد؟
Entity Resolution، Event Time در برابر Publish Time، Source Credibility، Launch/Unlock/Listing/Upgrade و Historical Event Impact.

### زمان‌بندی
Feed هر 1–5 دقیقه بسته به API؛ Research و Dedup روزانه

### نحوهٔ استفاده در Paper Trading
خبر فقط Candidate می‌سازد؛ اثر Eventهای هم‌نوع روی همان ارز/Sector در پنجره‌های زمانی مشخص Paper Test شود و از منبع رسمی پروژه تأیید گردد.

### حافظهٔ خصوصی
`agent/E14/news-catalyst`

---

## E15 — Watch & Alert Engine / Watch Agent

### سه کتاب مرجع
1. Streaming Systems — Tyler Akidau, Slava Chernyak & Reuven Lax
2. Enterprise Integration Patterns — Gregor Hohpe & Bobby Woolf
3. Release It! — Michael T. Nygard

### منبع پایش دائمی
- **اصلی:** https://prometheus.io/docs/alerting/latest/alertmanager/
- **تکمیلی/راستی‌آزمایی:** https://prometheus.io/docs/alerting/latest/configuration/

### دقیقاً چه چیزی یاد بگیرد؟
Proximity Alert، Debounce، Dedup، Cooldown، Alert Storm، Priority Queue و Re-analysis Trigger فوری.

### زمان‌بندی
Health پیوسته؛ Docs/Release هفتگی

### نحوهٔ استفاده در Paper Trading
Replay با 200 نماد؛ سنجش Missed Alert، Duplicate، Latency و اینکه Symbol اول منتظر Symbol دویستم نماند.

### حافظهٔ خصوصی
`agent/E15/watch-alert`

---

## E16 — Risk Engine / Risk Officer

### سه کتاب مرجع
1. Quantitative Risk Management — Alexander J. McNeil, Rüdiger Frey & Paul Embrechts
2. The Mathematics of Money Management — Ralph Vince
3. Systematic Trading — Robert Carver

### منبع پایش دائمی
- **اصلی:** https://www.cmegroup.com/education/courses/trade-and-risk-management
- **تکمیلی/راستی‌آزمایی:** https://rpc.cfainstitute.org/research

### دقیقاً چه چیزی یاد بگیرد؟
Position Sizing، Portfolio Heat، Correlation Cluster، Drawdown، Structural Stop، Tail Risk و حق Veto.

### زمان‌بندی
Risk Metrics پیوسته؛ Research ماهانه

### نحوهٔ استفاده در Paper Trading
Monte Carlo/Bootstrap، Stress Scenario، Gap/Slippage/Funding و مقایسه Risk Policyها بدون تغییر Entry Logic.

### حافظهٔ خصوصی
`agent/E16/risk`

---

## E17 — Signal Committee / Decision Agent

### سه کتاب مرجع
1. Bayesian Data Analysis — Andrew Gelman et al.
2. Superforecasting — Philip E. Tetlock & Dan Gardner
3. Forecasting: Principles and Practice — Rob J. Hyndman & George Athanasopoulos

### منبع پایش دائمی
- **اصلی:** https://scikit-learn.org/stable/modules/calibration.html
- **تکمیلی/راستی‌آزمایی:** https://scikit-learn.org/stable/api/sklearn.calibration.html

### دقیقاً چه چیزی یاد بگیرد؟
Probability Calibration، Evidence Weighting، Conflict Resolution، Abstention/NO_TRADE و جداسازی Confidence از Score.

### زمان‌بندی
Calibration هفتگی یا پس از Sample جدید کافی

### نحوهٔ استفاده در Paper Trading
Reliability Diagram، Brier Score، Calibration Error و Outcome Split بر اساس Regime/Strategy/Symbol.

### حافظهٔ خصوصی
`agent/E17/signal-committee`

---

## E18 — Paper / Replay / Backtest Engine / Experiment Agent

### سه کتاب مرجع
1. Evidence-Based Technical Analysis — David R. Aronson
2. Advances in Financial Machine Learning — Marcos López de Prado
3. Quantitative Trading — Ernest P. Chan

### منبع پایش دائمی
- **اصلی:** https://vectorbt.dev/
- **تکمیلی/راستی‌آزمایی:** https://vectorbt.dev/getting-started/resources/

### دقیقاً چه چیزی یاد بگیرد؟
No Look-ahead، Walk-forward، Purged Split، Fees/Slippage/Funding، Reproducibility، Parameter Stability و Historical Universe.

### زمان‌بندی
Paper پیوسته؛ Replay/Backfill شبانه؛ Research هفتگی

### نحوهٔ استفاده در Paper Trading
هر تغییر یک Experiment ID و Baseline؛ OOS، Bootstrap CI، Regime Split و Reproduction Script اجباری.

### حافظهٔ خصوصی
`agent/E18/experiments`

---

## E19 — Trade Management Engine / Trade Manager Agent

### سه کتاب مرجع
1. The Mathematics of Money Management — Ralph Vince
2. Systematic Trading — Robert Carver
3. Trading Psychology 2.0 — Brett N. Steenbarger

### منبع پایش دائمی
- **اصلی:** https://www.bitunix.com/api-docs/
- **تکمیلی/راستی‌آزمایی:** https://www.cmegroup.com/education/courses/trade-and-risk-management

### دقیقاً چه چیزی یاد بگیرد؟
Trailing ساختاری، Partial Exit، Invalidation، Time Stop، Order State و جلوگیری از مدیریت احساسی.

### زمان‌بندی
Position Event پیوسته؛ Review هفتگی

### نحوهٔ استفاده در Paper Trading
Entry ثابت نگه داشته شود و فقط Exit Policyها روی MFE/MAE، Expectancy و Drawdown مقایسه شوند.

### حافظهٔ خصوصی
`agent/E19/trade-management`

---

## E20 — Post-Trade Engine / Reviewer Agent

### سه کتاب مرجع
1. The Daily Trading Coach — Brett N. Steenbarger
2. The PlayBook — Mike Bellafiore
3. Evidence-Based Technical Analysis — David R. Aronson

### منبع پایش دائمی
- **اصلی:** https://cmtassociation.org/education/publications/journal-of-technical-analysis/
- **تکمیلی/راستی‌آزمایی:** https://github.com/ranaroussi/quantstats

### دقیقاً چه چیزی یاد بگیرد؟
MFE/MAE، Failure Taxonomy، Premortem/Postmortem، Attribution، خطای Data/Latency/Regime و تشخیص علت از هم‌زمانی.

### زمان‌بندی
پس از هر Close فوری؛ مرور 1h/6h/24h؛ جمع‌بندی هفتگی

### نحوهٔ استفاده در Paper Trading
بازبینی TP/SL و فرصت‌های ردشده؛ هر Lesson با Counterfactual و Evidence IDs ثبت شود.

### حافظهٔ خصوصی
`agent/E20/post-trade`

---

## E21 — Memory Store / Memory Curator Agent

### سه کتاب مرجع
1. Designing Data-Intensive Applications — Martin Kleppmann
2. Database Internals — Alex Petrov
3. Knowledge Graphs — Aidan Hogan et al.

### منبع پایش دائمی
- **اصلی:** https://docs.langchain.com/oss/python/langgraph/persistence
- **تکمیلی/راستی‌آزمایی:** https://docs.langchain.com/oss/javascript/langgraph/add-memory

### دقیقاً چه چیزی یاد بگیرد؟
Namespace، Provenance، Versioning، Semantic Retrieval، Conflict، Supersede، Expiry و Promotion کنترل‌شده.

### زمان‌بندی
Ingest رویدادمحور؛ Compaction شبانه؛ Audit هفتگی

### نحوهٔ استفاده در Paper Trading
Recall Precision، جلوگیری از Memory Contamination، Conflict Test و بازتولید Lesson از Evidence خام.

### حافظهٔ خصوصی
`agent/E21/memory-curator`

---

## E22 — Improvement Engine / Research Director

### سه کتاب مرجع
1. Causal Inference: The Mixtape — Scott Cunningham
2. Experimentation Works — Stefan H. Thomke
3. The Craft of Research — Wayne C. Booth, Gregory G. Colomb, Joseph M. Williams et al.

### منبع پایش دائمی
- **اصلی:** https://www.nber.org/papers
- **تکمیلی/راستی‌آزمایی:** https://www.ssrn.com/

### دقیقاً چه چیزی یاد بگیرد؟
Research Question، Causal Hypothesis، Experimental Design، Priority، Expected Value of Information و رد ایده‌های کم‌کیفیت.

### زمان‌بندی
Research Feed هفتگی؛ Backlog روزانه

### نحوهٔ استفاده در Paper Trading
یک تغییر کنترل‌شده در هر Cycle، Pre-registration، Baseline، Kill Criteria و تصمیم Keep/Revert.

### حافظهٔ خصوصی
`agent/E22/improvement`

---

## E23 — Supervisor / SRE Agent

### سه کتاب مرجع
1. Site Reliability Engineering — Betsy Beyer, Chris Jones, Jennifer Petoff & Niall Richard Murphy (eds.)
2. The Site Reliability Workbook — Betsy Beyer et al.
3. Observability Engineering — Charity Majors, Liz Fong-Jones & George Miranda

### منبع پایش دائمی
- **اصلی:** https://sre.google/resources/
- **تکمیلی/راستی‌آزمایی:** https://sre.google/books/

### دقیقاً چه چیزی یاد بگیرد؟
SLO، Latency، Queue Lag، Circuit Breaker، Recovery، Error Budget، Capacity و Health هر Engine/Agent.

### زمان‌بندی
Monitoring پیوسته؛ SRE Review هفتگی

### نحوهٔ استفاده در Paper Trading
Fault Injection، Worker Restart، DB Failure، Telegram Failure و اثبات Recovery بدون Duplicate/Data Loss.

### حافظهٔ خصوصی
`agent/E23/sre`

---

## E24 — Panel Contract Engine / UI QA Agent

### سه کتاب مرجع
1. Continuous Delivery — Jez Humble & David Farley
2. The Art of Software Testing — Glenford J. Myers, Corey Sandler & Tom Badgett
3. Designing Interfaces — Jenifer Tidwell, Charles Brewer & Aynne Valencia

### منبع پایش دائمی
- **اصلی:** https://playwright.dev/docs/intro
- **تکمیلی/راستی‌آزمایی:** https://spec.openapis.org/oas/latest.html

### دقیقاً چه چیزی یاد بگیرد؟
API/UI Contract، E2E، Cross-browser، Freshness Badge، Source/Trace ID، Paper/Live Separation و Accessibility.

### زمان‌بندی
Contract Test در هر Commit؛ E2E شبانه و قبل Deploy

### نحوهٔ استفاده در Paper Trading
Playwright روی تمام Tabها، Mock ممنوع در Production، Tie-out عدد UI با DB/API و Screenshot/Trace روی Failure.

### حافظهٔ خصوصی
`agent/E24/panel-qa`

---

## E25 — Telegram Delivery Engine / Notification Agent

### سه کتاب مرجع
1. Enterprise Integration Patterns — Gregor Hohpe & Bobby Woolf
2. Release It! — Michael T. Nygard
3. Designing Data-Intensive Applications — Martin Kleppmann

### منبع پایش دائمی
- **اصلی:** https://core.telegram.org/bots/api
- **تکمیلی/راستی‌آزمایی:** https://prometheus.io/docs/alerting/latest/alertmanager/

### دقیقاً چه چیزی یاد بگیرد؟
Outbox، Idempotency، Retry، Rate Limit، Signal ID، Photo+Caption، Reply به Message ID و Delivery Receipt.

### زمان‌بندی
Delivery پیوسته؛ API Change هفتگی

### نحوهٔ استفاده در Paper Trading
قطع شبکه، Retry، Duplicate Event، Message Reply Mapping و اثبات Exactly-once منطقی با Unique Constraint.

### حافظهٔ خصوصی
`agent/E25/telegram`

---

## برنامهٔ مطالعهٔ کتاب‌ها

برای هر کتاب:

1. ابتدا فهرست و فصل‌های مرتبط با مسئولیت Engine استخراج شود.
2. هر فصل به کارت‌های دانشی کوچک تبدیل شود: `definition`, `formula`, `assumption`, `failure_mode`, `testable_claim`.
3. هر Claim یک سؤال آزمایشی و معیار رد داشته باشد.
4. Agent حق ندارد جملهٔ کتاب را به Rule معاملاتی تبدیل کند؛ E18 باید آن را روی دادهٔ واقعی و Paper آزمایش کند.
5. خلاصهٔ هر فصل حداکثر چند پاراگراف باشد و Citation فصل/صفحه ذخیره شود.
6. پس از پایان کتاب، یک `BOOK_COMPLETION_REPORT` شامل آموخته‌ها، ایده‌های ردشده، آزمایش‌های پیشنهادی و خلأهای باقی‌مانده تولید شود.

## زمان‌بندی Source Monitor

- **Real-time data:** WebSocket و API بازار، بدون LLM.
- **روزانه:** Listing/Delisting، Catalyst، API Changelog، پروژه‌های جدید، خطاهای داده.
- **هفتگی:** مقاله‌ها، Release Notes، CMT/Coinbase/CoinGecko/CFA/NBER/arXiv.
- **ماهانه:** بازبینی وزن Ruleها، Source Credibility، Memory Expiry و Research Backlog.
- **فصلی:** مرور دوبارهٔ کتاب‌ها و مقایسه با رفتار جدید بازار.

## مسئولیت‌ها در چرخهٔ یادگیری

```text
Source Monitor (Python)
→ Research Agent
→ Engine-specific Agent
→ E22 Research Director
→ E18 Backtest/Paper
→ E20 Post-Trade Review
→ E21 Memory Curator
→ E23 Audit
```

## قانون نهایی

هدف «جمع‌کردن بیشترین مقاله» نیست. هدف ساختن کمترین تعداد Lesson با بیشترین شواهد، قابلیت بازتولید و اثر واقعی روی Paper/Shadow است.
