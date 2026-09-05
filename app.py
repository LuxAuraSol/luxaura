import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import pandas as pd
import time

st.set_page_config(page_title="LuxAura", layout="wide")
st.title("LuxAura - Luxury Property Search")

API_KEY = st.secrets["TRACERFY_API_KEY"]

with st.sidebar:
    st.header("Search filters")
    city = st.text_input("City", value="Ponte Vedra Beach")
    state = st.text_input("State (2-letter)", value="FL")
    value_min = st.number_input("Min value ($)", value=750000, step=50000)
    value_max = st.number_input("Max value ($)", value=1500000, step=50000)
    count = st.number_input("Max results", value=50, min_value=1, max_value=500)
    run = st.button("Search", type="primary")

if run:
    headers = {
        "Authorization": "Bearer " + API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "strategy": "custom",
        "geography": {"mode": "city", "cities": [city], "states": [state]},
        "filter_overrides": {
            "absentee_owner": True,
            "free_clear": True,
            "value_min": int(value_min),
            "value_max": int(value_max),
        },
        "requested_count": int(count),
        "name": city + " " + state,
    }

    with st.spinner("Building lead list..."):
        exec_resp = requests.post(
            "https://tracerfy.com/v1/api/property-search/execute/",
            json=payload,
            headers=headers,
        )

    if exec_resp.status_code not in (200, 202):
        st.error("Error: " + exec_resp.text)
        st.stop()

    list_id = exec_resp.json().get("id")
    progress = st.progress(0)
    status_text
