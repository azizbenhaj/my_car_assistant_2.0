# Domain notes

## Structured fields (today’s graph)

| Key | Meaning / normalization |
|-----|--------------------------|
| `intent` | `buy` \| `sell` |
| `maker` | OEM / brand label (trimmed casing LLM-dependent) |
| `model` | Model line substring |
| `year` | Numeric year; prompts use heuristics for “brand new”; **CSV uses `first_registration` (DATE text)** → use `extract(year …)` **or substring first 4 chars** when querying |
| `km` | Odometer kilometres; grounded to user wording in code |
| `fuel` | `gasoline`, `diesel`, `electric`, `hybrid` (lowercase normalized) |
| `gearbox` | `automatic`, `manual` |

**Completeness gate for DB:** non-null **`intent`, `maker`, `model`, `year`, `km`** before running listing SQL — consider relaxing fields if product allows broader match (later).

## Runtime retrieval (`listings_retrieval.py`)

When all five required keys are present, the app builds a **`WHERE`** clause from:

| JSON field | SQL idea |
|------------|----------|
| `maker` | `TRIM(maker) ILIKE TRIM(%pattern%)` (same brand) |
| `model` | `TRIM(model) ILIKE TRIM(%pattern%)` (same model line) |
| `year` | registration year from **`first_registration`** within **`±LISTINGS_YEAR_TOLERANCE`** years of JSON `year` (default **±2**) |
| `km` | parsed listing `km` (digits only) within **`±LISTINGS_KM_TOLERANCE`** of JSON `km` (default **±20 000** km) |

**Not used in SQL:** `fuel`, `gearbox`, `intent` (ignored for matching). Env overrides: **`LISTINGS_YEAR_TOLERANCE`**, **`LISTINGS_KM_TOLERANCE`**. Result capped at **50** rows (`LIMIT`), no `ORDER BY` (yet).

---

## CSV columns (`autoscout_de_parsed.csv`)

**17 columns.** Ingest with **`load_csv_to_postgres.py`** into Postgres (table columns match CSV names, all **TEXT**; column **`Fuel`** is mixed-case — quote as `"Fuel"` in SQL).

| Column | Role / keyword | Example raw value | Notes for filtering |
|--------|----------------|-------------------|---------------------|
| `url` | listing link | `https://…` | Show as “open listing”; primary key surrogate = row id if none |
| `image` | photo URL | `https://…` | Optional thumbnails |
| `make_model` | combined title string | `Volkswagen Polo 1.2 47kW` | Full-text auxiliary; overlaps `maker`+`model`+`extra` |
| `price` | display price | `€ 500` | **Needs parsing** (`regexp_replace`/`CAST`) for min/max euros |
| `km` | mileage display | `164,200 km` | Strip `km`, commas → integer **in SQL/Python** |
| `Fuel` | fuel type | `Gasoline` | Map to extractor: case-insensitive; “Petrol”→gasoline etc. |
| `gearbox` | transmission | `Manual` | Match `ILIKE` to `manual` / `automatic` |
| `first_registration` | reg date | `2003-04-01` | Filter **year**: `CAST(left(first_registration,4) AS int)` or `DATE` cast + `extract` |
| `hp` | power | `64.0` | Optional filter / sort |
| `vehicle_type` | body/class | `Car` | Rarely needed for MVP |
| `co2_g_per_km` | emissions text | `- (g/km)` … | Scraped mess; analytics later |
| `cons_comb` | consumption label | `5.9 l/100 km (comb.)` | Display / analytics later |
| `seller_type` | Dealer/Private… | `Dealer` | Optional filter |
| `city` | location | `Kassel` | Optional filter (`ILIKE`) |
| `maker` | brand | `Volkswagen` | **Primary** match; tolerate case |
| `model` | model line | `Polo` | **`ILIKE '%' || model || '%'`** cautiously (ambiguous short names) |
| `extra` | trim/snippet | `1.2 47kW` | Optional containment search |

---

## JSON → column mapping (query design)

| Extractor JSON | CSV / SQL idea |
|----------------|----------------|
| `maker` | `LOWER(TRIM(maker)) = LOWER(:maker)` (+ fuzzy later) |
| `model` | `model ILIKE '%' || :model || '%'` (tune!) |
| `year` | `LEFT(first_registration, 4) = :year` or date range ±0 years |
| `km` | parse listing `km` to int; **`<= :km_user` or band** (“around 80k” → ±10%) once product rule defined |
| `fuel` | map JSON → synonyms; `Fuel` **`ILIKE`** match |
| `gearbox` | `gearbox` **`ILIKE`** match |
| `intent` | not in CSV — **routing only** (buy→compare; sell→“comps” wording) |

**Gotchas**

- Postgres table uses quoted identifiers **`"Fuel"`** (mixed case column name).
- `price`/`km` are human strings, not typed numbers until you CAST in query or preprocess in ingest v2.

## User expectations

Conversational results; collapsible technical JSON optional later.
