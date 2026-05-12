# Project overview

## Intent

Replace the **classic car-filter UI** used on marketplaces such as **[autoscout.ee](https://www.autoscout.ee/)** (and similar sites): the user **types** what they want. The assistant turns text into structured filters against a **PostgreSQL** table loaded from **`autoscout_de_parsed.csv`**, shows matches, then on request produces **PDF** and/or **statistics** — see `product_logic.md`.

## What exists today (`car_assistant/`)

- **Orchestrator contract** (`orchestrator.py`): five required keys **`intent`, `maker`, `model`, `km`, `year`** before treating extraction as complete for downstream search.
- **LangGraph**: **extract** → **evaluate** (Ollama `ChatOllama`; optional **different** model per agent via env).
- **Evaluator refinement**: multiple passes per user message (`EVALUATOR_MAX_PASSES`), bounded when missing set stops improving.
- **Streamlit**: chat, two JSON panels, missing-field prompts, **context-rich follow-up** (prior JSON + user line).
- **Data path**: **`load_csv_to_postgres.py`** ( **`psql` + `COPY`** + `DATABASE_URL` ).
- **Retrieval**: **`listings_retrieval.py`** + **`psycopg`** — up to **50** rows; **maker/model** `ILIKE`; **year ±2** / **km ±20k** tolerances (env-tunable); **fuel/gearbox/intent** not filtered.

## What is still missing

- **PDF / statistics** from last result set.
- **Richer listing UX** (cards, `url` links, pagination); **`intent`** not yet used as a SQL filter.

## Stack

Python 3.10+, Streamlit, LangGraph, LangChain ↔ Ollama, PostgreSQL + **`psql`** for bulk CSV ingest.

Run from **`car_assistant/`**: `streamlit run main.py`; load data per root **`README.md`** + **`car_assistant/.env.example`**.

## Constraints

Large CSV (~630 k rows); Ollama default `http://127.0.0.1:11434`; bulk load requires **`psql`** on PATH.

## Where truth lives

| Concern | File |
|---------|------|
| Live “what’s done” snapshot | `draft/current_state.md` |
| File map & commands | `draft/technical_map.md` |
| CSV ↔ JSON mapping | `draft/domain_notes.md` |
