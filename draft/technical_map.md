# Technical map

## Layout

```
<repo>/README.md               → points here + draft/
car_assistant/
  main.py                      max 10 saved sessions + compare up to 3 autosaved profiles
  graph.py                     LangGraph: extractor_agent → evaluator_agent
  orchestrator.py              Five required keys + missing / message helpers
  state.py                     QueryState TypedDict
  prompt.py                    Extract + evaluator prompts
  listings_retrieval.py        psycopg: top-50 SELECT from evaluated JSON + env
  load_csv_to_postgres.py      CSV → Postgres via psql COPY
  autoscout_de_parsed.csv      Raw listing export
  requirements.txt             + psycopg[binary]
  README.md                    Run + env + Postgres load + retrieval note
  .env.example                 DATABASE_URL, optional LISTINGS_TABLE
draft/
  README.md                    Index + sync policy
  current_state.md             Live snapshot vs code
  …
```

## Runtime entry points

```bash
cd car_assistant
export DATABASE_URL=postgresql://USER@localhost:5432/DBNAME   # same shell for streamlit + retrieval
pip install -r requirements.txt
streamlit run main.py
python load_csv_to_postgres.py --csv autoscout_de_parsed.csv --table autoscout_de_parsed
```

## Implemented flow (today)

1. Buttons: **Buy or sell a car** | **Compare cars** (`flow_mode`; `preferred_intent` usually unset for single).
2. Chat → **`graph.invoke`** (+ intent / compare-slot preamble) → extract → evaluate → JSON + **`missing_required_fields`**.
3. **`single` + complete** → **`fetch_top_listings`** (≤50) → ask **quick** vs **deep** → routed LLM parses next user line → cards / dashboard + PDF.
4. **`compare`** → choose **autosaved** JSONs (multiselect, max 3, order = columns) → **Build comparison** → side‑by‑side JSON; **no** Postgres search yet; chat is not the compare input path.

## Target incremental wiring

Post-result **PDF / statistics**; optional **`ORDER BY`** / price parsing; dotenv for `DATABASE_URL`.

## Maintenance

After meaningful **`car_assistant/`** changes, update **`draft/current_state.md`**, **`technical_map.md`**, **`journal.md`**, and **`backlog.md`** as needed.
