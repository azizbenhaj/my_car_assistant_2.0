"""Bundesland chart: Plotly choropleth if available + GeoJSON fetch, else Streamlit-friendly bar."""

from __future__ import annotations

from typing import Any

# English labels from PLZ heuristic → GeoJSON NAME_1 (German) used by common DE datasets
EN_TO_DE_NAME1: dict[str, str] = {
    "Baden-Württemberg": "Baden-Württemberg",
    "Bavaria": "Bayern",
    "Berlin": "Berlin",
    "Brandenburg": "Brandenburg",
    "Bremen": "Bremen",
    "Hamburg": "Hamburg",
    "Hesse": "Hessen",
    "Mecklenburg-Vorpommern": "Mecklenburg-Vorpommern",
    "Lower Saxony": "Niedersachsen",
    "North Rhine-Westphalia": "Nordrhein-Westfalen",
    "Rhineland-Palatinate": "Rheinland-Pfalz",
    "Saarland": "Saarland",
    "Saxony": "Sachsen",
    "Saxony-Anhalt": "Sachsen-Anhalt",
    "Schleswig-Holstein": "Schleswig-Holstein",
    "Thuringia": "Thüringen",
    "Unknown": "",
    "Unknown (DE)": "",
}


def region_counts_for_plotly(counts: dict[str, int]) -> tuple[list[str], list[int]]:
    locs: list[str] = []
    vals: list[int] = []
    for k, v in counts.items():
        if v <= 0:
            continue
        de = EN_TO_DE_NAME1.get(k)
        if not de:
            continue
        locs.append(de)
        vals.append(int(v))
    return locs, vals


def try_choropleth_germany(counts: dict[str, int]) -> Any | None:
    try:
        import json
        import urllib.request

        import plotly.graph_objects as go
    except Exception:
        return None

    locs, vals = region_counts_for_plotly(counts)
    if not locs:
        return None

    url = "https://raw.githubusercontent.com/isellsoap/deutschlandGeoJSON/main/2_bundeslaender/4_niedrig.geo.json"
    try:
        with urllib.request.urlopen(url, timeout=12) as r:
            geo = json.load(r)
    except Exception:
        return None

    name_to_z = dict(zip(locs, vals))
    locations = []
    z = []
    for feat in geo.get("features", []):
        props = feat.get("properties") or {}
        n = props.get("NAME_1") or props.get("name")
        if not n:
            continue
        locations.append(n)
        z.append(float(name_to_z.get(n, 0)))

    if not any(z):
        return None

    fig = go.Figure(
        go.Choropleth(
            geojson=geo,
            featureidkey="properties.NAME_1",
            locations=locations,
            z=z,
            colorscale="Blues",
            marker_line_color="white",
            marker_line_width=0.4,
            showscale=True,
            zmin=0,
        )
    )
    fig.update_geos(fitbounds="locations")
    fig.update_layout(
        margin=dict(l=0, r=0, t=36, b=0),
        height=380,
        title="Listings by Bundesland (city → locality; PLZ fallback)",
    )
    return fig
