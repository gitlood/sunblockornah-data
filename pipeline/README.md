# UV pipeline

Builds the schema v1 files in `v1/` from the CAMS global forecast (AU/NZ, 96 h) and publishes
them by committing to `main` (served by GitHub Pages). Runs on GitHub-hosted `ubuntu-latest`.

## Workflows
- `uv-pipeline.yml`: cron every 3 h plus manual dispatch. `uvpipe.check` (no secrets, no network)
  decides whether to run the full job: a newer CAMS run is expected, published city ids differ
  from `uvpipe/cities.py`, nothing is published, or the `force` input is set. `publish.sh` runs
  the job (CDSAPI secrets only in that step); `push.sh` commits and pushes with `GITHUB_TOKEN`
  (`contents: write`, only in that step). A missed cron is picked up on the next tick.
- `stale-check.yml`: daily; fails (GitHub emails the owner) when live `cities.json` `gen` is over
  18 h old. Test the alarm: Run workflow with `simulate_stale = true`; the run must go red.
- `ci.yml`: offline tests on pull requests (read-only token, no secrets).

## Setup (repo owner)
Repository secrets: `CDSAPI_URL`, `CDSAPI_KEY`. Keep the interaction limit at collaborators only.
Workflows that use secrets run only on `schedule` / `workflow_dispatch`, never on `pull_request`.

## Local
`make test` (hash-pinned venv, offline). Golden files: `UPDATE_GOLDEN=1 make test`.
The place list `uvpipe/cities.py` is mirrored in the app repo (`BundledCities.kt` and a fixture);
change both together.
