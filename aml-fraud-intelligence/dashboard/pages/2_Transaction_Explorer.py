"""Transaction Explorer — searchable, filterable transaction table."""
import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

st.set_page_config(page_title="Transaction Explorer | AML", layout="wide", page_icon="🔍")
st.markdown("""<style>
[data-testid="stAppViewContainer"]{background:#0d1117}
[data-testid="stSidebar"]{background:#161b22}
h1,h2,h3,p,label,span{color:#c9d1d9!important}
.stDataFrame{background:#161b22}
</style>""", unsafe_allow_html=True)

st.title("🔍 Transaction Explorer")
st.markdown("---")

from dashboard.utils.api_client import get_flagged_transactions, get_risk_profile

@st.cache_data(ttl=60)
def load_data():
    return get_flagged_transactions(limit=500)

data = load_data()
df = pd.DataFrame(data) if data else pd.DataFrame()

if df.empty:
    st.warning("No flagged transactions available. Run the data seeder and wait for ML scoring.")
    st.stop()

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

# ── Filters ───────────────────────────────────────────────────────────────────
st.markdown("### Filters")
fcol1, fcol2, fcol3, fcol4 = st.columns(4)

with fcol1:
    patterns = ["All"] + sorted(df["aml_label"].dropna().unique().tolist())
    pattern_filter = st.selectbox("AML Pattern", patterns)

with fcol2:
    tiers = ["All"] + sorted(df["risk_tier"].dropna().unique().tolist()) if "risk_tier" in df else ["All"]
    tier_filter = st.selectbox("Risk Tier", tiers)

with fcol3:
    min_amount = float(df["amount"].min() or 0)
    max_amount = float(df["amount"].max() or 1_000_000)
    amount_range = st.slider("Amount Range ($)", min_amount, max_amount,
                             (min_amount, max_amount), format="$%.0f")

with fcol4:
    search = st.text_input("Search Account ID", "")

# Apply filters
mask = pd.Series([True] * len(df))
if pattern_filter != "All":
    mask &= df["aml_label"] == pattern_filter
if tier_filter != "All" and "risk_tier" in df:
    mask &= df["risk_tier"] == tier_filter
mask &= (df["amount"] >= amount_range[0]) & (df["amount"] <= amount_range[1])
if search:
    mask &= (
        df["sender_account_id"].str.contains(search, na=False)
        | df["receiver_account_id"].str.contains(search, na=False)
    )

filtered = df[mask]
st.markdown(f"**{len(filtered):,}** transactions matching filters")
st.markdown("---")

# ── Table ─────────────────────────────────────────────────────────────────────
display_cols = [c for c in [
    "timestamp", "sender_account_id", "receiver_account_id",
    "amount", "currency", "transaction_type", "aml_label",
    "composite_score", "risk_tier",
] if c in filtered.columns]

st.dataframe(
    filtered[display_cols].sort_values("timestamp", ascending=False),
    use_container_width=True,
    height=450,
)

# ── Drill-down ────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Account Risk Profile Drill-down")
selected_account = st.text_input("Enter Account ID to inspect")
if selected_account:
    with st.spinner("Fetching risk profile (Redis-first)..."):
        try:
            profile = get_risk_profile(selected_account)
            col1, col2, col3 = st.columns(3)
            col1.metric("Composite Score", f"{profile.get('composite_score', 0):.1f}/100")
            col2.metric("Risk Tier", profile.get("risk_tier", "UNKNOWN"))
            col3.metric("Cached", "✅ Redis" if profile.get("cached") else "🔄 Snowflake")
            st.json(profile)
        except Exception as e:
            st.error(f"Could not fetch profile: {e}")
