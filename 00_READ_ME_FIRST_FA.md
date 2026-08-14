# اول این فایل را بخوان

این بسته نسخه‌ی 2.1 سیستم AuraLiam369/LIAM است و برای Claude Fable 5 آماده شده است.

## تفاوت دو نوع Skill

1. `.claude/skills/.../SKILL.md`: به Claude Code می‌گوید هر بخش را چگونه بسازد، بررسی کند و تحقیق کند.
2. `runtime/skills/*.yaml`: قرارداد رفتاری Engine/Agent واقعی داخل Runtime Python/LangGraph است.

Claude Code خودش حلقه‌ی ۲۴ساعته‌ی ۲۰۰ ارز نیست. آن حلقه باید با Python اجرا شود.

## محتویات

- 26 Engine Skill
- 26 Claude domain specialist با حافظه‌ی Project و حالت read-only
- 4 Skill مشترک شخصی‌سازی/تحقیق/سیگنال/پولبک بین OBها
- Personalization کامل حمید و قوانین PDF ورژن دو
- معماری 30s event-driven بدون batch barrier
- Lead-Lag/Pump Chain دقیق
- Post-trade learning و Memory promotion
- Chart/Telegram reply contract
- Source curriculum و update routines
- Hooks، validator و tests

## روش تحویل به Claude

1. ZIP را در ریشه‌ی Repository استخراج کن؛ محتویات پوشه باید مستقیماً کنار فایل‌های پروژه قرار گیرد.
2. Claude Code را با Fable 5 در ریشه‌ی Repository باز کن.
3. متن `prompts/CLAUDE_FABLE5_APPLY_NOW_FA.txt` را کامل Paste کن.
4. Claude ابتدا Audit و Gap Matrix می‌سازد؛ سپس مرحله‌ای تغییر می‌دهد.
5. پس از نصب، `/skills` و `/agents` یا `/doctor` برای بررسی Loading اجرا شود.

## تست بسته

```bash
python scripts/validate_skill_package.py
python -m pytest tests/test_package_integrity.py tests/test_signal_id.py
```

## محدودیت فعلی تصاویر

چهار عکس توضیح‌داده‌شده در پیام حمید در این گفتگو ضمیمه نشده‌اند؛ بنابراین تحلیل دقیق «چند کندل تا حرکت اصلی» ساخته نشده است. پروتکل کامل کالیبراسیون در `docs/PULLBACK_BETWEEN_OPPOSING_OB_FA.md` آماده است.
