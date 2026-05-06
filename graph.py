import json
import os
import re

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from prompt import evaluate_json_prompt, extract_json_prompt
from state import QueryState

extractor_llm = evaluator_llm = ChatOllama(
    model=os.getenv("EXTRACTOR_LLM_MODEL", "llama3.2"),
    base_url="http://127.0.0.1:11434",
)

def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group())
        except Exception:
            return {}


def _llm_content_to_text(content) -> str:
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    return str(content or "")


def _normalize_extracted(data: dict) -> dict:
    intent = data.get("intent")
    fuel = data.get("fuel")
    gearbox = data.get("gearbox")

    if isinstance(intent, str):
        intent = intent.strip().lower()
        if intent not in {"buy", "sell"}:
            intent = None
    if isinstance(fuel, str):
        fuel = fuel.strip().lower()
        if fuel == "petrol":
            fuel = "gasoline"
        if fuel not in {"gasoline", "diesel", "electric", "hybrid"}:
            fuel = None
    if isinstance(gearbox, str):
        gearbox = gearbox.strip().lower()
        if gearbox in {"stick", "stick shift"}:
            gearbox = "manual"
        if gearbox not in {"automatic", "manual"}:
            gearbox = None

    return {
        "intent": intent,
        "maker": data.get("maker"),
        "model": data.get("model"),
        "year": data.get("year"),
        "km": data.get("km"),
        "gearbox": gearbox,
        "fuel": fuel,
    }


def _query_implies_new_car(query: str) -> bool:
    q = query.lower()
    return any(token in q for token in ["brand new", "unused", " new "]) or q.startswith(
        "new "
    )


def _query_has_explicit_km(query: str) -> bool:
    q = query.lower()
    patterns = [
        r"\b\d{1,3}(?:[.,]\d{3})+\s*km\b",  # 134,500 km
        r"\b\d+\s*km\b",  # 80000 km
        r"\b\d+(?:\.\d+)?\s*k\b(?:\s*km)?",  # 80k, 80k km
    ]
    return any(re.search(pattern, q) for pattern in patterns)


def _extract_km_from_query(query: str):
    q = query.lower().replace(",", "")

    # Prefer explicit "zero km" wording.
    if re.search(r"\bzero\s*km\b", q):
        return 0

    # Match values with "k" suffix first (e.g., 80k, 80k km).
    match_k = re.search(r"\b(\d+(?:\.\d+)?)\s*k\b(?:\s*km)?", q)
    if match_k:
        return int(float(match_k.group(1)) * 1000)

    # Then match plain kilometers (e.g., 80 km, 189000 km).
    match_km = re.search(r"\b(\d+)\s*km\b", q)
    if match_km:
        return int(match_km.group(1))

    return None


def _enforce_query_grounding(query: str, extracted: dict) -> dict:
    grounded = dict(extracted)
    # Prevent model from inventing mileage values not present in query.
    if _query_implies_new_car(query):
        grounded["km"] = 0
    else:
        parsed_km = _extract_km_from_query(query)
        if parsed_km is not None:
            grounded["km"] = parsed_km
        elif not _query_has_explicit_km(query):
            grounded["km"] = None
    return grounded


def extraction_agent(state: QueryState) -> QueryState:
    query = state.get("query", "")
    chain = extract_json_prompt | extractor_llm
    response = chain.invoke({"query": query})
    data = _extract_json(_llm_content_to_text(response.content))
    output = _enforce_query_grounding(query, _normalize_extracted(data))
    return {
        "query": query,
        "extracted": output,
        "missing_required_fields": [],
    }


def evaluator_agent(state: QueryState) -> QueryState:
    query = state.get("query", "")
    first_extracted = state.get("extracted", {})

    chain = evaluate_json_prompt | evaluator_llm
    response = chain.invoke(
        {
            "query": query,
            "first_extracted": json.dumps(first_extracted, ensure_ascii=False),
        }
    )
    evaluated_data = _extract_json(_llm_content_to_text(response.content))

    corrected = _normalize_extracted(evaluated_data.get("corrected", {}))
    corrected = _enforce_query_grounding(query, corrected)
    missing_required = [
        key for key in ["maker", "model", "year", "km"] if corrected.get(key) is None
    ]
    ask_user = ""
    if missing_required:
        ask_user = (
            "Please add missing required info: " + ", ".join(missing_required) + "."
        )

    return {
        "query": query,
        "extracted": first_extracted,
        "evaluated_extracted": corrected,
        "missing_required_fields": missing_required,
        "ask_user": ask_user,
    }


builder = StateGraph(QueryState)
builder.add_node("extractor_agent", extraction_agent)
builder.add_node("evaluator_agent", evaluator_agent)
builder.add_edge(START, "extractor_agent")
builder.add_edge("extractor_agent", "evaluator_agent")
builder.add_edge("evaluator_agent", END)
graph = builder.compile()
