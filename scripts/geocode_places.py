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

    # cities: name -> (lat, lng) keeping the largest-population match
    cities = {}
    citycoords_by_iso_capital = {}
    for c in gc.get_cities().values():
        key = c["name"].lower()
        lat, lng, pop = c["latitude"], c["longitude"], c.get("population", 0)
        if key not in cities or pop > cities[key][2]:
            cities[key] = (lat, lng, pop)

    # country centroid ~ its most populous city
    country_centroid = {}
    for c in gc.get_cities().values():
        iso = c["countrycode"]
        pop = c.get("population", 0)
        cur = country_centroid.get(iso)
        if cur is None or pop > cur[2]:
            country_centroid[iso] = (c["latitude"], c["longitude"], pop)

    return gc, countries, cities, country_centroid


# Accented / historical / regional names the gazetteer misses, hand-mapped.
ALIASES = {
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


def geocode_one(name, path, countries, cities, country_centroid):
    """Return (lat, lng, match_level) or (None, None, None)."""
    n = name.strip().lower()

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

    # 3) city
    if n in cities:
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
        if t in cities:
            lat, lng, _ = cities[t]
            return lat, lng, "path-city"

    return None, None, None


def main():
    rows = json.loads(RAW.read_text())
    print(f"loaded {len(rows)} places", flush=True)

    _, countries, cities, country_centroid = build_lookups()
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
                r["place"], r.get("path"), countries, cities, country_centroid
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
