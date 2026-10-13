"""Entry point: page setup, shared style and navigation."""
import streamlit as st

from geotech import ui

st.set_page_config(page_title="Montréal Geotechnical Atlas", page_icon="🪨", layout="wide",
                   initial_sidebar_state="expanded")
ui.apply_style()

pages = {
    "Navigate": [
        st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
        st.Page("views/guide.py", title="User guide", icon=":material/menu_book:"),
    ],
    "Explore the data": [
        st.Page("views/explore.py", title="Map and 3D", icon=":material/map:"),
        st.Page("views/insights.py", title="Insights", icon=":material/insights:"),
        st.Page("views/site_report.py", title="Site report", icon=":material/location_searching:"),
    ],
    "Contribute": [
        st.Page("views/contribute.py", title="Contribute data", icon=":material/upload_file:"),
        st.Page("views/curate.py", title="Curate", icon=":material/fact_check:"),
    ],
}
page = st.navigation(pages, position="sidebar", expanded=True)
ui.sidebar_credit()  # pinned to the foot of the sidebar by CSS, after any page filters
page.run()
