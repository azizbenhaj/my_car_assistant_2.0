# Decisions

Short log of intentional choices — append new bullets as needed.

| # | Decision | Notes |
|---|----------|-------|
| 1 | **Ollama locally** (`127.0.0.1:11434`) | Cheap iteration; override with `OLLAMA_BASE_URL`. |
| 2 | **Two-pass graph** extractor → evaluator | Better JSON before any DB joins. |
| 3 | **Ground `km` in code** alongside prompts | Limits phantom mileage vs query text / “brand new”. |
| 4 | **Bulk load Postgres via external `psql` + COPY** | Fast; keeps Python deps thinner; requires `psql` CLI. |
| 5 | **`car_assistant/` app**, **`draft/` memory** only | Separation of runnable code vs notes. |
| 6 | **Evaluator JSON drives SQL** *(planned)* | Prefer parameterized SELECT from corrected fields; reject free-form LLM-SQL in v1. |
| 7 | **PostgreSQL only for listings storage** | SQLite + Docker-based DB helpers **removed** from repo; single path = `load_csv_to_postgres.py`. |
| 8 | **Five required handoff fields** | `intent`, `maker`, `model`, `km`, `year` — centralized in `orchestrator.py` for graph + messages. |
| 9 | **Evaluator may repeat LLM calls** on one user message | Up to `EVALUATOR_MAX_PASSES` while missing-slot count improves; avoids infinite loops when text lacks facts. |
| 10 | **Runtime retrieval via `psycopg`** | `listings_retrieval.py` uses parameterized queries (not `psql` subprocess) so Streamlit can fetch rows safely. |
| 11 | **Loose match on year/km** | Default **±2 years** and **±20 000 km** vs listing fields; **fuel/gearbox/intent** not used in `WHERE` so results stay broader. |
