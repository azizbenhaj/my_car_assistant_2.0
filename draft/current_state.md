# Current state (synced with `car_assistant/`)

*Last aligned: listings quick/deep routing + similarity + PDF (`main.py`) — update when the app changes.*

## Implemented

| Area | Detail |
|------|--------|
| **Orchestration** | LangGraph `START → extractor_agent → evaluator_agent → END` (`graph.py`). |
| **Required JSON** | Five slots before “complete”: **`intent`, `maker`, `model`, `km`, `year`** — `orchestrator.py` (`REQUIRED_JSON_KEYS`, `missing_required_slots`, `format_missing_message`). |
| **Evaluator** | Up to **`EVALUATOR_MAX_PASSES`** (default 3) internal LLM passes while missing list **shrinks**. |
| **LLM config** | **`EXTRACTOR_LLM_MODEL`**, **`EVALUATOR_LLM_MODEL`**, **`OLLAMA_BASE_URL`** (`graph.py`). |
| **Grounding** | `km` / “new car” heuristics in `graph.py`. |
| **Prompts** | Evaluator rule §8 for required handoff fields (`prompt.py`). |
| **Streamlit** | Greeting: **Buy or sell** vs **Compare**. **Autosave**: completed extraction → **Saved cars** in sidebar (**Load/Del**, PDF stub); list capped at **10** (newest first, oldest trimmed). **Compare**: multiselect up to **3** saves (selection order); side‑by‑side JSON; **`Start over`** clears chat/flow **not** saved cars. (`main.py`) |
| **Postgres ingest** | **`load_csv_to_postgres.py`** — `CREATE TABLE` + `COPY` via **`psql`**. |
| **Listings retrieval** | **`listings_retrieval.py`**: **`psycopg`** … **`LIMIT 50`** — **maker/model** `ILIKE`; **year ±2** vs `first_registration` (override **`LISTINGS_YEAR_TOLERANCE`**); **km ±20 000** vs parsed listing km (**`LISTINGS_KM_TOLERANCE`**). **Fuel / gearbox / intent** not filtered. Env: **`DATABASE_URL`**, **`LISTINGS_TABLE`**. |
| **Results in UI** | **Quick:** photo cards + **compact PDF**. **Deep:** horizontal **price bars**, **photo grid**, characteristic **table + URL links**, choropleth from **city** (**`geonamescache`** + PLZ fallback), km & **year vs price**, **deep PDF** (per-row photo + clickable link). |
| **Deps** | **`psycopg[binary]>=3.1`**, **pandas**, **numpy**, **rapidfuzz**, **matplotlib**, **plotly**, **reportlab**, **pillow**, **geonamescache**. |
| **Repo hygiene** | `car_assistant/.gitignore`; **`.env.example`** — `DATABASE_URL`, optional `LISTINGS_TABLE`. |
| **Docs** | `car_assistant/README.md` — env table includes `DATABASE_URL` for Streamlit retrieval. |

## Explicitly not implemented

| Area | Detail |
|------|--------|
| **PDF / statistics** | **Deep** listings path: PDF (**ReportLab**) + aggregates + OLS hints. Broader statistics product still backlog. |
| **Tests** | No pytest for retrieval or graph. |
| **`.env` auto-load** | Streamlit does not load `.env` unless you add `python-dotenv` and call `load_dotenv()`. |
| **Rich result UX** | No per-row cards, links column not specially rendered; `intent` not used in SQL filter. |

## Removed / reversed earlier experiments

- **SQLite** loader removed; **Docker** Postgres helper removed — **PostgreSQL only**.

## Next engineering move

Compare + retrieval across selected profiles; real PDF/statistics hooks; optional `python-dotenv`; tighter SQL (`ORDER BY`, etc.). Optional richer drag‑and‑drop (custom component).
