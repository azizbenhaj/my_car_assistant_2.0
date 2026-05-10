import json
import os
import re

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from orchestrator import format_missing_message, missing_required_slots
from prompt import evaluate_json_prompt, extract_json_prompt
from state import QueryState

_OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
_DEFAULT_MODEL = os.getenv("EXTRACTOR_LLM_MODEL", "llama3.2")

extractor_llm = ChatOllama(
    model=_DEFAULT_MODEL,
    base_url=_OLLAMA_BASE,
)

evaluator_llm = ChatOllama(
    model=os.getenv("EVALUATOR_LLM_MODEL", _DEFAULT_MODEL),
    base_url=_OLLAMA_BASE,
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

    if re.search(r"\bzero\s*km\b", q):
        return 0

    match_k = re.search(r"\b(\d+(?:\.\d+)?)\s*k\b(?:\s*km)?", q)
    if match_k:
        return int(float(match_k.group(1)) * 1000)

    match_km = re.search(r"\b(\d+)\s*km\b", q)
    if match_km:
        return int(match_km.group(1))

    return None


def _enforce_query_grounding(query: str, extracted: dict) -> dict:
    grounded = dict(extracted)
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


def _run_single_evaluator_pass(query: str, first_json: dict, chain) -> dict:
    response = chain.invoke(
        {
            "query": query,
            "first_extracted": json.dumps(first_json, ensure_ascii=False),
        }
    )
    evaluated_data = _extract_json(_llm_content_to_text(response.content))
    corrected = _normalize_extracted(evaluated_data.get("corrected", {}))
    return _enforce_query_grounding(query, corrected)


def evaluator_agent(state: QueryState) -> QueryState:
    """
    Second agent: refine JSON; may call the evaluator LLM several times on the
    same user ``query``, feeding the latest corrected JSON as ``first_extracted``,
    until required slots are filled or there is no shrink in ``missing`` / cap.
    """
    query = state.get("query", "")
    first_extracted = state.get("extracted", {})

    chain = evaluate_json_prompt | evaluator_llm
    max_passes = max(1, int(os.getenv("EVALUATOR_MAX_PASSES", "3")))

    corrected = _run_single_evaluator_pass(query, first_extracted, chain)
    prev_missing = missing_required_slots(corrected)

    for _ in range(1, max_passes):
        if not prev_missing:
            break
        next_json = dict(corrected)
        candidate = _run_single_evaluator_pass(query, next_json, chain)
        new_missing = missing_required_slots(candidate)
        if new_missing == prev_missing:
            break
        if len(new_missing) > len(prev_missing):
            break
        corrected = candidate
        prev_missing = new_missing

    missing_required = missing_required_slots(corrected)
    ask_user = format_missing_message(missing_required) if missing_required else ""

    return {
        "query": query,
        "extracted": first_extracted,
        "evaluated_extracted": corrected,
        "missing_required_fields": missing_required,
        "ask_user": ask_user,
    }


# Orchestrator graph: START → extractor_agent → evaluator_agent → END
builder = StateGraph(QueryState)
builder.add_node("extractor_agent", extraction_agent)
builder.add_node("evaluator_agent", evaluator_agent)
builder.add_edge(START, "extractor_agent")
builder.add_edge("extractor_agent", "evaluator_agent")
builder.add_edge("evaluator_agent", END)
graph = builder.compile()
