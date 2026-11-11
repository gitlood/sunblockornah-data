"""Turn one CAMS run (xarray Dataset) into the schema v1 documents."""
import json

import numpy as np

from .cities import CITIES

SCHEMA_V = 1
STEPS = 96  # 4 days; the app accepts 48..96 (ForecastValidation.kt)
UVI_PER_UVBED = 40  # UV biologically effective dose (W m-2) x 40 = UVI
ATTR = ("Contains modified Copernicus Atmosphere Monitoring Service "
        "information 2026")


def _iso_min(v):
    return np.datetime_as_string(v, unit="m") + "Z"


def select_run(ds, index=-1):
    if "forecast_reference_time" in ds.dims:
        ds = ds.isel(forecast_reference_time=index)
    return ds


def build_files(ds, mask, gen, cities=None):
    """Return (cities_doc, grid_doc). `ds` holds one run; `gen` is an ISO UTC string."""
    cities = CITIES if cities is None else cities
    ds = select_run(ds)
    if ds.sizes["forecast_period"] != STEPS:
        raise ValueError(f"expected {STEPS} lead hours")
    run = np.datetime_as_string(ds.forecast_reference_time.values, unit="h") + "Z"
    valid = ds.valid_time.values
    start = _iso_min(valid[0])
    if (np.diff(valid) != np.timedelta64(1, "h")).any():
        raise ValueError("valid_time is not hourly")
    lat, lon = ds.latitude.values, ds.longitude.values
    if (len(lat) != mask["ny"] or len(lon) != mask["nx"]
            or abs(lat[0] - mask["lat0"]) > 1e-3 or abs(lon[0] - mask["lon0"]) > 1e-3):
        raise ValueError("CAMS grid does not match the committed land mask")

    uvi = (ds.uvbed * UVI_PER_UVBED).clip(min=0)
    uvi_cs = (ds.uvbedcs * UVI_PER_UVBED).clip(min=0)
    uvi = uvi.transpose("forecast_period", "latitude", "longitude").values
    uvi_cs = uvi_cs.transpose("forecast_period", "latitude", "longitude").values

    out = []
    for cid, (name, clat, clon, tz, _pop) in cities.items():
        iy = int(np.abs(lat - clat).argmin())
        ix = int(np.abs(lon - clon).argmin())
        p, c = uvi[:, iy, ix], uvi_cs[:, iy, ix]
        p, c = [round(float(v), 1) for v in p], [round(float(v), 1) for v in c]
        i = p.index(max(p))  # earliest hour of the max *rounded* value
        out.append({"id": cid, "name": name, "lat": clat, "lon": clon, "tz": tz,
                    "uvi": p, "uvi_cs": c,
                    "peak": {"t": _iso_min(valid[i]), "uvi": p[i]}})
    head = {"v": SCHEMA_V, "run": run, "gen": gen, "start": start, "step_h": 1,
            "attr": ATTR}
    cities_doc = {**head, "cities": out}

    cells = np.asarray(mask["cells"], dtype=np.int64)
    flat = lambda a: np.rint(a.reshape(STEPS, -1)[:, cells] * 10).astype(int).tolist()
    grid_doc = {**head, "lat0": mask["lat0"], "lon0": mask["lon0"],
                "dlat": mask["dlat"], "dlon": mask["dlon"],
                "ny": mask["ny"], "nx": mask["nx"], "cells": cells.tolist(),
                "uvi_x10": flat(uvi), "uvi_cs_x10": flat(uvi_cs)}
    return cities_doc, grid_doc


def dumps(doc):
    return json.dumps(doc, separators=(",", ":"), allow_nan=False)
