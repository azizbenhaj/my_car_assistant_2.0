# My Car Assistant 2.0

Welcome. This app helps you **describe a car in your own words**, then finds **matching listings** from your own database, **ranks** them, and shows **photos, charts, maps, and PDFs** — so you spend less time fiddling with filters and more time deciding.

---

## What you’ll see on the screen (step by step)

### 1. Open the app

After you run Streamlit (commands are at the **end** of this file), your browser opens the app, usually at **http://localhost:8501**.

---

### 2. Home screen — pick how you want to work

You see a short greeting and **two large buttons**:

| Button | What it’s for |
|--------|----------------|
| **Buy or sell a car** | One car at a time. You chat with the assistant until it knows enough to search listings. |
| **Compare cars** | Compare **2 or 3** cars you **already saved** from earlier runs (no chat here). |

Pick one. You can always use **Start over (new goal)** later (in the sidebar) to come back to this choice.

---

### 3. Path A — **Buy or sell a car** (main chat flow)

**3.1 — Start chatting**  
- The chat box is at the bottom. Type things like: *I want to buy a 2019 BMW 320d, automatic, around 80k km* or *Selling my 2014 Clio diesel, about 198k km*.  
- You can use the **example lines** on the page as inspiration.

**3.2 — First answer from the assistant**  
- The app runs two AI steps in the background (**extract** your story into fields, then **evaluate** and clean them up).  
- If something important is still missing (**intent**, **maker**, **model**, **year**, **km**), you’ll see a **warning** telling you what’s missing. Reply in the chat with **only** those details (or a fuller sentence — both work).

**3.3 — Follow-up turns until complete**  
- Each time you reply, the app **merges** what you said with what it already knew and asks again if anything is still missing.  
- When everything required is filled in, you’ll see a **success** message that all fields are present.

**3.4 — Listings appear automatically**  
- If your database is set up, the app **searches listings** and shows:  
  - **Photo cards** for the closest matches (up to **20**), with **match %**, price, km, registration, city, and a link to open the original listing.  
  - Top matches may show a **star** if they’re among the **3 closest** to your query.  
  - A **Download PDF** button for a compact report (photos + links + charts in the PDF).

**3.5 — Chat closes for this run**  
- After listings are shown, the chat input shows a message that **this run is complete**.  
- To search again, use **Start over (new goal)** in the sidebar, or **Load** a saved car (see below).

---

### 4. Sidebar — **Saved cars** (while you use the app)

On the **left**, each saved car shows:

| Control | What it does |
|---------|----------------|
| **Load** | Opens that save again: restores the last **marketplace view** (cards + PDF) when a snapshot was stored; otherwise loads the vehicle profile only. |
| **PDF** | Downloads the **same style of PDF** as after a live run (from the saved snapshot, or rebuilt from the database if needed). If the button is greyed out, hover it to read **why** (e.g. no database, no rows). |
| **Del** | Deletes that save from the list (and from disk). |

Saves appear automatically after a **successful** buy/sell run with listings (up to **10** cars, newest first).

Below the list you’ll find **Session** (shows your current mode) and **Start over (new goal)** — clears the chat, compare selection, and flow so you can pick **Buy or sell** or **Compare** again from the home step.

---

### 5. Path B — **Compare cars**

**5.1 — You need at least two saves**  
- Finish **Buy or sell a car** twice (or more) so two cars appear under **Saved cars** in the sidebar.

**5.2 — Open Compare**  
- From the home screen, click **Compare cars**. The chat stays **off** in this mode by design.

**5.3 — Select cars**  
- Use the **multiselect** list: choose **2 or 3** saved cars. **Order matters** — first selected = **blue** in charts, second = **red**, third = **green**.

**5.4 — Run the comparison**  
- Click **Compare** (only enabled when at least **two** cars are selected).  
- You’ll see: **Price vs km** and **Price vs year** charts (all cars on the same plot), a **price summary** line chart (min / median / average / max), a **Germany map** with points per listing and a **legend** by car, side‑by‑side **tables** (up to 20 rows per car), and **Download comparison PDF** at the bottom.

**5.5 — Change your mind**  
- Use **Change selection** to pick different saves and run **Compare** again.

---

### 6. How this feels vs only using a big classifieds website

Large sites (like **AutoScout24**) are great for **browsing everything** yourself: many filters, long result lists, and lots of tabs.

This app is for when you already know **what you’re looking for in words** and want a **short ranked list**, **match explanations**, **charts**, and **one‑click PDFs** on data **you host** — plus **side‑by‑side comparison** of a few saved searches. It does **not** replace the public marketplace; it’s a **local assistant** on top of similar-style listing data.

---

## Commands to run the interface

Run everything from the **`car_assistant`** folder (the same folder as this `README.md`).

**1. Install Python packages**

```bash
cd car_assistant
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Start Ollama (needed for the AI steps)**

```bash
ollama pull llama3.2
ollama serve
```

Leave that terminal open.

**3. Get the listing data (CSV)**

The download link is inside **`link_to_download_dataset.rtf`** (open it in any text editor — the URL is plain text inside the file).  
Same link here: **[Dataset on Google Drive](https://drive.google.com/file/d/1a58G-aLexDRJP_PzFN5qVcPrI4Hfu2rN/view?usp=sharing)**  
Save the file (e.g. as `autoscout_de_parsed.csv`) where you can point the importer to it.

**4. Create the database and load the CSV**

```bash
createdb car_assistant
export DATABASE_URL='postgresql://YOUR_USER@localhost:5432/car_assistant'
python load_csv_to_postgres.py --csv autoscout_de_parsed.csv --table autoscout_de_parsed
```

Use `--truncate-first` if you need to replace an old table. Large CSVs can take a while.

**5. Launch the app**

```bash
cd car_assistant
export DATABASE_URL='postgresql://YOUR_USER@localhost:5432/car_assistant'
streamlit run main.py
```

Then open the address Streamlit prints (usually **http://localhost:8501**).

**Optional settings** (same terminal, before `streamlit run`):

| Variable | Meaning |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (needed for search + import). |
| `LISTINGS_TABLE` | Table name (default `autoscout_de_parsed`). |
| `LISTINGS_YEAR_TOLERANCE` | How many years a listing may differ from your `year` (default `2`). |
| `LISTINGS_KM_TOLERANCE` | How many km a listing may differ from your `km` (default `20000`). |
| `OLLAMA_BASE_URL` | Where Ollama listens (default `http://127.0.0.1:11434`). |
| `EXTRACTOR_LLM_MODEL` / `EVALUATOR_LLM_MODEL` | Model names (default `llama3.2`). |

More examples live in **`.env.example`**.

**If something fails:** no listings → check `DATABASE_URL` and that the CSV loaded; AI errors → check `ollama serve` and that the model is pulled; PDF map missing → install **`kaleido`** (`requirements.txt` already lists it).

---

## Skills & technical libraries used

**Ideas the code demonstrates**

- Turning **free text** into a **strict JSON schema** with a **second pass** to fix and validate.  
- **Stateful chat**: remember partial JSON and only ask for what’s missing.  
- **SQL search** with tolerances (not only exact matches).  
- **Ranking and explanations** (match %, tolerances, “top 3” tier).  
- **Maps and charts** from real rows, then **PDF export**.  
- **Saving and reloading** sessions; **multi‑profile comparison**.

**Libraries & tools (from `requirements.txt` and the stack)**

| Library / tool | Role in the project |
|----------------|---------------------|
| **Python 3** | Whole application. |
| **Streamlit** | Web UI, chat, sidebar, buttons, downloads. |
| **LangGraph** | Wires **extractor → evaluator** as a small graph. |
| **LangChain Core** | Shared types and building blocks for chains. |
| **LangChain Ollama** | Calls your **local Ollama** LLM. |
| **langgraph** (package) | Graph runtime used with LangChain. |
| **psycopg** | Talks to **PostgreSQL** for listing search. |
| **pandas** | Tables and data display in the UI. |
| **numpy** | Averages, medians, simple regression lines in charts. |
| **rapidfuzz** | Fuzzy matching on maker/model text vs listings. |
| **matplotlib** | Static charts (including combined panels for PDFs). |
| **plotly** | Interactive maps and choropleth; static map images with **kaleido**. |
| **kaleido** | Export Plotly figures to PNG for PDFs. |
| **reportlab** | Build PDF documents (layout, tables, links). |
| **pillow** | Image sizing for thumbnails inside PDFs. |
| **geonamescache** | Match city text to German regions and coordinates. |
| **Ollama** (installed separately) | Runs the LLM on your machine. |
| **PostgreSQL** + **psql** | Database and optional bulk load via the loader script. |

---

## License

Add a **`LICENSE`** file at the repository root when you publish (for example MIT).
