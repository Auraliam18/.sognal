"""اجتماع دفتر ضدتکرار ارسال — برای تلاش‌های تکراری push در زنجیره.

دفتر sent.json حافظهٔ ضدتکرار تلگرام است؛ اگر بعد از reset گم شود، سیگنال
تکراری می‌رود (همان دردی که حمید بارها گفت). قاعده: برای هر کلید، جدیدترین
مُهر زمانی می‌ماند — از هر دو نسخه.

    python3 -m hamid.merge_sent <snapshot.json> <target.json>
"""
import json
import sys
from pathlib import Path


def merge(snap_path, target_path):
    snap = Path(snap_path)
    target = Path(target_path)
    if not snap.exists():
        return 0
    a = json.loads(snap.read_text() or "{}")
    try:
        b = json.loads(target.read_text() or "{}")
    except Exception:                                # noqa: BLE001
        b = {}
    n = 0
    for k, v in a.items():
        if not isinstance(v, (int, float)):
            continue
        if v >= b.get(k, 0):
            b[k] = v
            n += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(b, indent=1))
    return n


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: merge_sent.py <snapshot.json> <target.json>")
    print(f"sent.json merged: {merge(sys.argv[1], sys.argv[2])} keys kept")
