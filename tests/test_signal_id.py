from datetime import datetime, timezone
import importlib.util
from pathlib import Path


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts/generate_signal_id.py"
    spec = importlib.util.spec_from_file_location("signal_id", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_signal_id_shape_and_uniqueness():
    mod = load_module()
    now = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
    a = mod.generate_signal_id("BTCUSDT", "IBS_PULLBACK_PLUS", now)
    b = mod.generate_signal_id("BTCUSDT", "IBS_PULLBACK_PLUS", now)
    assert a.startswith("LIAM-20260813T120000000Z-BTCUSDT-IBSPULLBACKPLUS-")
    assert a != b
