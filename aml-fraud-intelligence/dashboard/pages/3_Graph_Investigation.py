"""Graph Investigation — interactive PyVis network visualization."""
import streamlit as st
import streamlit.components.v1 as components
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

st.set_page_config(page_title="Graph Investigation | AML", layout="wide", page_icon="🕸️")
st.markdown("""<style>
[data-testid="stAppViewContainer"]{background:#0d1117}
[data-testid="stSidebar"]{background:#161b22}
h1,h2,h3,p,label,span{color:#c9d1d9!important}
</style>""", unsafe_allow_html=True)

st.title("🕸️ Graph Investigation View")
st.markdown("---")

from dashboard.utils.api_client import get_graph_neighbors, get_graph_cycles, get_graph_mules


def _risk_color(score: float) -> str:
    if score >= 90: return "#ff1744"
    if score >= 70: return "#ff6d00"
    if score >= 30: return "#ffd600"
    return "#00c853"


def build_pyvis_graph(center_id: str, neighbors: list[dict]) -> str:
    try:
        from pyvis.network import Network
        net = Network(height="550px", width="100%", bgcolor="#0d1117",
                      font_color="#c9d1d9", notebook=False)
        net.set_options("""{"physics":{"solver":"forceAtlas2Based",
            "forceAtlas2Based":{"gravitationalConstant":-50}}}""")

        net.add_node(center_id, label=center_id[:8], color="#00e5ff",
                     size=25, title=f"Focus Account: {center_id}")

        for nbr in neighbors:
            nbr_id = nbr.get("account_id", "")
            score = float(nbr.get("risk_score") or 0)
            color = _risk_color(score)
            net.add_node(nbr_id, label=nbr_id[:8], color=color, size=15,
                         title=f"Account: {nbr_id}\nRisk: {score:.1f}")
            net.add_edge(center_id, nbr_id)

        tmp = f"/tmp/graph_{center_id[:8]}.html"
        net.save_graph(tmp)
        with open(tmp) as f:
            return f.read()
    except ImportError:
        return "<p style='color:#c9d1d9'>PyVis not installed. Run: pip install pyvis</p>"


tab1, tab2, tab3 = st.tabs(["🎯 Account Neighbors", "🔄 Cycle Detection", "🎭 Mule Accounts"])

with tab1:
    account_id = st.text_input("Account ID to investigate", key="graph_acct")
    if st.button("Load Graph") and account_id:
        with st.spinner("Fetching 2-hop neighbors (Redis cache-aside)..."):
            try:
                neighbors = get_graph_neighbors(account_id)
                if neighbors:
                    st.markdown(f"Found **{len(neighbors)}** neighbors within 2 hops")
                    html = build_pyvis_graph(account_id, neighbors)
                    components.html(html, height=580)
                    st.markdown("#### Neighbor Risk Table")
                    import pandas as pd
                    st.dataframe(pd.DataFrame(neighbors), use_container_width=True)
                else:
                    st.info("No neighbors found in Neo4j. Build the graph first.")
            except Exception as e:
                st.error(f"Graph query failed: {e}")

with tab2:
    lookback = st.slider("Lookback window (days)", 1, 30, 3)
    if st.button("Detect Circular Flows"):
        with st.spinner("Running cycle detection in Neo4j..."):
            try:
                cycles = get_graph_cycles(lookback_days=lookback)
                if cycles:
                    st.success(f"Detected **{len(cycles)}** circular fund flows")
                    import pandas as pd
                    st.dataframe(pd.DataFrame(cycles), use_container_width=True)
                else:
                    st.info("No cycles detected in the selected time window.")
            except Exception as e:
                st.error(f"Cycle detection failed: {e}")

with tab3:
    if st.button("Run Mule Detection"):
        with st.spinner("Analysing fan-in/fan-out patterns..."):
            try:
                mules = get_graph_mules()
                if mules:
                    st.warning(f"Found **{len(mules)}** potential mule accounts")
                    import pandas as pd
                    st.dataframe(pd.DataFrame(mules), use_container_width=True)
                else:
                    st.info("No mule patterns detected.")
            except Exception as e:
                st.error(f"Mule detection failed: {e}")
