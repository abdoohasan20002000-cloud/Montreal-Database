"""Entry point: page setup, shared style and navigation."""
import streamlit as st

from geotech import ui

st.set_page_config(page_title="Montréal Geotechnical Atlas", page_icon="🪨", layout="wide",
                   initial_sidebar_state="expanded")
ui.apply_style()

pages = [
    st.Page("views/explore.py", title="Explore", icon=":material/travel_explore:", default=True),
    st.Page("views/insights.py", title="Insights", icon=":material/insights:"),
    st.Page("views/site_report.py", title="Site report", icon=":material/location_searching:"),
    st.Page("views/contribute.py", title="Contribute data", icon=":material/upload_file:"),
    st.Page("views/curate.py", title="Curate", icon=":material/fact_check:"),
    st.Page("views/about.py", title="About the data", icon=":material/menu_book:"),
]
st.navigation(pages, position="sidebar").run()
