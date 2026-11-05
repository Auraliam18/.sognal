"""Bundle changed generated data before uploading; tar accepts the ledger's Unicode names."""
import io
import json
import os
import subprocess
import tarfile
from pathlib import Path

SCOPES = ["brain", "signals", "claude-liam-signal/backtests"]


def git(*args):
    return subprocess.check_output(["git", *args])


def archive(destination):
    try:
        base = git("merge-base", "HEAD", "origin/main").decode().strip()
    except subprocess.CalledProcessError:
        base = git("rev-parse", "HEAD").decode().strip()
    paths = set(git("diff", "--name-only", "-z", base, "--", *SCOPES).split(b"\0"))
    paths.update(git("ls-files", "-o", "--exclude-standard", "-z", "--", *SCOPES).split(b"\0"))
    manifest = {"base": base, "head": git("rev-parse", "HEAD").decode().strip(), "files": [], "absent": []}
    with tarfile.open(destination, "w:gz", compresslevel=1) as tar:
        for raw in sorted(paths - {b""}):
            p = Path(os.fsdecode(raw))
            if p.is_absolute() or ".." in p.parts:
                raise ValueError("unexpected archive path")
            if p.is_symlink() or not p.is_file():
                manifest["absent"].append(p.as_posix())
                continue
            tar.add(p, arcname=p.as_posix(), recursive=False)
            manifest["files"].append(p.as_posix())
        body = json.dumps(manifest, ensure_ascii=False).encode()
        header = tarfile.TarInfo("manifest.json")
        header.size = len(body)
        tar.addfile(header, io.BytesIO(body))
    print(f"archived {len(manifest['files'])} changed output files", flush=True)


if __name__ == "__main__":
    archive(Path(os.environ["RUNNER_TEMP"]) / "unpublished.tar.gz")
