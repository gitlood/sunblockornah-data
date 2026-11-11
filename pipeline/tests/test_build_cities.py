"""Selection rules of build_cities.py on a small synthetic GeoNames list (no dump needed)."""
import build_cities as bc
from uvpipe.cities import CITIES

# The first 62-city list, frozen: favourites, widgets and alerts store these ids, so none may go or move.
ORIGINAL_62 = {
    "syd": ('Sydney', -33.87, 151.21, 'Australia/Sydney'),
    "mel": ('Melbourne', -37.81, 144.96, 'Australia/Melbourne'),
    "bne": ('Brisbane', -27.47, 153.03, 'Australia/Brisbane'),
    "per": ('Perth', -31.95, 115.86, 'Australia/Perth'),
    "adl": ('Adelaide', -34.93, 138.6, 'Australia/Adelaide'),
    "hba": ('Hobart', -42.88, 147.33, 'Australia/Hobart'),
    "drw": ('Darwin', -12.46, 130.84, 'Australia/Darwin'),
    "cbr": ('Canberra', -35.28, 149.13, 'Australia/Sydney'),
    "ool": ('Gold Coast', -28.02, 153.4, 'Australia/Brisbane'),
    "ntl": ('Newcastle', -32.93, 151.78, 'Australia/Sydney'),
    "wol": ('Wollongong', -34.42, 150.89, 'Australia/Sydney'),
    "mcy": ('Sunshine Coast', -26.65, 153.07, 'Australia/Brisbane'),
    "gee": ('Geelong', -38.15, 144.36, 'Australia/Melbourne'),
    "tsv": ('Townsville', -19.26, 146.82, 'Australia/Brisbane'),
    "cns": ('Cairns', -16.92, 145.77, 'Australia/Brisbane'),
    "twb": ('Toowoomba', -27.56, 151.95, 'Australia/Brisbane'),
    "bal": ('Ballarat', -37.56, 143.85, 'Australia/Melbourne'),
    "bdg": ('Bendigo', -36.76, 144.28, 'Australia/Melbourne'),
    "aby": ('Albury', -36.08, 146.92, 'Australia/Sydney'),
    "lst": ('Launceston', -41.43, 147.14, 'Australia/Hobart'),
    "mky": ('Mackay', -21.14, 149.19, 'Australia/Brisbane'),
    "rok": ('Rockhampton', -23.38, 150.51, 'Australia/Brisbane'),
    "bnk": ('Ballina', -28.87, 153.56, 'Australia/Sydney'),
    "cff": ('Coffs Harbour', -30.3, 153.11, 'Australia/Sydney'),
    "wga": ('Wagga Wagga', -35.12, 147.37, 'Australia/Sydney'),
    "bme": ('Broome', -17.96, 122.24, 'Australia/Perth'),
    "asp": ('Alice Springs', -23.7, 133.88, 'Australia/Darwin'),
    "kta": ('Karratha', -20.74, 116.85, 'Australia/Perth'),
    "kgi": ('Kalgoorlie', -30.75, 121.47, 'Australia/Perth'),
    "bun": ('Bunbury', -33.33, 115.64, 'Australia/Perth'),
    "alb": ('Albany', -35.02, 117.88, 'Australia/Perth'),
    "gex": ('Geraldton', -28.77, 114.61, 'Australia/Perth'),
    "mia": ('Mildura', -34.19, 142.16, 'Australia/Melbourne'),
    "mgb": ('Mount Gambier', -37.83, 140.78, 'Australia/Adelaide'),
    "pla": ('Port Lincoln', -34.72, 135.86, 'Australia/Adelaide'),
    "isa": ('Mount Isa', -20.73, 139.49, 'Australia/Brisbane'),
    "ktr": ('Katherine', -14.47, 132.26, 'Australia/Darwin'),
    "dbo": ('Dubbo', -32.25, 148.6, 'Australia/Sydney'),
    "tmw": ('Tamworth', -31.09, 150.93, 'Australia/Sydney'),
    "oag": ('Orange', -33.28, 149.1, 'Australia/Sydney'),
    "bhq": ('Broken Hill', -31.95, 141.47, 'Australia/Broken_Hill'),
    "bdb": ('Bundaberg', -24.87, 152.35, 'Australia/Brisbane'),
    "hvb": ('Hervey Bay', -25.29, 152.85, 'Australia/Brisbane'),
    "pqq": ('Port Macquarie', -31.43, 152.91, 'Australia/Sydney'),
    "esp": ('Esperance', -33.86, 121.89, 'Australia/Perth'),
    "ldh": ('Lord Howe Island', -31.55, 159.08, 'Australia/Lord_Howe'),
    "akl": ('Auckland', -36.85, 174.76, 'Pacific/Auckland'),
    "wlg": ('Wellington', -41.29, 174.78, 'Pacific/Auckland'),
    "chc": ('Christchurch', -43.53, 172.64, 'Pacific/Auckland'),
    "ham": ('Hamilton', -37.79, 175.28, 'Pacific/Auckland'),
    "trg": ('Tauranga', -37.69, 176.17, 'Pacific/Auckland'),
    "dud": ('Dunedin', -45.87, 170.5, 'Pacific/Auckland'),
    "pmr": ('Palmerston North', -40.35, 175.61, 'Pacific/Auckland'),
    "npe": ('Napier', -39.49, 176.91, 'Pacific/Auckland'),
    "nsn": ('Nelson', -41.27, 173.28, 'Pacific/Auckland'),
    "rot": ('Rotorua', -38.14, 176.25, 'Pacific/Auckland'),
    "npl": ('New Plymouth', -39.06, 174.08, 'Pacific/Auckland'),
    "wre": ('Whangarei', -35.73, 174.32, 'Pacific/Auckland'),
    "ivc": ('Invercargill', -46.41, 168.35, 'Pacific/Auckland'),
    "zqn": ('Queenstown', -45.03, 168.66, 'Pacific/Auckland'),
    "gis": ('Gisborne', -38.66, 178.02, 'Pacific/Auckland'),
    "lau": ('Lauder', -45.04, 169.68, 'Pacific/Auckland'),
}

SYD = ("Sydney", -33.87, 151.21, "Australia/Sydney", 5_000_000)  # big city: 30 km radius
DUBBO = ("Dubbo", -32.25, 148.6, "Australia/Sydney", 40_000)  # normal place: 15 km radius
LEGACY = {"syd": SYD[:4], "dbo": DUBBO[:4]}


def north(base, km_, lon=None):
    """A point km_ south of base (111.2 km per degree of latitude)."""
    return round(base[1] - km_ / 111.2, 4), base[2] if lon is None else lon


def row(name, lat, lon, pop=20_000, tz="Australia/Sydney"):
    return (name, lat, lon, tz, pop)


def names(kept):
    return {v[0] for v in kept.values()}


def sel(*rows):
    return bc.select([SYD, DUBBO, *rows], LEGACY)


def test_floor_is_5000_people():
    kept, _ = sel(row("Tiny", -30.0, 150.0, 4999), row("Just", -30.0, 152.0, 5000))
    assert "Just" in names(kept) and "Tiny" not in names(kept)


def test_normal_spacing_is_15_km():
    kept, _ = sel(row("Near", *north(DUBBO, 14)), row("Far", *north(DUBBO, 16)))
    assert "Near" not in names(kept) and "Far" in names(kept)


def test_big_city_spacing_is_30_km():
    # 20 km from Sydney is a suburb, 31 km is a town; fails if the metro radius drops to 15 km or rises past 31.
    kept, _ = sel(row("Suburb", *north(SYD, 20)), row("Outer", *north(SYD, 31)))
    assert "Suburb" not in names(kept) and "Outer" in names(kept)
    assert (bc.MIN_KM, bc.METRO_KM, bc.METRO_POP, bc.MIN_POP) == (15, 30, 250_000, 5000)


def test_a_place_just_under_a_small_city_uses_the_normal_radius():
    # Population below the metro line: 20 km away is outside the 15 km rule, so it is kept.
    kept, _ = sel(row("Satellite", *north(DUBBO, 20)))
    assert "Satellite" in names(kept)


def test_the_larger_place_wins():
    kept, _ = sel(row("Big", -20.0, 140.0, 50_000), row("Small", -20.05, 140.0, 9_000))
    assert "Big" in names(kept) and "Small" not in names(kept)


def test_keep_list_survives_the_big_city_radius():
    akl = ("Auckland", -36.85, 174.76, "Pacific/Auckland", 1_400_000)
    kept, _ = bc.select([akl, row("Lower Hutt", -36.9, 174.8, 100_000, "Pacific/Auckland"),
                         row("Suburb", -36.9, 174.8, 90_000, "Pacific/Auckland")], {"akl": akl[:4]})
    assert "Lower Hutt" in bc.KEEP
    assert "Lower Hutt" in names(kept) and "Suburb" not in names(kept)


def test_skip_list_removes_non_towns():
    assert "Blue Mountains" in bc.SKIP
    kept, _ = sel(row("Blue Mountains", -20.0, 140.0, 70_000), row("Real Town", -21.0, 140.0, 70_000))
    assert "Blue Mountains" not in names(kept) and "Real Town" in names(kept)


def test_places_outside_the_region_are_dropped_and_reported():
    kept, dropped = sel(row("Kupang", -10.17, 123.6, 300_000))
    assert "Kupang" not in names(kept) and dropped == ["Kupang"]


def test_legacy_ids_are_always_kept():
    kept, _ = sel()
    assert set(LEGACY) <= set(kept)
    kept, _ = bc.select([], {"ldh": ("Lord Howe Island", -31.55, 159.08, "Australia/Lord_Howe")})
    assert kept["ldh"][4] == bc.LEGACY_POP["ldh"]


def test_slug_makes_unique_ids():
    assert bc.slug("Wyndham Vale", {}) == "wyndham_vale"
    assert bc.slug("Hamilton", {"hamilton": 1}) == "hamilton_2"
    assert bc.slug("T\u016brangi", {}) == "turangi"


def test_all_62_original_ids_are_still_in_the_list_unchanged():
    assert len(ORIGINAL_62) == 62
    changed = [k for k, v in ORIGINAL_62.items() if k not in CITIES or CITIES[k][:4] != v]
    assert changed == []


def test_list_is_sorted_by_population_largest_first():
    pops = [v[4] for v in CITIES.values()]
    assert pops == sorted(pops, reverse=True)
