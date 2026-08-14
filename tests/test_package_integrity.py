from pathlib import Path
import subprocess
import sys


def test_package_validator_passes():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / "scripts/validate_skill_package.py"), "--repo-root", str(root)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
