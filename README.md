# My Car Assistant 2.0

**Natural language → structured car profile → PostgreSQL search → ranked listings, charts, maps, and PDFs** — with a **Streamlit** UI and **LangGraph** + **LangChain** (**Ollama**).

## What problem it solves

Classified sites expect you to **translate your goal into many filters** and scroll **long unprioritized lists**. This app lets you **say what you want once**, keeps a **consistent vehicle profile** across follow-up messages, then returns a **short ranked shortlist** with **match %**, **charts**, **maps**, and **PDFs** on data **you host locally** — plus **compare 2–3 saved searches** side by side.

## Interface in pictures

The home screen lets you start a **single-car** chat or open **Compare** once you have saved profiles.

![Home — choose Buy or sell a car or Compare cars](images/Screenshot%202026-05-12%20at%2016.32.43.png)

In **Buy or sell a car**, you describe the vehicle in chat; the assistant fills **intent, maker, model, year, km** (and optional details) before searching.

![Buy or sell — chat and extraction flow](images/Screenshot%202026-05-12%20at%2016.32.58.png)

**Compare cars** uses your sidebar saves: pick **2 or 3** and run **Compare** to see overlaid charts and tables (no chat in this mode).

![Compare cars — multiselect and comparison workspace](images/Screenshot%202026-05-12%20at%2016.33.20.png)

After a successful search you get **ranked listing cards**, metrics, charts/maps where data allows, and **download** actions for reports.

![Listings, analytics, and export actions](images/Screenshot%202026-05-12%20at%2016.34.26.png)

## How to use the interface (short)

1. **Run the app** (see commands below) and open the URL Streamlit prints (usually `http://localhost:8501`).
2. **Home:** choose **Buy or sell a car** *or* **Compare cars**.
3. **Buy or sell:** chat at the bottom; answer missing **intent / maker / model / year / km** if the assistant asks. When complete, **listing cards** (up to 20), **Download PDF**, and **autosave** in the sidebar; chat **locks** until **Start over** or **Load**.
4. **Sidebar:** **Load** restores a save, **PDF** exports the quick dossier, **Del** removes it; **Start over (new goal)** resets the flow.
5. **Compare:** needs **2+ saves** first → **Compare cars** → multiselect **2 or 3** (order = blue / red / green in charts) → **Compare** → charts, map, tables, **comparison PDF**; **Change selection** to redo.

**Dataset CSV:** link in [`car_assistant/link_to_download_dataset.rtf`](car_assistant/link_to_download_dataset.rtf) — or [Google Drive](https://drive.google.com/file/d/1a58G-aLexDRJP_PzFN5qVcPrI4Hfu2rN/view?usp=sharing).

## Run it

```bash
cd car_assistant
pip install -r requirements.txt
ollama pull llama3.2 && ollama serve   # keep running in another terminal
createdb car_assistant
export DATABASE_URL='postgresql://USER@localhost:5432/car_assistant'
python load_csv_to_postgres.py --csv autoscout_de_parsed.csv --table autoscout_de_parsed
streamlit run main.py
```

Use `--truncate-first` on the loader if you need to replace rows. See **`car_assistant/.env.example`** for optional env vars (`LISTINGS_TABLE`, tolerances, Ollama URL/models).

## Stack (libraries)

`langgraph`, `langchain-core`, `langchain-ollama`, `streamlit`, `psycopg`, `pandas`, `numpy`, `rapidfuzz`, `matplotlib`, `plotly`, `kaleido`, `reportlab`, `pillow`, `geonamescache` — plus **PostgreSQL**, **Ollama**, and **Python 3**.

## Repo layout

| Path | Contents |
|------|----------|
| **`car_assistant/`** | App (`main.py`, `graph.py`, listings, PDFs), `requirements.txt`, dataset RTF, CSV loader. |
| **`images/`** | Screenshots and **example PDFs** (see below). |
| **`draft/`** | Project notes. |

## Example PDFs

These files live in **`images/`** so you can open them directly from the repo.

- **[Quick listing PDF](images/car_listings_quick.pdf)** — from a completed **Buy or sell** run (or the main **Download PDF** on that screen): top listings with photos/links plus the combined chart page.  
- **[Sidebar listing PDF](images/Porsche_911_2026_6d70881e_listings.pdf)** — second vehicle dossier from **Sidebar → PDF** on a save (filename = label + session id). *The **Compare** screen’s download is **`car_listings_compare.pdf`** (multi-car layout); drop that export into `images/` and add a link if you want that exact sample in the README.*

