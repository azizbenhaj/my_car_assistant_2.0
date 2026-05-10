# Engineering journal

Add newest entries at top (short bullets).

---

## 2026-05-09 — Photos / PDF dossier / city→state geo

- **SQL** includes `vehicle_type`, `co2_g_per_km`, `cons_comb`. **`listings_geo_de`**: GeoNames locality → Bundesland (**`city`** column), **`listings_media`**, **`pillow`** resized thumbs, **`combined_market_dashboard_png`**, revamped **`generate_deep_listings_pdf_bytes`** (links + thumbnails + stacked analytics). **Quick** path: photos in cards + **compact PDF**.

---

## 2026-05-09 — NumPy + RapidFuzz for listing math

- **`listings_similarity.py`**: **RapidFuzz** `partial_ratio` for maker/model vs listing text; **NumPy** `polyfit` / `mean` / `median` for slopes and price aggregates. **`listings_viz.py`**: trend line via **`np.polyfit`**.

---

## 2026-05-09 — Listings: quick vs deep + PDF

- **`listings_similarity.py`**, **`listings_present.py`**, **`listings_pdf.py`**, **`listings_viz.py`**, **`region_chart.py`**, **`results_router.py`**: similarity scores, routed follow-up (**Ollama** JSON), cards vs deep dashboard (Plotly choropleth/bar, styled table, downloadable PDF portrait two-column dense).
- **`main.py`**: **`awaiting_results_choice`** gate for the user’s next reply; **`_listing_response_fields`** wires **`listings_bundle`**.

---

## 2026-05-09 — Cap saved sessions at 10

- **`MAX_SAVED_SESSIONS = 10`**: each autosave **prepends**; list trimmed to **10** newest (oldest index dropped); compare still **`MAX_COMPARE_CARS = 3`**. (`main.py`)

---

## 2026-05-09 — Sidebar sessions + compare from saves

- **Autosave** complete buy/sell extractions into **`saved_car_sessions`** (deduped signature); sidebar **Load / PDF stub / Del**.
- **Compare** no longer chats three sequential cars: **ordered multiselect** of saves (≤3) → **Build comparison**; **Change selection** resets widget state.
- **`Start over`** clears flow + chat **not** the saved-car list (`main.py`).
- **`streamlit>=1.33`** for **`max_selections`** on multiselect.

---

## 2026-05-09 — Two-button greeting

- **Buy or sell** vs **Compare** on the greeting screen (intent from chat for single flow).

---

## 2026-05-09 — Greeting + compare-three flow

- **`main.py`**: initial mode buttons + warm copy; **`compare`** runs **three** full extraction sequences (`compare_cars`), **no** `fetch_top_listings` until comparison product exists.

---

## 2026-05-09 — Post-listings PDF / stats prompt (UI only)

- After a non-empty **`st.dataframe`**, show **`st.info`** suggesting user reply **PDF** and/or **statistics**; no backend behavior yet.

---

## 2026-05-09 — Relaxed listing retrieval

- **`listings_retrieval.py`**: year **±2** years, km **±20 000** km (env-tunable); dropped **fuel** / **gearbox** filters; **`intent`** still unused in SQL.

---

## 2026-05-09 — Postgres retrieval (top 50)

- Added **`listings_retrieval.py`**: `fetch_top_listings` from evaluated JSON + **`DATABASE_URL`** / **`LISTINGS_TABLE`**.
- **`main.py`**: after five required fields filled, run retrieval; show **`st.dataframe`** or error / no-match; history stores `listings` / `listings_error` on assistant turns.
- **`requirements.txt`**: `psycopg[binary]>=3.1`. **`README.md`**, **`.env.example`**, **`draft/*`** updated to match.

---

## 2026-05-09 — draft sync with `car_assistant/`

- Added **`draft/current_state.md`** as the canonical “what’s implemented” snapshot (orchestrator, 5 required keys, multi-pass evaluator, env vars, Postgres-only ingest, removed SQLite/Docker).
- Refreshed **`project_overview.md`**, **`backlog.md`** (done vs pending), **`decisions.md`**, **`roadmap.md`**, **`technical_map.md`**, **`draft/README.md`** — maintenance rule: **update draft after main-folder advances**.

---

## 2026-05-09 — purpose restatement

- Positioning clarified: conversational **filtering app** for AutoScout-style sites (explicitly **AutoScout.ee** and peers); filters via **text**.
- Outputs are **user-requested**: **PDF** and/or **statistics** over the filtered matches (implement later).

---

## 2026-05-09

- Moved app into `car_assistant/`; seeded then **slimmed** `draft/` to eight topical markdown files (+ index README).
- Product vision anchored: conversational filters → Postgres snapshot → PDF/stats branching (not implemented yet).
