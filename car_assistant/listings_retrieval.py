"""
Retrieve up to N listing rows from PostgreSQL using evaluated extractor JSON.

Filters (relaxed):
  - Same **maker** / **model** (trimmed `ILIKE` patterns).
  - **Year**: first_registration model year within ±LISTINGS_YEAR_TOLERANCE (default 2) of extracted year.
  - **km**: parsed listing odometer within ±LISTINGS_KM_TOLERANCE (default 20_000) of extracted km.
  - **fuel** / **gearbox** / **intent** are not used in SQL (ignored).

Requires DATABASE_URL; table default autoscout_de_parsed (LISTINGS_TABLE).
"""

from __future__ import annotations

import os
import re
from typing import Any

import psycopg
from psycopg.rows import dict_row

_DEFAULT_LIMIT = 50
_TABLE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

_PARSED_KM_SQL = (
    "NULLIF(REGEXP_REPLACE(REPLACE(TRIM(km), ',', ''), '[^0-9]', '', 'g'), '')::bigint"
)


def _table_name() -> str:
    return os.getenv("LISTINGS_TABLE", "autoscout_de_parsed").strip()


def env_listing_tolerances() -> tuple[int, int]:
    """Km tolerance then year tolerance — matches WHERE clause."""
    return max(0, _int_env("LISTINGS_KM_TOLERANCE", 20_000)), max(
        0, _int_env("LISTINGS_YEAR_TOLERANCE", 2)
    )


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def fetch_top_listings(
    evaluated: dict[str, Any],
    *,
    limit: int = _DEFAULT_LIMIT,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Return (rows, error_message). rows is empty if error_message is set or no matches.
    """
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return [], "DATABASE_URL is not set — export it to search listings."

    table = _table_name()
    if not _TABLE_RE.match(table):
        return [], "Invalid LISTINGS_TABLE (use letters, numbers, underscore only)."

    if limit < 1 or limit > 500:
        limit = _DEFAULT_LIMIT

    km_tol = max(0, _int_env("LISTINGS_KM_TOLERANCE", 20_000))
    year_tol = max(0, _int_env("LISTINGS_YEAR_TOLERANCE", 2))

    where_parts: list[str] = []
    params: list[Any] = []

    maker = evaluated.get("maker")
    if maker is not None and str(maker).strip():
        where_parts.append("TRIM(maker) ILIKE TRIM(%s)")
        params.append(f"%{str(maker).strip()}%")

    model = evaluated.get("model")
    if model is not None and str(model).strip():
        where_parts.append("TRIM(model) ILIKE TRIM(%s)")
        params.append(f"%{str(model).strip()}%")

    year = evaluated.get("year")
    if year is not None:
        try:
            y = int(year)
            where_parts.append(
                "(SUBSTRING(TRIM(first_registration) FROM 1 FOR 4) ~ '^[0-9]{4}$' "
                "AND ABS(CAST(SUBSTRING(TRIM(first_registration) FROM 1 FOR 4) AS INTEGER) - %s) <= %s)"
            )
            params.append(y)
            params.append(year_tol)
        except (TypeError, ValueError):
            pass

    km = evaluated.get("km")
    if km is not None:
        try:
            km_int = int(km)
        except (TypeError, ValueError):
            km_int = None
        if km_int is not None:
            pk = _PARSED_KM_SQL
            where_parts.append(f"({pk} IS NOT NULL AND ABS({pk} - %s) <= %s)")
            params.append(km_int)
            params.append(km_tol)

    if not where_parts:
        where_parts.append("TRUE")

    where_sql = " AND ".join(where_parts)

    sql = f"""
        SELECT
            url,
            image,
            make_model,
            price,
            km,
            "Fuel",
            gearbox,
            first_registration,
            hp,
            seller_type,
            city,
            maker,
            model,
            vehicle_type,
            co2_g_per_km,
            cons_comb,
            extra
        FROM {table}
        WHERE {where_sql}
        LIMIT %s
    """
    params.append(limit)

    try:
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        return [dict(r) for r in rows], None
    except psycopg.Error as e:
        return [], f"Database error: {e}"
