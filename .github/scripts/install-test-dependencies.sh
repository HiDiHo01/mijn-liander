#!/usr/bin/env bash
set -euo pipefail

# Keep this explicit allowlist aligned with the source-distribution policy:
# PyRIC and mock-open do not publish wheels for the versions used by this lock.
source_distribution_allowlist="pyric,mock-open"

printf 'Allowed source distributions: %s\n' "$source_distribution_allowlist"
python -m pip install \
  --require-hashes \
  --only-binary=:all: \
  --no-binary="$source_distribution_allowlist" \
  -r requirements_test.txt
