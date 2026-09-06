"""Transaction Explorer — filterable scored transactions + SHAP breakdown."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from api_client import ApiError, get

st.set_page_config(page_title="Transaction Explorer", page_icon="🔍", layout="wide")
st.title("🔍 Transaction Explorer")

TIER_COLORS = {
    "CRITICAL": "#d62728",
    "HIGH": "#ff7f0e",
    "MEDIUM": "#bcbd22",
    "LOW": "#2ca02c",
}


def color_tier(val: str) -> str:
    color = TIER_COLORS.get(str(val), "#888")
    return f"color: {color}; font-weight: 600"


try:
    rows = get("/transactions", params={"limit": 1000})
except ApiError as exc:
    st.error(str(exc))
    st.stop()

if not rows:
    st.warning("No scored transactions in Redis yet.")
    st.stop()

df = pd.DataFrame(rows)
# Prefer rows joined to CSV (sender present); orphan legacy scores sort last
if "sender_account" in df.columns:
    df["_has_csv"] = df["sender_account"].notna()
    df = df.sort_values(["_has_csv", "composite_score"], ascending=[False, False]).drop(
        columns=["_has_csv"]
    )
for col in ("composite_score", "amount"):
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

tiers = sorted([t for t in df.get("tier", pd.Series(dtype=str)).dropna().unique().tolist()])
patterns = sorted([
    p for p in df.get("pattern_label", pd.Series(dtype=str)).dropna().unique().tolist() if p
])

f1, f2, f3 = st.columns([2, 2, 2])
with f1:
    tier_sel = st.multiselect("Tier", options=tiers, default=tiers)
with f2:
    pattern_sel = st.multiselect("Pattern", options=patterns, default=[])
with f3:
    min_score = st.slider("Min score", 0, 100, 0)

view = df.copy()
if tier_sel:
    view = view[view["tier"].isin(tier_sel)]
if pattern_sel:
    view = view[view["pattern_label"].isin(pattern_sel)]
view = view[view["composite_score"].fillna(0) >= min_score]

display = view.copy()
if "transaction_id" in display.columns:
    display["transaction_id"] = display["transaction_id"].astype(str).str[:8]
if "amount" in display.columns:
    display["amount"] = display["amount"].apply(
        lambda x: f"${x:,.2f}" if pd.notna(x) else "—"
    )

cols = [
    c for c in [
        "transaction_id", "timestamp", "sender_account", "receiver_account",
        "amount", "bank", "pattern_label", "composite_score", "tier",
    ] if c in display.columns
]

st.caption(f"Showing {len(display):,} of {len(df):,} loaded scored transactions")
styled = display[cols].style.map(color_tier, subset=["tier"]) if "tier" in cols else display[cols]
st.dataframe(styled, use_container_width=True, hide_index=True)

st.subheader("SHAP breakdown")
# Prefer full IDs from filtered view for selection
id_map = {
    f"{str(r.get('transaction_id'))[:8]}… score={r.get('composite_score')}": r.get("transaction_id")
    for _, r in view.iterrows()
    if r.get("transaction_id")
}
choice = st.selectbox("Select a transaction", options=list(id_map.keys()) if id_map else [])
if choice:
    full_id = id_map[choice]
    try:
        detail = get(f"/transactions/{full_id}")
    except ApiError as exc:
        st.error(str(exc))
    else:
        shap = detail.get("shap") or []
        if shap:
            sdf = pd.DataFrame(shap)
            if "feature" in sdf.columns and "value" in sdf.columns:
                fig = px.bar(
                    sdf,
                    x="value",
                    y="feature",
                    orientation="h",
                    title=f"Top SHAP features — {str(full_id)[:8]}…",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.json(shap)
        else:
            st.info("No SHAP values cached for this transaction (restart ml_scorer to write shap: keys).")
        st.json({
            "composite_score": detail.get("composite_score"),
            "tier": detail.get("tier"),
            "pattern_label": detail.get("pattern_label"),
        })
