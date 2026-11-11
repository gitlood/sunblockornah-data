"""One-off: build mask/au_nz_cells.json from Natural Earth admin-0 countries.

Usage: python build_mask.py ne_50m_admin_0_countries.geojson
Land cells of Australia and New Zealand on the CAMS 0.4 deg grid, buffered by one
cell, plus the nearest cell of every city. Not run by the job or the tests.
"""
import json
import os
import sys

import numpy as np
import shapely
from shapely.geometry import box, shape
from shapely.ops import unary_union

from uvpipe.cities import CITIES

LAT0, LON0, D, NY, NX = -9.2, 112.0, 0.4, 98, 168
KEEP = {"Australia", "New Zealand"}


def main(path):
    feats = json.load(open(path))["features"]
    polys = [shape(f["geometry"]) for f in feats if f["properties"]["ADMIN"] in KEEP]
    region = box(LON0 - 1, LAT0 - NY * D, LON0 + NX * D, LAT0 + 1)
    land = unary_union(polys).intersection(region).buffer(D)
    lats = LAT0 - D * np.arange(NY)
    lons = LON0 + D * np.arange(NX)
    gx, gy = np.meshgrid(lons, lats)
    inside = shapely.contains_xy(land, gx, gy)
    cells = set(np.flatnonzero(inside.ravel()).tolist())
    for _, (_, lat, lon, _, _) in CITIES.items():
        cells.add(int(np.abs(lats - lat).argmin()) * NX + int(np.abs(lons - lon).argmin()))
    doc = {"lat0": LAT0, "lon0": LON0, "dlat": -D, "dlon": D, "ny": NY, "nx": NX,
           "cells": sorted(cells)}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mask", "au_nz_cells.json")
    with open(out, "w") as f:
        json.dump(doc, f, separators=(",", ":"))
    print(len(cells), "cells")


if __name__ == "__main__":
    main(sys.argv[1])
