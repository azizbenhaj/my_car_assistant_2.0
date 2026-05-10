# Product logic & target flow

## Problem

Sites like **AutoScout.ee** (and comparable listings portals) rely on forms: maker, mileage, fuel, gearbox, … The same mental model repeats on every search.

## Target loop

0. Assistant asks **how to help**: **buy or sell one car** vs **compare cars** (today: two buttons).  
1. User describes intent + car in plain language (**buy/sell**). **Compare** selects **already-saved** profiles (up to three) assembled from prior completed extractions — not another three chat passes.
2. **Extract** structured JSON (LLM) + **evaluate/refine** (second LLM) — already coded.
3. Use **corrected/evaluated JSON** to drive **PostgreSQL** filters on data loaded from **`autoscout_de_parsed.csv`**.
4. Present **matching listings / summary** back in conversation.
5. User can **ask explicitly** — e.g. “give me a **PDF**” or “show **statistics**” (counts, bands, aggregates). Optionally the UI can prompt “PDF or statistics?” once results exist.
6. Generate **only what they asked for** (PDF alone, statistics alone, or both) from **that match set**.

Today: steps **1–2** in the app (extract + evaluate with **five** required slots — `orchestrator.py`); **CSV→Postgres** via `load_csv_to_postgres.py`; **step 3 partial** — **`listings_retrieval.py`** loads up to **50** matching rows into Streamlit when `DATABASE_URL` is set. Steps **4–6** (rich results UX, PDF/stats) still open — see `current_state.md`.

## Phased build (bookmark)

| Phase | Deliverable |
|-------|--------------|
| P1 | CSV/Postgres column ↔ extractor field map (explicit) |
| P2 | Query module from evaluated JSON (+ safe SQL) |
| P3 | Show results in Streamlit |
| P4 | PDF export path |
| P5 | Statistics / aggregates (+ optional plots) |

**Risks:** maker/model string mismatch vs CSV text (fuzzy map or synonym table later); broad queries (`LIMIT`, “narrow down” UX).
