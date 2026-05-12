"""PDF reports — deep listing dossiers with thumbnails, links, and charts."""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)

from listings_media import fetch_image_png_bytes
from listings_similarity import intent_buy_or_sell_plain


class _SizedPngImage(Flowable):
    """PNG drawn at fixed pt size — avoids RL ``Image._setup_inner`` + ``ImageReader.getSize()`` bugs in tables."""

    _fixedWidth = 1
    _fixedHeight = 1

    def __init__(self, png_bytes: bytes, draw_width: float, draw_height: float):
        self._png = png_bytes
        self.drawWidth = draw_width
        self.drawHeight = draw_height
        self.hAlign = "LEFT"

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        return self.drawWidth, self.drawHeight

    def draw(self) -> None:
        from reportlab.lib.utils import ImageReader

        self.canv.drawImage(
            ImageReader(io.BytesIO(self._png)),
            0,
            0,
            width=self.drawWidth,
            height=self.drawHeight,
            mask="auto",
        )


def _reportlab_png(
    buf: io.BytesIO | None,
    *,
    max_draw_width: float,
    max_draw_height: float,
) -> Flowable | None:
    """
    Fixed-size PNG flowable: Pillow measures pixels; ReportLab ImageReader sizing in tables was unreliable (~1e7 pt height).
    """
    if buf is None:
        return None
    raw = buf.getvalue()
    if not raw:
        return None
    try:
        from PIL import Image as PILImage

        src = PILImage.open(io.BytesIO(raw))
        try:
            src.load()
            w0, h0 = src.size
        finally:
            src.close()
        if not w0 or not h0:
            return None
        scale = min(max_draw_width / float(w0), max_draw_height / float(h0))
        rw = max(1.0, w0 * scale)
        rh = max(1.0, h0 * scale)
        return _SizedPngImage(raw, rw, rh)
    except Exception:
        return None


def _xml_txt(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _p(html: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(html.replace("\n", "<br/>"), style)


def _para_from_url(url: str | None, link_style: ParagraphStyle) -> Paragraph:
    if not url or not str(url).strip().startswith("http"):
        return Paragraph("<i>No URL</i>", link_style)
    u = _xml_txt(str(url).strip())
    return Paragraph(
        f'<a href="{u}" color="blue"><font size="7"><u>Open listing webpage</u></font></a>',
        link_style,
    )


def _listing_spec_html(row: dict[str, Any], include_tolerance: bool) -> str:
    """All listing characteristics — no gaps vs query."""
    chunks: list[str] = []

    def add(label: str, key: str) -> None:
        v = row.get(key)
        if v is None or str(v).strip() == "":
            return
        chunks.append(f"<b>{label}:</b> {_xml_txt(str(v).strip())[:520]}")

    add("Make / model", "make_model")
    add("Brand", "maker")
    add("Model", "model")
    add("Price", "price")
    add("Km", "km")
    add("Fuel", "Fuel")
    add("Gearbox", "gearbox")
    add("Horsepower", "hp")
    add("Vehicle type", "vehicle_type")
    add("CO2 (g/km)", "co2_g_per_km")
    add("Consumption comb.", "cons_comb")
    add("Seller", "seller_type")
    add("City", "city")
    add("Registration", "first_registration")
    add("Match vs query %", "_match_pct")
    if row.get("_top3_similar"):
        chunks.append("<b>Similarity tier:</b> among top‑3 closest matches ★")

    tol = "; ".join(row.get("_tolerance_notes") or [])
    if include_tolerance and tol:
        chunks.append(f"<b>Tolerance / confidence:</b> {_xml_txt(tol)[:520]}")

    return "<br/>".join(chunks) if chunks else "<i>(limited detail)</i>"


def generate_deep_listings_pdf_bytes(
    *,
    evaluated: dict[str, Any],
    pool: list[dict[str, Any]],
    stats: dict[str, Any],
    region_lines: list[str],
    charts_combined_png: io.BytesIO | None,
    max_cards: int = 50,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        title="Marketplace report",
        leftMargin=0.35 * inch,
        rightMargin=0.38 * inch,
        topMargin=0.42 * inch,
        bottomMargin=0.42 * inch,
        pageCompression=True,
    )

    ss = getSampleStyleSheet()
    title_st = ParagraphStyle(
        name="Tit",
        parent=ss["Heading1"],
        fontSize=13,
        textColor=colors.HexColor("#0d47a1"),
    )
    body = ParagraphStyle(
        name="Bod",
        parent=ss["BodyText"],
        fontSize=8,
        leading=10,
    )
    small = ParagraphStyle(
        name="Sm",
        parent=ss["BodyText"],
        fontSize=7,
        leading=8.8,
        textColor=colors.HexColor("#37474f"),
    )
    link_st = ParagraphStyle(
        name="Ln",
        parent=ss["BodyText"],
        fontSize=7,
        alignment=TA_LEFT,
    )
    body_card = ParagraphStyle(
        name="BodCard",
        parent=ss["BodyText"],
        fontSize=7.5,
        leading=9,
    )

    story: list[Any] = []

    intro = intent_buy_or_sell_plain(evaluated)
    stats_line = (
        f"Matched <b>{len(pool)}</b> listings (shown up to {max_cards} with thumbnails). "
        f"Parsable prices: <b>{stats.get('count', 0)}</b>."
    )

    rg = "<br/>".join(_xml_txt(x) for x in region_lines[:22]) if region_lines else "—"

    tbl_intro = Table(
        [
            [
                _p("<b>Synopsis</b><br/><br/>" + _xml_txt(intro) + "<br/><br/>" + stats_line, small),
                _p("<b>Listings per Bundesland</b><br/><i>(derived from city + Geonames / PLZ)</i><br/><br/>" + rg, small),
            ]
        ],
        colWidths=[(doc.width - 14) / 2] * 2,
    )
    tbl_intro.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#1565c0")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafcff")),
            ]
        )
    )

    story.append(_p("<b>Car assistant — deep marketplace dossier</b>", title_st))
    story.append(Spacer(1, 0.08 * inch))
    story.append(tbl_intro)
    story.append(Spacer(1, 0.12 * inch))

    if charts_combined_png is not None:
        charts_combined_png.seek(0)
        chart_img = _reportlab_png(
            charts_combined_png,
            max_draw_width=doc.width * 0.98,
            max_draw_height=doc.height * 0.62,
        )
        if chart_img is not None:
            story.append(_p("<b>Market charts — 2×2 (price, km, year, Germany map)</b>", body))
            story.append(Spacer(1, 0.05 * inch))
            story.append(chart_img)
            story.append(Spacer(1, 0.14 * inch))

    story.append(_p("<b>Detailed listings</b> <font size=\"6\">(image + clickable link per row)</font>", body))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#90a4ae")))
    story.append(Spacer(1, 0.08 * inch))

    thumb_w = 1.15 * inch
    text_col = doc.width - thumb_w - 16
    slice_pool = pool[:max_cards]

    for idx, row in enumerate(slice_pool):
        png = fetch_image_png_bytes(row.get("image"))
        ph = _reportlab_png(
            png,
            max_draw_width=thumb_w,
            max_draw_height=thumb_w * 0.95,
        )
        if ph is None:
            ph = Paragraph("<i>No photo</i>", small)

        spec = Paragraph(_listing_spec_html(row, include_tolerance=True), body_card)
        lk = _para_from_url(row.get("url"), link_st)
        # Not KeepTogether: KT.wrap() returns height 0xffffff which breaks Table row sizing.
        right_cells: list[Any] = [lk, Spacer(1, 0.035 * inch), spec]
        card = Table([[ph, right_cells]], colWidths=[thumb_w + 6, max(text_col, 220)])
        card.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        colors.HexColor("#e8f5e9")
                        if row.get("_top3_similar")
                        else colors.white,
                    ),
                    ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#cfd8dc")),
                ]
            )
        )
        banner = Paragraph(
            f"<b>Listing {idx + 1}</b> — "
            + _xml_txt((row.get("make_model") or "?")[:80]),
            ParagraphStyle(name="Bx", parent=body, fontSize=8.5, textColor=colors.HexColor("#1a237e")),
        )

        blk = KeepTogether([banner, Spacer(1, 2), card])
        story.append(blk)
        story.append(Spacer(1, 0.055 * inch))
        if (idx + 1) % 5 == 0 and idx + 1 < len(slice_pool):
            story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()


def generate_quick_listings_pdf_bytes(
    pool_rows: list[dict[str, Any]],
    evaluated: dict[str, Any],
    *,
    max_cards: int = 20,
) -> bytes:
    """Compact dossier PDF (default top 20) with thumbnails and links."""
    from listings_similarity import aggregate_by_region, aggregate_prices

    cap = max(1, min(int(max_cards), 50))
    slim = pool_rows[:cap]
    agg = aggregate_prices(slim)
    regs = aggregate_by_region(slim)
    lines = [
        f"{k}: {v}"
        for k, v in sorted(regs.items(), key=lambda x: (-x[1], x[0]))[:22]
    ]

    combo = None
    try:
        from listings_viz import combined_market_dashboard_png

        combo = combined_market_dashboard_png(slim, agg)
    except Exception:
        combo = None

    return generate_deep_listings_pdf_bytes(
        evaluated=evaluated,
        pool=slim,
        stats=agg,
        region_lines=lines or ["(No region aggregates)"],
        charts_combined_png=combo,
        max_cards=cap,
    )


def generate_compare_listings_pdf_bytes(
    sessions: list[dict[str, Any]],
    *,
    max_per_car: int = 20,
) -> bytes:
    """Multi-car PDF: shared comparison charts + per-car listing cards (thumbnails, links, specs)."""
    from listings_similarity import aggregate_prices

    if len(sessions) < 2:
        return b""

    cap = max(1, min(int(max_per_car), 20))
    labels = [str(s.get("label") or "?") for s in sessions]
    rows_per = [list(s.get("enriched_slim") or [])[:cap] for s in sessions]
    series = list(zip(labels, rows_per))
    stats_list = [aggregate_prices(r) for r in rows_per]

    buf_km = buf_y = buf_s = buf_m = None
    try:
        from listings_viz import (
            compare_km_price_png,
            compare_price_stats_lines_png,
            compare_year_price_png,
            germany_listings_map_png_multi,
        )

        buf_km = compare_km_price_png(series)
        buf_y = compare_year_price_png(series)
        buf_s = compare_price_stats_lines_png(labels, stats_list)
        buf_m = germany_listings_map_png_multi(series)
    except Exception:
        pass

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        title="Car comparison report",
        leftMargin=0.35 * inch,
        rightMargin=0.38 * inch,
        topMargin=0.42 * inch,
        bottomMargin=0.42 * inch,
        pageCompression=True,
    )

    ss = getSampleStyleSheet()
    title_st = ParagraphStyle(
        name="TitCmp",
        parent=ss["Heading1"],
        fontSize=13,
        textColor=colors.HexColor("#0d47a1"),
    )
    body = ParagraphStyle(
        name="BodCmp",
        parent=ss["BodyText"],
        fontSize=8,
        leading=10,
    )
    small = ParagraphStyle(
        name="SmCmp",
        parent=ss["BodyText"],
        fontSize=7,
        leading=8.8,
        textColor=colors.HexColor("#37474f"),
    )
    link_st = ParagraphStyle(
        name="LnCmp",
        parent=ss["BodyText"],
        fontSize=7,
        alignment=TA_LEFT,
    )
    body_card = ParagraphStyle(
        name="BodCardCmp",
        parent=ss["BodyText"],
        fontSize=7.5,
        leading=9,
    )
    car_head = ParagraphStyle(
        name="CarHeadCmp",
        parent=body,
        fontSize=9.5,
        textColor=colors.HexColor("#1565c0"),
    )

    story: list[Any] = []
    story.append(_p("<b>Car assistant — marketplace comparison</b>", title_st))
    story.append(Spacer(1, 0.08 * inch))

    intro_bits: list[str] = []
    for i, s in enumerate(sessions):
        ev = dict(s.get("evaluated_snapshot") or s.get("vehicle_json") or {})
        line = intent_buy_or_sell_plain(ev)
        intro_bits.append(
            f"<b>{i + 1}.</b> {_xml_txt(labels[i])}<br/><i>{_xml_txt(line)[:340]}</i>"
        )
    story.append(_p("<br/><br/>".join(intro_bits), small))
    story.append(Spacer(1, 0.12 * inch))

    chart_specs = [
        ("Price vs km (all cars)", buf_km),
        ("Price vs registration year (all cars)", buf_y),
        ("Price summary — min / median / average / max", buf_s),
        ("Germany — listing locations", buf_m),
    ]
    for tit, blob in chart_specs:
        if blob is None:
            continue
        blob.seek(0)
        im = _reportlab_png(
            blob,
            max_draw_width=doc.width * 0.98,
            max_draw_height=doc.height * 0.33,
        )
        if im is None:
            continue
        story.append(_p(f"<b>{tit}</b>", body))
        story.append(Spacer(1, 0.04 * inch))
        story.append(im)
        story.append(Spacer(1, 0.1 * inch))

    story.append(PageBreak())
    story.append(
        _p(
            '<b>Listings by car</b> <font size="6">(up to 20 per vehicle — thumbnail + link)</font>',
            body,
        )
    )
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#90a4ae")))
    story.append(Spacer(1, 0.08 * inch))

    thumb_w = 1.1 * inch
    text_col = doc.width - thumb_w - 12

    for ci, sess in enumerate(sessions):
        story.append(_p(f"<b>Car {ci + 1}:</b> {_xml_txt(str(sess.get('label') or '?'))}", car_head))
        story.append(Spacer(1, 0.06 * inch))
        rows = list(sess.get("enriched_slim") or [])[:cap]
        if not rows:
            story.append(
                _p(
                    "<i>No listing rows for this profile — complete a buy/sell run with database matches.</i>",
                    small,
                )
            )
            story.append(Spacer(1, 0.12 * inch))
            continue
        for idx, row in enumerate(rows):
            png = fetch_image_png_bytes(row.get("image"))
            ph = _reportlab_png(
                png,
                max_draw_width=thumb_w,
                max_draw_height=thumb_w * 0.95,
            )
            if ph is None:
                ph = Paragraph("<i>No photo</i>", small)

            spec = Paragraph(_listing_spec_html(row, include_tolerance=True), body_card)
            lk = _para_from_url(row.get("url"), link_st)
            right_cells: list[Any] = [lk, Spacer(1, 0.035 * inch), spec]
            card = Table([[ph, right_cells]], colWidths=[thumb_w + 6, max(text_col, 200)])
            card.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        (
                            "BACKGROUND",
                            (0, 0),
                            (-1, -1),
                            colors.HexColor("#e8f5e9")
                            if row.get("_top3_similar")
                            else colors.white,
                        ),
                        ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#cfd8dc")),
                    ]
                )
            )
            banner = Paragraph(
                f"<b>Car {ci + 1} · Listing {idx + 1}</b> — "
                + _xml_txt((row.get("make_model") or "?")[:76]),
                ParagraphStyle(
                    name=f"BxCmp{ci}_{idx}",
                    parent=body,
                    fontSize=8.5,
                    textColor=colors.HexColor("#1a237e"),
                ),
            )
            story.append(KeepTogether([banner, Spacer(1, 2), card]))
            story.append(Spacer(1, 0.055 * inch))
            if (idx + 1) % 4 == 0 and idx + 1 < len(rows):
                story.append(PageBreak())
        if ci < len(sessions) - 1:
            story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()
