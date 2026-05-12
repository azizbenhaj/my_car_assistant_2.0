import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from graph import graph
import listings_present as lp
from listings_retrieval import fetch_top_listings
from orchestrator import format_missing_message

MAX_SAVED_SESSIONS = 10
MAX_COMPARE_CARS = 3

_APP_DIR = Path(__file__).resolve().parent
_SAVED_SESSIONS_PATH = _APP_DIR / ".saved_car_sessions.json"

# Only evaluator fields — never persist / replay listing UI keys on saved profiles.
_VEHICLE_PROFILE_KEYS: frozenset[str] = frozenset(
    {"intent", "maker", "model", "year", "km", "fuel", "gearbox"}
)


def _sanitize_vehicle_profile(raw: dict | None) -> dict:
    if not raw:
        return {}
    return {k: raw[k] for k in _VEHICLE_PROFILE_KEYS if k in raw and raw[k] is not None}


def _load_saved_car_sessions() -> list:
    try:
        raw = _SAVED_SESSIONS_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        cleaned: list = []
        for item in data[:MAX_SAVED_SESSIONS]:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            if "vehicle_json" in row:
                row["vehicle_json"] = _sanitize_vehicle_profile(row.get("vehicle_json"))
            ls = row.get("listing_snapshot")
            if isinstance(ls, dict) and isinstance(ls.get("evaluated_snapshot"), dict):
                ls = dict(ls)
                ls["evaluated_snapshot"] = _sanitize_vehicle_profile(ls.get("evaluated_snapshot"))
                row["listing_snapshot"] = ls
            cleaned.append(row)
        return cleaned
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return []


def _persist_saved_car_sessions() -> None:
    try:
        _SAVED_SESSIONS_PATH.write_text(
            json.dumps(st.session_state.saved_car_sessions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def _listing_response_fields(
    merged: dict, listings_rows: list | None, listings_err: str | None
) -> dict:
    """When DB returns rows: auto quick view + PDF; then lock buy/sell chat (session done)."""
    if listings_err:
        return {"listings_error": listings_err}
    if not listings_rows:
        return {"listings_empty": True}

    scored = lp.enrich_listing_pool(merged, listings_rows)
    n_show = lp.AUTO_QUICK_CARD_COUNT
    top = scored[:n_show]
    slim = lp.slim_enriched(top, max_rows=n_show)
    st.session_state.buy_sell_chat_locked = True
    st.session_state.sidebar_delete_disabled = False
    return {
        "results_style": "quick",
        "listing_count": len(scored),
        "evaluated_snapshot": dict(merged),
        "enriched_slim": slim,
    }


def _render_message_listing_extras(msg: dict, turn_key: str) -> None:
    if msg.get("listings_error"):
        st.error(msg["listings_error"])
        return
    if msg.get("listings_empty"):
        st.info("No listings matched these filters in the database.")
        return
    rs = msg.get("results_style")
    if rs in ("quick", "deep"):
        slim = msg.get("enriched_slim") or []
        ev = msg.get("evaluated_snapshot") or {}
        if rs == "quick":
            lp.render_quick_cards(slim, limit=lp.AUTO_QUICK_CARD_COUNT)
            qp = lp.quick_cards_pdf_bytes(slim, ev, n=lp.AUTO_QUICK_CARD_COUNT)
            st.download_button(
                label=f"Download PDF (top {lp.AUTO_QUICK_CARD_COUNT} cars, photos & links)",
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


def _append_listing_summary_to_assistant_text(turn: dict, listing_extras: dict) -> None:
    if listing_extras.get("results_style") != "quick":
        return
    n = int(listing_extras.get("listing_count") or 0)
    k = lp.AUTO_QUICK_CARD_COUNT
    turn["text"] = (
        str(turn.get("text") or "").rstrip()
        + f" Matched **{n}** listings — **{k}** closest below (photos) + PDF. "
        "**Chat is closed for this run** — use **Start over (new goal)** or **Load** a saved car when you want to go again."
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


def _listing_snapshot_from_extras(listing_extras: dict | None) -> dict | None:
    """JSON-safe blob to restore quick cards + PDF on Load."""
    if not listing_extras or listing_extras.get("results_style") != "quick":
        return None
    ev = listing_extras.get("evaluated_snapshot") or {}
    slim = listing_extras.get("enriched_slim") or []
    try:
        return json.loads(
            json.dumps(
                {
                    "results_style": "quick",
                    "listing_count": int(listing_extras.get("listing_count") or 0),
                    "evaluated_snapshot": dict(ev),
                    "enriched_slim": slim,
                },
                default=str,
            )
        )
    except (TypeError, ValueError):
        return None


def _maybe_autosave_completed_session(
    vehicle: dict, listing_extras: dict | None = None
) -> None:
    """Save or update a sidebar session; attach listing snapshot when quick view + PDF was shown."""
    sig = _vehicle_signature(vehicle)
    snap = _listing_snapshot_from_extras(listing_extras)

    if sig == st.session_state.last_autosaved_signature:
        if snap:
            for row in st.session_state.saved_car_sessions:
                if _vehicle_signature(row.get("vehicle_json") or {}) == sig:
                    row["listing_snapshot"] = snap
                    row["saved_at"] = _utc_now_iso()
                    break
            _persist_saved_car_sessions()
        return

    st.session_state.last_autosaved_signature = sig
    label = _make_session_label(vehicle)
    sid = str(uuid.uuid4())
    entry: dict = {
        "id": sid,
        "label": label,
        "vehicle_json": _sanitize_vehicle_profile(dict(vehicle)),
        "saved_at": _utc_now_iso(),
    }
    if snap:
        entry["listing_snapshot"] = snap
    st.session_state.saved_car_sessions.insert(0, entry)
    st.session_state.saved_car_sessions = st.session_state.saved_car_sessions[
        :MAX_SAVED_SESSIONS
    ]
    _persist_saved_car_sessions()


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


def _build_compare_sessions_from_ids(picked_ids: list[str]) -> list[dict]:
    """Load up to 20 enriched listings per saved car (snapshot or live fetch)."""
    by_id = {s["id"]: s for s in st.session_state.saved_car_sessions}
    out: list[dict] = []
    for pid in picked_ids:
        sess = by_id.get(pid)
        if not sess:
            continue
        vehicle = dict(sess.get("vehicle_json") or {})
        evaluated = dict(vehicle)
        slim: list = []
        snap = sess.get("listing_snapshot")
        if isinstance(snap, dict):
            ev = snap.get("evaluated_snapshot")
            if isinstance(ev, dict) and ev:
                evaluated = {**evaluated, **ev}
            es = snap.get("enriched_slim")
            if isinstance(es, list) and es:
                slim = list(es)[:20]
        if len(slim) < 1:
            rows, err = fetch_top_listings(evaluated, limit=50)
            if not err and rows:
                scored = lp.enrich_listing_pool(evaluated, rows)
                slim = lp.slim_enriched(scored[:20], max_rows=20)
        out.append(
            {
                "id": sess["id"],
                "label": str(sess.get("label") or _make_session_label(vehicle)),
                "vehicle_json": _sanitize_vehicle_profile(vehicle),
                "evaluated_snapshot": evaluated,
                "enriched_slim": slim,
            }
        )
    return out


def _reset_flow() -> None:
    st.session_state.flow_mode = None
    st.session_state.preferred_intent = None
    st.session_state.compare_cars = []
    st.session_state.compare_sessions = []
    st.session_state.compare_built = False
    st.session_state.base_json = {}
    st.session_state.missing_required_fields = []
    st.session_state.chat_history = []
    st.session_state.last_autosaved_signature = None
    st.session_state.pop("compare_multiselect", None)
    st.session_state.pop("_sidebar_pdf_cache", None)
    st.session_state.sidebar_delete_disabled = False
    st.session_state.buy_sell_chat_locked = False


def _apply_loaded_session(sess: dict) -> None:
    st.session_state.flow_mode = "single"
    vj = _sanitize_vehicle_profile(sess.get("vehicle_json"))
    st.session_state.preferred_intent = vj.get("intent")
    st.session_state.base_json = dict(vj)
    st.session_state.missing_required_fields = []
    st.session_state.compare_built = False
    st.session_state.compare_cars = []
    st.session_state.compare_sessions = []
    st.session_state.sidebar_delete_disabled = False
    st.session_state.last_autosaved_signature = _vehicle_signature(vj)
    if "car_assistant_chat_input" in st.session_state:
        del st.session_state["car_assistant_chat_input"]

    snap = sess.get("listing_snapshot")
    if (
        isinstance(snap, dict)
        and snap.get("results_style") == "quick"
        and isinstance(snap.get("enriched_slim"), list)
        and snap["enriched_slim"]
    ):
        ev_snap = _sanitize_vehicle_profile(snap.get("evaluated_snapshot")) or dict(vj)
        n = int(snap.get("listing_count") or 0)
        k = lp.AUTO_QUICK_CARD_COUNT
        st.session_state.buy_sell_chat_locked = True
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "text": (
                    f"Loaded saved car **{sess['label']}** — **restored** the last marketplace view "
                    f"(**{k}** closest matches, photos, PDF). Matched **{n}** listings in that run. "
                    "**Chat is closed** — use **Start over (new goal)** for a new search."
                ),
                "results_style": "quick",
                "listing_count": n,
                "evaluated_snapshot": dict(ev_snap),
                "enriched_slim": snap["enriched_slim"],
            }
        ]
    else:
        st.session_state.buy_sell_chat_locked = False
        st.session_state.chat_history = [
            {
                "role": "assistant",
                "text": (
                    f"Loaded saved car **{sess['label']}**. "
                    "No saved listing snapshot for this save — vehicle JSON only. "
                    "Use **Start over** then describe the car again to fetch listings, or complete a "
                    "run once to store cards + PDF with this profile."
                ),
            }
        ]


def _delete_session(session_id: str) -> None:
    st.session_state.saved_car_sessions = [
        s for s in st.session_state.saved_car_sessions if s["id"] != session_id
    ]
    st.session_state.get("_sidebar_pdf_cache", {}).pop(session_id, None)
    _persist_saved_car_sessions()


def _pdf_bytes_for_saved_session(sess: dict) -> tuple[bytes | None, str | None]:
    """Quick-listings PDF bytes: snapshot if present, else live DB fetch + enrich."""
    vehicle = dict(sess.get("vehicle_json") or {})
    if not vehicle:
        return None, "No vehicle profile in this save."
    evaluated = dict(vehicle)
    slim: list = []
    snap = sess.get("listing_snapshot")
    if isinstance(snap, dict):
        ev = snap.get("evaluated_snapshot")
        if isinstance(ev, dict) and ev:
            evaluated = {**evaluated, **ev}
        es = snap.get("enriched_slim")
        if isinstance(es, list) and es:
            slim = list(es)
    if not slim:
        rows, err = fetch_top_listings(evaluated, limit=50)
        if err:
            return None, err
        if not rows:
            return None, "No DB matches for this profile (check DATABASE_URL and filters)."
        scored = lp.enrich_listing_pool(evaluated, rows)
        slim = lp.slim_enriched(scored[: lp.AUTO_QUICK_CARD_COUNT], max_rows=lp.AUTO_QUICK_CARD_COUNT)
    if not slim:
        return None, "No listing rows to put in the PDF."
    try:
        b = lp.quick_cards_pdf_bytes(slim, evaluated, n=lp.AUTO_QUICK_CARD_COUNT)
    except Exception as ex:
        return None, str(ex) or "PDF build failed."
    if not b or len(b) < 200:
        return None, "PDF build returned empty output."
    return b, None


def _safe_pdf_filename(label: str, session_id: str) -> str:
    base = "".join(c if c.isalnum() or c in " -_" else "_" for c in (label or "car").strip())[:40] or "car"
    short = (session_id or "id")[:8]
    return f"{base.replace(' ', '_')}_{short}_listings.pdf"


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
if "compare_sessions" not in st.session_state:
    st.session_state.compare_sessions = []
if "saved_car_sessions" not in st.session_state:
    st.session_state.saved_car_sessions = _load_saved_car_sessions()
if len(st.session_state.saved_car_sessions) > MAX_SAVED_SESSIONS:
    st.session_state.saved_car_sessions = st.session_state.saved_car_sessions[
        :MAX_SAVED_SESSIONS
    ]
    _persist_saved_car_sessions()
if "last_autosaved_signature" not in st.session_state:
    st.session_state.last_autosaved_signature = None
if "sidebar_delete_disabled" not in st.session_state:
    st.session_state.sidebar_delete_disabled = False
if "buy_sell_chat_locked" not in st.session_state:
    st.session_state.buy_sell_chat_locked = False

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
                    pdf_cache = st.session_state.setdefault("_sidebar_pdf_cache", {})
                    sid = sess["id"]
                    cached = pdf_cache.get(sid)
                    pdf_b: bytes | None = None
                    pdf_err: str | None = None
                    if isinstance(cached, bytes) and len(cached) > 200:
                        pdf_b = cached
                    else:
                        b, err = _pdf_bytes_for_saved_session(sess)
                        if b is not None:
                            pdf_cache[sid] = b
                            pdf_b = b
                        else:
                            pdf_err = err or "Unavailable"
                    if pdf_b is not None:
                        st.download_button(
                            label="PDF",
                            data=pdf_b,
                            file_name=_safe_pdf_filename(str(sess.get("label") or "car"), sid),
                            mime="application/pdf",
                            key=f"pdf_dl_{sid}",
                            use_container_width=True,
                        )
                    else:
                        st.button(
                            "PDF",
                            key=f"pdf_na_{sid}",
                            use_container_width=True,
                            disabled=True,
                            help=(pdf_err or "PDF unavailable")[:220],
                        )
                with c3:
                    if st.button(
                        "Del",
                        key=f"del_{sess['id']}",
                        use_container_width=True,
                        disabled=st.session_state.get("sidebar_delete_disabled", False),
                    ):
                        _delete_session(sess["id"])
                        st.rerun()
            st.divider()

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
                ncmp = len(st.session_state.get("compare_sessions") or st.session_state.compare_cars)
                st.caption(f"Comparison: **{ncmp}** car(s)")
            else:
                st.caption("Pick **2 or 3** saved cars, then **Compare**.")
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
            st.session_state.compare_sessions = []
            st.session_state.sidebar_delete_disabled = False
            st.session_state.buy_sell_chat_locked = False
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
            st.session_state.compare_sessions = []
            st.session_state.base_json = {}
            st.session_state.missing_required_fields = []
            st.session_state.sidebar_delete_disabled = False
            st.session_state.buy_sell_chat_locked = False
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "text": (
                        "**Compare** — pick **two or three** saved cars in the panel below (order = chart "
                        "colors: blue, red, green), then press **Compare**. Chat stays off here."
                    ),
                }
            )
            st.rerun()
    st.caption(
        "Two-pass extraction (extractor → evaluator) applies in buy/sell chat. "
        "Compare uses profiles you already saved from completed extractions."
    )
else:
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
    n_saved = len(st.session_state.saved_car_sessions)
    if n_saved < 2:
        st.warning(
            "You need at least **two saved cars** (each from a completed **Buy or sell a car** run). "
            "They appear under **Saved cars** in the sidebar."
        )
    elif not st.session_state.compare_built:
        labels_by_id = {s["id"]: s["label"] for s in st.session_state.saved_car_sessions}
        ids = [s["id"] for s in st.session_state.saved_car_sessions]
        picked = st.multiselect(
            f"Select **2 or 3** saved cars (order = **1st → blue**, **2nd → red**, **3rd → green** in charts)",
            options=ids,
            default=[],
            format_func=lambda i: labels_by_id.get(i, i),
            max_selections=MAX_COMPARE_CARS,
            key="compare_multiselect",
        )
        n_pick = len(picked)
        if st.button(
            "Compare",
            type="primary",
            disabled=n_pick < 2,
            key="compare_run_btn",
            help="Select at least two saved cars to enable Compare.",
        ):
            sessions = _build_compare_sessions_from_ids(list(picked))
            if len(sessions) < 2:
                st.error("Could not load at least two car profiles with the current selection.")
            else:
                st.session_state.compare_sessions = sessions
                st.session_state.compare_cars = [
                    _sanitize_vehicle_profile(dict(s.get("vehicle_json") or {})) for s in sessions
                ]
                st.session_state.compare_built = True
                st.rerun()
    else:
        n = len(st.session_state.compare_sessions or st.session_state.compare_cars)
        st.success(f"Comparing **{n}** saved car(s).")
        lp.render_compare_dashboard(list(st.session_state.compare_sessions or []))
        if st.button("Change selection", key="compare_change_btn"):
            st.session_state.compare_built = False
            st.session_state.compare_cars = []
            st.session_state.compare_sessions = []
            st.session_state.pop("compare_multiselect", None)
            st.rerun()
    st.markdown("---")

# Chat history replay
for turn_i, msg in enumerate(st.session_state.chat_history):
    with st.chat_message(msg["role"]):
        st.write(msg["text"])
        if msg.get("warning"):
            st.warning(msg["warning"])
        if msg.get("role") == "assistant" and (
            msg.get("listings_error")
            or msg.get("listings_empty")
            or msg.get("results_style")
        ):
            _render_message_listing_extras(msg, f"h{turn_i}")

chat_placeholder = (
    "Pick **Buy or sell a car** above to enable chat. **Compare cars** uses only the panel "
    "(multiselect + **Compare**) — no chat here."
)
if (
    st.session_state.flow_mode == "single"
    and st.session_state.get("buy_sell_chat_locked")
):
    chat_placeholder = (
        "This run is complete (listings + PDF above). Use **Start over (new goal)** or **Load** "
        "a saved car to continue."
    )
elif st.session_state.flow_mode == "single":
    chat_placeholder = "Buying or selling? Describe the car…"
elif st.session_state.flow_mode == "compare":
    chat_placeholder = (
        "Chat is disabled in **Compare cars**. Use the panel above, or **Start over (new goal)** "
        "to use buy/sell chat."
    )

_chat_disabled = (
    st.session_state.flow_mode is None
    or st.session_state.flow_mode == "compare"
    or (
        st.session_state.flow_mode == "single"
        and st.session_state.get("buy_sell_chat_locked")
    )
)
user_input = st.chat_input(
    chat_placeholder,
    key="car_assistant_chat_input",
    disabled=_chat_disabled,
)

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
            "warning": warning_msg,
            **listing_extras,
        }
        _append_listing_summary_to_assistant_text(assistant_turn, listing_extras)
        st.session_state.chat_history.append(assistant_turn)

        if not still_missing:
            _maybe_autosave_completed_session(merged, listing_extras)

        with st.chat_message("assistant"):
            st.write(assistant_turn["text"])
            if still_missing:
                st.warning(warning_msg)
            else:
                st.success(warning_msg)
            if not still_missing and retrieve_listings and listing_extras:
                lk = f"l{len(st.session_state.chat_history) - 1}"
                _render_message_listing_extras(assistant_turn, lk)
        if listing_extras.get("results_style") == "quick":
            st.rerun()
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
        "warning": warning_msg,
        **listing_extras,
    }
    _append_listing_summary_to_assistant_text(assistant_turn, listing_extras)
    st.session_state.chat_history.append(assistant_turn)

    if not missing_required:
        _maybe_autosave_completed_session(second_json, listing_extras)

    with st.chat_message("assistant"):
        st.write(assistant_turn["text"])
        if warning_msg:
            if missing_required:
                st.warning(warning_msg)
            else:
                st.success(warning_msg)

        if not missing_required and listing_extras:
            lk = f"l{len(st.session_state.chat_history) - 1}"
            _render_message_listing_extras(assistant_turn, lk)

    if listing_extras.get("results_style") == "quick":
        st.rerun()
    st.stop()
