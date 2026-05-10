"""Charts for Streamlit UI and embedded PDF thumbnails."""

from __future__ import annotations

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
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
    fig.tight_layout()
    bio = io.BytesIO()
    fig.savefig(bio, format="png", dpi=120)
    plt.close(fig)
    bio.seek(0)
    return bio


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
    """Single stacked PNG for PDF/app: bar summary + km scatter + year scatter."""
    bio_bar = price_distribution_bar_png(stats)
    bio_km = scatter_km_price_png(rows)
    bio_yr = scatter_year_price_png(rows)
    if bio_bar is None and bio_km is None and bio_yr is None:
        return None

    titles = ("Price overview (EUR)", "Price vs km", "Price vs registration year")
    blobs = (bio_bar, bio_km, bio_yr)
    fig, axes = plt.subplots(3, 1, figsize=(6.6, 8.2))
    for ax, title, blob in zip(axes, titles, blobs):
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
