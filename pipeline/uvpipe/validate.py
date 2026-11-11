"""Pre-publish checks. Raise ValidationError; the job then does not push."""
import datetime as dt
import re

from .build import SCHEMA_V, STEPS

MAX_UVI = 25.0
MAX_CITIES = 500  # installed apps reject more (ForecastValidation.kt)
RUN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}Z$")
GEN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
START_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z$")


class ValidationError(Exception):
    pass


def _need(cond, msg):
    if not cond:
        raise ValidationError(msg)


def _series(a, scale, what):
    _need(isinstance(a, list) and len(a) == STEPS, f"{what}: need {STEPS} hours")
    for v in a:
        _need(isinstance(v, (int, float)) and not isinstance(v, bool),
              f"{what}: non-numeric")
        _need(0 <= v <= MAX_UVI * scale, f"{what}: value {v} out of range")


def _head(doc, name):
    _need(doc.get("v") == SCHEMA_V, f"{name}: v must be {SCHEMA_V}")
    _need(RUN_RE.match(str(doc.get("run"))) is not None, f"{name}: bad run")
    _need(GEN_RE.match(str(doc.get("gen"))) is not None, f"{name}: bad gen")
    _need(START_RE.match(str(doc.get("start"))) is not None, f"{name}: bad start")
    _need(doc.get("step_h") == 1, f"{name}: step_h must be 1")
    _need(isinstance(doc.get("attr"), str) and doc["attr"], f"{name}: attr missing")


def validate(cities_doc, grid_doc, published_run=None):
    """Schema, ranges and hour coverage; `run` must be newer than `published_run`."""
    _head(cities_doc, "cities")
    _head(grid_doc, "grid")
    for k in ("run", "gen", "start"):
        _need(cities_doc[k] == grid_doc[k], f"cities/grid {k} differ")

    cs = cities_doc.get("cities")
    _need(isinstance(cs, list) and len(cs) > 0, "cities empty")
    _need(len(cs) <= MAX_CITIES, f"too many cities: {len(cs)} > {MAX_CITIES}")
    _need(len({c["id"] for c in cs}) == len(cs), "duplicate city id")
    for c in cs:
        w = f"city {c.get('id')}"
        for k in ("id", "name", "lat", "lon", "tz", "uvi", "uvi_cs", "peak"):
            _need(k in c, f"{w}: missing {k}")
        _series(c["uvi"], 1, w + " uvi")
        _series(c["uvi_cs"], 1, w + " uvi_cs")
        _need(c["peak"]["uvi"] == max(c["uvi"]), f"{w}: peak mismatch")
        i = c["uvi"].index(max(c["uvi"]))
        want = (dt.datetime.strptime(cities_doc["start"], "%Y-%m-%dT%H:%MZ")
                + dt.timedelta(hours=i)).strftime("%Y-%m-%dT%H:%MZ")
        _need(c["peak"].get("t") == want, f"{w}: peak.t is not the hour of the peak")
        _need(c["peak"]["uvi"] > 0, f"{w}: no daylight UV in the forecast")

    cells = grid_doc.get("cells")
    ny, nx = grid_doc.get("ny"), grid_doc.get("nx")
    _need(isinstance(cells, list) and cells, "grid cells empty")
    _need(all(a < b for a, b in zip(cells, cells[1:])), "cells not ascending")
    _need(0 <= cells[0] and cells[-1] < ny * nx, "cell index out of grid")
    _need(grid_doc.get("dlat") < 0 < grid_doc.get("dlon"), "bad grid steps")
    for key in ("uvi_x10", "uvi_cs_x10"):
        rows = grid_doc.get(key)
        _need(isinstance(rows, list) and len(rows) == STEPS, f"{key}: need {STEPS} hours")
        for row in rows:
            _need(len(row) == len(cells), f"{key}: row length != cells")
            for v in row:
                _need(type(v) is int and 0 <= v <= MAX_UVI * 10, f"{key}: bad value {v}")
    _need(any(v > 0 for row in grid_doc["uvi_x10"] for v in row), "grid is all zero")

    if published_run is not None:
        _need(cities_doc["run"] > published_run,
              f"run {cities_doc['run']} not newer than published {published_run}")
