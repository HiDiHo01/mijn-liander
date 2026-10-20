#!/usr/bin/env bash
set -euo pipefail

# Keep this explicit allowlist aligned with the source-distribution policy:
# PyRIC and mock-open do not publish wheels for the versions used by this lock.
source_distribution_allowlist="pyric,mock-open"

printf 'Allowed source distributions: %s\n' "$source_distribution_allowlist"

# Fail early if the allowlist and the compiled, hash-pinned lock file drift apart.
python - "$source_distribution_allowlist" requirements_test.txt <<'PY'
import re
import sys
from pathlib import Path

allowlist = {
    package.strip().lower().replace("_", "-").replace(".", "-")
    for package in sys.argv[1].split(",")
    if package.strip()
}
requirements_path = Path(sys.argv[2])
requirements = requirements_path.read_text(encoding="utf-8")
locked_packages = {
    name.lower().replace("_", "-").replace(".", "-")
    for name in re.findall(r"(?m)^([A-Za-z0-9][A-Za-z0-9_.-]*)==", requirements)
}
missing = sorted(allowlist - locked_packages)

if missing:
    print(
        f"Source-distribution allowlist entries are not pinned in "
        f"{requirements_path}: {', '.join(missing)}",
        file=sys.stderr,
    )
    sys.exit(1)

print(
    f"Validated source-distribution allowlist against {requirements_path}."
)
PY

python -m pip install \
  --require-hashes \
  --only-binary=:all: \
  --no-binary="$source_distribution_allowlist" \
  -r requirements_test.txt
