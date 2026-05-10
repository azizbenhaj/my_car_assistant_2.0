# Phase 1 Query Extractor (Car Assistant)

Run commands from this directory (`car_assistant/`).

Chat UI plus LangGraph **orchestrator**: `extractor_agent` → `evaluator_agent` over Ollama. See `orchestrator.py` for the **five** required keys (`intent`, `maker`, `model`, `km`, `year`) and messages.

## What it does
- **Start screen**: **two** choices — **Buy or sell a car** or **Compare cars**.
- **Saved cars (sidebar)**: up to **10** sessions (newest wins; oldest removed on overflow). When a buy/sell turn reaches **no missing required fields**, that evaluator JSON is **auto‑saved** (**Load**, **PDF** stub, **Del**).
- **Compare**: pick **1–3** sidebar saves via ordered **multiselect** (same **Streamlit run** limits true drag‑and‑drop from the sidebar → selection order defines column order); **Build comparison** shows JSON columns. No listing retrieval in compare yet.
- **Streamlit UI**: chat; first + corrected JSON; retrieval only on buy/sell after all required fields are filled.
- **Graph**: extracts structured fields (`intent`, `maker`, `model`, `year`, `km`, `gearbox`, `fuel`) with query-grounding rules for `km`; evaluator refines JSON and surfaces missing required fields.
- **Listings retrieval**: when all five required keys are present, **`listings_retrieval.py`** queries PostgreSQL (up to **50** rows) using **maker** + **model** (`ILIKE`), **year ±2** vs `first_registration`, **km ±20 000** vs parsed listing mileage; **fuel / gearbox / intent** are not filtered. Tolerances: **`LISTINGS_YEAR_TOLERANCE`** (default `2`), **`LISTINGS_KM_TOLERANCE`** (default `20000`). Needs **`DATABASE_URL`** in the same environment as `streamlit run`.
- **After matches**: the app asks **quick** (top **10** similar cars as **cards**, no spreadsheet) vs **deep** (styled table with **match %**, tolerances, price stats, OLS **€/km** & **€/year** on the sample, **Bundesland** map when Plotly can load GeoJSON, scatter **km–price**). Your **next chat line** is classified by a small **Ollama JSON** router (`RESULTS_ROUTER_LLM_MODEL` optional; same **`OLLAMA_BASE_URL`** as the graph). **Deep** mode adds a **ReportLab** PDF (A4 portrait, two-column intro + dense table, **top 3** rows tinted, optional embedded scatter). Similarity scoring uses **RapidFuzz** for brand/model text and **NumPy** for aggregates + linear fits (see `listings_similarity.py`).

## Setup
```bash
pip install -r requirements.txt
```

Make sure Ollama is running locally and `llama3.2` is available:
```bash
ollama pull llama3.2
ollama serve
```

Optional environment (defaults shown):

| Variable | Default | Meaning |
|----------|---------|---------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama HTTP API |
| `EXTRACTOR_LLM_MODEL` | `llama3.2` | First agent (extract) model |
| `EVALUATOR_LLM_MODEL` | same as extractor | Second agent (evaluate) — set to a different tag if you want |
| `EVALUATOR_MAX_PASSES` | `3` | Max evaluator LLM calls per user message while missing slots keep shrinking |
| `DATABASE_URL` | _(unset)_ | PostgreSQL URL for **`listings_retrieval`** (and `load_csv_to_postgres.py`) |

When you already have a Postgres table from an older export, add any missing columns expected by the loader (e.g. `vehicle_type`, `co2_g_per_km`, `cons_comb`) with `ALTER TABLE … ADD COLUMN … TEXT` **or** recreate the table via `load_csv_to_postgres.py` so the `SELECT` matches the CSV.
| `LISTINGS_TABLE` | `autoscout_de_parsed` | Table name created by the CSV loader |
| `LISTINGS_YEAR_TOLERANCE` | `2` | Listing reg. year may differ by this many years from extracted `year` |
| `LISTINGS_KM_TOLERANCE` | `20000` | Listing km may differ by this many km from extracted `km` |

## Run (Streamlit)

From **`car_assistant/`** (this folder):

```bash
streamlit run main.py
```

Then open the URL Streamlit prints (usually `http://localhost:8501`). Export **`DATABASE_URL`** in the **same** shell before `streamlit run` if you want listing search. Type a car description; if **intent / maker / model / km / year** are missing, reply with only the missing facts — the app sends prior JSON + your line back through both agents.

## Listings database (PostgreSQL only)

You need **PostgreSQL running**, **`createdb`** (or any empty database), and the **`psql`** client on your PATH.

**1. Create a database** (example name `car_assistant`; skip if it already exists):

```bash
createdb car_assistant
```

**2. Connection string** (adjust user/password/host if needed):

```bash
export DATABASE_URL='postgresql://YOUR_USER@localhost:5432/car_assistant'
# or: postgresql://USER:PASSWORD@localhost:5432/car_assistant
```

**3. Load the CSV** (from `car_assistant/`):

```bash
cd car_assistant
python load_csv_to_postgres.py --csv autoscout_de_parsed.csv --table autoscout_de_parsed
```

Replace existing rows in the table:

```bash
python load_csv_to_postgres.py --truncate-first
```

Full import can take a long time.

**4. Inspect with `psql`:**

```bash
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM autoscout_de_parsed;"
psql "$DATABASE_URL" -c "SELECT maker, model, km, price, \"Fuel\", first_registration FROM autoscout_de_parsed LIMIT 5;"
```

See `.env.example` for `DATABASE_URL`. The **loader** uses `psql`; the **Streamlit app** uses **`psycopg`** (`listings_retrieval.py`) when `DATABASE_URL` is set.
