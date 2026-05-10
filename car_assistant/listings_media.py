"""Fetch listing images over HTTP for Streamlit/PDF embedding."""

from __future__ import annotations

import io
import urllib.error
import urllib.request

DEFAULT_UA = (
    "Mozilla/5.0 (compatible; CarAssistant/1.0; +https://example.invalid)"
)


def fetch_image_png_bytes(url: str | None, *, timeout: float = 10.0) -> io.BytesIO | None:
    if not url or not str(url).strip().startswith("http"):
        return None
    req = urllib.request.Request(
        str(url).strip(),
        headers={"User-Agent": DEFAULT_UA},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if not raw or len(raw) > 8_000_000:
        return None
    try:
        from PIL import Image as PILImage
    except ImportError:
        bio = io.BytesIO(raw)
        bio.seek(0)
        return bio

    try:
        im = PILImage.open(io.BytesIO(raw))
        im = im.convert("RGB")
        im.thumbnail((280, 200), PILImage.Resampling.LANCZOS)
        out = io.BytesIO()
        im.save(out, format="PNG", optimize=True)
        out.seek(0)
        return out
    except Exception:
        return None
