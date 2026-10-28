#!/usr/bin/env bash
# Stage and verify SECA provenance metadata before publishing it; roll back on failure.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import hashlib
import os
import re
from pathlib import Path
import subprocess
import tempfile

root = Path.cwd()
source = root / "experimental"
pin = root / "docker/seca/SOURCE_REVISION"
hashes = root / "docker/seca/SOURCE.sha256"
dockerfile = root / "docker/Dockerfile.app"
def git(*args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()
if git("status", "--porcelain", "--untracked-files=all"):
    raise SystemExit("Refusing provenance update: experimental submodule is dirty; commit it first.")
revision = git("rev-parse", "HEAD")
original = {pin: pin.read_bytes(), hashes: hashes.read_bytes(), dockerfile: dockerfile.read_bytes()}
lines = []
for line in hashes.read_text().splitlines():
    _, filename = line.split("  ", 1)
    path = Path(filename)
    if path.is_absolute() or ".." in path.parts:
        raise SystemExit(f"Invalid hash path: {filename}")
    lines.append(f"{hashlib.sha256((source / path).read_bytes()).hexdigest()}  {filename}\n")
with tempfile.TemporaryDirectory(prefix=".seca-pin-", dir=pin.parent) as tmp:
    staged = Path(tmp)
    new_hashes = staged / "SOURCE.sha256"
    new_hashes.write_text("".join(lines))
    subprocess.run(["sha256sum", "--check", str(new_hashes)], cwd=source, check=True)
    if git("rev-parse", "HEAD") != revision or git("status", "--porcelain", "--untracked-files=all"):
        raise SystemExit("Submodule changed while staging provenance")
    new_pin = staged / "SOURCE_REVISION"
    new_pin.write_text(revision + "\n")
    new_dockerfile = staged / "Dockerfile.app"
    content, replacements = re.subn(r'(org\.risklive\.seca\.source-revision=")[0-9a-f]+(")',
                                   lambda m: m[1] + revision + m[2], dockerfile.read_text())
    if replacements != 1:
        raise SystemExit("Expected exactly one Docker SECA revision label")
    new_dockerfile.write_text(content)
    try:
        os.replace(new_dockerfile, dockerfile)
        os.replace(new_hashes, hashes)
        os.replace(new_pin, pin)
        assert git("rev-parse", "HEAD") == pin.read_text().strip()
        subprocess.run(["sha256sum", "--check", str(hashes)], cwd=source, check=True)
        assert not git("status", "--porcelain", "--untracked-files=all")
    except BaseException:
        for target, content in original.items():
            rollback = staged / target.name
            rollback.write_bytes(content)
            os.replace(rollback, target)
        raise
print(f"SECA pin and listed hashes updated and verified: {revision}")
PY
