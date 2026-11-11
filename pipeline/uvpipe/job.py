"""CAMS AU/NZ job: fetch, build schema v1, validate, write the publish tree.

Exit codes: 0 wrote new files, 3 nothing newer than the published run and the city
list unchanged, 1 fetch or network failure (retryable), 2 build or validation failure
(not retried). The same run is rebuilt when --force is given or the published city ids
differ from uvpipe.cities.CITIES.
Usage: python -m uvpipe.job --out DIR [--dry-run] [--force] [--nc FILE] [--work DIR]
"""
import argparse
import datetime as dt
import json
import os
import sys
import tempfile
import time

from . import fetch
from .build import build_files, dumps
from .check import published_ids, published_run, rebuild_needed
from .validate import ValidationError, validate

HERE = os.path.dirname(os.path.abspath(__file__))
MASK_PATH = os.path.join(HERE, "..", "mask", "au_nz_cells.json")
README = """# Sunblock or Nah UV data

Static UV forecast files for Australia and New Zealand, read by the Sunblock or
Nah app. Schema v1: `v1/cities.json` and `v1/grid.json`.

Contains modified Copernicus Atmosphere Monitoring Service information 2026.
Source: CAMS global atmospheric composition forecasts, Copernicus / ECMWF,
licensed CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/). Neither the
European Commission nor ECMWF is responsible for any use of this information.
The values are modified: cut to AU/NZ, converted to UV index and rounded.
"""


def load_mask(path=MASK_PATH):
    with open(path) as f:
        return json.load(f)


def write_tree(out_dir, cities_doc, grid_doc):
    v1 = os.path.join(out_dir, "v1")
    os.makedirs(v1, exist_ok=True)
    # grid first, cities last: the client keys off cities.run and checks the pair.
    for name, doc in (("grid.json", grid_doc), ("cities.json", cities_doc)):
        tmp = os.path.join(v1, name + ".tmp")
        with open(tmp, "w") as f:
            f.write(dumps(doc))
        os.replace(tmp, os.path.join(v1, name))
    open(os.path.join(out_dir, ".nojekyll"), "w").close()
    with open(os.path.join(out_dir, "README.md"), "w") as f:
        f.write(README)


def gen_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def acquire(work, attempts=3, now=None):
    """Newest available run -> (label, netCDF path). Falls back to older runs."""
    now = now or dt.datetime.now(dt.timezone.utc)
    last = None
    for run in fetch.candidate_runs(now):
        for n in range(attempts):
            try:
                return fetch.run_label(run), fetch.fetch_run(run, work)
            except fetch.RunNotAvailable as e:
                last = e
                break
            except Exception as e:
                last = e
                print(f"fetch attempt {n + 1} failed: {type(e).__name__}", file=sys.stderr)
                time.sleep(60 * (n + 1))
    raise RuntimeError(f"no CAMS run could be fetched (last error: {type(last).__name__})")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="write to --out only, skip the newer-than-published check")
    ap.add_argument("--force", action="store_true",
                    help="rebuild and publish even when the run is not newer")
    ap.add_argument("--nc", help="use this netCDF instead of fetching")
    ap.add_argument("--work", help="scratch dir for the download")
    a = ap.parse_args(argv)

    import xarray as xr
    pub = None if a.dry_run else published_run(a.out)
    rebuild = a.force or rebuild_needed(a.out)
    work = a.work or tempfile.mkdtemp(prefix="cams-")
    try:
        if a.nc:
            nc = a.nc
        else:
            label, nc = acquire(work)
            if pub is not None and label <= pub and not rebuild:
                print(f"up to date: newest run {label}, published {pub}")
                return 3
    except Exception as e:
        print(f"fetch failed: {type(e).__name__}", file=sys.stderr)
        return 1
    try:
        with xr.open_dataset(nc) as ds:
            cities_doc, grid_doc = build_files(ds.load(), load_mask(), gen_now())
        validate(cities_doc, grid_doc, None if rebuild else pub)
    except ValidationError as e:
        print(f"validation failed: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"build failed: {type(e).__name__}", file=sys.stderr)
        return 2
    write_tree(a.out, cities_doc, grid_doc)
    print(f"wrote run {cities_doc['run']} to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
