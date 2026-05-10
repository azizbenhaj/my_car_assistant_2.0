from typing import TypedDict


class QueryState(TypedDict, total=False):
    query: str
    extracted: dict
    evaluated_extracted: dict
    missing_required_fields: list[str]
    ask_user: str
