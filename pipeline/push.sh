#!/bin/sh
# Commit the data files the job wrote and push to main with GITHUB_TOKEN (contents: write).
# The token is passed to git only, via an HTTP header; it is never in the job's environment.
set -eu
: "${GITHUB_TOKEN:?GITHUB_TOKEN missing}"
REPO_URL=${REPO_URL:-https://github.com/${GITHUB_REPOSITORY:?GITHUB_REPOSITORY missing}.git}
HDR="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 | tr -d '\n')"
unset GITHUB_TOKEN
gitt() { git -c "http.https://github.com/.extraheader=$HDR" "$@"; }

git add -A v1 .nojekyll README.md
if git diff --cached --quiet; then echo "no data changes"; exit 0; fi
git -c user.name="uv-pipeline" -c user.email="uv-pipeline@users.noreply.github.com" \
  commit --quiet -m "UV data $(date -u +%Y-%m-%dT%H:%MZ)"
for attempt in 1 2 3; do
  gitt push --quiet "$REPO_URL" HEAD:main && { echo "published"; exit 0; }
  gitt pull --quiet --rebase "$REPO_URL" main || exit 1
done
exit 1
