"""Risk Heatmaps — transaction volume heatmap and geo scatter map."""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

st.set_page_config(page_title="Risk Heatmaps | AML", layout="wide", page_icon="🌡️")
st.markdown("""<style>
[data-testid="stAppViewContainer"]{background:#0d1117}
[data-testid="stSidebar"]{background:#161b22}
h1,h2,h3,p,label,span{color:#c9d1d9!important}
</style>""", unsafe_allow_html=True)

st.title("🌡️ Risk Heatmaps")
st.markdown("---")

from dashboard.utils.api_client import get_flagged_transactions

@st.cache_data(ttl=60)
def load_data():
    return get_flagged_transactions(limit=500)

data = load_data()
df = pd.DataFrame(data) if data else pd.DataFrame()

if df.empty:
    st.warning("No data available yet.")
    st.stop()

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df["hour"] = df["timestamp"].dt.hour
df["day_name"] = df["timestamp"].dt.day_name()
df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

tab1, tab2 = st.tabs(["🕐 Hour × Day Heatmap", "🌍 Geographic Scatter"])

with tab1:
    st.subheader("Transaction Volume by Hour of Day × Day of Week")
    pivot = df.groupby(["day_name", "hour"]).size().unstack(fill_value=0)
    day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    pivot = pivot.reindex([d for d in day_order if d in pivot.index])

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=[str(h) + ":00" for h in pivot.columns],
        y=pivot.index.tolist(),
        colorscale=[[0,"#0d1117"],[0.3,"#00e5ff"],[0.7,"#ff6d00"],[1,"#ff1744"]],
        hovertemplate="Day: %{y}<br>Hour: %{x}<br>Transactions: %{z}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
        font_color="#c9d1d9",
        xaxis=dict(color="#c9d1d9"), yaxis=dict(color="#c9d1d9"),
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Average Amount by AML Pattern")
    if "aml_label" in df:
        pattern_avg = df.groupby("aml_label")["amount"].mean().sort_values(ascending=False).reset_index()
        fig2 = px.bar(pattern_avg, x="aml_label", y="amount",
                      color="amount",
                      color_continuous_scale=["#00e5ff", "#ff1744"],
                      labels={"aml_label": "Pattern", "amount": "Avg Amount ($)"})
        fig2.update_layout(paper_bgcolor="#0d1117", plot_bgcolor="#161b22",
                           font_color="#c9d1d9")
        st.plotly_chart(fig2, use_container_width=True)

with tab2:
    st.subheader("Flagged Transaction Geographic Distribution")
    if "geo_lat" in df and "geo_lon" in df:
        geo_df = df.dropna(subset=["geo_lat", "geo_lon"]).copy()
        geo_df["geo_lat"] = pd.to_numeric(geo_df["geo_lat"], errors="coerce")
        geo_df["geo_lon"] = pd.to_numeric(geo_df["geo_lon"], errors="coerce")
        geo_df = geo_df.dropna(subset=["geo_lat", "geo_lon"])

        if not geo_df.empty:
            fig3 = px.scatter_geo(
                geo_df,
                lat="geo_lat", lon="geo_lon",
                color="composite_score" if "composite_score" in geo_df else "amount",
                size="amount",
                hover_data=["sender_account_id", "amount", "aml_label"],
                color_continuous_scale=["#00e5ff", "#ff1744"],
                projection="natural earth",
            )
            fig3.update_layout(
                paper_bgcolor="#0d1117", geo=dict(bgcolor="#0d1117",
                showland=True, landcolor="#161b22", showocean=True, oceancolor="#0d1117"),
                font_color="#c9d1d9",
            )
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No geo coordinates available in flagged transactions.")
    else:
        st.info("Geo data not available in the current dataset.")
