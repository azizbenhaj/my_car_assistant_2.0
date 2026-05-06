import streamlit as st
from graph import graph


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

# Hidden one-time warm-up call to reduce first-turn cold start issues.
if not st.session_state.llm_warmed_up:
    try:
        graph.invoke(
            {
                "query": "I'm checking the price of a Golf 2017 TDI, manual, ~134.5k on odo (not sure exact).",
                "extracted": {},
            }
        )
    except Exception:
        # Keep UI clean; app still works and user can retry.
        pass
    finally:
        st.session_state.llm_warmed_up = True

st.write("Describe the car you want to buy/sell... Here are some examples:")
st.markdown(
    """
    <style>
      .example-query {
        color: #8a8f98;
        font-size: 0.86rem;
        line-height: 1.2;
        margin: 0.1rem 0;
      }
      .example-wrap {
        margin-top: -0.2rem;
      }
    </style>
    <div class="example-wrap">
      <p class="example-query">I’m selling my almost-new 2021 Mercedes C200 petrol auto, around 87k... what price should I put?</p>
      <p class="example-query">I'm checking the price of a Golf 2017 TDI, manual, ~134.5k on odo (not sure exact).</p>
      <p class="example-query">Thinking to buy a brand-new Model 3 Performance, 0 km, any idea if worth?</p>
      <p class="example-query">Selling 2014 Renault Clio diesel stick, odo close to 198k, engine fine.</p>
      <p class="example-query">Want to buy a 320d from 2019, automatic, ~72k. (BMW maybe?)</p>
      <p class="example-query">I might sell my A4, 2016, petrol manual, just over 110k, unsure trim.</p>
      <p class="example-query">Looking at an unused Corolla hybrid auto (dealer says 0 km), maybe 2026.</p>
      <p class="example-query">Selling Ford Focus gasoline manual, 245k clocked; forgot exact year.</p>
      <p class="example-query">Evaluate buying HyundaiTucson 2018 diesel auto, exactly 80000 km.</p>
      <p class="example-query">Selling a like-new Kia Sportage hybrid auto, only 15k, reg 2025, maker obvious right?</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Render full chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["text"])
        if msg.get("first_json") is not None:
            st.caption("First Extracted JSON")
            st.json(msg["first_json"])
        if msg.get("second_json") is not None:
            st.caption("Second (Evaluator Corrected) JSON")
            st.json(msg["second_json"])
        if msg.get("warning"):
            st.warning(msg["warning"])

user_input = st.chat_input("Describe the car you want to buy/sell...")

if user_input:
    st.session_state.chat_history.append({"role": "user", "text": user_input.strip()})
    with st.chat_message("user"):
        st.write(user_input.strip())

    pending_missing = st.session_state.missing_required_fields
    base_json = st.session_state.base_json

    if pending_missing and base_json:
        with st.spinner("Extracting only missing fields..."):
            follow_up = graph.invoke({"query": user_input.strip(), "extracted": {}})
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
            warning_msg = (
                "Still missing required info: "
                + ", ".join(still_missing)
                + ". Please provide only those fields."
            )
        else:
            warning_msg = "All required fields are now present."

        assistant_turn = {
            "role": "assistant",
            "text": "Updated your previous extraction using only missing fields.",
            "first_json": base_json,
            "second_json": merged,
            "warning": warning_msg,
        }
        st.session_state.chat_history.append(assistant_turn)

        with st.chat_message("assistant"):
            st.write(assistant_turn["text"])
            st.caption("Previous JSON")
            st.json(base_json)
            st.caption("Updated JSON")
            st.json(merged)
            if still_missing:
                st.warning(warning_msg)
            else:
                st.success(warning_msg)
        st.stop()

    with st.spinner("Running extraction and evaluation..."):
        result = graph.invoke({"query": user_input.strip(), "extracted": {}})
        first_extracted = result.get("extracted", {})
        second_extracted = result.get("evaluated_extracted", {})
        missing_required = result.get("missing_required_fields", [])
        ask_user = result.get("ask_user", "")

    second_json = second_extracted or first_extracted
    warning_msg = ""

    if missing_required:
        st.session_state.base_json = second_json
        st.session_state.missing_required_fields = missing_required
        warning_msg = (
            ask_user
            or (
                "Please provide at least maker, model, year, and km. Missing: "
                + ", ".join(missing_required)
            )
        )
    else:
        st.session_state.base_json = second_extracted
        st.session_state.missing_required_fields = []

    assistant_turn = {
        "role": "assistant",
        "text": "Here is the extraction result.",
        "first_json": first_extracted,
        "second_json": second_json,
        "warning": warning_msg,
    }
    st.session_state.chat_history.append(assistant_turn)

    with st.chat_message("assistant"):
        st.write(assistant_turn["text"])
        st.caption("First Extracted JSON")
        st.json(first_extracted)
        st.caption("Second (Evaluator Corrected) JSON")
        st.json(second_json)
        if warning_msg:
            st.warning(warning_msg)
