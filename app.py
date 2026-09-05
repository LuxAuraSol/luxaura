import streamlit as st
import requests
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="LuxAura", layout="wide")
st.title("LuxAura — Luxury Property Search")

API_KEY = st.secrets["TRACERFY_API_KEY"]

# --- Sidebar filters ---
with st.sidebar:
    st.header("Search filters")
    city = st.text_input("City", value="Ponte Vedra Beach")
    state = st.text_input("State (2-letter)", value="FL")
    value_min = st.number_input("Min value ($)", value=750000, step=50000)
    value_max = st.number_input("Max value ($)", value=1500000, step=50000)
    lot_min = st.number_input("Min lot size (sqft)", value=14000, step=1000)
    lot_max = st.number_input("Max lot size (sqft)", value=43000, step=1000)
    count = st.number_input("Max results", value=50, min_value=1, max_value=500)
    run = st.button("Search", type="primary")

if run:
    with st.spinner("Searching..."):
        payload = {
            "strategy": "custom",
            "geography": {"mode": "city", "cities": [city], "states": [state]},
            "filter_overrides": {
                "absentee_owner": True,
                "free_clear": True,
                "value_min": int(value_min),
                "value_max": int(value_max),
                "lot_size_sqft_min": int(lot_min),
                "lot_size_sqft_max": int(lot_max),
            },
            "requested_count": int(count),
            "include_pins": True,
        }

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }

        preview = requests.post(
            "https://tracerfy.com/v1/api/property-search/preview/",
            json=payload,
            headers=headers,
        )

        if preview.status_code != 200:
            st.error(f"API error: {preview.text}")
            st.stop()

        data = preview.json()
        total = data.get("count", 0)
        capped = data.get("capped_count", 0)
        cost_usd = data.get("max_credit_cost_usd", 0)

        st.info(f"**{total}** properties match. Pulling up to **{capped}** rows. Estimated cost: **${cost_usd:.2f}**")

    confirm = st.button(f"Confirm — pull {capped} properties (${cost_usd:.2f})")

    if confirm:
        execute_payload = {**payload, "name": f"{city} {state} search"}
        execute_payload.pop("include_pins", None)

        exec_resp = requests.post(
            "https://tracerfy.com/v1/api/property-search/execute/",
            json=execute_payload,
            headers=headers,
        )

        if exec_resp.status_code not in (200, 202):
            st.error(f"Execute error: {exec_resp.text}")
            st.stop()

        list_id = exec_resp.json().get("id")

        import time
        progress = st.progress(0)
        for _ in range(60):
            status_resp = requests.get(
                f"https://tracerfy.com/v1/api/property-search/{list_id}/",
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
            f"https://tracerfy.com/v1/api/property-search/{list_id}/rows/?per_page=500",
            headers=headers,
        )
        rows = rows_resp.json().get("rows", [])

        if not rows:
            st.warning("No rows returned.")
            st.stop()

        st.success(f"{len(rows)} properties loaded.")

        # Map
        lats = [r["latitude"] for r in rows if r.get("latitude")]
        lons = [r["longitude"] for r in rows if r.get("longitude")]
        if lats:
            m = folium.Map(location=[sum(lats)/len(lats), sum(lons)/len(lons)], zoom_start=13)
            for r in rows:
                if r.get("latitude") and r.get("longitude"):
                    popup = f"""
                    <b>{r['address']}</b><br>
                    Value: ${r.get('estimated_value', 0):,}<br>
                    Lot: {r.get('lot_size_sqft', 0):,} sqft<br>
                    Owner: {r.get('owner_1_first_name','')} {r.get('owner_1_last_name','')}
                    """
                    folium.Marker(
                        [r["latitude"], r["longitude"]],
                        popup=folium.Popup(popup, max_width=250),
                        icon=folium.Icon(color="blue", icon="home"),
                    ).add_to(m)
            st_folium(m, width=None, height=500)

        # Table
        import pandas as pd
        df = pd.DataFrame([{
            "Address": r.get("address"),
            "City": r.get("city"),
            "Est. Value": f"${r.get('estimated_value', 0):,}",
            "Lot (sqft)": f"{r.get('lot_size_sqft', 0):,}",
            "Equity %": r.get("equity_percent"),
            "Owner": f"{r.get('owner_1_first_name','')} {r.get('owner_1_last_name','')}",
            "Phone": r.get("primary_phone"),
            "Absentee": r.get("absentee_owner"),
            "Free & Clear": r.get("free_clear"),
        } for r in rows])

        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, "luxaura_leads.csv", "text/csv")
