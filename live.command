#!/bin/bash
# حلقهٔ زندهٔ حمید — مک: دوبار کلیک کن، همین.
cd "$(dirname "$0")"
git pull --rebase origin main 2>/dev/null
cd claude-liam-signal/python
echo "═══ حلقهٔ زندهٔ حمید — برای توقف: Ctrl+C یا بستن پنجره ═══"
python3 -m hamid.live_service
