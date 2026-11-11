#!/bin/sh
# Run the CAMS job in the data repo checkout, writing v1/ files in place. No git, no
# repo token: the workflow commits and pushes afterwards (push.sh).
# Env: optional CDSAPI_URL/CDSAPI_KEY, FORCE=true, OUT (default: repo root).
# Exit 0 = new files written or nothing to do; else nothing was written.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${OUT:-$(cd "$HERE/.." && pwd)}
# Empty secrets must not shadow ~/.cdsapirc.
[ -n "${CDSAPI_URL:-}" ] && [ -n "${CDSAPI_KEY:-}" ] || unset CDSAPI_URL CDSAPI_KEY
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
trap 'exit 1' INT TERM
PY=${PYTHON:-python3}
FORCE_ARG=
[ "${FORCE:-}" = "true" ] && FORCE_ARG=--force

rc=1
for attempt in 1 2 3; do
  rc=0
  (cd "$HERE" && "$PY" -m uvpipe.job --out "$OUT" --work "$W/work" $FORCE_ARG) || rc=$?
  [ "$rc" -ne 1 ] && break   # only fetch/network failures (1) are retried
  echo "job attempt $attempt failed" >&2
  [ "$attempt" -lt 3 ] && sleep 900
done
[ "$rc" -eq 3 ] && { echo "nothing new to publish"; exit 0; }
[ "$rc" -eq 0 ] || exit 1
