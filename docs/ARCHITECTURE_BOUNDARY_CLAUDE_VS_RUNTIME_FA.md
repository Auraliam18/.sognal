# مرز مسئولیت Claude، Python، LangGraph، n8n و GitHub Actions

## Claude Fable 5

- Lead developer/researcher/auditor
- مناسب کارهای طولانی، طراحی، کدنویسی، Vision و Subagent coordination
- Skills در `.claude/skills/*/SKILL.md` و Subagents در `.claude/agents/` قرار می‌گیرند.
- حافظه‌ی Project برای Subagentها جداست؛ Canonical Trading Memory در Runtime DB باقی می‌ماند.

## Python Runtime

- WebSocket و Top-200
- Indicators/Structure/SMC/Liquidity
- 30s heartbeat + continuous events
- Backtest/Replay/Paper
- Signal chart و Telegram
- Metrics/health/recovery

## LangGraph

- Case orchestration، checkpoint، resume، subgraph و handoff برای تحلیل‌های استدلالی.
- جایگزین Event Bus یا دیتابیس Tick نیست.

## n8n

- Telegram/Webhook/Calendar/Email/report integrations و queue workers.
- نه محاسبه‌ی ۲۰۰ ارز و نه حلقه‌ی ۳۰ثانیه‌ای قیمت.

## GitHub Actions

- CI، تست، release، بک‌فیل محدود و گزارش.
- Schedule رسمی GitHub حداقل ۵ دقیقه است و امکان تأخیر دارد؛ پس برای پایش ۳۰ثانیه‌ای مناسب نیست.

## منابع رسمی

- Anthropic Skills: https://code.claude.com/docs/en/skills
- Anthropic Subagents: https://code.claude.com/docs/en/sub-agents
- Anthropic Memory: https://code.claude.com/docs/en/memory
- Anthropic Hooks: https://code.claude.com/docs/en/hooks
- LangGraph Persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- n8n Queue Mode: https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode
- GitHub schedule: https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions#onschedule
