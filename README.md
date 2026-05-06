# Phase 1 Query Extractor

Minimal separate project that uses LangGraph with one agent node.

## What it does
- Takes a user query text.
- Runs one LLM extraction agent.
- Returns JSON with only: `maker`, `model`, `year`, `km`.

## Setup
```bash
pip install -r requirements.txt
```

Make sure Ollama is running locally and `llama3.2` is available:
```bash
ollama pull llama3.2
ollama serve
```

## Run
```bash
python main.py
```
