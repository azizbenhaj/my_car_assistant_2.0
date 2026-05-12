# My Car Assistant 2.0

A **Streamlit** app that turns natural-language car buy/sell questions into **structured JSON**, searches a **PostgreSQL** listings database, scores matches, and shows **cards, charts, maps, and PDFs** — powered by **LangGraph** + **LangChain Ollama** (local LLMs).

---

## Table of contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Architecture (LangGraph)](#architecture-langgraph)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Install & run](#install--run)
- [Environment variables](#environment-variables)
- [Database: Postgres + CSV load](#database-postgres--csv-load)
- [How to use the app](#how-to-use-the-app)
- [PDFs & exports](#pdfs--exports)
- [Listings, scoring & charts](#listings-scoring--charts)
- [Optional / extension points](#optional--extension-points)
- [Troubleshooting](#troubleshooting)

---

## Features

| Area | What you get |
|------|----------------|
| **Home** | Choose **Buy or sell a car** (chat flow) or **Compare cars** (saved profiles only, no chat). |
| **Buy / sell chat** | Two-pass NLP: **extractor** → **evaluator** over **Ollama**; collects **intent, maker, model, year, km** (+ optional **fuel, gearbox**). |
| **Missing fields** | Targeted follow-up: prior JSON + your reply is merged until all required keys are present. |
| **Listings search** | After fields are complete, **PostgreSQL** query (maker/model `ILIKE`, registration **year ± tolerance**, odometer **km ± tolerance**). |
| **Quick results (default)** | Up to **20** top similar listings as **photo cards**, match %, metadata, **download PDF** (quick dossier). Chat locks when the run completes. |
| **Deep results (code path)** | Full **dashboard**: price metrics, **2×2** chart grid (price bars, km vs price, year vs price, **Germany map**), Bundesland choropleth/table, wide listing table, **deep PDF** — still rendered if a message carries `results_style: "deep"` (main flow today always uses **quick**). |
| **Saved cars (sidebar)** | Up to **10** autosaved sessions after a successful listing run; **Load** restores view, **PDF** exports quick dossier (snapshot or live DB rebuild), **Del** removes. |
| **Compare** | Pick **2 or 3** saved cars → **Compare** → overlaid **km/price** and **year/price** plots, **price summary** lines (min/median/avg/max), **multi-series Germany map** with legend, side-by-side listing tables (20 rows each), **comparison PDF**. |
| **Geography** | City → **Bundesland** (GeoNames + PLZ fallback); map points via **GeoNames** lat/lon where available. |
| **Similarity** | **RapidFuzz** on maker/model, tolerances, **NumPy** aggregates and OLS-style slopes for charts. |

---

## Tech stack

- **UI:** [Streamlit](https://streamlit.io/) (`main.py`)
- **Orchestration:** [LangGraph](https://github.com/langchain-ai/langgraph) `StateGraph` — linear graph **START → extractor → evaluator → END** (`graph.py`)
- **LLM integration:** [LangChain Ollama](https://python.langchain.com/docs/integrations/chat/ollama/) `ChatOllama` (`langchain-ollama`, `langchain-core`)
- **Database:** [psycopg](https://www.psycopg.org/) 3 (`listings_retrieval.py`)
- **Data / math:** pandas, numpy, RapidFuzz
- **Viz:** matplotlib, plotly (+ **kaleido** for static map/chart PNGs), ReportLab + Pillow for PDFs
- **Geo:** [geonamescache](https://pypi.org/project/geonamescache/) for German cities / coordinates

> **Note on “skills”:** This repository is the application code. If you use **Cursor**, you can attach community or custom **Agent Skills** (e.g. CI, PR hygiene) in your own environment — they are not vendored here. The “skills” of the product itself are the **structured extraction**, **SQL retrieval**, and **ranking/visualization** layers above.

---

## Architecture (LangGraph)

```mermaid
flowchart LR
  START([START]) --> E[extractor_agent]
  E --> V[evaluator_agent]
  V --> END([END])
```

- **`extractor_agent`:** Free text → draft JSON; **query grounding** for `km` (e.g. explicit “80k km” vs vague text).
- **`evaluator_agent`:** Refines JSON; may run up to **`EVALUATOR_MAX_PASSES`** internal LLM passes until required slots stop shrinking or cap is hit.
- **State:** `state.QueryState` — `query`, `extracted`, `evaluated_extracted`, `missing_required_fields`, `ask_user`.

Invoke from Python: `from graph import graph` then `graph.invoke({"query": "...", "extracted": {}})`.

---

## Repository layout

| Path | Role |
|------|------|
| `main.py` | Streamlit entrypoint: flows, sidebar, chat, listings extras, compare, PDF wiring. |
| `graph.py` | LangGraph builder + extractor/evaluator nodes. |
| `orchestrator.py` | Required keys, missing-slot helpers, user-facing messages. |
| `prompt.py` | LangChain prompt templates for extract/evaluate. |
| `state.py` | `TypedDict` for graph state. |
| `listings_retrieval.py` | SQL + env tolerances. |
| `listings_similarity.py` | Enrichment, match %, regions, aggregates, slopes. |
| `listings_geo_de.py` | City → Bundesland / lat-lon (GeoNames). |
| `listings_viz.py` | Matplotlib + Plotly PNG builders (single + compare). |
| `listings_present.py` | Streamlit render helpers (quick/deep/compare). |
| `listings_pdf.py` | ReportLab: quick, deep, **compare** PDFs. |
| `listings_media.py` | Image fetch for thumbnails. |
| `region_chart.py` | Plotly Bundesland choropleth (GeoJSON). |
| `results_router.py` | Optional LLM+keyword **quick vs deep** classifier (not wired to the main chat loop today). |
| `load_csv_to_postgres.py` | Shell out to `psql` **COPY** for bulk CSV import. |
| `.saved_car_sessions.json` | Persisted sidebar saves (created at runtime; gitignore if you add it). |
| `requirements.txt` | Python dependencies. |
| `.env.example` | Example env vars for Postgres / Ollama. |

---

## Prerequisites

- **Python 3.11+** (3.10+ usually fine; tested patterns assume a recent 3.x)
- **Ollama** running locally with a chat model (default **`llama3.2`**)
- **PostgreSQL** + **`psql`** on `PATH` if you use listings or the CSV loader
- Optional: **`DATABASE_URL`** exported in the same shell as `streamlit run`

---

## Install & run

All commands assume the **`car_assistant/`** directory (this folder).

### 1. Virtual environment (recommended)

```bash
cd car_assistant
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Ollama model

```bash
ollama pull llama3.2
ollama serve
```

### 3. Start the app

```bash
cd car_assistant
export DATABASE_URL='postgresql://USER@localhost:5432/car_assistant'   # optional but needed for listings
streamlit run main.py
```

Open the URL Streamlit prints (typically **http://localhost:8501**).

### 4. (Optional) Load listings CSV into Postgres

See [Database](#database-postgres--csv-load) below.

---

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama HTTP API |
| `EXTRACTOR_LLM_MODEL` | `llama3.2` | Extract agent model |
| `EVALUATOR_LLM_MODEL` | same as extractor | Evaluate agent model |
| `EVALUATOR_MAX_PASSES` | `3` | Max evaluator refinement loops per user message |
| `DATABASE_URL` | _(unset)_ | PostgreSQL URL for listing search + loader |
| `LISTINGS_TABLE` | `autoscout_de_parsed` | Table name |
| `LISTINGS_YEAR_TOLERANCE` | `2` | Allowed year delta vs listing registration year |
| `LISTINGS_KM_TOLERANCE` | `20000` | Allowed km delta vs extracted km |
| `RESULTS_ROUTER_LLM_MODEL` | falls back to extractor model | Used only by `results_router.py` if you wire it in |

Copy **`.env.example`** to **`.env`** for documentation; Streamlit does not load `.env` unless you use a loader — **export** vars in the shell for runs.

---

## Database: Postgres + CSV load

### Create DB

```bash
createdb car_assistant
export DATABASE_URL='postgresql://YOUR_USER@localhost:5432/car_assistant'
```

### Load CSV

From `car_assistant/`:

```bash
python load_csv_to_postgres.py --csv autoscout_de_parsed.csv --table autoscout_de_parsed
```

Replace table contents first:

```bash
python load_csv_to_postgres.py --truncate-first
```

Large imports can take a long time. The loader prints progress to the terminal.

### Sanity checks

```bash
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM autoscout_de_parsed;"
psql "$DATABASE_URL" -c "SELECT maker, model, km, price, \"Fuel\", first_registration FROM autoscout_de_parsed LIMIT 5;"
```

If an older table is missing columns the app expects, add them with `ALTER TABLE … ADD COLUMN …` or recreate via the loader so `SELECT` in `listings_retrieval.py` matches your schema.

---

## How to use the app

### Buy or sell a car

1. Tap **Buy or sell a car**.
2. Describe the vehicle (buy vs sell, brand, model, year, mileage, etc.).
3. If fields are missing, answer with the missing facts — the app merges into prior JSON and re-runs the graph.
4. When complete and **`DATABASE_URL`** is set, listings load automatically: **quick cards** (default **20**), **PDF download**, session **autosave** in the sidebar. **Chat locks** for that run until **Start over** or **Load**.

### Compare cars

1. Complete at least **two** buy/sell runs so they appear under **Saved cars**.
2. Tap **Compare cars**, multiselect **2 or 3** saves (order = blue → red → green in charts).
3. Press **Compare** — charts, Germany map, tables, and **comparison PDF** (no chat in this mode).

### Sidebar

- **Load** — Restores that vehicle + last quick listing snapshot when available.
- **PDF** — Downloads the **quick** ReportLab PDF (from snapshot or refetched listings); successful PDFs are cached in-session per save id.
- **Del** — Removes the saved session (and its PDF cache entry).
- **Start over (new goal)** — Clears flow, chat, compare selection, and sidebar PDF cache.

---

## PDFs & exports

| PDF | When |
|-----|------|
| **Quick** (`car_listings_quick.pdf`) | After a completed buy/sell listing run (top N cards, photos, links, 2×2 chart page in dossier layout). |
| **Deep** | From `deep_pdf_bytes` / `generate_deep_listings_pdf_bytes` when deep UI path is used (full analytics + up to 50 cards). |
| **Compare** | From compare dashboard — all comparison charts + per-car listing sections. |
| **Sidebar PDF** | Same quick dossier as above, per saved car. |

Static Plotly figures need **kaleido** (listed in `requirements.txt`).

---

## Listings, scoring & charts

- **SQL filters:** maker/model patterns, registration year window, km window (see env tolerances). Fuel, gearbox, intent are **not** applied as hard SQL filters.
- **Ranking:** similarity score → **match %**, optional **top‑3** tier highlighting, tolerance notes vs query year/km.
- **Regions:** `city` text → Bundesland via GeoNames + PLZ prefix fallback.
- **Charts:** matplotlib scatters (integer year ticks on year plot), combined 2×2 dashboard for single-car PDFs, plotly **Scattergeo** for Germany (single + multi-compare with side legend).

---

## Optional / extension points

- **`results_router.classify_results_style`** — LLM + keyword fallback to return `"quick"` vs `"deep"`; ready to plug in if you want a second user turn after listings to choose presentation (today the app always attaches **quick** extras after retrieval).
- **Deep mode** — `render_deep_dashboard` / `deep_pdf_bytes` remain available for demos or API extensions.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| No listings | `DATABASE_URL`, table name, CSV loaded, tolerances not too strict |
| LLM errors | `ollama serve`, model pulled, `OLLAMA_BASE_URL` |
| Map / chart PNG missing in PDF | `kaleido` installed; network for Plotly GeoJSON (choropleth) if used |
| Sidebar PDF disabled | Hover **PDF** for reason (no rows, DB error, etc.); fix env and rerun — failed builds are not cached, successful ones are until delete / start over |

---

## License

Specify your license in a root **`LICENSE`** file (e.g. MIT) when you publish the repo; this README does not impose one.
