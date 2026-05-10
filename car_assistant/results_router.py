"""LLM-backed routing: quick (top cards) vs deep (full breakdown + PDF-ready payload)."""

from __future__ import annotations

import json
import os

from langchain_ollama import ChatOllama


def classify_results_style(user_reply: str) -> str:
    """
    Returns 'quick' | 'deep'. Ambiguous/off-topic replies default to quick.
    """
    text = (user_reply or "").strip()
    if not text:
        return "quick"

    llm = ChatOllama(
        model=os.getenv("RESULTS_ROUTER_LLM_MODEL", os.getenv("EXTRACTOR_LLM_MODEL", "llama3.2")),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        format="json",
        temperature=0,
    )

    prompt = (
        'The user answered how they want marketplace results shown:\n"'
        + text.replace("\\", "").replace('"', "\\")[:600]
        + "\"\n\n"
        'Return ONLY JSON: {"style":"quick"|"deep"} (use deep for extended / full-report requests)\n'
        "- quick: short view, overview, top picks, summaries, cards, easy, concise, fastest, TL;DR.\n"
        "- deep: full details, extended analysis, charts, statistics, spreadsheet/table, regressions, map, percentages, PDF, exhaustive.\n"
        "If unclear, {\"style\":\"quick\"}.\n"
    )
    raw = ""
    try:
        msg = llm.invoke(prompt)
        raw = getattr(msg, "content", None) or str(msg)
        if isinstance(raw, list):
            raw = "".join(
                getattr(p, "text", str(p))
                if not isinstance(p, dict)
                else p.get("text", "")
                for p in raw
            )
        data = json.loads(raw.strip())
        s = data.get("style", "").lower()
        return "deep" if s in ("deep", "extended") else "quick"
    except Exception:
        t = text.lower()
        deep_kw = (
            "deep",
            "extended",
            "extend",
            "detail",
            "stat",
            "pdf",
            "chart",
            "map",
            "table",
            "column",
            "all info",
            "full",
        )
        if any(k in t for k in deep_kw):
            return "deep"
        return "quick"
