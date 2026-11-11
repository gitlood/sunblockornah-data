"""Pipeline tests: no network. Also writes/checks the golden v1 files for the client."""
import copy
import datetime as dt
import json
import os

import numpy as np
import pytest
import xarray as xr

from uvpipe import check, fetch, job, stale
from uvpipe.build import STEPS, build_files, dumps
from uvpipe.cities import CITIES
from uvpipe.validate import ValidationError, validate

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "v1")
GEN = "2026-11-06T22:40:00Z"
GOLDEN_CITIES = {k: CITIES[k] for k in ("syd", "per", "akl")}
LAT0, LON0, NY, NX = -9.2, 112.0, 98, 168


def synthetic_ds(run="2026-11-06T12:00"):
    t0 = np.datetime64(run)
    lat = LAT0 - 0.4 * np.arange(NY)
    lon = LON0 + 0.4 * np.arange(NX)
    hours = np.arange(STEPS)
    utc_h = (t0.astype("datetime64[h]").astype(int) % 24 + hours) % 24
    # Daylight bump at local solar noon (lon / 15 h east of UTC), smaller towards the pole.
    solar = (utc_h[:, None] + lon[None, :] / 15.0 - 12.0) % 24 - 12.0
    day = np.clip(np.cos(solar / 6.0 * np.pi / 2.0), 0, None)
    scale = np.cos(np.radians(lat))[:, None] ** 2
    cs = 0.3 * day[:, None, :] * scale[None]
    tot = cs * 0.8
    valid = t0 + hours.astype("timedelta64[h]")
    dims = ("forecast_period", "forecast_reference_time", "latitude", "longitude")
    return xr.Dataset(
        {"uvbed": (dims, tot[:, None].astype("float32")),
         "uvbedcs": (dims, cs[:, None].astype("float32"))},
        coords={"forecast_period": hours.astype("timedelta64[h]").astype("timedelta64[ns]"),
                "forecast_reference_time": [t0],
                "valid_time": (("forecast_reference_time", "forecast_period"), valid[None]),
                "latitude": lat, "longitude": lon})


FULL_MASK = job.load_mask()


def small_mask():
    full = FULL_MASK
    idx = [int(np.abs(full["lat0"] + full["dlat"] * np.arange(NY) - c[1]).argmin()) * NX
           + int(np.abs(full["lon0"] + full["dlon"] * np.arange(NX) - c[2]).argmin())
           for c in GOLDEN_CITIES.values()]
    cells = sorted({i + d for i in idx for d in (0, 1, NX)})
    return {**full, "cells": cells}


def golden_docs():
    return build_files(synthetic_ds(), small_mask(), GEN, GOLDEN_CITIES)


# ---- golden fixtures (feeds #9 client tests) ----
@pytest.mark.parametrize("name,i", [("cities.json", 0), ("grid.json", 1)])
def test_golden_v1_files_match_committed(name, i):
    text = dumps(golden_docs()[i]) + "\n"
    path = os.path.join(GOLDEN, name)
    if os.environ.get("UPDATE_GOLDEN"):
        os.makedirs(GOLDEN, exist_ok=True)
        open(path, "w").write(text)
    assert open(path).read() == text, "golden drifted; rerun with UPDATE_GOLDEN=1 and commit"


# ---- schema and content ----
def test_schema_v1_fields_and_hourly_values():
    c, g = golden_docs()
    for d in (c, g):
        assert d["v"] == 1 and d["step_h"] == 1 and d["run"] == "2026-11-06T12Z"
        assert d["gen"] == GEN and d["start"] == "2026-11-06T12:00Z" and d["attr"]
    for city in c["cities"]:
        assert len(city["uvi"]) == len(city["uvi_cs"]) == STEPS
        assert city["peak"]["uvi"] == max(city["uvi"])
        i = city["uvi"].index(city["peak"]["uvi"])
        hour = dt.datetime(2026, 11, 6, 12) + dt.timedelta(hours=i)
        assert city["peak"]["t"] == hour.strftime("%Y-%m-%dT%H:00Z")
    assert len(g["uvi_x10"]) == len(g["uvi_cs_x10"]) == STEPS
    assert all(len(r) == len(g["cells"]) for r in g["uvi_x10"])
    validate(c, g)


def test_peak_is_earliest_hour_of_max_rounded_value():
    # Two hours round to the same 10.0 but the later one is larger unrounded.
    ds = synthetic_ds()
    full = FULL_MASK
    lats = full["lat0"] + full["dlat"] * np.arange(NY)
    lons = full["lon0"] + full["dlon"] * np.arange(NX)
    _, la, lo = CITIES["syd"][:3]
    iy, ix = int(np.abs(lats - la).argmin()), int(np.abs(lons - lo).argmin())
    ds["uvbed"][10, 0, iy, ix] = 0.2501
    ds["uvbed"][20, 0, iy, ix] = 0.2504
    c, g = build_files(ds, small_mask(), GEN, GOLDEN_CITIES)
    syd = next(x for x in c["cities"] if x["id"] == "syd")
    assert syd["uvi"][10] == syd["uvi"][20] == 10.0
    assert syd["peak"] == {"t": "2026-11-06T22:00Z", "uvi": 10.0}
    validate(c, g)


def test_clear_sky_not_below_total_sky():
    c, _ = golden_docs()
    for city in c["cities"]:
        assert all(cs >= t for t, cs in zip(city["uvi"], city["uvi_cs"]))


# ---- mask ----
def test_committed_mask_covers_every_city_and_matches_cams_grid():
    m = job.load_mask()
    assert (m["ny"], m["nx"], m["lat0"], m["lon0"]) == (NY, NX, LAT0, LON0)
    cells = m["cells"]
    assert cells == sorted(set(cells)) and 0 <= cells[0] and cells[-1] < NY * NX
    lats = m["lat0"] + m["dlat"] * np.arange(NY)
    lons = m["lon0"] + m["dlon"] * np.arange(NX)
    for cid, (_, la, lo, *_rest) in CITIES.items():
        assert int(np.abs(lats - la).argmin()) * NX + int(np.abs(lons - lo).argmin()) in set(cells), cid


def test_build_rejects_grid_that_differs_from_mask():
    ds = synthetic_ds().isel(latitude=slice(1, None))
    with pytest.raises(ValueError):
        build_files(ds, small_mask(), GEN, GOLDEN_CITIES)


# ---- validation ----
def mutated(fn):
    c, g = golden_docs()
    c, g = copy.deepcopy(c), copy.deepcopy(g)
    fn(c, g)
    return c, g


@pytest.mark.parametrize("fn", [
    lambda c, g: c.update(v=2),
    lambda c, g: c["cities"][0]["uvi"].pop(),
    lambda c, g: c["cities"][0]["uvi"].__setitem__(3, 26.0),
    lambda c, g: c["cities"][0]["uvi"].__setitem__(3, -0.1),
    lambda c, g: g["uvi_x10"].pop(),
    lambda c, g: g["uvi_x10"][5].pop(),
    lambda c, g: g["uvi_cs_x10"][5].__setitem__(0, 300),
    lambda c, g: g["cells"].reverse(),
    lambda c, g: g.update(run="2026-11-06T00Z"),
    lambda c, g: c.update(gen="yesterday"),
    lambda c, g: c["cities"][0].update(uvi=[0.0] * STEPS, peak={"t": "2026-11-06T12:00Z", "uvi": 0.0}),
    lambda c, g: c["cities"][0]["peak"].update(t="2026-11-06T13:00Z"),
    lambda c, g: c.pop("attr"),
    lambda c, g: c.update(cities=[dict(c["cities"][0], id=f"c{i}") for i in range(501)]),
])
def test_validation_rejects(fn):
    c, g = mutated(fn)
    with pytest.raises(ValidationError):
        validate(c, g)


def test_validation_requires_run_newer_than_published():
    c, g = golden_docs()
    validate(c, g, "2026-11-06T00Z")
    for published in ("2026-11-06T12Z", "2026-11-07T00Z"):
        with pytest.raises(ValidationError):
            validate(c, g, published)


# ---- job ----
def test_job_dry_run_writes_publish_tree(tmp_path, monkeypatch):
    nc = tmp_path / "in.nc"
    synthetic_ds().to_netcdf(nc)
    monkeypatch.setattr(job, "load_mask", small_mask)
    monkeypatch.setattr(check, "CITIES", GOLDEN_CITIES)
    monkeypatch.setattr(job, "build_files",
                        lambda ds, m, g: build_files(ds, m, g, GOLDEN_CITIES))
    out = tmp_path / "out"
    assert job.main(["--dry-run", "--out", str(out), "--nc", str(nc)]) == 0
    assert json.load(open(out / "v1" / "cities.json"))["run"] == "2026-11-06T12Z"
    assert (out / "v1" / "grid.json").exists() and (out / ".nojekyll").exists()
    assert "CC-BY-4.0" in (out / "README.md").read_text()
    assert job.published_run(str(out)) == "2026-11-06T12Z"


def test_job_refuses_run_not_newer_than_published(tmp_path, monkeypatch):
    nc = tmp_path / "in.nc"
    synthetic_ds().to_netcdf(nc)
    monkeypatch.setattr(job, "load_mask", small_mask)
    monkeypatch.setattr(check, "CITIES", GOLDEN_CITIES)
    monkeypatch.setattr(job, "build_files",
                        lambda ds, m, g: build_files(ds, m, g, GOLDEN_CITIES))
    out = tmp_path / "out"
    assert job.main(["--dry-run", "--out", str(out), "--nc", str(nc)]) == 0
    before = (out / "v1" / "cities.json").read_text()
    assert job.main(["--out", str(out), "--nc", str(nc)]) == 2
    assert (out / "v1" / "cities.json").read_text() == before


# ---- run selection ----
def test_candidate_runs_newest_first():
    now = dt.datetime(2026, 11, 7, 11, 30, tzinfo=dt.timezone.utc)
    assert [fetch.run_label(r) for r in fetch.candidate_runs(now)] == [
        "2026-11-07T00Z", "2026-11-06T12Z", "2026-11-06T00Z"]
    now = dt.datetime(2026, 11, 6, 23, 30, tzinfo=dt.timezone.utc)
    assert fetch.run_label(fetch.candidate_runs(now)[0]) == "2026-11-06T12Z"


def test_request_has_96_leads_and_both_variables():
    r = fetch.request_for(dt.datetime(2026, 11, 7, 12, tzinfo=dt.timezone.utc))
    assert len(r["leadtime_hour"]) == STEPS == 96 and len(r["variable"]) == 2
    assert r["time"] == ["12:00"] and r["date"] == ["2026-11-07"]


# ---- place list (#108) ----
def in_region(la, lo):
    """Mirror of RegionBounds.kt."""
    box = lambda a, b, c, d: a <= la <= b and c <= lo <= d
    inc = (box(-44.0, -10.5, 113.0, 154.0) or box(-31.8, -31.4, 158.9, 159.3)
           or box(-47.5, -34.0, 166.0, 178.7) or box(-44.5, -43.5, -177.2, -175.5))
    return inc and not (box(-12.0, 0.0, 118.0, 129.0) or box(-12.5, 0.0, 144.0, 154.0))


def test_place_list_is_about_300_sorted_unique_in_region_towns():
    assert 250 <= len(CITIES) <= 350
    pops = [v[4] for v in CITIES.values()]
    assert pops == sorted(pops, reverse=True)
    assert len({v[0:3] for v in CITIES.values()}) == len(CITIES)
    for cid, (name, la, lo, tz, pop) in CITIES.items():
        assert cid.replace("_", "").isalnum() and cid == cid.lower(), cid
        assert in_region(la, lo), name
        assert tz in {"Pacific/Auckland", "Australia/Sydney", "Australia/Melbourne", "Australia/Brisbane",
                      "Australia/Perth", "Australia/Adelaide", "Australia/Darwin", "Australia/Hobart",
                      "Australia/Broken_Hill", "Australia/Lord_Howe"}, (name, tz)
        assert pop >= 100 and (pop >= 5000 or cid in ("ldh", "lau")), name


def test_500_cities_is_the_most_the_apps_accept():
    c, g = mutated(lambda c, g: c.update(cities=[dict(c["cities"][0], id=f"c{i}") for i in range(500)]))
    validate(c, g)


def test_every_place_has_a_land_mask_cell():
    cells = set(FULL_MASK["cells"])
    lats = FULL_MASK["lat0"] + FULL_MASK["dlat"] * np.arange(NY)
    lons = FULL_MASK["lon0"] + FULL_MASK["dlon"] * np.arange(NX)
    missing = [v[0] for v in CITIES.values()
               if int(np.abs(lats - v[1]).argmin()) * NX + int(np.abs(lons - v[2]).argmin()) not in cells]
    assert missing == []


def test_edge_towns_pass_region_bounds_and_the_mask():
    """The extreme town in each direction, plus Lord Howe, must be in the region and have data."""
    ps = list(CITIES.values())
    edges = {"north": min(ps, key=lambda v: -v[1]), "south": min(ps, key=lambda v: v[1]),
             "east": max(ps, key=lambda v: v[2] if v[2] > 0 else -999),
             "west": min(ps, key=lambda v: v[2] if v[2] > 0 else 999),
             "lord howe": CITIES["ldh"]}
    cells = set(FULL_MASK["cells"])
    lats = FULL_MASK["lat0"] + FULL_MASK["dlat"] * np.arange(NY)
    lons = FULL_MASK["lon0"] + FULL_MASK["dlon"] * np.arange(NX)
    for side, v in edges.items():
        assert in_region(v[1], v[2]), (side, v[0])
        assert int(np.abs(lats - v[1]).argmin()) * NX + int(np.abs(lons - v[2]).argmin()) in cells, (side, v[0])


def test_full_place_list_builds_and_validates():
    c, g = build_files(synthetic_ds(), job.load_mask(), GEN)
    validate(c, g)
    assert len(c["cities"]) == len(CITIES)


def test_cities_json_stays_inside_the_download_budget():
    # Measured with 270 places: 144 KB raw, 16 KB gzip. cities.json is fetched on every refresh, so budget
    # 250 KB raw / 40 KB gzip (the app's cellular cost for the file that matters on each open).
    import gzip
    c, _ = build_files(synthetic_ds(), job.load_mask(), GEN)
    raw = dumps(c).encode()
    assert len(raw) < 250_000, len(raw)
    assert len(gzip.compress(raw)) < 40_000


# ---- gate (check.py) and rebuild on city change ----
NOW = dt.datetime(2026, 11, 7, 11, 30, tzinfo=dt.timezone.utc)  # newest expected run: 2026-11-07T00Z


def publish(tmp_path, monkeypatch, run, ids=None):
    v1 = tmp_path / "v1"
    v1.mkdir(exist_ok=True)
    ids = list(GOLDEN_CITIES) if ids is None else ids
    (v1 / "cities.json").write_text(json.dumps({"run": run, "cities": [{"id": i} for i in ids]}))
    monkeypatch.setattr(check, "CITIES", GOLDEN_CITIES)
    return str(tmp_path)


def test_gate_changed_list_runs_even_when_run_is_current(tmp_path, monkeypatch):
    out = publish(tmp_path, monkeypatch, "2026-11-07T00Z", ids=["syd", "per"])
    run, why = check.should_run(out, NOW)
    assert run and "city ids differ" in why


def test_gate_unchanged_list_and_current_run_skips(tmp_path, monkeypatch):
    out = publish(tmp_path, monkeypatch, "2026-11-07T00Z")
    assert check.should_run(out, NOW)[0] is False
    # One tick later, still nothing new before the 12Z run is due (12Z + 9 h = 21:00Z).
    assert check.should_run(out, NOW + dt.timedelta(hours=9))[0] is False


def test_gate_newer_run_expected_runs(tmp_path, monkeypatch):
    out = publish(tmp_path, monkeypatch, "2026-11-07T00Z")
    run, why = check.should_run(out, NOW + dt.timedelta(hours=10))  # 21:30Z: 12Z run due
    assert run and "2026-11-07T12Z" in why


def test_gate_missed_cron_self_heals_on_next_tick(tmp_path, monkeypatch):
    out = publish(tmp_path, monkeypatch, "2026-11-06T12Z")  # 00Z run was never published
    assert check.should_run(out, NOW)[0] is True


def test_gate_force_and_empty_repo_run(tmp_path, monkeypatch):
    out = publish(tmp_path, monkeypatch, "2026-11-07T00Z")
    assert check.should_run(out, NOW, force=True)[0] is True
    assert check.should_run(str(tmp_path / "nothing"), NOW)[0] is True


def test_gate_writes_github_output(tmp_path, monkeypatch):
    out = publish(tmp_path, monkeypatch, "2026-11-07T00Z")
    gh = tmp_path / "gh_out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(gh))
    check.main(["--out", out], now=NOW)
    check.main(["--out", out, "--force"], now=NOW)
    assert gh.read_text().split() == ["run=false", "run=true"]


def test_job_rebuilds_same_run_when_city_list_changed(tmp_path, monkeypatch):
    nc = tmp_path / "in.nc"
    synthetic_ds().to_netcdf(nc)
    monkeypatch.setattr(job, "load_mask", small_mask)
    monkeypatch.setattr(job, "build_files", lambda ds, m, g: build_files(ds, m, g, GOLDEN_CITIES))
    out = tmp_path / "out"
    monkeypatch.setattr(check, "CITIES", GOLDEN_CITIES)
    assert job.main(["--dry-run", "--out", str(out), "--nc", str(nc)]) == 0
    # City list grows: same run is rebuilt instead of "up to date".
    monkeypatch.setattr(check, "CITIES", {**GOLDEN_CITIES, "zzz": GOLDEN_CITIES["syd"]})
    assert job.rebuild_needed(str(out)) is True
    assert job.main(["--out", str(out), "--nc", str(nc)]) == 0


def test_job_force_rebuilds_same_run(tmp_path, monkeypatch):
    nc = tmp_path / "in.nc"
    synthetic_ds().to_netcdf(nc)
    monkeypatch.setattr(job, "load_mask", small_mask)
    monkeypatch.setattr(job, "build_files", lambda ds, m, g: build_files(ds, m, g, GOLDEN_CITIES))
    monkeypatch.setattr(check, "CITIES", GOLDEN_CITIES)
    out = tmp_path / "out"
    assert job.main(["--dry-run", "--out", str(out), "--nc", str(nc)]) == 0
    assert job.main(["--out", str(out), "--nc", str(nc)]) == 2
    assert job.main(["--out", str(out), "--nc", str(nc), "--force"]) == 0


# ---- stale alarm (stale.py) ----
def gen_ago(h):
    return (NOW - dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_stale_fresh_data_is_ok():
    assert stale.check({"run": "2026-11-07T00Z", "gen": gen_ago(11)}, NOW)[0] is True
    assert stale.check({"run": "x", "gen": gen_ago(18)}, NOW)[0] is True


def test_stale_data_over_18h_fails():
    ok, msg = stale.check({"run": "2026-11-06T00Z", "gen": gen_ago(18.1)}, NOW)
    assert ok is False and "18" in msg


def test_stale_malformed_or_future_fails():
    assert stale.check({"run": "x"}, NOW)[0] is False
    assert stale.check({"run": "x", "gen": "yesterday"}, NOW)[0] is False
    assert stale.check({"run": "x", "gen": gen_ago(-3)}, NOW)[0] is False


def test_stale_main_exit_codes(monkeypatch, capsys):
    monkeypatch.setattr(stale, "fetch_live", lambda url: {"run": "r", "gen": gen_ago(2)})
    assert stale.main([], now=NOW) == 0
    monkeypatch.setattr(stale, "fetch_live", lambda url: {"run": "r", "gen": gen_ago(40)})
    assert stale.main([], now=NOW) == 1
    assert "STALE" in capsys.readouterr().err


def test_stale_simulate_flag_fails_without_network(monkeypatch):
    def boom(url):
        raise AssertionError("must not fetch")
    monkeypatch.setattr(stale, "fetch_live", boom)
    assert stale.main(["--simulate-stale"], now=NOW) == 1


def test_stale_unreachable_site_fails(monkeypatch):
    def down(url):
        raise RuntimeError("cannot fetch")
    monkeypatch.setattr(stale, "fetch_live", down)
    assert stale.main([], now=NOW) == 1
