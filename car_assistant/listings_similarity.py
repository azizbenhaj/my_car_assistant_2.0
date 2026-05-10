"""
Rank listings vs evaluated JSON, derive match % / tolerances, aggregates and region buckets.

Maker/model alignment uses **RapidFuzz** (`partial_ratio`). Price stats and km/year vs price
slopes use **NumPy** (`mean`, `median`, `polyfit`), same as the scatter line in `listings_viz.py`.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
from rapidfuzz import fuzz

# Rough DE postcode (first two digits) → Bundesland English label (+ ISO-ish key for choropleths)
ZIP2_LABEL: dict[str, str] = {
    "01": "Saxony",
    "02": "Brandenburg",
    "03": "Brandenburg",
    "04": "Saxony",
    "06": "Saxony-Anhalt",
    "07": "Thuringia",
    "08": "Saxony",
    "09": "Saxony",
    "10": "Berlin",
    "11": "Berlin",
    "12": "Berlin",
    "13": "Berlin",
    "14": "Brandenburg",
    "15": "Brandenburg",
    "16": "Brandenburg",
    "17": "Mecklenburg-Vorpommern",
    "18": "Mecklenburg-Vorpommern",
    "19": "Mecklenburg-Vorpommern",
    "20": "Hamburg",
    "21": "Lower Saxony",
    "22": "Schleswig-Holstein",
    "23": "Schleswig-Holstein",
    "24": "Schleswig-Holstein",
    "25": "Schleswig-Holstein",
    "26": "Lower Saxony",
    "27": "Lower Saxony",
    "28": "Bremen",
    "29": "Lower Saxony",
    "30": "North Rhine-Westphalia",
    "31": "North Rhine-Westphalia",
    "32": "North Rhine-Westphalia",
    "33": "North Rhine-Westphalia",
    "34": "North Rhine-Westphalia",
    "35": "Hesse",
    "36": "Hesse",
    "37": "Lower Saxony",
    "38": "Lower Saxony",
    "39": "Saxony-Anhalt",
    "40": "North Rhine-Westphalia",
    "41": "North Rhine-Westphalia",
    "42": "North Rhine-Westphalia",
    "43": "North Rhine-Westphalia",
    "44": "North Rhine-Westphalia",
    "45": "North Rhine-Westphalia",
    "46": "North Rhine-Westphalia",
    "47": "North Rhine-Westphalia",
    "48": "North Rhine-Westphalia",
    "49": "Lower Saxony",
    "50": "North Rhine-Westphalia",
    "51": "North Rhine-Westphalia",
    "52": "North Rhine-Westphalia",
    "53": "North Rhine-Westphalia",
    "54": "Rhineland-Palatinate",
    "55": "Rhineland-Palatinate",
    "56": "Rhineland-Palatinate",
    "57": "North Rhine-Westphalia",
    "58": "North Rhine-Westphalia",
    "59": "North Rhine-Westphalia",
    "60": "Hesse",
    "61": "Hesse",
    "62": "Hesse",
    "63": "Hesse",
    "64": "Hesse",
    "65": "Hesse",
    "66": "Saarland",
    "67": "Rhineland-Palatinate",
    "68": "Baden-Württemberg",
    "69": "Baden-Württemberg",
    "70": "Baden-Württemberg",
    "71": "Baden-Württemberg",
    "72": "Baden-Württemberg",
    "73": "Baden-Württemberg",
    "74": "Baden-Württemberg",
    "75": "Baden-Württemberg",
    "76": "Baden-Württemberg",
    "77": "Baden-Württemberg",
    "78": "Baden-Württemberg",
    "79": "Baden-Württemberg",
    "80": "Bavaria",
    "81": "Bavaria",
    "82": "Bavaria",
    "83": "Bavaria",
    "84": "Bavaria",
    "85": "Bavaria",
    "86": "Bavaria",
    "87": "Bavaria",
    "88": "Baden-Württemberg",
    "89": "Baden-Württemberg",
    "90": "Bavaria",
    "91": "Bavaria",
    "92": "Bavaria",
    "93": "Bavaria",
    "94": "Bavaria",
    "95": "Bavaria",
    "96": "Bavaria",
    "97": "Bavaria",
    "98": "Thuringia",
    "99": "Thuringia",
}


def region_label_for_row(row: dict[str, Any]) -> str:
    from listings_geo_de import region_from_city_field

    return region_from_city_field(row.get("city"))


def parse_listing_price(price_raw: Any) -> float | None:
    if price_raw is None:
        return None
    digits = re.sub(r"[^\d]", "", str(price_raw))
    if not digits:
        return None
    try:
        v = float(digits)
        return v if 500 <= v <= 2_000_000 else None
    except ValueError:
        return None


def parse_listing_year(first_reg: Any) -> int | None:
    if first_reg is None:
        return None
    m = re.match(r"\s*([12][0-9]{3})", str(first_reg).strip())
    if not m:
        return None
    try:
        y = int(m.group(1))
        return y if 1980 <= y <= 2035 else None
    except ValueError:
        return None


def parse_listing_km(km_raw: Any) -> int | None:
    if km_raw is None:
        return None
    digits = re.sub(r"[^\d]", "", str(km_raw).replace(",", ""))
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _nz(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def _fuzz_field_score(needle: str, min_len: int, *haystacks: str) -> float:
    """0..15 from best partial_ratio across listing text fields (library match, not substring hacks)."""
    n = (needle or "").strip().lower()
    if len(n) < min_len:
        return 0.0
    best = 0.0
    for h in haystacks:
        hh = (h or "").strip().lower()
        if not hh:
            continue
        best = max(best, fuzz.partial_ratio(n, hh) / 100.0)
    return best * 15.0


def _maker_model_hit(evaluated: dict[str, Any], row: dict[str, Any]) -> tuple[float, float]:
    maker_e = _nz(evaluated.get("maker"))
    model_e = _nz(evaluated.get("model"))
    mm = _nz(row.get("make_model"))
    mk_col = _nz(row.get("maker"))
    mo_col = _nz(row.get("model"))
    maker_score = _fuzz_field_score(maker_e, 1, mm, mk_col)
    model_score = _fuzz_field_score(model_e, 2, mm, mo_col)
    return maker_score, model_score


def _confidence_tolerances(
    evaluated: dict[str, Any],
    row: dict[str, Any],
    year_tol: int,
    km_tol: int,
    y_row: int | None,
    km_row: int | None,
) -> tuple[list[str], list[str]]:
    """Return (missing_vs_query_hints, tolerance_confidence_notes)."""
    tgt_y = evaluated.get("year")
    tgt_k = evaluated.get("km")
    miss: list[str] = []
    notes: list[str] = []

    try:
        y_t = int(tgt_y) if tgt_y is not None else None
    except (TypeError, ValueError):
        y_t = None
    try:
        k_t = int(tgt_k) if tgt_k is not None else None
    except (TypeError, ValueError):
        k_t = None

    fu = evaluated.get("fuel")
    gb = evaluated.get("gearbox")
    if fu:
        fv = row.get("Fuel") or row.get("fuel")
        if fv and _nz(fv) != _nz(fu):
            notes.append(f"Fuel differs (listing {fv}; query {fu})")

    if gb:
        gv = row.get("gearbox")
        if gv and _nz(gv) != _nz(gb):
            notes.append(f"Gearbox differs (listing {gv}; query {gb})")

    if y_t is not None:
        if y_row is None:
            miss.append("listing year unclear")
            notes.append("Year confidence lower (registration text unparsed)")
        else:
            dy = abs(y_row - y_t)
            if dy <= year_tol:
                notes.append(f"Year within ±{year_tol} ({dy}y off)")
            else:
                miss.append(f"year Δ{dy}y beyond ±{year_tol}")
                notes.append(f"Year outside ±{year_tol} tolerance ({dy}y)")

    if k_t is not None:
        if km_row is None:
            miss.append("listing km unclear")
            notes.append("Km confidence lower (listing odometer unparsed)")
        else:
            dk = abs(km_row - k_t)
            if dk <= km_tol:
                notes.append(f"Km within ±{km_tol:,} ({dk:,} km off)")
            else:
                miss.append(f"km Δ{dk:,} beyond ±{km_tol:,}")
                notes.append(f"Km outside ±{km_tol:,} tolerance ({dk:,} km)")

    return miss, notes


def similarity_and_match_pct(
    evaluated: dict[str, Any],
    row: dict[str, Any],
    *,
    year_tol: int,
    km_tol: int,
) -> tuple[float, float, list[str], list[str]]:
    """
    Return (similarity_rank_score_higher_is_better, match_pct 0..100,
            missing_dimensions, tolerance_confidence_notes).
    """
    y_row = parse_listing_year(row.get("first_registration"))
    km_row = parse_listing_km(row.get("km"))
    y_t = None
    k_t = None
    tgt_y = evaluated.get("year")
    tgt_k = evaluated.get("km")
    try:
        y_t = int(tgt_y) if tgt_y is not None else None
    except (TypeError, ValueError):
        pass
    try:
        k_t = int(tgt_k) if tgt_k is not None else None
    except (TypeError, ValueError):
        pass

    year_part = 0.0
    if y_t is None:
        year_part = 50.0
    elif y_row is None:
        year_part = 15.0
    else:
        dy = abs(y_row - y_t)
        year_part = max(0.0, 50.0 - dy * 8.0)

    km_part = 0.0
    if k_t is None:
        km_part = 50.0
    elif km_row is None:
        km_part = 15.0
    else:
        dk = abs(km_row - k_t)
        km_part = max(0.0, 50.0 - (dk / 3000.0) * 5.0)

    mk_score, md_score = _maker_model_hit(evaluated, row)
    raw = year_part + km_part + mk_score + md_score
    # Typical scale ~130 when year/km/targets align strongly; normalize to percentage.
    match_pct = max(0.0, min(100.0, (raw / 130.0) * 100.0))

    missing, tol_notes = _confidence_tolerances(
        evaluated, row, year_tol, km_tol, y_row, km_row
    )
    similarity = raw
    return similarity, match_pct, missing, tol_notes


def enrich_rows(
    evaluated: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    year_tol: int,
    km_tol: int,
) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        row = dict(r)
        score, pct, missing, tol = similarity_and_match_pct(
            evaluated, row, year_tol=year_tol, km_tol=km_tol
        )
        row["_parsed_price"] = parse_listing_price(row.get("price"))
        row["_parsed_year"] = parse_listing_year(row.get("first_registration"))
        row["_parsed_km"] = parse_listing_km(row.get("km"))
        row["_similarity_score"] = score
        row["_match_pct"] = round(pct, 1)
        row["_missing_vs_query"] = missing
        row["_tolerance_notes"] = tol
        row["_region"] = region_label_for_row(row)
        out.append(row)

    out.sort(key=lambda x: x["_similarity_score"], reverse=True)
    top3 = set(id(x) for x in out[:3])
    for row in out:
        row["_top3_similar"] = id(row) in top3

    return out


def aggregate_prices(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    prices = [r["_parsed_price"] for r in rows if r.get("_parsed_price") is not None]
    if not prices:
        return {
            "average": None,
            "median": None,
            "lowest": None,
            "highest": None,
            "count": 0,
        }
    prices_f = sorted(float(p) for p in prices)
    arr = np.asarray(prices_f, dtype=float)
    return {
        "average": float(arr.mean()),
        "median": float(np.median(arr)),
        "lowest": float(prices_f[0]),
        "highest": float(prices_f[-1]),
        "count": len(prices_f),
    }


def aggregate_by_region(rows: list[dict[str, Any]]) -> dict[str, int]:
    from collections import Counter

    c = Counter((r.get("_region") or "Unknown") for r in rows)
    return dict(sorted(c.items(), key=lambda x: (-x[1], x[0])))


def _polyfit_slope(xs: list[float], ys: list[float]) -> float | None:
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    if x.size < 4 or float(np.std(x)) == 0.0:
        return None
    m, _intercept = np.polyfit(x, y, deg=1)
    return float(m)


def price_movement_vs_km_eur_per_km(rows: list[dict[str, Any]]) -> float | None:
    pts = [
        (float(r["_parsed_km"]), float(r["_parsed_price"]))
        for r in rows
        if r.get("_parsed_km") is not None and r.get("_parsed_price") is not None
    ]
    if len(pts) < 4:
        return None
    pts.sort(key=lambda t: t[0])
    xs = [t[0] for t in pts]
    ys = [t[1] for t in pts]
    return _polyfit_slope(xs, ys)


def price_movement_vs_year_eur_per_year(rows: list[dict[str, Any]]) -> float | None:
    pts = [
        (float(r["_parsed_year"]), float(r["_parsed_price"]))
        for r in rows
        if r.get("_parsed_year") is not None and r.get("_parsed_price") is not None
    ]
    if len(pts) < 4:
        return None
    pts.sort(key=lambda t: t[0])
    xs = [t[0] for t in pts]
    ys = [t[1] for t in pts]
    return _polyfit_slope(xs, ys)


def intent_buy_or_sell_plain(evaluated: dict[str, Any]) -> str:
    intent = (evaluated.get("intent") or "buy").strip().lower()
    maker = evaluated.get("maker") or ""
    model = evaluated.get("model") or ""
    year = evaluated.get("year") or ""
    km = evaluated.get("km") or ""
    kind = (
        "selling"
        if intent == "sell"
        else ("buying" if intent == "buy" else intent)
    )
    return (
        f"Following your intention of {kind} a {maker} {model} "
        f"(year ~{year}, km ~{km}), here are the listings we matched."
    )


def intent_buy_or_sell_line(evaluated: dict[str, Any]) -> str:
    intent = (evaluated.get("intent") or "buy").strip().lower()
    maker = evaluated.get("maker") or ""
    model = evaluated.get("model") or ""
    year = evaluated.get("year") or ""
    km = evaluated.get("km") or ""
    kind = (
        "selling"
        if intent == "sell"
        else ("buying" if intent == "buy" else intent)
    )
    return f"Following your intention of **{kind}** a **{maker} {model}** (year ~{year}, km ~{km}), here are the listings we matched."
