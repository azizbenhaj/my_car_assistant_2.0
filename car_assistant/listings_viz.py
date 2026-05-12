"""Charts for Streamlit UI and embedded PDF thumbnails."""

from __future__ import annotations

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402
import numpy as np


def scatter_km_price_png(rows: list[dict[str, Any]]) -> io.BytesIO | None:
    xs = []
    ys = []
    cols = []
    for r in rows:
        pk = r.get("_parsed_km")
        pp = r.get("_parsed_price")
        if pk is None or pp is None:
            continue
        xs.append(float(pk))
        ys.append(float(pp))
        cols.append("#2e7d32" if r.get("_top3_similar") else "#1565c0")
    if len(xs) < 2:
        return None

    fig, ax = plt.subplots(figsize=(4.2, 2.6))
    ax.scatter(xs, ys, c=cols, s=22, alpha=0.82, edgecolors="white", linewidths=0.3)
    if len(xs) >= 4:
        x_a = np.asarray(xs, dtype=float)
        y_a = np.asarray(ys, dtype=float)
        if float(np.std(x_a)) > 0.0:
            m, b = np.polyfit(x_a, y_a, deg=1)
            xa = sorted(xs)
            ax.plot(xa, [m * xi + b for xi in xa], "--", color="#c62828", linewidth=1, label="OLS fit")
            ax.legend(loc="upper right", fontsize=6)
    ax.set_xlabel("km")
    ax.set_ylabel("Price (EUR)")
    ax.ticklabel_format(style="plain", axis="y")
    fig.tight_layout()
    bio = io.BytesIO()
    fig.savefig(bio, format="png", dpi=120)
    plt.close(fig)
    bio.seek(0)
    return bio


def scatter_year_price_png(rows: list[dict[str, Any]]) -> io.BytesIO | None:
    xs: list[float] = []
    ys: list[float] = []
    cols: list[str] = []
    for r in rows:
        py = r.get("_parsed_year")
        pp = r.get("_parsed_price")
        if py is None or pp is None:
            continue
        xs.append(float(py))
        ys.append(float(pp))
        cols.append("#2e7d32" if r.get("_top3_similar") else "#6a1b9a")
    if len(xs) < 2:
        return None

    fig, ax = plt.subplots(figsize=(4.2, 2.6))
    ax.scatter(xs, ys, c=cols, s=22, alpha=0.82, edgecolors="white", linewidths=0.3)
    if len(xs) >= 4:
        x_a = np.asarray(xs, dtype=float)
        y_a = np.asarray(ys, dtype=float)
        if float(np.std(x_a)) > 0.0:
            m, b = np.polyfit(x_a, y_a, deg=1)
            xa = sorted(xs)
            ax.plot(xa, [m * xi + b for xi in xa], "--", color="#c62828", linewidth=1, label="OLS fit")
            ax.legend(loc="upper right", fontsize=6)
    ax.set_xlabel("Registration year")
    ax.set_ylabel("Price (EUR)")
    ax.ticklabel_format(style="plain", axis="y")
    # Years are discrete — avoid fractional tick labels (e.g. 2025.5).
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=8))
    ax.ticklabel_format(style="plain", axis="x", useOffset=False)
    fig.tight_layout()
    bio = io.BytesIO()
    fig.savefig(bio, format="png", dpi=120)
    plt.close(fig)
    bio.seek(0)
    return bio


def germany_listings_map_png(rows: list[dict[str, Any]]) -> io.BytesIO | None:
    """
    Static PNG: Germany map with one marker per row where `city` resolves to lat/lon (Geonames DE).
    Requires plotly + kaleido for raster export.
    """
    try:
        import plotly.graph_objects as go
    except Exception:
        return None

    from listings_geo_de import latlon_from_city_field

    lats: list[float] = []
    lons: list[float] = []
    texts: list[str] = []
    colors: list[str] = []
    key_counts: dict[tuple[float, float], int] = {}

    for r in rows:
        city = r.get("city")
        ll = latlon_from_city_field(city)
        if ll is None:
            continue
        la, lo = ll
        n = key_counts.get((la, lo), 0)
        key_counts[(la, lo)] = n + 1
        # Slight jitter so stacked same-city listings remain visible.
        jitter_la = la + (n % 5) * 0.012 - 0.024
        jitter_lo = lo + (n // 5) * 0.014 - 0.021
        lats.append(jitter_la)
        lons.append(jitter_lo)
        label = str(city or "").strip()[:48] or "?"
        mm = (r.get("make_model") or "").strip()[:40]
        texts.append(f"{label}<br>{mm}" if mm else label)
        colors.append("#2e7d32" if r.get("_top3_similar") else "#1565c0")

    if len(lats) < 1:
        return None

    fig = go.Figure(
        data=[
            go.Scattergeo(
                lat=lats,
                lon=lons,
                mode="markers",
                marker=dict(
                    size=11,
                    color=colors,
                    line=dict(width=0.8, color="white"),
                    opacity=0.92,
                ),
                text=texts,
                hoverinfo="text",
            )
        ]
    )
    fig.update_geos(
        visible=True,
        resolution=50,
        showcountries=True,
        countrycolor="#b0bec5",
        showland=True,
        landcolor="#eceff1",
        showcoastlines=True,
        coastlinecolor="#90a4ae",
        projection_type="mercator",
        lonaxis_range=[5.6, 15.3],
        lataxis_range=[47.2, 55.1],
        bgcolor="white",
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=36, b=0),
        height=420,
        width=720,
        title="Listing locations (city → Geonames, Germany)",
        title_font=dict(size=14, color="#0d47a1"),
        paper_bgcolor="white",
    )

    out = io.BytesIO()
    try:
        fig.write_image(out, format="png", scale=1.5)
    except Exception:
        return None
    out.seek(0)
    if not out.getvalue():
        return None
    return out


def price_distribution_bar_png(stats: dict[str, Any]) -> io.BytesIO | None:
    """Horizontal bar chart: min, median, average, max (same sample)."""
    keys = ("lowest", "median", "average", "highest")
    labels = ("Min", "Median", "Average", "Max")
    vals: list[float] = []
    lbls: list[str] = []
    for key, lb in zip(keys, labels):
        v = stats.get(key)
        if v is not None:
            try:
                vals.append(float(v))
                lbls.append(lb)
            except (TypeError, ValueError):
                pass
    if len(vals) < 2:
        return None

    fig_h = max(2.8, 0.55 + 0.45 * len(vals))
    fig, ax = plt.subplots(figsize=(5.8, fig_h))
    y_pos = np.arange(len(vals))[::-1]
    colors = ("#546e7a", "#039be5", "#00897b", "#f57c00")[: len(vals)]
    bars = ax.barh(y_pos, vals, height=0.55, color=colors, alpha=0.9, edgecolor="white")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(lbls, fontsize=9)
    ax.set_xlabel("Price (EUR)", fontsize=9)
    ax.ticklabel_format(style="plain", axis="x")
    for bar, v in zip(bars, vals):
        ax.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            f" €{v:,.0f}",
            va="center",
            fontsize=8,
            color="#1a237e",
        )
    ax.set_title("Price spread on matched listings", fontsize=10, pad=10)
    fig.tight_layout()
    bio = io.BytesIO()
    fig.savefig(bio, format="png", dpi=140)
    plt.close(fig)
    bio.seek(0)
    return bio


def combined_market_dashboard_png(
    rows: list[dict[str, Any]],
    stats: dict[str, Any],
) -> io.BytesIO | None:
    """Single PNG for PDF/app: 2×2 grid — price bar | km scatter / year scatter | Germany map."""
    bio_bar = price_distribution_bar_png(stats)
    bio_km = scatter_km_price_png(rows)
    bio_yr = scatter_year_price_png(rows)
    bio_map = germany_listings_map_png(rows)
    if bio_bar is None and bio_km is None and bio_yr is None and bio_map is None:
        return None

    titles = (
        "Price overview (EUR)",
        "Price vs km",
        "Price vs registration year",
        "Listing locations (Germany)",
    )
    blobs = (bio_bar, bio_km, bio_yr, bio_map)
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 7.2))
    for ax, title, blob in zip(axes.flat, titles, blobs):
        ax.set_title(title, fontsize=9, pad=4)
        if blob is None:
            ax.text(0.5, 0.5, "Not enough data", ha="center", va="center", fontsize=10)
            ax.axis("off")
            continue
        blob.seek(0)
        ax.imshow(matplotlib.image.imread(blob))
        ax.axis("off")

    fig.tight_layout()
    bio = io.BytesIO()
    fig.savefig(bio, format="png", dpi=132, bbox_inches="tight")
    plt.close(fig)
    bio.seek(0)
    return bio


# Distinct series colors for 2–3 car comparisons (matches map legend).
COMPARE_SERIES_COLORS: tuple[str, ...] = ("#1565c0", "#c62828", "#2e7d32")


def compare_km_price_png(
    series: list[tuple[str, list[dict[str, Any]]]],
) -> io.BytesIO | None:
    """One scatter + optional OLS line per car (different color + legend)."""
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    drew = False
    for idx, (label, rows) in enumerate(series):
        color = COMPARE_SERIES_COLORS[idx % len(COMPARE_SERIES_COLORS)]
        xs: list[float] = []
        ys: list[float] = []
        for r in rows:
            pk = r.get("_parsed_km")
            pp = r.get("_parsed_price")
            if pk is None or pp is None:
                continue
            xs.append(float(pk))
            ys.append(float(pp))
        if len(xs) < 2:
            continue
        drew = True
        leg = str(label)[:34]
        ax.scatter(
            xs,
            ys,
            c=color,
            s=28,
            alpha=0.86,
            edgecolors="white",
            linewidths=0.35,
            label=leg,
        )
        if len(xs) >= 4:
            x_a = np.asarray(xs, dtype=float)
            y_a = np.asarray(ys, dtype=float)
            if float(np.std(x_a)) > 0.0:
                m, b = np.polyfit(x_a, y_a, deg=1)
                xa = sorted(xs)
                ax.plot(
                    xa,
                    [m * xi + b for xi in xa],
                    "--",
                    color=color,
                    linewidth=1.15,
                    alpha=0.95,
                )
    if not drew:
        plt.close(fig)
        return None
    ax.set_xlabel("km")
    ax.set_ylabel("Price (EUR)")
    ax.ticklabel_format(style="plain", axis="y")
    ax.legend(loc="upper right", fontsize=7, framealpha=0.92)
    ax.set_title("Price vs km — compared cars", fontsize=10)
    fig.tight_layout()
    bio = io.BytesIO()
    fig.savefig(bio, format="png", dpi=128)
    plt.close(fig)
    bio.seek(0)
    return bio


def compare_year_price_png(
    series: list[tuple[str, list[dict[str, Any]]]],
) -> io.BytesIO | None:
    """One scatter + optional OLS per car; year axis as integers."""
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    drew = False
    for idx, (label, rows) in enumerate(series):
        color = COMPARE_SERIES_COLORS[idx % len(COMPARE_SERIES_COLORS)]
        xs: list[float] = []
        ys: list[float] = []
        for r in rows:
            py = r.get("_parsed_year")
            pp = r.get("_parsed_price")
            if py is None or pp is None:
                continue
            xs.append(float(py))
            ys.append(float(pp))
        if len(xs) < 2:
            continue
        drew = True
        ax.scatter(
            xs,
            ys,
            c=color,
            s=28,
            alpha=0.86,
            edgecolors="white",
            linewidths=0.35,
            label=str(label)[:34],
        )
        if len(xs) >= 4:
            x_a = np.asarray(xs, dtype=float)
            y_a = np.asarray(ys, dtype=float)
            if float(np.std(x_a)) > 0.0:
                m, b = np.polyfit(x_a, y_a, deg=1)
                xa = sorted(xs)
                ax.plot(
                    xa,
                    [m * xi + b for xi in xa],
                    "--",
                    color=color,
                    linewidth=1.15,
                    alpha=0.95,
                )
    if not drew:
        plt.close(fig)
        return None
    ax.set_xlabel("Registration year")
    ax.set_ylabel("Price (EUR)")
    ax.ticklabel_format(style="plain", axis="y")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=8))
    ax.ticklabel_format(style="plain", axis="x", useOffset=False)
    ax.legend(loc="upper right", fontsize=7, framealpha=0.92)
    ax.set_title("Price vs registration year — compared cars", fontsize=10)
    fig.tight_layout()
    bio = io.BytesIO()
    fig.savefig(bio, format="png", dpi=128)
    plt.close(fig)
    bio.seek(0)
    return bio


def compare_price_stats_lines_png(
    labels: list[str],
    stats_list: list[dict[str, Any]],
) -> io.BytesIO | None:
    """One line per car over Min → Median → Average → Max (EUR)."""
    keys = ("lowest", "median", "average", "highest")
    x_labels = ("Min", "Median", "Average", "Max")
    x = np.arange(len(x_labels), dtype=float)
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    drew = False
    for i, (lab, stats) in enumerate(zip(labels, stats_list)):
        ys: list[float] = []
        for k in keys:
            v = stats.get(k)
            ys.append(float(v) if v is not None else float("nan"))
        if all(np.isnan(np.asarray(ys, dtype=float))):
            continue
        drew = True
        color = COMPARE_SERIES_COLORS[i % len(COMPARE_SERIES_COLORS)]
        ax.plot(
            x,
            ys,
            marker="o",
            linewidth=2.1,
            markersize=8,
            color=color,
            label=str(lab)[:30],
        )
    if not drew:
        plt.close(fig)
        return None
    ax.set_xticks(x, x_labels)
    ax.set_ylabel("Price (EUR)")
    ax.ticklabel_format(style="plain", axis="y")
    ax.legend(loc="best", fontsize=7, framealpha=0.92)
    ax.set_title("Price summary — min / median / average / max", fontsize=10)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    bio = io.BytesIO()
    fig.savefig(bio, format="png", dpi=128)
    plt.close(fig)
    bio.seek(0)
    return bio


def germany_listings_map_png_multi(
    series: list[tuple[str, list[dict[str, Any]]]],
) -> io.BytesIO | None:
    """Germany map: one Scattergeo trace per car (color + name in legend)."""
    try:
        import plotly.graph_objects as go
    except Exception:
        return None

    from listings_geo_de import latlon_from_city_field

    traces: list[Any] = []
    for si, (car_label, rows) in enumerate(series):
        color = COMPARE_SERIES_COLORS[si % len(COMPARE_SERIES_COLORS)]
        key_counts: dict[tuple[float, float], int] = {}
        lats: list[float] = []
        lons: list[float] = []
        texts: list[str] = []
        for r in rows:
            city = r.get("city")
            ll = latlon_from_city_field(city)
            if ll is None:
                continue
            la, lo = ll
            n = key_counts.get((la, lo), 0)
            key_counts[(la, lo)] = n + 1
            jitter_la = la + (n % 5) * 0.012 - 0.024
            jitter_lo = lo + (n // 5) * 0.014 - 0.021
            lats.append(jitter_la)
            lons.append(jitter_lo)
            label = str(city or "").strip()[:40] or "?"
            mm = (r.get("make_model") or "").strip()[:36]
            car_short = str(car_label)[:28]
            texts.append(f"<b>{car_short}</b><br>{label}<br>{mm}" if mm else f"<b>{car_short}</b><br>{label}")
        if not lats:
            continue
        _leg = str(car_label).strip()
        _short_leg = (_leg[:26] + "…") if len(_leg) > 26 else _leg
        traces.append(
            go.Scattergeo(
                lat=lats,
                lon=lons,
                mode="markers",
                marker=dict(size=10, color=color, line=dict(width=0.7, color="white"), opacity=0.9),
                name=f"({si + 1}) {_short_leg}",
                text=texts,
                hovertemplate="%{text}<extra></extra>",
            )
        )
    if not traces:
        return None

    fig = go.Figure(data=traces)
    fig.update_geos(
        visible=True,
        resolution=50,
        showcountries=True,
        countrycolor="#b0bec5",
        showland=True,
        landcolor="#eceff1",
        showcoastlines=True,
        coastlinecolor="#90a4ae",
        projection_type="mercator",
        lonaxis_range=[5.6, 15.3],
        lataxis_range=[47.2, 55.1],
        bgcolor="white",
        domain=dict(x=[0.0, 0.62], y=[0.02, 0.96]),
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=48, b=24),
        height=440,
        width=880,
        title=dict(
            text="Listing locations — compared cars (Geonames)",
            font=dict(size=14, color="#0d47a1"),
            x=0.31,
            xanchor="center",
        ),
        paper_bgcolor="white",
        legend=dict(
            orientation="v",
            xref="paper",
            yref="paper",
            x=0.64,
            y=0.52,
            xanchor="left",
            yanchor="middle",
            bgcolor="rgba(255,255,255,0.97)",
            bordercolor="#90a4ae",
            borderwidth=1,
            font=dict(size=11),
            tracegroupgap=18,
            itemsizing="constant",
            title=dict(text="Cars", side="top", font=dict(size=11)),
        ),
    )
    out = io.BytesIO()
    try:
        fig.write_image(out, format="png", scale=1.45)
    except Exception:
        return None
    out.seek(0)
    if not out.getvalue():
        return None
    return out
