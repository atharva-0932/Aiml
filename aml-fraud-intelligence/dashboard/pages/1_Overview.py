"""Overview Dashboard — KPI cards, risk distribution, top flagged accounts."""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="Overview | AML Platform", layout="wide", page_icon="📊")
st.markdown("""<style>
[data-testid="stAppViewContainer"]{background:#0d1117}
[data-testid="stSidebar"]{background:#161b22}
h1,h2,h3,p,label,span{color:#c9d1d9!important}
.stMetric [data-testid="stMetricValue"]{color:#00e5ff!important;font-weight:700}
</style>""", unsafe_allow_html=True)

st.title("📊 Overview Dashboard")
st.markdown("---")

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from dashboard.utils.api_client import get_flagged_transactions, get_top_flagged

@st.cache_data(ttl=30)
def load_flagged():
    return get_flagged_transactions(limit=500)

@st.cache_data(ttl=10)
def load_top_flagged():
    return get_top_flagged(n=20)

flagged = load_flagged()
top_flagged = load_top_flagged()
df = pd.DataFrame(flagged) if flagged else pd.DataFrame()

# ── KPI Cards ─────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("🚨 Total Flagged", len(df))
c2.metric("🔴 Critical", len(df[df.get("risk_tier", pd.Series()) == "CRITICAL"]) if not df.empty and "risk_tier" in df else 0)
c3.metric("🟠 High Risk", len(df[df.get("risk_tier", pd.Series()) == "HIGH"]) if not df.empty and "risk_tier" in df else 0)
c4.metric("💰 Total Suspicious Volume",
          f"${df['amount'].sum():,.0f}" if not df.empty and "amount" in df else "$0")

st.markdown("---")

col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("Risk Tier Distribution")
    if not df.empty and "risk_tier" in df:
        tier_counts = df["risk_tier"].value_counts().reset_index()
        tier_counts.columns = ["tier", "count"]
        colors = {"CRITICAL": "#ff1744", "HIGH": "#ff6d00", "MEDIUM": "#ffd600", "LOW": "#00c853"}
        fig = px.pie(tier_counts, names="tier", values="count",
                     color="tier", color_discrete_map=colors,
                     hole=0.45)
        fig.update_layout(paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                          font_color="#c9d1d9", legend_font_color="#c9d1d9")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No flagged transactions yet. Run the data seeder.")

with col_right:
    st.subheader("Flagging Trend (by AML Pattern)")
    if not df.empty and "aml_label" in df and "timestamp" in df:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df["date"] = df["timestamp"].dt.date
        trend = df.groupby(["date", "aml_label"]).size().reset_index(name="count")
        fig2 = px.line(trend, x="date", y="count", color="aml_label",
                       color_discrete_sequence=px.colors.qualitative.Set2)
        fig2.update_layout(paper_bgcolor="#0d1117", plot_bgcolor="#161b22",
                           font_color="#c9d1d9", legend_font_color="#c9d1d9",
                           xaxis=dict(color="#c9d1d9"), yaxis=dict(color="#c9d1d9"))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No trend data available yet.")

st.markdown("---")
st.subheader("🏆 Top Risk Accounts (Live — Redis Leaderboard)")
if top_flagged:
    top_df = pd.DataFrame(top_flagged)
    top_df["risk_bar"] = top_df["composite_score"].apply(lambda x: "█" * int(x / 5))
    st.dataframe(top_df[["account_id", "composite_score", "risk_bar"]].head(15),
                 use_container_width=True)
else:
    st.info("Redis leaderboard is empty. Ingest some transactions first.")
