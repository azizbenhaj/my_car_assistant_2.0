# Roadmap

1. **Wire data model** — `domain_notes.md` already maps CSV columns; add **`listings_query.py`** with parameterized SQL.
2. **Query helper** — `evaluated_extracted` → `SELECT` on `autoscout_de_parsed`; caps / paging.
3. **Streamlit** — run query when five required keys present; **`st.dataframe`** (or cards) for matches.
4. **Post-result UX** — PDF vs stats vs neither; persist last result set in session.
5. **PDF generator** — from last result snapshot.
6. **Statistics** — SQL aggregates + readable summaries (optional charts).
7. **Tests / hygiene** — pytest on graph; optional **`python-dotenv`**; quieter or visible warm-up diagnostics.
