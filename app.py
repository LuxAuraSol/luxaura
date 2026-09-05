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
    }

    with st.spinner("Checking matches..."):
        preview = requests.post(
            "https://tracerfy.com/v1/api/property-search/preview/",
            json=payload,
            headers=headers,
        )

    if preview.status_code != 200:
        st.error("API error: " + preview.text)
        st.stop()

    data = preview.json()
    total = data.get("count", 0)
    capped = data.get("capped_count", 0)
    cost = data.get("max_credit_cost_usd", 0)

    st.info(str(total) + " properties match. Will pull up to " + str(capped) + " rows. Cost: $" + str(cost))

    if st.button("Confirm and pull results ($" + str(cost) + ")"):
        exec_payload = dict(payload)
        exec_payload["name"] = city + " " + state + " search"

        exec_resp = requests.post(
            "https://tracerfy.com/v1/api/property-search/execute/",
            json=exec_payload,
            headers=headers,
        )

        if exec_resp.status_code not in (200, 202):
            st.error("Execute error: " + exec_resp.text)
            st.stop()

        list_id = exec_resp.json().get("id")
        progress = st.progress(0)

        for _ in range(60):
            status_resp = requests.get(
                "https://tracerfy.com/v1/api/property-search/" + str(list_id) + "/",
                headers=headers,
            )
            status = status_resp.json()
            if status.get("status") == "complete":
                progress.progress(100)
                break
            pct = status.get("progress_percent", 0)
            progress.progress(pct)
            time.sleep(5)

        rows_resp = requests.get(
            "https://tracerfy.com/v1/api/property-search/" + str(list_id) + "/rows/?per_page=500",
            headers=headers,
        )
        rows = rows_resp.json().get("rows", [])

        if not rows:
            st.warning("No rows returned.")
            st.stop()

        st.success(str(len(rows)) + " properties loaded.")

        lats = [r["latitude"] for r in rows if r.get("latitude")]
        lons = [r["longitude"] for r in rows if r.get("longitude")]
        if lats:
            m = folium.Map(location=[sum(lats)/len(lats), sum(lons)/len(lons)], zoom_start=13)
            for r in rows:
                if r.get("latitude") and r.get("longitude"):
                    popup = r["address"] + " | $" + str(r.get("estimated_value", 0))
                    folium.Marker(
                        [r["latitude"], r["longitude"]],
                        popup=folium.Popup(popup, max_width=250),
                        icon=folium.Icon(color="blue", icon="home"),
                    ).add_to(m)
            st_folium(m, width=None, height=500)

        df = pd.DataFrame([{
            "Address": r.get("address"),
            "City": r.get("city"),
            "Est. Value": r.get("estimated_value"),
            "Lot sqft": r.get("lot_size_sqft"),
            "Equity %": r.get("equity_percent"),
            "Owner": r.get("owner_1_first_name", "") + " " + r.get("owner_1_last_name", ""),
            "Phone": r.get("primary_phone"),
            "Absentee": r.get("absentee_owner"),
            "Free & Clear": r.get("free_clear"),
        } for r in rows])

        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, "luxaura_leads.csv", "text/csv")
