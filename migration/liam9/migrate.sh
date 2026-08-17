#!/bin/bash
# مهاجرت لیام تریدر ۹ به ریپوی مستقل — از داخل کلونِ ریپوی جدید اجرا شود.
# استفاده:  bash migration-from-old/migrate.sh   یا مستقیم بعد از دانلود.
set -e
OLD="https://github.com/Auraliam18/.sognal.git"
SRC="$(mktemp -d)"
echo "── دریافت سورس از ریپوی قدیمی…"
git clone --depth 1 "$OLD" "$SRC"

echo "── کپی استک لیام تریدر ۹ (بدون تاریخچهٔ مشترک)…"
rsync -a "$SRC"/ ./ \
  --exclude .git --exclude migration --exclude workflows-disabled \
  --exclude hamid.html --exclude signal-room-v4.html \
  --exclude "brain/cases/*"
# پرونده‌های معاملهٔ مشترک قدیمی نمی‌آیند — قانون ۹ حمید: دفترهای جدا؛
# دفتر معاملهٔ این پنل از صفرِ خودش شروع می‌شود.
mkdir -p brain/cases

echo "── جداسازی هویتی…"
cat >> CLAUDE.md <<'SEP'

## استقلال کامل (مهاجرت ۱۷ اوت)

این ریپو خانهٔ انحصاری «لیام تریدر ۹» است. ریپوی قدیمی (.sognal) متعلق
به پنل دیگر است — از این پس هیچ خواندن/نوشتنی آن‌جا انجام نمی‌شود و
نتیجه‌گیری‌هایش مرجع نیست. برند، دفترها، حافظه و سیگنال‌ها همه از صفرِ
همین‌جا.
SEP

echo "── کامیت و پوش…"
git add -A
git commit -m "مهاجرت لیام تریدر ۹ — استک کامل، مستقل از پنل قدیمی"
git push -u origin main

echo ""
echo "✅ مهاجرت تمام. دو کار دستی باقی است:"
echo "  1) Settings → Secrets → Actions: TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID"
echo "  2) Settings → Pages → روشن کردن"
