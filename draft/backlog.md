# Backlog — master build order

Check off top-to-bottom unless you consciously parallelise.

### Recently completed (synced with `car_assistant/` code)

- [x] **Two-agent graph** + explicit **`orchestrator.py`** (five required keys, shared messages).
- [x] **Evaluator multi-pass** + **`EVALUATOR_MAX_PASSES`**; separate **`EVALUATOR_LLM_MODEL`** / **`OLLAMA_BASE_URL`** support.
- [x] **Follow-up UX** — augmented query string with prior JSON for missing-slot turns.
- [x] **Postgres-only** data path documented; removed SQLite + Docker helper from repo.
- [x] **`car_assistant/README.md`** + **`.env.example`** for Postgres + Ollama env vars.
- [x] **`listings_retrieval.py`** + **`main.py`** wiring: top-50 parameterized Postgres query from evaluated JSON; **`st.dataframe`** when complete.

### 0 · Prerequisites

- [ ] Postgres running; **`psql`** on PATH for bulk load.
- [ ] Ollama running; **`llama3.2`** (or chosen models) pulled.
- [ ] `pip install -r car_assistant/requirements.txt`; run app from **`car_assistant/`**.

### 1 · Data in DB

- [ ] **`export DATABASE_URL=...`** and run `load_csv_to_postgres.py` (full import once — long).
- [ ] Verify row count (`SELECT COUNT(*) FROM autoscout_de_parsed;`) — table name equals default `--table`.
- [ ] Run **manual test queries** mirroring mappings in `domain_notes.md` (`maker`, `model`, year from `first_registration`, `km`/`price` parsing experiments).

### 2 · Env & LLM configs

- [ ] Optional **`car_assistant/.env`** + **`python-dotenv`** so Streamlit reads `DATABASE_URL` / Ollama vars without manual `export`.

### 3 · Query module (backend core)

- [x] **`listings_retrieval.py`** — parameterized SQL from **`evaluated_extracted`**; **`LIMIT 50`**; no LLM SQL.
- [x] **`ILIKE`** / trim on `maker` / `model`; **`year`** ± tolerance vs `first_registration`; **`km`** ± tolerance vs parsed listing km; **no** fuel/gearbox SQL filters.
- [ ] **`price`** numeric filter / **`ORDER BY`**; typed columns migration (**v2**).
- [ ] **`OFFSET`** paging beyond first 50.

### 4 · Hook DB into chat flow

- [x] After **`missing_required_fields` empty**, call **`fetch_top_listings`**; results stored on assistant chat turn for history replay.
- [ ] Persist **`st.session_state.last_listings`** explicitly for PDF / stats next step.

### 5 · Streamlit UX (listing results)

- [x] **`st.dataframe`** for retrieved rows; empty + error messaging.
- [ ] Rich cards / click **`url`**; “narrow search” nudges when count is 0.

### 6 · Deliverables fork (PDF / statistics)

- [ ] Sidebar or prompts: **“Export PDF”** / **“Show statistics”** (and/or NLP intent classifier later).
- [ ] **Statistics**: aggregates on loaded frame or SQL (`AVG`/percentiles parsed **price**); simple charts optional.
- [ ] **PDF**: generate from last results (minimal table columns + titles); choose library (**fpdf2** / ReportLab).

### 7 · Conversation polish & graph (optional expansions)

- [ ] Extra LangGraph node for **routing** (search vs pdf vs stats) once stable.
- [ ] Relax / tighten required fields versus product (e.g. allow missing `year`).
- [ ] Warm-up silent failure logging (sidebar debug).

### 8 · Tests & release hygiene

- [ ] Golden extractor inputs → snapshot JSON (**pytest**).
- [ ] Fixture DB or mocked cursor for **`listings_query`**.

### 9 · Documentation

- [ ] Keep **`draft/current_state.md`** + **`technical_map.md`** in sync after each merge-worthy change to `car_assistant/`.

### 10 · Compare mode (beyond extraction)

- [ ] Use **`st.session_state.compare_cars`** for side-by-side table / retrieval / summaries (user deferred).
