"""
Car assistant orchestrator — LangGraph topology (two NLP agents).

1. **extractor_agent** — maps free-text user input → draft JSON
   (required: intent, maker, model, year, km; optional fuel / gearbox).

2. **evaluator_agent** — second NLP pass: corrects / normalizes JSON and checks
   **required slots**. It may run **multiple internal passes** on the same user
   query (see ``EVALUATOR_MAX_PASSES``) feeding the previous corrected JSON back
   in, until slots are filled or there is no progress / max passes.

**Five required slots for downstream (e.g. Postgres):** ``intent`` (``buy`` |
``sell``), ``maker``, ``model``, ``kilometers`` (JSON key ``km``), ``year``.

Other CSV columns are **not** part of this stage — only this structured slice.
"""

from __future__ import annotations

REQUIRED_JSON_KEYS: tuple[str, ...] = ("intent", "maker", "model", "km", "year")

# Human-facing labels for chat / warnings (key stays ``km`` in JSON).
FIELD_LABELS: dict[str, str] = {
    "intent": "intent (buy or sell)",
    "maker": "maker (brand)",
    "model": "model",
    "km": "kilometers (km)",
    "year": "year",
}


def missing_required_slots(evaluated: dict | None) -> list[str]:
    """Return keys among REQUIRED_JSON_KEYS that are still null / missing."""
    if not evaluated:
        return list(REQUIRED_JSON_KEYS)
    return [k for k in REQUIRED_JSON_KEYS if evaluated.get(k) is None]


def format_missing_message(missing: list[str]) -> str:
    labels = [FIELD_LABELS.get(k, k) for k in missing]
    return (
        "Need these before we can search listings: "
        + ", ".join(labels)
        + ". Reply with only what is missing (or a fuller sentence)."
    )
