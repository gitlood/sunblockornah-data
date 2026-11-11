"""Fetch one CAMS run (UV total + clear sky, 96 leads, AU/NZ box) from the ADS.

Credentials: CDSAPI_URL / CDSAPI_KEY from the environment when both are set,
else ~/.cdsapirc (cdsapi default). The key is never printed or logged.
"""
import datetime as dt
import os
import time
import zipfile

DATASET = "cams-global-atmospheric-composition-forecasts"
AREA = [-9, 112, -48, 179]  # N, W, S, E
LEADS = 96
RUN_HOURS = (0, 12)
# A run is normally on the ADS about 9-10 h after its nominal time.
AVAILABILITY_LAG = dt.timedelta(hours=9)


class RunNotAvailable(Exception):
    pass


def candidate_runs(now, count=3):
    """Newest-first runs (UTC datetimes at 00/12) that should be published by `now`."""
    t = now.astimezone(dt.timezone.utc) - AVAILABILITY_LAG
    t = t.replace(minute=0, second=0, microsecond=0)
    t = t.replace(hour=max(h for h in RUN_HOURS if h <= t.hour))
    out = []
    for _ in range(count):
        out.append(t)
        t -= dt.timedelta(hours=12)
    return out


def run_label(run):
    return run.strftime("%Y-%m-%dT%HZ")


def request_for(run):
    return {
        "variable": ["uv_biologically_effective_dose",
                     "uv_biologically_effective_dose_clear_sky"],
        "date": [run.strftime("%Y-%m-%d")],
        "time": [run.strftime("%H:00")],
        "leadtime_hour": [str(h) for h in range(LEADS)],
        "type": ["forecast"],
        "area": AREA,
        "data_format": "netcdf_zip",
    }


def _client():
    import cdsapi
    url, key = os.environ.get("CDSAPI_URL"), os.environ.get("CDSAPI_KEY")
    if url and key:
        return cdsapi.Client(url=url, key=key, quiet=True, wait_until_complete=False,
                             delete=False)
    return cdsapi.Client(quiet=True, wait_until_complete=False, delete=False)


def fetch_run(run, work_dir, timeout_s=3 * 3600, poll_s=15):
    """Download one run and return the path of the extracted netCDF."""
    os.makedirs(work_dir, exist_ok=True)
    zip_path = os.path.join(work_dir, "run.zip")
    try:
        result = _client().retrieve(DATASET, request_for(run))
        deadline = time.time() + timeout_s
        while True:
            result.update()
            state = result.reply["state"]
            if state == "completed":
                break
            if state == "failed":
                raise RunNotAvailable(f"CAMS request failed for {run_label(run)}")
            if time.time() > deadline:
                raise TimeoutError("CAMS request timed out")
            time.sleep(poll_s)
        result.download(zip_path)
    except RunNotAvailable:
        raise
    except Exception as e:  # never echo request headers or the key
        if "no data" in str(e).lower() or "not available" in str(e).lower():
            raise RunNotAvailable(run_label(run)) from None
        raise RuntimeError(f"CAMS fetch failed: {type(e).__name__}") from None
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if n.endswith(".nc")]
        if not names:
            raise RuntimeError("CAMS zip holds no netCDF")
        z.extract(names[0], work_dir)
    return os.path.join(work_dir, names[0])
