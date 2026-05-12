# My Car Assistant 2.0

LangGraph + LangChain (Ollama) **car assistant**: natural language → structured vehicle JSON → PostgreSQL marketplace search → ranked listings, charts, maps, and PDFs — with a **Streamlit** UI.

## Documentation

**→ Full README (features, commands, env, database, architecture): [`car_assistant/README.md`](car_assistant/README.md)**

Quick start:

```bash
cd car_assistant
pip install -r requirements.txt
ollama pull llama3.2 && ollama serve   # separate terminal
export DATABASE_URL='postgresql://USER@localhost:5432/car_assistant'   # optional
streamlit run main.py
```

## Repository layout

| Path | Contents |
|------|----------|
| **`car_assistant/`** | Application: `main.py`, LangGraph `graph.py`, listings, PDFs, `requirements.txt`. |
| **`draft/`** | Project notes (`draft/README.md`, `draft/current_state.md`). |
