#!/bin/sh
# Publish the data files in the CURRENT directory as ONE orphan commit force-pushed to the
# `gh-pages` branch (data only: .nojekyll, README.md, v1/...). Code on main is untouched.
# Run it from an empty scratch dir holding just the data files.
# Uses GITHUB_TOKEN (contents: write) via an HTTP header; the token is never in the
# Python job's environment. Force-push is safe: the concurrency group allows one writer.
set -eu
: "${GITHUB_TOKEN:?GITHUB_TOKEN missing}"
REPO_URL=${REPO_URL:-https://github.com/${GITHUB_REPOSITORY:?GITHUB_REPOSITORY missing}.git}
BRANCH=${BRANCH:-gh-pages}
HDR="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 | tr -d '\n')"
unset GITHUB_TOKEN
gitt() { git -c "http.https://github.com/.extraheader=$HDR" "$@"; }

[ -f v1/cities.json ] && [ -f v1/grid.json ] || { echo "data files missing" >&2; exit 1; }
[ ! -e .git ] || { echo "run in a clean scratch dir" >&2; exit 1; }
git init --quiet -b "$BRANCH"
git add -A
git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
  commit --quiet -m "UV data $(date -u +%Y-%m-%dT%H:%MZ)"
for attempt in 1 2 3; do
  gitt push --quiet --force "$REPO_URL" "$BRANCH:$BRANCH" && { echo "published"; exit 0; }
  echo "push attempt $attempt failed" >&2
  sleep $((attempt * 10))
done
exit 1
