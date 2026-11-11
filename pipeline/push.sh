#!/bin/sh
# Publish the checkout as ONE orphan commit replacing main (history stays small).
# Input: a checkout whose working tree holds the repo files plus the new v1/ data.
# Uses GITHUB_TOKEN (contents: write) via an HTTP header; the token is never in the
# Python job's environment. Force-push is safe: the concurrency group allows one writer.
set -eu
: "${GITHUB_TOKEN:?GITHUB_TOKEN missing}"
REPO_URL=${REPO_URL:-https://github.com/${GITHUB_REPOSITORY:?GITHUB_REPOSITORY missing}.git}
HDR="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 | tr -d '\n')"
unset GITHUB_TOKEN
gitt() { git -c "http.https://github.com/.extraheader=$HDR" "$@"; }

# Same tree as main except the data files? Then there is nothing to publish.
if [ -z "$(git status --porcelain -- v1 .nojekyll README.md)" ]; then echo "no data changes"; exit 0; fi

git checkout --quiet --orphan publish
git add -A
git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
  commit --quiet -m "UV data $(date -u +%Y-%m-%dT%H:%MZ)"
# Orphan force-push needs no pull/rebase, so a retry is the same command.
for attempt in 1 2 3; do
  gitt push --quiet --force "$REPO_URL" publish:main && { echo "published"; exit 0; }
  echo "push attempt $attempt failed" >&2
  sleep $((attempt * 10))
done
exit 1
