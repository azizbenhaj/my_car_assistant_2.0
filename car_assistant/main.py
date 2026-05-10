import json
import uuid
from datetime import datetime, timezone

import streamlit as st
from graph import graph
import listings_present as lp
from listings_retrieval import fetch_top_listings
from orchestrator import format_missing_message
from results_router import classify_results_style

MAX_SAVED_SESSIONS = 10
MAX_COMPARE_CARS = 3


def _listing_response_fields(
    merged: dict, listings_rows: list | None, listings_err: str | None
) -> dict:
    """Side effects on listings_bundle / awaiting_results_choice; extra keys for assistant turn."""
    if listings_err:
        st.session_state.awaiting_results_choice = False
        st.session_state.listings_bundle = None
        st.session_state.listings_quick_deep_turn_done = False
        return {"listings_error": listings_err}
    if not listings_rows:
        st.session_state.awaiting_results_choice = False
        st.session_state.listings_bundle = None
        st.session_state.listings_quick_deep_turn_done = False
        return {"listings_empty": True}

    st.session_state.listings_quick_deep_turn_done = False
    scored = lp.enrich_listing_pool(merged, listings_rows)
    st.session_state.listings_bundle = {
        "evaluated": dict(merged),
        "enriched": scored,
    }
    st.session_state.awaiting_results_choice = True
    return {
        "listing_choice_prompt": True,
        "listing_count": len(scored),
        "evaluated_snapshot": dict(merged),
        "enriched_slim": lp.slim_enriched(scored),
    }


def _render_message_listing_extras(msg: dict, turn_key: str) -> None:
    if msg.get("listings_error"):
        st.error(msg["listings_error"])
        return
    if msg.get("listings_empty"):
        st.info("No listings matched these filters in the database.")
        return
    if msg.get("listing_choice_prompt"):
        n = int(msg.get("listing_count") or 0)
        st.success(f"Matched **{n}** listing(s). How should we display them?")
        st.markdown(lp.CHOICE_PROMPT_MARKDOWN)
        return
    rs = msg.get("results_style")
    if rs in ("quick", "deep"):
        slim = msg.get("enriched_slim") or []
        ev = msg.get("evaluated_snapshot") or {}
        if rs == "quick":
            lp.render_quick_cards(slim)
            qp = lp.quick_cards_pdf_bytes(slim, ev)
            st.download_button(
                label="Download compact PDF (10 cars, photos & links)",
                data=qp,
                file_name="car_listings_quick.pdf",
                mime="application/pdf",
                key=f"pdf_quick_{turn_key}",
            )
        else:
            lp.render_deep_dashboard(slim, ev)
            pdf_bytes = lp.deep_pdf_bytes(slim, ev)
            st.download_button(
                label="Download full PDF (photos, links, analytics)",
                data=pdf_bytes,
                file_name="car_listings_report.pdf",
                mime="application/pdf",
                key=f"pdf_dl_{turn_key}",
            )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_session_label(vehicle: dict) -> str:
    maker = (vehicle.get("maker") or "?").strip()
    model = (vehicle.get("model") or "?").strip()
    year = vehicle.get("year")
    y = str(year).strip() if year is not None else "?"
    return f"{maker} {model} {y}".strip()


def _vehicle_signature(vehicle: dict) -> str:
    keys = ("intent", "maker", "model", "km", "year")
    subset = {k: vehicle.get(k) for k in keys}
    return json.dumps(subset, sort_keys=True, ensure_ascii=False)


def _maybe_autosave_completed_session(vehicle: dict) -> None:
    """When a single-car flow finishes required fields, record one sidebar session (deduped)."""
    sig = _vehicle_signature(vehicle)
    if sig == st.session_state.last_autosaved_signature:
        return
    st.session_state.last_autosaved_signature = sig
    label = _make_session_label(vehicle)
    sid = str(uuid.uuid4())
    st.session_state.saved_car_sessions.insert(
        0,
        {
            "id": sid,
            "label": label,
            "vehicle_json": dict(vehicle),
            "saved_at": _utc_now_iso(),
        },
    )
    st.session_state.saved_car_sessions = st.session_state.saved_car_sessions[
        :MAX_SAVED_SESSIONS
    ]


def _intent_preamble_buy_sell() -> str:
    pref = st.session_state.get("preferred_intent")
    if pref == "buy":
        return "The user wants to **buy** a vehicle.\n\n"
    if pref == "sell":
        return "The user wants to **sell** their vehicle.\n\n"
    return (
        "The user is in the **buy-or-sell a single car** flow: infer **intent** (buy vs sell) "
        "from whether they want to acquire a vehicle or sell one.\n\n"
    )


def _reset_flow() -> None:
    st.session_state.flow_mode = None
    st.session_state.preferred_intent = None
    st.session_state.compare_cars = []
    st.session_state.compare_built = False
    st.session_state.base_json = {}
    st.session_state.missing_required_fields = []
    st.session_state.chat_history = []
    st.session_state.last_autosaved_signature = None
    st.session_state.pop("compare_multiselect", None)
    st.session_state.awaiting_results_choice = False
    st.session_state.listings_bundle = None
    st.session_state.listings_quick_deep_turn_done = False


def _apply_loaded_session(sess: dict) -> None:
    st.session_state.flow_mode = "single"
    st.session_state.preferred_intent = sess["vehicle_json"].get("intent")
    st.session_state.base_json = dict(sess["vehicle_json"])
    st.session_state.missing_required_fields = []
    st.session_state.compare_built = False
    st.session_state.compare_cars = []
    st.session_state.awaiting_results_choice = False
    st.session_state.listings_bundle = None
    st.session_state.listings_quick_deep_turn_done = False
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "text": (
                f"Loaded saved car **{sess['label']}**. "
                "Ask for listings again, PDF/statistics when we support them, or refine details in chat."
            ),
        }
    ]


def _delete_session(session_id: str) -> None:
    st.session_state.saved_car_sessions = [
        s for s in st.session_state.saved_car_sessions if s["id"] != session_id
    ]


st.set_page_config(page_title="Car Assistant Chatbot", page_icon="🚗")
st.title("Car Assistant Chatbot")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "base_json" not in st.session_state:
    st.session_state.base_json = {}
if "missing_required_fields" not in st.session_state:
    st.session_state.missing_required_fields = []
if "llm_warmed_up" not in st.session_state:
    st.session_state.llm_warmed_up = False
if "flow_mode" not in st.session_state:
    st.session_state.flow_mode = None
if "preferred_intent" not in st.session_state:
    st.session_state.preferred_intent = None
if "compare_cars" not in st.session_state:
    st.session_state.compare_cars = []
if "compare_built" not in st.session_state:
    st.session_state.compare_built = False
if "saved_car_sessions" not in st.session_state:
    st.session_state.saved_car_sessions = []
if len(st.session_state.saved_car_sessions) > MAX_SAVED_SESSIONS:
    st.session_state.saved_car_sessions = st.session_state.saved_car_sessions[
        :MAX_SAVED_SESSIONS
    ]
if "last_autosaved_signature" not in st.session_state:
    st.session_state.last_autosaved_signature = None
if "awaiting_results_choice" not in st.session_state:
    st.session_state.awaiting_results_choice = False
if "listings_bundle" not in st.session_state:
    st.session_state.listings_bundle = None
if "listings_quick_deep_turn_done" not in st.session_state:
    st.session_state.listings_quick_deep_turn_done = False

_LISTINGS_TURN_CLOSED = (
    "This marketplace run is **finished** (quick or extended/deep view is above). "
    "Tap **Start over (new goal)** in the sidebar to clear the chat and run a **new** search."
)
_LISTINGS_ACK_TAIL = (
    "\n\n**This marketplace run is complete.** "
    "Tap **Start over (new goal)** in the sidebar when you want a new search."
)

with st.sidebar:
    st.markdown("### Saved cars")
    st.caption(
        f"Up to **{MAX_SAVED_SESSIONS}** cars are kept (newest first; oldest drops off). "
        "Each completed buy/sell extraction is listed here for PDF/statistics later and for **Compare**."
    )
    sessions = st.session_state.saved_car_sessions
    if not sessions:
        st.caption("No saved cars yet — complete one in **Buy or sell a car**.")
    else:
        for sess in sessions:
            with st.container():
                st.markdown(f"**{sess['label']}**")
                st.caption(sess["saved_at"][:19].replace("T", " ") + " UTC")
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("Load", key=f"load_{sess['id']}", use_container_width=True):
                        _apply_loaded_session(sess)
                        st.rerun()
                with c2:
                    if st.button("PDF", key=f"pdf_{sess['id']}", use_container_width=True):
                        st.session_state["_pdf_stub"] = sess["id"]
                with c3:
                    if st.button("Del", key=f"del_{sess['id']}", use_container_width=True):
                        _delete_session(sess["id"])
                        st.rerun()
            st.divider()

    if st.session_state.get("_pdf_stub"):
        sid = st.session_state.pop("_pdf_stub")
        st.info("PDF export is not wired yet — this will use the selected saved car when it is.")

    st.markdown("---")
    st.markdown("### Session")
    if st.session_state.flow_mode is not None:
        st.caption(
            f"Mode: **{st.session_state.flow_mode}**"
            + (
                f" ({st.session_state.preferred_intent})"
                if st.session_state.flow_mode == "single"
                and st.session_state.preferred_intent is not None
                else ""
            )
            + (
                " (buy/sell inferred from chat)"
                if st.session_state.flow_mode == "single"
                and st.session_state.preferred_intent is None
                else ""
            )
        )
        if st.session_state.flow_mode == "compare":
            if st.session_state.compare_built:
                st.caption(f"Comparison: **{len(st.session_state.compare_cars)}** car(s)")
            else:
                st.caption("Pick **1–3** saved cars, then build comparison.")
    if st.button("Start over (new goal)"):
        _reset_flow()
        st.rerun()

# Warm-up LLM once
if not st.session_state.llm_warmed_up:
    try:
        graph.invoke(
            {
                "query": "I'm checking the price of a Golf 2017 TDI, manual, ~134.5k on odo (not sure exact).",
                "extracted": {},
            }
        )
    except Exception:
        pass
    finally:
        st.session_state.llm_warmed_up = True

if st.session_state.flow_mode is None:
    st.markdown(
        "**Good morning. How can I help you today?**\n\n"
        "Pick **one** path: either **buy or sell a single car**, or **compare several cars** — "
        "then we continue in chat."
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Buy or sell a car", use_container_width=True):
            st.session_state.flow_mode = "single"
            st.session_state.preferred_intent = None
            st.session_state.base_json = {}
            st.session_state.missing_required_fields = []
            st.session_state.compare_built = False
            st.session_state.compare_cars = []
            st.session_state.awaiting_results_choice = False
            st.session_state.listings_bundle = None
            st.session_state.listings_quick_deep_turn_done = False
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "text": (
                        "Say clearly if you’re **buying** or **selling**, then describe the car — "
                        "maker, model, year, mileage, and anything helpful."
                    ),
                }
            )
            st.rerun()
    with col2:
        if st.button("Compare cars", use_container_width=True):
            st.session_state.flow_mode = "compare"
            st.session_state.compare_built = False
            st.session_state.compare_cars = []
            st.session_state.base_json = {}
            st.session_state.missing_required_fields = []
            st.session_state.awaiting_results_choice = False
            st.session_state.listings_bundle = None
            st.session_state.listings_quick_deep_turn_done = False
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "text": (
                        "Use the **comparison panel** below: choose **up to three** saved cars from the "
                        "sidebar list (they appear in the multiselect). **Selection order is comparison "
                        "order** — pick the first car first, then the second, then the third. "
                        "*(Streamlit can’t drag from the sidebar; use the ordered multiselect.)*"
                    ),
                }
            )
            st.rerun()
    st.caption(
        "Two-pass extraction (extractor → evaluator) applies in buy/sell chat. "
        "Compare uses profiles you already saved from completed extractions."
    )
else:
    st.caption(
        "Orchestrator: extractor → evaluator. Required JSON: intent, maker, model, km, year. "
        "Compare uses saved sessions only (no typing three cars in chat)."
    )
    if st.session_state.flow_mode == "single":
        st.markdown("---")
        st.write("Examples you can riff on:")
        st.markdown(
            """
            - *I'm checking the price of a Golf 2017 TDI, manual, ~134.5k on the clock.*
            - *Selling a 2014 Clio diesel, about 198k km.*
            - *Want to buy a BMW 320d from 2019, auto, roughly 72k km.*
            """
        )

if st.session_state.flow_mode == "compare":
    st.markdown("### Compare cars")
    if not st.session_state.saved_car_sessions:
        st.warning(
            "You need at least **one saved car**. Finish a **Buy or sell a car** chat until all "
            "required fields are present — it will appear under **Saved cars** in the sidebar."
        )
    elif not st.session_state.compare_built:
        labels_by_id = {s["id"]: s["label"] for s in st.session_state.saved_car_sessions}
        ids = [s["id"] for s in st.session_state.saved_car_sessions]
        picked = st.multiselect(
            f"Choose **1–{MAX_COMPARE_CARS}** saved cars (order = left-to-right in the comparison)",
            options=ids,
            default=[],
            format_func=lambda i: labels_by_id.get(i, i),
            max_selections=MAX_COMPARE_CARS,
            key="compare_multiselect",
        )
        if st.button("Build comparison", type="primary"):
            if not picked:
                st.error("Pick at least one saved car.")
            else:
                by_id = {s["id"]: s for s in st.session_state.saved_car_sessions}
                st.session_state.compare_cars = [
                    dict(by_id[i]["vehicle_json"]) for i in picked if i in by_id
                ]
                st.session_state.compare_built = True
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "text": (
                            f"**Comparison ready** — {len(st.session_state.compare_cars)} car(s). "
                            "Retrieval / PDF across profiles is still on the backlog."
                        ),
                    }
                )
                st.rerun()
    else:
        n = len(st.session_state.compare_cars)
        st.success(f"Showing **{n}** profile(s).")
        cols = st.columns(max(n, 1))
        for i, car in enumerate(st.session_state.compare_cars):
            with cols[i]:
                st.subheader(_make_session_label(car))
                st.json(car)
        if st.button("Change car selection"):
            st.session_state.compare_built = False
            st.session_state.compare_cars = []
            st.session_state.pop("compare_multiselect", None)
            st.rerun()
    st.markdown("---")

# Chat history replay
for turn_i, msg in enumerate(st.session_state.chat_history):
    with st.chat_message(msg["role"]):
        st.write(msg["text"])
        if msg.get("first_json") is not None:
            st.caption("First Extracted JSON")
            st.json(msg["first_json"])
        if msg.get("second_json") is not None:
            label = msg.get("json_caption_ev", "Second (Evaluator Corrected) JSON")
            st.caption(label)
            st.json(msg["second_json"])
        if msg.get("warning"):
            st.warning(msg["warning"])
        if msg.get("role") == "assistant" and (
            msg.get("listings_error")
            or msg.get("listings_empty")
            or msg.get("listing_choice_prompt")
            or msg.get("results_style")
        ):
            _render_message_listing_extras(msg, f"h{turn_i}")

chat_placeholder = "Choose an option above first..."
if (
    st.session_state.flow_mode == "single"
    and st.session_state.get("listings_quick_deep_turn_done")
):
    chat_placeholder = (
        "This search is complete (results above). Use Start over (new goal) in the sidebar."
    )
elif (
    st.session_state.flow_mode == "single"
    and st.session_state.get("awaiting_results_choice")
    and st.session_state.get("listings_bundle")
):
    chat_placeholder = "Quick cards (top 10) or deep analysis + PDF? Reply in plain language."
elif st.session_state.flow_mode == "single":
    chat_placeholder = "Buying or selling? Describe the car..."
elif st.session_state.flow_mode == "compare":
    if not st.session_state.compare_built:
        chat_placeholder = "Use the comparison panel above — multiselect saved cars, then Build."
    else:
        chat_placeholder = "Comparison follow-up chat is not wired yet."

user_input = st.chat_input(chat_placeholder)

if user_input:
    text = user_input.strip()
    if st.session_state.flow_mode is None:
        st.session_state.chat_history.append({"role": "user", "text": text})
        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "text": "Please tap **Buy or sell a car** or **Compare cars** above so I know how to help.",
            }
        )
        st.stop()

    if st.session_state.flow_mode == "compare":
        st.session_state.chat_history.append({"role": "user", "text": text})
        with st.chat_message("user"):
            st.write(text)
        if not st.session_state.compare_built:
            hint = (
                "In **Compare** mode, pick saved cars in the panel above (in the order you want them "
                "compared) and tap **Build comparison**."
            )
        else:
            hint = "Questions that reference this comparison aren’t wired to the LLM yet — backlog."
        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "text": hint,
            }
        )
        with st.chat_message("assistant"):
            st.write(st.session_state.chat_history[-1]["text"])
        st.stop()

    if (
        st.session_state.flow_mode == "single"
        and st.session_state.get("listings_quick_deep_turn_done")
        and not st.session_state.get("awaiting_results_choice")
    ):
        st.session_state.chat_history.append({"role": "user", "text": text})
        with st.chat_message("user"):
            st.write(text)
        st.session_state.chat_history.append(
            {"role": "assistant", "text": _LISTINGS_TURN_CLOSED}
        )
        with st.chat_message("assistant"):
            st.write(_LISTINGS_TURN_CLOSED)
        st.stop()

    if (
        st.session_state.flow_mode == "single"
        and st.session_state.get("awaiting_results_choice")
        and st.session_state.get("listings_bundle")
    ):
        st.session_state.chat_history.append({"role": "user", "text": text})
        with st.chat_message("user"):
            st.write(text)

        bundle = st.session_state.listings_bundle
        evaluated = bundle["evaluated"]
        enriched = bundle["enriched"]
        slim = lp.slim_enriched(enriched)

        style = classify_results_style(text)
        ack = (
            "Here are the **10 most similar** cars in a compact card layout." + _LISTINGS_ACK_TAIL
            if style == "quick"
            else (
                "Here’s the **deep / extended** view — table with match % / tolerances, stats, maps, "
                "trends, and PDF."
                + _LISTINGS_ACK_TAIL
            )
        )
        assistant_turn = {
            "role": "assistant",
            "text": ack,
            "results_style": style,
            "enriched_slim": slim,
            "evaluated_snapshot": dict(evaluated),
        }
        st.session_state.chat_history.append(assistant_turn)
        st.session_state.awaiting_results_choice = False
        st.session_state.listings_bundle = None
        st.session_state.listings_quick_deep_turn_done = True

        live_k = f"l{len(st.session_state.chat_history) - 1}"
        with st.chat_message("assistant"):
            st.write(ack)
            _render_message_listing_extras(assistant_turn, live_k)
        st.stop()

    st.session_state.chat_history.append({"role": "user", "text": text})
    with st.chat_message("user"):
        st.write(text)

    pending_missing = st.session_state.missing_required_fields
    base_json = st.session_state.base_json
    retrieve_listings = True

    preamble = _intent_preamble_buy_sell()

    if pending_missing and base_json:
        with st.spinner("Running extractor + evaluator on your follow-up..."):
            ctx = json.dumps(base_json, ensure_ascii=False)
            augmented_query = (
                f"{preamble}"
                "Prior extracted vehicle JSON from this conversation "
                "(preserve non-null values unless the user clearly corrects them):\n"
                f"{ctx}\n\n"
                "User follow-up (fill or correct missing intent, maker, model, km, year if stated):\n"
                f"{text}"
            )
            follow_up = graph.invoke({"query": augmented_query, "extracted": {}})
            follow_up_json = (
                follow_up.get("evaluated_extracted")
                or follow_up.get("extracted")
                or {}
            )

            merged = dict(base_json)
            for field in pending_missing:
                value = follow_up_json.get(field)
                if value is not None:
                    merged[field] = value

            still_missing = [
                field for field in pending_missing if merged.get(field) is None
            ]
            st.session_state.base_json = merged
            st.session_state.missing_required_fields = still_missing

        warning_msg = ""
        if still_missing:
            warning_msg = format_missing_message(still_missing)
        else:
            warning_msg = "All required fields are now present."

        listings_rows: list | None = None
        listings_err: str | None = None
        listing_extras: dict = {}
        if not still_missing and retrieve_listings:
            listings_rows, listings_err = fetch_top_listings(merged)
            listing_extras = _listing_response_fields(merged, listings_rows, listings_err)

        assistant_turn = {
            "role": "assistant",
            "text": "Updated your previous extraction using only missing fields.",
            "first_json": base_json,
            "second_json": merged,
            "json_caption_ev": "Second (Evaluator Corrected) JSON",
            "warning": warning_msg,
            **listing_extras,
        }
        st.session_state.chat_history.append(assistant_turn)

        if not still_missing:
            _maybe_autosave_completed_session(merged)

        with st.chat_message("assistant"):
            st.write(assistant_turn["text"])
            st.caption("Previous JSON")
            st.json(base_json)
            st.caption(assistant_turn["json_caption_ev"])
            st.json(merged)
            if still_missing:
                st.warning(warning_msg)
            else:
                st.success(warning_msg)
            if not still_missing and retrieve_listings and listing_extras:
                lk = f"l{len(st.session_state.chat_history) - 1}"
                _render_message_listing_extras(assistant_turn, lk)
        st.stop()

    with st.spinner("Running extraction and evaluation..."):
        full_query = f"{preamble}{text}"
        result = graph.invoke({"query": full_query, "extracted": {}})
        first_extracted = result.get("extracted", {})
        second_extracted = result.get("evaluated_extracted", {})
        missing_required = result.get("missing_required_fields", [])
        ask_user = result.get("ask_user", "")

    second_json = second_extracted or first_extracted
    warning_msg = ""

    if missing_required:
        st.session_state.base_json = second_json
        st.session_state.missing_required_fields = missing_required
        warning_msg = ask_user or format_missing_message(missing_required)
    else:
        st.session_state.base_json = second_extracted
        st.session_state.missing_required_fields = []

    listings_rows = None
    listings_err = None
    listing_extras: dict = {}
    if not missing_required and retrieve_listings:
        listings_rows, listings_err = fetch_top_listings(second_json)
        listing_extras = _listing_response_fields(second_json, listings_rows, listings_err)

    assistant_turn = {
        "role": "assistant",
        "text": "Here is the extraction result.",
        "first_json": first_extracted,
        "second_json": second_json,
        "json_caption_ev": "Second (Evaluator Corrected) JSON",
        "warning": warning_msg,
        **listing_extras,
    }
    st.session_state.chat_history.append(assistant_turn)

    if not missing_required:
        _maybe_autosave_completed_session(second_json)

    with st.chat_message("assistant"):
        st.write(assistant_turn["text"])
        st.caption("First Extracted JSON")
        st.json(first_extracted)
        st.caption(assistant_turn["json_caption_ev"])
        st.json(second_json)
        if warning_msg:
            if missing_required:
                st.warning(warning_msg)
            else:
                st.success(warning_msg)

        if not missing_required and listing_extras:
            lk = f"l{len(st.session_state.chat_history) - 1}"
            _render_message_listing_extras(assistant_turn, lk)
