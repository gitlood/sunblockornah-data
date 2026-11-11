"""Cheap gate: decide whether the full CAMS job needs to run.

Runs with no secrets and no network. Prints the reason and, under GitHub Actions, writes
`run=true|false` to $GITHUB_OUTPUT. Run the job when any of these holds:
  - `--force` (the workflow_dispatch `force` input)
  - nothing is published yet
  - the published city ids differ from uvpipe.cities.CITIES
  - a CAMS run newer than the published one should be available by now
    (clock only: fetch.candidate_runs applies the availability lag)
A missed cron therefore self-heals on the next 3 hourly tick.
Usage: python -m uvpipe.check --out DIR [--force]
"""
import argparse
import datetime as dt
import json
import os
import sys

from . import fetch
from .cities import CITIES


def published_run(out_dir):
    try:
        with open(os.path.join(out_dir, "v1", "cities.json")) as f:
            return json.load(f)["run"]
    except (OSError, ValueError, KeyError):
        return None


def published_ids(out_dir):
    try:
        with open(os.path.join(out_dir, "v1", "cities.json")) as f:
            return {c["id"] for c in json.load(f)["cities"]}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def rebuild_needed(out_dir, force=False):
    """True when the published files must be rebuilt even from the same CAMS run."""
    return force or published_ids(out_dir) != set(CITIES)


def should_run(out_dir, now, force=False):
    """Return (run: bool, reason: str)."""
    if force:
        return True, "force requested"
    pub = published_run(out_dir)
    if pub is None:
        return True, "nothing published yet"
    if published_ids(out_dir) != set(CITIES):
        return True, "published city ids differ from the city list"
    newest = fetch.run_label(fetch.candidate_runs(now)[0])
    if newest > pub:
        return True, f"newer CAMS run expected: {newest} > published {pub}"
    return False, f"up to date: published {pub}, newest expected {newest}"


def main(argv=None, now=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    run, reason = should_run(a.out, now or dt.datetime.now(dt.timezone.utc), a.force)
    print(f"{'RUN' if run else 'SKIP'}: {reason}")
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as f:
            f.write(f"run={'true' if run else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
