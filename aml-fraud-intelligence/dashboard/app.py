"""
Streamlit entrypoint — dark enterprise AML dashboard.
Run: streamlit run dashboard/app.py
"""
import streamlit as st

st.set_page_config(
    page_title="AML Intelligence Platform",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global dark theme ─────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Dark background */
  [data-testid="stAppViewContainer"] { background-color: #0d1117; }
  [data-testid="stSidebar"]          { background-color: #161b22; }
  [data-testid="stHeader"]           { background-color: #0d1117; }
  section[data-testid="stSidebar"] * { color: #c9d1d9 !important; }
  h1, h2, h3, h4, p, label, span    { color: #c9d1d9 !important; }
  .stMetric label                    { color: #8b949e !important; }
  .stMetric [data-testid="stMetricValue"] { color: #00e5ff !important; font-weight: 700; }
  .stDataFrame                       { background: #161b22; }
  [data-testid="stDataFrame"] *      { color: #c9d1d9 !important; }
  .stButton button {
    background: #00e5ff; color: #0d1117; font-weight: 700;
    border: none; border-radius: 6px;
  }
  .stSelectbox > div, .stTextInput > div { background: #21262d; }
  hr { border-color: #30363d; }
  .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 🔐 AML Intelligence")
st.sidebar.markdown("---")
st.sidebar.markdown("**Navigation**")
st.sidebar.markdown("""
- 📊 Overview Dashboard  
- 🔍 Transaction Explorer  
- 🕸️ Graph Investigation  
- 🌡️ Risk Heatmaps  
- ⏱️ Timeline Replay  
- 🤖 Copilot Chat  
- 📄 Evidence Reports  
""")
st.sidebar.markdown("---")

from dashboard.utils.api_client import health
h = health()
status_color = "#00c853" if h.get("status") == "ok" else "#ff1744"
st.sidebar.markdown(
    f'<span style="color:{status_color}">● API: {h.get("status", "unknown").upper()}</span>',
    unsafe_allow_html=True,
)

# ── Home landing ──────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center; padding: 40px 0;'>
  <h1 style='font-size: 2.4em; color: #00e5ff !important; letter-spacing: 2px;'>
    🔐 AML FRAUD INTELLIGENCE PLATFORM
  </h1>
  <p style='color: #8b949e; font-size: 1.1em;'>
    Real-time Anti-Money Laundering Detection · Graph Analytics · AI Investigator Copilot
  </p>
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
col1.info("**Lambda Architecture**\nKafka hot path + Snowflake cold path")
col2.info("**Neo4j Graph Engine**\nCycle, layering & mule detection")
col3.info("**GenAI Copilot**\nLangChain RAG + SAR generation")

st.markdown("---")
st.markdown("*Select a page from the sidebar to begin investigation.*")
