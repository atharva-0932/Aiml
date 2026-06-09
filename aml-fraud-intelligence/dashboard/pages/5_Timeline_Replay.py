"""Timeline Replay — animated Plotly fund flow timeline."""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

st.set_page_config(page_title="Timeline Replay | AML", layout="wide", page_icon="⏱️")
st.markdown("""<style>
[data-testid="stAppViewContainer"]{background:#0d1117}
[data-testid="stSidebar"]{background:#161b22}
h1,h2,h3,p,label,span{color:#c9d1d9!important}
</style>""", unsafe_allow_html=True)

st.title("⏱️ Timeline Replay")
st.markdown("*Replay how suspicious funds moved through accounts over time.*")
st.markdown("---")

from dashboard.utils.api_client import get_flagged_transactions

@st.cache_data(ttl=60)
def load_data():
    return get_flagged_transactions(limit=500)

data = load_data()
df = pd.DataFrame(data) if data else pd.DataFrame()

if df.empty:
    st.warning("No flagged transactions available.")
    st.stop()

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
df = df.sort_values("timestamp")

col1, col2 = st.columns([2, 1])
with col1:
    pattern_opts = ["All"] + sorted(df["aml_label"].dropna().unique().tolist())
    selected_pattern = st.selectbox("Filter by AML Pattern", pattern_opts)
with col2:
    top_n = st.slider("Show top N transactions", 20, 200, 50)

plot_df = df.copy()
if selected_pattern != "All":
    plot_df = df[df["aml_label"] == selected_pattern]
plot_df = plot_df.head(top_n)

# ── Animated scatter timeline ─────────────────────────────────────────────────
st.subheader("Animated Fund Flow Timeline")
if not plot_df.empty:
    plot_df["date"] = plot_df["timestamp"].dt.date.astype(str)
    plot_df["sender_short"] = plot_df["sender_account_id"].str[:8]

    fig = px.scatter(
        plot_df,
        x="timestamp",
        y="amount",
        color="aml_label",
        size="amount",
        hover_data=["sender_account_id", "receiver_account_id", "transaction_type"],
        animation_frame="date",
        range_y=[0, plot_df["amount"].quantile(0.98)],
        color_discrete_sequence=px.colors.qualitative.Set2,
        labels={"timestamp": "Time", "amount": "Amount ($)", "aml_label": "Pattern"},
    )
    fig.update_layout(
        paper_bgcolor="#0d1117", plot_bgcolor="#161b22", font_color="#c9d1d9",
        xaxis=dict(color="#c9d1d9"), yaxis=dict(color="#c9d1d9"),
        height=480,
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Cumulative volume ─────────────────────────────────────────────────────────
st.subheader("Cumulative Suspicious Volume by Pattern")
if "aml_label" in df:
    df_sorted = df.sort_values("timestamp")
    df_sorted["cum_amount"] = df_sorted.groupby("aml_label")["amount"].cumsum()
    fig2 = px.line(df_sorted, x="timestamp", y="cum_amount", color="aml_label",
                   color_discrete_sequence=px.colors.qualitative.Set2)
    fig2.update_layout(paper_bgcolor="#0d1117", plot_bgcolor="#161b22",
                       font_color="#c9d1d9", height=350)
    st.plotly_chart(fig2, use_container_width=True)
