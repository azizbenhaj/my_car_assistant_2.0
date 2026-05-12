# My Car Assistant 2.0

**Natural language → structured car profile → PostgreSQL search → ranked listings, charts, maps, and PDFs** — with a **Streamlit** UI and **LangGraph** + **LangChain** ( **Ollama** ).

**Full guide (how the interface works, then how to run, then libraries):** [`car_assistant/README.md`](car_assistant/README.md)

**Dataset:** link inside [`car_assistant/link_to_download_dataset.rtf`](car_assistant/link_to_download_dataset.rtf) (also linked from that README).

Quick start:

```bash
cd car_assistant
pip install -r requirements.txt
ollama pull llama3.2 && ollama serve   # separate terminal
export DATABASE_URL='postgresql://USER@localhost:5432/car_assistant'
streamlit run main.py
```

| Folder | Contents |
|--------|----------|
| **`car_assistant/`** | App code, `requirements.txt`, dataset RTF, loader. |
| **`draft/`** | Project notes. |
