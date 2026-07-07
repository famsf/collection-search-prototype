"""Geocode the aggregated place-of-creation list against an offline gazetteer.

Input:  scripts/places_raw.json   (place, type, n, path[])  — 1,907 rows
Output: public/data/places.ndjson (one JSON object per line, streamable)

Matching cascade per place name:
  1. exact country name / alt-name  -> country centroid
  2. exact city name (largest pop)  -> city coords
  3. continent/region name          -> hand-coded centroid
  4. walk the hierarchy path upward  (Flores -> Southeast Asia -> Asia ...)
Anything still unmatched is written with lat/lng null + matched=false so the
front end can report coverage (that's the point of the experiment).

Run:  uv run --with geonamescache python scripts/geocode_places.py
"""

import json
from pathlib import Path

import geonamescache

HERE = Path(__file__).parent
RAW = HERE / "places_raw.json"
OUT = HERE.parent / "public" / "data" / "places.ndjson"

# Continent / broad-region centroids the gazetteer won't have as "cities".
REGION_CENTROIDS = {
    "World": (20.0, 0.0),
    "Africa": (2.0, 21.0),
    "Europe": (54.0, 15.0),
    "Asia": (34.0, 100.0),
    "North America": (46.0, -100.0),
    "South America": (-15.0, -60.0),
    "Central America": (15.0, -88.0),
    "Oceania": (-22.0, 140.0),
    "Antarctica": (-75.0, 0.0),
    "Southeast Asia": (5.0, 110.0),
    "East Asia": (35.0, 115.0),
    "South Asia": (22.0, 78.0),
    "Central Asia": (43.0, 68.0),
    "Western Asia": (33.0, 44.0),
    "Middle East": (29.0, 45.0),
    "Near East": (33.0, 40.0),
    "Caribbean": (18.0, -73.0),
    "West Africa": (10.0, -5.0),
    "East Africa": (0.0, 37.0),
    "North Africa": (28.0, 15.0),
    "Central Africa": (2.0, 20.0),
    "Southern Africa": (-26.0, 26.0),
    "Scandinavia": (63.0, 15.0),
    "Mesoamerica": (17.0, -92.0),
    "Andes": (-13.0, -72.0),
    "Polynesia": (-10.0, -150.0),
    "Melanesia": (-8.0, 160.0),
    "Micronesia": (7.0, 150.0),
}


def build_lookups():
    gc = geonamescache.GeonamesCache()

    countries = {}
    for c in gc.get_countries().values():
        # country centroid isn't in the dataset; use capital city coords as a
        # stand-in via the cities index below. Store name -> iso for a second pass.
        countries[c["name"].lower()] = c["iso"]

    # cities: name -> (lat, lng, pop) keeping the largest-population match, AND
    # a country-scoped index (name, iso) -> (lat, lng, pop) so a city can be
    # disambiguated within the country its hierarchy path names (e.g. "Salem"
    # in the US vs in India).
    cities = {}
    cities_by_country = {}
    city_iso = {}  # name -> countrycode of the global best (largest-pop) match
    for c in gc.get_cities().values():
        key = c["name"].lower()
        lat, lng, pop = c["latitude"], c["longitude"], c.get("population", 0)
        if key not in cities or pop > cities[key][2]:
            cities[key] = (lat, lng, pop)
            city_iso[key] = c["countrycode"]
        ck = (key, c["countrycode"])
        if ck not in cities_by_country or pop > cities_by_country[ck][2]:
            cities_by_country[ck] = (lat, lng, pop)

    # country centroid ~ its most populous city
    country_centroid = {}
    for c in gc.get_cities().values():
        iso = c["countrycode"]
        pop = c.get("population", 0)
        cur = country_centroid.get(iso)
        if cur is None or pop > cur[2]:
            country_centroid[iso] = (c["latitude"], c["longitude"], pop)

    return gc, countries, cities, country_centroid, cities_by_country, city_iso


# US states + major subnational regions: the gazetteer has no admin-1 units, so
# a bare state name would otherwise fall through to the US centroid (or match a
# tiny same-named town — e.g. "California" landing on the US east coast).
US_STATES = {
    "alabama": (32.8, -86.8), "alaska": (64.2, -152.0), "arizona": (34.3, -111.7),
    "arkansas": (34.8, -92.4), "california": (37.2, -119.5), "colorado": (39.0, -105.5),
    "connecticut": (41.6, -72.7), "delaware": (39.0, -75.5), "florida": (28.6, -82.4),
    "georgia": (32.6, -83.4), "hawaii": (20.3, -156.4), "idaho": (44.2, -114.5),
    "illinois": (40.0, -89.2), "indiana": (39.9, -86.3), "iowa": (42.0, -93.5),
    "kansas": (38.5, -98.4), "kentucky": (37.5, -85.3), "louisiana": (31.0, -92.0),
    "maine": (45.4, -69.2), "maryland": (39.0, -76.8), "massachusetts": (42.3, -71.8),
    "michigan": (44.3, -85.4), "minnesota": (46.3, -94.3), "mississippi": (32.7, -89.7),
    "missouri": (38.4, -92.5), "montana": (46.9, -110.0), "nebraska": (41.5, -99.8),
    "nevada": (39.3, -116.6), "new hampshire": (43.7, -71.6), "new jersey": (40.1, -74.7),
    "new mexico": (34.4, -106.1), "new york": (42.9, -75.5), "north carolina": (35.6, -79.4),
    "north dakota": (47.5, -100.3), "ohio": (40.3, -82.8), "oklahoma": (35.6, -97.5),
    "oregon": (44.0, -120.5), "pennsylvania": (40.9, -77.8), "rhode island": (41.7, -71.6),
    "south carolina": (33.9, -80.9), "south dakota": (44.4, -100.2), "tennessee": (35.9, -86.4),
    "texas": (31.5, -99.3), "utah": (39.3, -111.7), "vermont": (44.1, -72.7),
    "virginia": (37.5, -78.9), "washington": (47.4, -120.5), "west virginia": (38.6, -80.6),
    "wisconsin": (44.6, -89.9), "wyoming": (43.0, -107.5),
    "washington dc": (38.9, -77.0), "district of columbia": (38.9, -77.0),
    # US regions
    "southwest": (34.0, -106.0), "pacific northwest": (46.0, -121.0),
    "new england": (44.0, -71.5), "midwest": (41.5, -93.0),
    "eastern united states": (39.0, -80.0), "southern united states": (33.0, -86.0),
    "aleutian islands": (52.0, -176.0), "st. lawrence island": (63.4, -170.4),
    "nunivak island": (60.0, -166.3),
    # Canadian provinces that appear
    "british columbia": (53.7, -125.0), "ontario": (50.0, -85.0), "quebec": (52.0, -72.0),
}

# European (and other) sub-national / historical regions the gazetteer lacks;
# without these they collapse onto the Europe centroid (~Belarus).
EURO_REGIONS = {
    "england": (52.5, -1.5), "scotland": (56.8, -4.2), "wales": (52.3, -3.8),
    "great britain": (54.0, -2.5), "northern ireland": (54.6, -6.7),
    "bavaria": (48.9, 11.5), "saxony": (51.0, 13.4), "prussia": (52.5, 13.4),
    "flanders": (51.0, 3.7), "wallonia": (50.4, 4.9),
    "bohemia": (49.9, 14.5), "moravia": (49.4, 16.8),
    "tuscany": (43.4, 11.1), "sicily": (37.6, 14.0), "lombardy": (45.5, 9.7),
    "venice": (45.4, 12.3), "veneto": (45.5, 11.9), "naples": (40.85, 14.27),
    "catalonia": (41.8, 1.5), "andalusia": (37.5, -4.8), "castile": (40.5, -4.0),
    "normandy": (49.0, 0.2), "brittany": (48.2, -3.0), "burgundy": (47.0, 4.8),
    "provence": (43.9, 6.0), "alsace": (48.3, 7.4),
    "rhineland": (50.5, 7.0), "westphalia": (51.8, 8.0), "swabia": (48.4, 9.8),
    "silesia": (51.0, 17.0), "pomerania": (53.8, 15.5),
    "holland": (52.3, 4.9), "netherlands": (52.2, 5.3),
    "scandinavia": (63.0, 15.0), "iberia": (40.0, -4.0),
    "anatolia": (39.0, 35.0), "levant": (33.9, 35.5), "persia": (32.4, 53.7),
}

# City/region names the gazetteer resolves to the WRONG same-named place
# (usually a small US town winning over the intended European/Asian original).
# Verified against each row's hierarchy path in the extract.
COLLISIONS = {
    "worcester": (52.19, -2.22),      # England, not Massachusetts
    "chantilly": (49.19, 2.47),       # France, not Virginia
    "corinth": (37.94, 22.93),        # Greece, not Texas
    "geneva": (46.20, 6.14),          # Switzerland, not Illinois
    "cambridge": (52.20, 0.12),       # England, not the US
    "franconia": (49.8, 10.9),        # Germany (Franken), not Virginia
    "new britain": (-5.5, 150.7),     # Papua New Guinea, not Connecticut
    "palestine": (31.9, 35.2),        # Levant, not Texas
    "caroline islands": (7.0, 150.0), # Micronesia, not Australia
    "ifugao province": (16.83, 121.1),# Philippines, not central China
    "victoria": (-37.0, 144.5),       # Australia (state), not Hong Kong
}


# Accented / historical / regional names the gazetteer misses, hand-mapped.
ALIASES = {
    **US_STATES,
    **EURO_REGIONS,
    # Big countries: use a geographic centroid, not the most-populous city, so
    # the country dot doesn't jam against one coast (e.g. US → NYC).
    "united states": (39.5, -98.35),
    "united states of america": (39.5, -98.35),
    "canada": (56.0, -96.0),
    "russia": (61.5, 90.0),
    "china": (35.9, 104.2),
    "brazil": (-10.3, -53.2),
    "australia": (-25.0, 134.0),
    "méxico": (19.43, -99.13),
    "west mexico": (20.67, -103.35),
    "roman empire": (41.9, 12.5),
    "eastern mediterranean": (34.0, 33.0),
    "petén": (16.9, -89.9),
    "yucatan": (20.7, -89.0),
    "yucatán": (20.7, -89.0),
    "jalisco": (20.67, -103.35),
    "nayarit": (21.75, -104.85),
    "perú": (-12.05, -77.04),
    "kitava island": (-8.6, 151.3),
    "trobriand islands": (-8.6, 151.1),
    "middle sepik river": (-4.2, 143.3),
    "malay archipelago": (0.0, 118.0),
    "mexican empire": (19.43, -99.13),
    "roman republic": (41.9, 12.5),
    "byzantine empire": (41.0, 28.98),
    "gandhara": (34.0, 72.0),
    "mesopotamia": (33.2, 44.4),
    "levant": (33.9, 35.5),
    "anatolia": (39.0, 35.0),
    "new spain": (19.43, -99.13),
}


# Terms the FAMSF hierarchy uses as REGION groupings that collide with real
# country names — don't treat them as the expected country. "Luxembourg" here
# groups the Low Countries (Belgium/Netherlands cities sit under it); "Georgia"
# could mean the US state or the country, so leave it to the city/state logic.
AMBIGUOUS_PATH_COUNTRIES = {"luxembourg", "georgia"}


def expected_country_iso(path, countries):
    """The ISO of the country named in the hierarchy path, if any.

    Prefer the SHALLOWEST country in the path (closest to World) — the top-level
    country is the reliable one; a deeper term that happens to share a country
    name (e.g. a "Luxembourg" province) must not win. Region groupings that
    collide with country names are skipped.
    """
    for term in path or []:  # shallow -> deep
        t = term.strip().lower()
        if t in AMBIGUOUS_PATH_COUNTRIES:
            continue
        iso = countries.get(t)
        if iso:
            return iso
    return None


def geocode_one(
    name, path, countries, cities, country_centroid, cities_by_country, city_iso
):
    """Return (lat, lng, match_level) or (None, None, None)."""
    n = name.strip().lower()
    exp_iso = expected_country_iso(path, countries)

    if n in COLLISIONS:
        lat, lng = COLLISIONS[n]
        return lat, lng, "collision-fix"

    if n in ALIASES:
        lat, lng = ALIASES[n]
        return lat, lng, "alias"

    # 1) country
    if n in countries:
        iso = countries[n]
        cc = country_centroid.get(iso)
        if cc:
            return cc[0], cc[1], "country"

    # 2) region/continent
    if name in REGION_CENTROIDS:
        lat, lng = REGION_CENTROIDS[name]
        return lat, lng, "region"

    # 3) city — prefer a same-named city INSIDE the country the path names, so
    #    "Salem, US" doesn't resolve to Salem, India, etc.
    if exp_iso and (n, exp_iso) in cities_by_country:
        lat, lng, _ = cities_by_country[(n, exp_iso)]
        return lat, lng, "city-in-country"
    if n in cities:
        # Reject a global city match that sits in a DIFFERENT country than the
        # path names (e.g. path says US but the only "Ipswich" in the gazetteer
        # is in England) — fall through to the state/country centroid instead.
        if not (exp_iso and city_iso.get(n) and city_iso[n] != exp_iso):
            lat, lng, _ = cities[n]
            return lat, lng, "city"

    # 4) walk the hierarchy path upward (skip the leaf == name itself and "World")
    for term in reversed(path or []):
        if term == name or term == "World":
            continue
        t = term.strip().lower()
        if t in ALIASES:
            lat, lng = ALIASES[t]
            return lat, lng, "path-alias"
        if term in REGION_CENTROIDS:
            lat, lng = REGION_CENTROIDS[term]
            return lat, lng, "path-region"
        if t in countries:
            cc = country_centroid.get(countries[t])
            if cc:
                return cc[0], cc[1], "path-country"
        if exp_iso and (t, exp_iso) in cities_by_country:
            lat, lng, _ = cities_by_country[(t, exp_iso)]
            return lat, lng, "path-city-in-country"
        if t in cities and not (
            exp_iso and city_iso.get(t) and city_iso[t] != exp_iso
        ):
            lat, lng, _ = cities[t]
            return lat, lng, "path-city"

    # 5) last resort: if the path names a country, use its centroid
    if exp_iso and country_centroid.get(exp_iso):
        cc = country_centroid[exp_iso]
        return cc[0], cc[1], "path-country-fallback"

    return None, None, None


# Known synonymous place names → one canonical label. Only true synonyms of the
# SAME place (not "New Mexico" vs "Mexico" — those are distinct and left alone).
CANONICAL = {
    "united states of america": "United States",
    "america": "United States",
    "u.s.a.": "United States",
    "usa": "United States",
    "méxico": "Mexico",
    "perú": "Peru",
    "great britain": "United Kingdom",
}


def dedupe_rows(rows):
    """Merge synonymous / case-variant place rows, summing object counts.

    Two rows merge when their canonical name matches (case-insensitively). The
    kept row kepts the highest-count variant's display name + path.
    """
    merged = {}
    for r in rows:
        name = r["place"]
        canon = CANONICAL.get(name.strip().lower(), name)
        key = canon.strip().lower()
        m = merged.get(key)
        if m is None:
            merged[key] = {
                "place": canon,
                "n": r["n"],
                "path": r.get("path"),
                "_best": r["n"],
            }
        else:
            m["n"] += r["n"]
            # keep the display name + path from the largest contributor
            if r["n"] > m["_best"]:
                m["_best"] = r["n"]
                # prefer an explicit canonical label if one applies
                m["place"] = CANONICAL.get(name.strip().lower(), name)
                m["path"] = r.get("path")
    out = [{k: v for k, v in m.items() if k != "_best"} for m in merged.values()]
    out.sort(key=lambda x: -x["n"])
    return out


# Continent / broad-region names (path depth 1 under World, or macro regions).
CONTINENTS = {
    "world", "africa", "europe", "asia", "north america", "south america",
    "north and central america", "central america", "oceania", "antarctica",
    "the americas",
}


def classify_tier(name, path, level, countries):
    """Bucket a place into continent / country / region / city for the grouped
    breakdown. Uses the gazetteer + the hierarchy path depth."""
    n = name.strip().lower()
    if n in CONTINENTS:
        return "continent"
    if n in countries or level in ("country", "path-country", "path-country-fallback"):
        return "country"
    # City-level matches (own name resolved to a city in the gazetteer).
    if level in ("city", "city-in-country", "path-city", "path-city-in-country"):
        return "city"
    # Otherwise a sub-national region/state/province (aliases, path-region, etc.)
    return "region"


def main():
    rows = json.loads(RAW.read_text())
    before = len(rows)
    rows = dedupe_rows(rows)
    print(f"loaded {before} places, {len(rows)} after de-duping synonyms", flush=True)

    _, countries, cities, country_centroid, cities_by_country, city_iso = build_lookups()
    print(
        f"gazetteer: {len(countries)} countries, {len(cities)} cities", flush=True
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    matched = 0
    matched_objs = 0
    total_objs = 0
    with OUT.open("w") as f:
        for i, r in enumerate(rows):
            lat, lng, level = geocode_one(
                r["place"],
                r.get("path"),
                countries,
                cities,
                country_centroid,
                cities_by_country,
                city_iso,
            )
            total_objs += r["n"]
            if lat is not None:
                matched += 1
                matched_objs += r["n"]
            rec = {
                "place": r["place"],
                "n": r["n"],
                "lat": round(lat, 3) if lat is not None else None,
                "lng": round(lng, 3) if lng is not None else None,
                "match": level,
                "tier": classify_tier(r["place"], r.get("path"), level, countries),
                "path": r.get("path"),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if (i + 1) % 500 == 0:
                print(f"  processed {i + 1}/{len(rows)}", flush=True)

    print(
        f"matched {matched}/{len(rows)} places "
        f"({100 * matched / len(rows):.1f}%), "
        f"{matched_objs}/{total_objs} objects "
        f"({100 * matched_objs / total_objs:.1f}%)",
        flush=True,
    )
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
