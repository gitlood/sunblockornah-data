#!/bin/sh
# Run the CAMS job; OUT is the published-data dir (gh-pages clone), v1/ files are written in place.
# No git and no repo token: the publish job pushes afterwards (push.sh).
# Env: OUT (required), optional CDSAPI_URL/CDSAPI_KEY, FORCE=true.
# Exit 0 = new files written or nothing to do; else nothing was written.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${OUT:?OUT (published data dir) missing}
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
