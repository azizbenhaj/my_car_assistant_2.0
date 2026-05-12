"""
Map listing `city` text → Bundesland (English label for charts / aggregation).

Uses **geonamescache** for German cities (admin1code → state) and **PLZ** fallback from
``listings_similarity.ZIP2_LABEL`` (imported lazily to avoid cycles). Results are **memoized**
per city string because Geonames search can be expensive.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any


# Geonames admin1code digits for Germany (validated against major cities).
DE_ADMIN1_DIGIT_TO_ENGLISH: dict[str, str] = {
    "01": "Baden-Württemberg",
    "02": "Bavaria",
    "03": "Bremen",
    "04": "Hamburg",
    "05": "Hesse",
    "06": "Lower Saxony",
    "07": "North Rhine-Westphalia",
    "08": "Rhineland-Palatinate",
    "09": "Saarland",
    "10": "Schleswig-Holstein",
    "11": "Brandenburg",
    "12": "Mecklenburg-Vorpommern",
    "13": "Saxony",
    "14": "Saxony-Anhalt",
    "15": "Thuringia",
    "16": "Berlin",
}


def _first_plz(text: str) -> str | None:
    m = re.search(r"\b(\d{5})\b", text)
    return m.group(1) if m else None


def _city_name_candidates(raw: str) -> list[str]:
    s = re.sub(r"^\s*\d{5}\s*", "", (raw or "").strip())
    parts = [p.strip() for p in re.split(r"[,;/|]", s) if p.strip()]
    if not parts and s:
        parts = [s]
    candidates: list[str] = []
    for p in parts[:3]:
        if len(p) < 2:
            continue
        candidates.append(p)
        inner = re.sub(r"\(.*?\)", "", p).strip()
        if inner and inner != p:
            candidates.append(inner)
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        k = c.casefold()
        if k in seen:
            continue
        seen.add(k)
        out.append(c)
    return out[:6]


@lru_cache(maxsize=1)
def _geonames_gc():
    from geonamescache import GeonamesCache

    return GeonamesCache(min_city_population=1000)


def _best_de_hit_for_candidates(candidates: list[str]) -> dict[str, Any] | None:
    gc = _geonames_gc()
    best: dict[str, Any] | None = None
    best_pop = -1

    def consider(rec: dict[str, Any]) -> None:
        nonlocal best, best_pop
        if rec.get("countrycode") != "DE":
            return
        pop = int(rec.get("population") or 0)
        adm = str(rec.get("admin1code") or "").zfill(2)
        if not adm:
            return
        if pop > best_pop:
            best_pop = pop
            best = rec

    for cand in candidates:
        for variant in (cand, cand.casefold(), cand.title()):
            try:
                buckets = gc.get_cities_by_name(variant)
            except Exception:
                buckets = []
            for bucket in buckets:
                for _gid, city in bucket.items():
                    consider(city)

    if best is not None:
        return best

    # Slower fallback: substring / alternate-name search (once per candidate).
    for cand in candidates[:2]:
        for rec in gc.search_cities(
            cand.casefold(), attribute="alternatenames", contains_search=True
        ):
            consider(rec)
    return best


@lru_cache(maxsize=4096)
def _region_for_normalized_city(blob: str) -> str:
    from listings_similarity import ZIP2_LABEL

    z = _first_plz(blob)
    if z and len(z) >= 2:
        plz_region = ZIP2_LABEL.get(z[:2])
        if plz_region:
            return plz_region

    hit = _best_de_hit_for_candidates(_city_name_candidates(blob))
    if hit:
        adm = str(hit.get("admin1code") or "").zfill(2)
        mapped = DE_ADMIN1_DIGIT_TO_ENGLISH.get(adm)
        if mapped:
            return mapped

    if z and len(z) >= 2:
        return ZIP2_LABEL.get(z[:2], "Unknown")
    return "Unknown"


def region_from_city_field(city_text: Any) -> str:
    if city_text is None:
        return "Unknown"
    blob = " ".join(str(city_text).split())
    if not blob:
        return "Unknown"
    return _region_for_normalized_city(blob)


def latlon_from_city_field(city_text: Any) -> tuple[float, float] | None:
    """Approximate (lat, lon) for a listing `city` string via Geonames DE city match (same logic as region)."""
    if city_text is None:
        return None
    blob = " ".join(str(city_text).split())
    if not blob:
        return None
    hit = _best_de_hit_for_candidates(_city_name_candidates(blob))
    if not hit:
        return None
    try:
        lat = float(hit.get("latitude"))
        lon = float(hit.get("longitude"))
    except (TypeError, ValueError):
        return None
    # Rough Germany bounding box (excludes obvious wrong-country hits).
    if not (47.0 <= lat <= 55.5 and 5.5 <= lon <= 15.5):
        return None
    return lat, lon
