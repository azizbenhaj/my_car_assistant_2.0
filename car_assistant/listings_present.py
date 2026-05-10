"""Build listing choice copy, Streamlit renders, and PDF bytes from scored rows."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
import streamlit as st

from listings_pdf import generate_deep_listings_pdf_bytes, generate_quick_listings_pdf_bytes
from listings_retrieval import env_listing_tolerances
from listings_similarity import (
    aggregate_by_region,
    aggregate_prices,
    enrich_rows,
    intent_buy_or_sell_line,
    intent_buy_or_sell_plain,
    price_movement_vs_km_eur_per_km,
    price_movement_vs_year_eur_per_year,
)
from listings_viz import (
    combined_market_dashboard_png,
    price_distribution_bar_png,
    scatter_km_price_png,
    scatter_year_price_png,
)
from region_chart import try_choropleth_germany


CHOICE_PROMPT_MARKDOWN = (
    "**Here’s how we can show these listings.**\n\n"
    "- **Quick:** **10** most similar cars — **photo** + key facts in **cards** plus a **compact PDF** "
    "with thumbnails & links.\n"
    "- **Deep:** full **characteristics** table, **better price chart** (min · median · avg · max), "
    "**km** and **registration year** scatter plots, Germany **map** (~50 matches, state from **city** + "
    "GeoNames), downloadable **PDF** with **every photo**, **clickable links**, and specs (no “gaps vs query” column).\n\n"
    "**Reply in your own words** (e.g. “quick” vs “extended / full report + PDF”)."
)


SLIM_KEYS: tuple[str, ...] = (
    "url",
    "image",
    "make_model",
    "price",
    "km",
    "Fuel",
    "gearbox",
    "seller_type",
    "city",
    "hp",
    "vehicle_type",
    "co2_g_per_km",
    "cons_comb",
    "first_registration",
    "maker",
    "model",
    "extra",
    "_similarity_score",
    "_match_pct",
    "_top3_similar",
    "_missing_vs_query",
    "_tolerance_notes",
    "_parsed_price",
    "_parsed_year",
    "_parsed_km",
    "_region",
)


def slim_enriched(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows[:50]:
        row: dict[str, Any] = {}
        for k in SLIM_KEYS:
            v = r.get(k)
            if isinstance(v, str) and len(v) > 500:
                v = v[:500]
            row[k] = v
        out.append(row)
    return out


def enrich_listing_pool(
    evaluated: dict[str, Any], raw_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    km_tol, year_tol = env_listing_tolerances()
    return enrich_rows(evaluated, raw_rows, year_tol=year_tol, km_tol=km_tol)


def render_quick_cards(enriched: list[dict[str, Any]]) -> None:
    top = enriched[:10]
    st.subheader("Top 10 similar cars — compact cards")
    for i, r in enumerate(top, start=1):
        title = (r.get("make_model") or "Listing")[:80]
        url = r.get("url") or ""
        img_u = str(r.get("image") or "").strip()
        with st.container(border=True):
            c_photo, c_meta = st.columns([1.1, 2.2])
            with c_photo:
                if img_u.startswith("http"):
                    try:
                        st.image(img_u, width="stretch", clamp=True)
                    except Exception:
                        st.caption("Photo unavailable")
                else:
                    st.caption("No image URL")
            with c_meta:
                st.markdown(f"**{i}. {title}**")
                st.caption(
                    f"Match **{r.get('_match_pct', 0)}%** · "
                    f"{r.get('price', '—')} · {r.get('km', '—')} km · "
                    f"{r.get('first_registration', '—')} · "
                    f"{r.get('city', '—')}"
                )
                if r.get("_top3_similar"):
                    st.caption("★ Among the **3 closest** matches")
                meta = []
                for k, lbl in (
                    ("Fuel", "Fuel"),
                    ("gearbox", "Gearbox"),
                    ("hp", "HP"),
                    ("vehicle_type", "Type"),
                ):
                    v = r.get(k)
                    if v:
                        meta.append(f"**{lbl}:** {v}")
                if meta:
                    st.caption(" · ".join(meta))
                if url and str(url).startswith("http"):
                    st.link_button("Listing page ↗", str(url), use_container_width=True)


def render_deep_dashboard(enriched: list[dict[str, Any]], evaluated: dict[str, Any]) -> None:
    st.markdown(intent_buy_or_sell_line(evaluated))

    pool = enriched[:50]
    stats = aggregate_prices(pool)
    slope_km = price_movement_vs_km_eur_per_km(pool)
    slope_y = price_movement_vs_year_eur_per_year(pool)
    regions = aggregate_by_region(pool)

    st.subheader("Price summary (parsable EUR in this sample)")
    bar_buf = price_distribution_bar_png(stats)
    if bar_buf is not None:
        st.image(bar_buf, width="stretch")
    cols = st.columns(4)
    labels = ("Average", "Median", "Min", "Max")
    keys = ("average", "median", "lowest", "highest")
    with cols[0]:
        st.metric("Average", _fmt_eur(stats.get(keys[0])))
    with cols[1]:
        st.metric("Median", _fmt_eur(stats.get(keys[1])))
    with cols[2]:
        st.metric("Lowest", _fmt_eur(stats.get(keys[2])))
    with cols[3]:
        st.metric("Highest", _fmt_eur(stats.get(keys[3])))

    r1, r2 = st.columns(2)
    with r1:
        st.metric("≈ € per extra km (OLS)", _fmt_eur_num(slope_km))
    with r2:
        st.metric("≈ € per newer model year (OLS)", _fmt_eur_num(slope_y))

    st.caption(
        "Slopes are ordinary least squares on rows with usable price/year/km — indicative only "
        f"( **n(price)** = **{stats.get('count', 0)}** )."
    )

    st.subheader("Listing thumbnails (photos from database URL)")
    ncols = 5
    row_items = pool[:50]
    for row_start in range(0, len(row_items), ncols):
        chunk = row_items[row_start : row_start + ncols]
        gutter = st.columns(ncols)
        for j, r in enumerate(chunk):
            with gutter[j]:
                u = str(r.get("image") or "").strip()
                if u.startswith("http"):
                    try:
                        st.image(u, width="stretch", clamp=True)
                    except Exception:
                        st.caption("—")
                else:
                    st.caption("—")
                st.caption((r.get("make_model") or "")[:42])

    st.subheader("Characteristics (matched listings)")
    rows_out = []
    for r in pool:
        rows_out.append(
            {
                "Make/model": (r.get("make_model") or "")[:55],
                "Maker": str(r.get("maker") or "")[:22],
                "Model": str(r.get("model") or "")[:22],
                "Price": r.get("price"),
                "Km": r.get("km"),
                "Reg.": r.get("first_registration"),
                "Fuel": r.get("Fuel"),
                "Gearbox": r.get("gearbox"),
                "HP": r.get("hp"),
                "Vehicle type": r.get("vehicle_type"),
                "CO₂ g/km": r.get("co2_g_per_km"),
                "Cons comb.": r.get("cons_comb"),
                "Seller": r.get("seller_type"),
                "City": str(r.get("city") or "")[:40],
                "Match %": r.get("_match_pct"),
                "Top-3": "★" if r.get("_top3_similar") else "",
                "URL": _short_link(r.get("url")) or "",
            }
        )
    df = pd.DataFrame(rows_out)
    ncol = len(df.columns)

    def highlight_top3(row: pd.Series) -> list[str]:
        if row.loc["Top-3"] == "★":
            return ["background-color: #c8e6c9; font-weight: 600"] * ncol
        return [""] * ncol

    df_kw: dict[str, Any] = dict(
        use_container_width=True,
        hide_index=True,
        height=min(580, 40 + len(df) * 32),
    )
    try:
        urls = df["URL"].astype(str)
        if urls.str.startswith("http").any():
            df_kw["column_config"] = {"URL": st.column_config.LinkColumn("Link")}
    except Exception:
        pass

    st.dataframe(df.style.apply(highlight_top3, axis=1), **df_kw)

    st.subheader("Germany — listings per state (~50 matched rows)")
    st.caption("States come from **city** (GeoNames locality → Bundesland) with PLZ fallback.")
    fig = try_choropleth_germany(regions)
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
    else:
        if regions:
            st.bar_chart(
                pd.DataFrame(
                    {"state": list(regions.keys()), "count": list(regions.values())}
                ).set_index("state")
            )
        else:
            st.caption("Insufficient region assignments.")

    c1, c2 = st.columns(2)
    with c1:
        buf_k = scatter_km_price_png(pool)
        if buf_k:
            st.subheader("Price vs km")
            st.image(buf_k, width="stretch")
        else:
            st.caption("Not enough km/price pairs for scatter.")
    with c2:
        buf_y = scatter_year_price_png(pool)
        if buf_y:
            st.subheader("Price vs registration year")
            st.image(buf_y, width="stretch")
        else:
            st.caption("Not enough year/price pairs for scatter.")


def _short_link(url: Any) -> str | None:
    if not url or not str(url).strip().startswith("http"):
        return None
    return str(url).strip()


def deep_pdf_bytes(enriched: list[dict[str, Any]], evaluated: dict[str, Any]) -> bytes:
    pool = enriched[:50]
    stats = aggregate_prices(pool)
    regions = aggregate_by_region(pool)
    region_lines = [
        f"{k}: {v}" for k, v in sorted(regions.items(), key=lambda x: (-x[1], x[0]))[:28]
    ]
    combo_buf: io.BytesIO | None = None
    buf_try = combined_market_dashboard_png(pool, stats)
    if buf_try is not None:
        combo_buf = buf_try

    return generate_deep_listings_pdf_bytes(
        evaluated=evaluated,
        pool=pool,
        stats=stats,
        region_lines=region_lines,
        charts_combined_png=combo_buf,
        max_cards=50,
    )


def quick_cards_pdf_bytes(slim_slice: list[dict[str, Any]], evaluated: dict[str, Any]) -> bytes:
    return generate_quick_listings_pdf_bytes(slim_slice[:10], evaluated)


def _fmt_eur(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"€{float(v):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_eur_plain(v: Any) -> str:
    if v is None:
        return "n/a"
    try:
        return f"{float(v):,.0f} EUR"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_eur_num(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return "—"
