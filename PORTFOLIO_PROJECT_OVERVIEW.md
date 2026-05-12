# Portfolio piece: **My Car Assistant 2.0**

*A narrative of what the project does, step by step, and the skills it demonstrates.  
(This document is meant for a personal portfolio or case study — not a setup guide.)*

---

## One-sentence summary

I built an **AI-assisted marketplace assistant** that turns **free-text car buy/sell descriptions** into **validated structured data**, **queries a real PostgreSQL inventory**, **ranks and explains listings**, and delivers **interactive dashboards, maps, and PDF reports** — using **LangGraph** for agent orchestration and **Streamlit** as the product surface.

---

## The problem (portfolio framing)

Car listings live in **messy natural language** and **wide tabular data** (many columns, inconsistent text). Buyers and sellers need a **fast, trustworthy bridge** from “what I want in words” to “what exists in the database and at what price,” without writing SQL or filling rigid forms. The project shows **end-to-end ownership**: NLP → structured schema → SQL → scoring → visualization → export → session persistence.

---

## Main steps of the solution (end-to-end story)

### 1. Intent and mode selection

The product opens with a **clear fork**: a **single-vehicle conversational flow** (buy or sell) versus a **multi-vehicle comparison** mode that works off **saved profiles** (no duplicate typing of three cars in chat). This demonstrates **UX design for branching workflows** and **stateful session design** in a web app.

### 2. Conversational extraction (first agent)

User prose is sent through a **LangChain + Ollama** chain with a **structured JSON-oriented prompt**. The first node (**extractor**) proposes fields such as **intent**, **maker**, **model**, **year**, **kilometerage**, and optional **fuel** / **gearbox**.  

**Query grounding** logic ties mileage to what the user actually said (e.g. explicit “80k km” vs vague text, “new car” → zero km), showing **defensive NLP** beyond “trust the model raw.”

**Skills involved:** prompt engineering, JSON repair/parsing from LLM output, Python text normalization, LangChain LCEL-style composition.

### 3. Evaluation and refinement (second agent)

A second node (**evaluator**) re-reads the same user query together with the draft JSON and returns a **corrected, normalized** object. The orchestrator defines **five required keys** for downstream SQL; the evaluator may run **multiple internal passes** (capped by configuration) until missing slots stop shrinking — a pattern of **iterative refinement** rather than a single brittle LLM call.

**Skills involved:** multi-step LLM workflows, convergence / stop conditions, separation of concerns (orchestrator vs graph vs prompts).

### 4. LangGraph orchestration

The two agents are wired as a **LangGraph `StateGraph`**: **START → extractor → evaluator → END**, with a small **typed state** (`TypedDict`) carrying the query, draft JSON, evaluated JSON, missing fields, and user-facing hints.

**Skills involved:** **LangGraph** state machines, explicit graph edges, compile/invoke API, reasoning about **observable state** for debugging and extension.

### 5. Slot filling and follow-up turns

If required fields are missing, the app **merges** user follow-ups into the prior JSON and **re-invokes** the graph only for what is still unknown — demonstrating **conversational form completion** and **minimal re-querying** instead of restarting from scratch each message.

**Skills involved:** session state design, merge semantics, user-facing validation copy.

### 6. Database retrieval against real inventory

Once the evaluator JSON is complete, a dedicated module issues **parameterized PostgreSQL** queries via **psycopg 3** (`dict_row`). Filters use **ILIKE** on maker/model and **tolerance windows** on parsed registration year and odometer; table and tolerance names are **environment-driven** with **basic injection hygiene** (validated table identifier pattern).

**Skills involved:** SQL design for fuzzy real-world data, connection handling, env-based configuration, separating “LLM world” from “database world.”

### 7. Similarity scoring and enrichment

Rows are **enriched** with parsed numerics, **per-listing match scores** vs the query vehicle, **tolerance explanations**, and **Bundesland** buckets derived from **city text** (GeoNames-backed locality resolution with **postcode fallback**). Aggregates (min/median/mean/max price) and **OLS-style slopes** (e.g. price vs km / year) use **NumPy**; string alignment for brand/model uses **RapidFuzz**.

**Skills involved:** feature engineering on tabular data, explainable heuristics, fuzzy string matching, lightweight numeric analysis, **geospatial / administrative geography** reasoning.

### 8. Presentation layer (Streamlit product)

The UI replays **chat history**, renders **metric strips**, **card grids**, **dataframes**, and **Plotly** charts (including a **choropleth** over German states when GeoJSON loads). A **compare** workspace overlays **multi-series matplotlib** plots and a **multi-trace Plotly map** with a **non-overlapping legend layout**, plus **side-by-side tables** for 2–3 cars.

**Skills involved:** **Streamlit** layout (columns, sidebars, download buttons, disabled states with help text), chart design, balancing information density vs clarity.

### 9. Document generation (ReportLab + static chart export)

**ReportLab** builds **portrait PDFs**: intros, combined chart panels, and **per-listing blocks** with thumbnails (fetched safely), hyperlinks, and compressed tables. **Matplotlib (Agg)** and **Plotly + Kaleido** produce **raster assets** embedded into PDFs — bridging **vector layout** and **pixel graphics**.

**Skills involved:** PDF layout, `Flowable` patterns, image sizing, multi-page reports, static export pipelines.

### 10. Persistence and reuse

Completed runs **autosave** a slim JSON snapshot (vehicle + enriched listing slice) to disk (capped list), enabling **Load**, **sidebar PDF export** (snapshot or refetch), **delete**, and **multi-car compare** without retyping. This shows **product continuity** beyond a single session.

**Skills involved:** JSON persistence design, privacy-minded field allowlists (what not to store), cache invalidation patterns at session boundaries.

### 11. Optional / latent capabilities (honest portfolio note)

The codebase includes a **small LLM router** (`results_router`) to classify whether a user wants a **“quick” vs “deep”** presentation, with **keyword fallback** if the model call fails — suitable for a **second conversational beat** after listings. The main UI path currently emphasizes the **quick** experience while keeping **deep** rendering and PDF paths available for extension.

**Skills involved:** designing for **feature flags** and future UX without deleting code paths.

---

## Skills & technologies (inventory)

Use this list as tags for your portfolio CMS or CV.

**Languages & runtime**

- Python 3.x  
- SQL (PostgreSQL dialect, parameterized queries)

**AI / LLM**

- **LangGraph** — graph compilation, linear multi-node workflows  
- **LangChain** — Ollama chat models, prompt templating, JSON-oriented generation  
- **Ollama** — local LLM hosting  
- Prompt design for **extraction** and **evaluation** passes  
- Optional: router pattern for **intent classification** (quick vs deep)

**Web & UI**

- **Streamlit** — multipage-style flows, sidebar, chat UI, session state, widgets  
- Product UX: **mode split** (single vs compare), **chat lock** after completion, **download** affordances  

**Data & backend**

- **PostgreSQL** + **psycopg 3**  
- Environment-driven configuration  
- **pandas** for tabular presentation  
- **NumPy** for aggregates and regression-style fits  

**Search & text**

- **RapidFuzz** — fuzzy maker/model alignment  
- **regex** — mileage and field cleanup in SQL and Python  
- **geonamescache** + custom heuristics — **DE city → state / coordinates**

**Visualization**

- **matplotlib** (Agg backend) — scatters, combined dashboards, grouped comparisons  
- **plotly** — choropleth / scattergeo maps  
- **kaleido** — raster export for PDF embedding  

**Documents**

- **ReportLab** — PDF composition, tables, styles, links  
- **Pillow** — image measurement for layout  

**Tooling & engineering practice**

- Modular package layout (retrieval, similarity, geo, viz, PDF, UI layers)  
- Typed helpers (`TypedDict`, type hints) where it pays off  
- Separation of **orchestration rules**, **graph topology**, and **UI**  
- Honest documentation of **what is wired vs what is ready to extend**

---

## What this project signals to employers or clients

- You can ship a **full vertical slice**: NLP → DB → analytics → export.  
- You understand **LLM limitations** and add **rules, grounding, and second-pass evaluation**.  
- You use **modern orchestration (LangGraph)** instead of a single monolithic prompt.  
- You connect **real data** (Postgres) to **human-facing** insight (Streamlit + PDF).  

---

## Suggested citation line for your portfolio

> **My Car Assistant 2.0** — LangGraph-orchestrated LangChain + Ollama pipeline for structured vehicle extraction, PostgreSQL marketplace retrieval, RapidFuzz/NumPy ranking, Streamlit dashboards, and ReportLab/Plotly PDF reporting with multi-car comparison.

Feel free to shorten or split that blurb for LinkedIn, a case-study hero, or a PDF résumé.
