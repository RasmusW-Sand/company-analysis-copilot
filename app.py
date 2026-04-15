import streamlit as st
from dotenv import load_dotenv
load_dotenv()

pages = [
    st.Page("1_Watchlist.py",        title="Watchlist",  icon="👁"),
    st.Page("pages/2_Analyser.py",   title="Analyser",   icon="🔍"),
    st.Page("pages/3_Agent_Log.py",  title="Agent Log",  icon="📋"),
    st.Page("pages/4_Screening.py",  title="Screening",  icon="📊"),
]

pg = st.navigation(pages)
pg.run()