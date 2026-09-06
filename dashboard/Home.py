"""
AML Fraud Intelligence — Overview (Home).

Run: streamlit run dashboard/Home.py --server.port 8501
"""
from __future__ import annotations

import time
from collections import Counter, defaultdict

import pandas as pd
import plotly.express as px
import streamlit as st

from api_client import ApiError, get

st.set_page_config(
    page_title="AML Overview",
    page_icon="🔐",
    layout="wide",
)

st.title("🔐 AML Fraud Intelligence")
st.caption("Overview — live alerts from FastAPI / Redis")


def load_overview():
    health = get("/health")
    alerts = get("/alerts", params={"limit": 1000})
    summary = get("/alerts/summary")
    return health, alerts, summary


try:
    health, alerts, summary = load_overview()
except ApiError as exc:
    st.error(str(exc))
    st.stop()

total_tx = int(health.get("transactions_loaded") or 0)
# Alerts = composite_score > 70 (API already filters); critical = score > 90
total_alerts = int(summary.get("total_alerts") or len(alerts))
critical = sum(1 for a in alerts if float(a.get("composite_score") or 0) > 90)
flagged_rate = (100.0 * total_alerts / total_tx) if total_tx else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Transactions", f"{total_tx:,}")
c2.metric("Total Alerts", f"{total_alerts:,}")
c3.metric("Critical Alerts", f"{critical:,}")
c4.metric("Flagged Rate", f"{flagged_rate:.2f}%")

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Pattern distribution")
    by_pattern = summary.get("by_pattern") or {}
    if not by_pattern and alerts:
        by_pattern = dict(Counter((a.get("pattern") or "unknown") for a in alerts))
    if by_pattern:
        pdf = pd.DataFrame(
            [{"pattern": k, "count": v} for k, v in by_pattern.items()]
        )
        fig = px.pie(pdf, names="pattern", values="count", hole=0.45)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No alerts yet. Restart ml_scorer + producer to populate Redis alert: keys.")

with right:
    st.subheader("Top 10 high-risk accounts")
    if alerts:
        acct = defaultdict(lambda: {"alert_count": 0, "max_score": 0.0, "patterns": set()})
        for a in alerts:
            aid = a.get("sender_account") or "unknown"
            score = float(a.get("composite_score") or 0)
            acct[aid]["alert_count"] += 1
            acct[aid]["max_score"] = max(acct[aid]["max_score"], score)
            if a.get("pattern"):
                acct[aid]["patterns"].add(a["pattern"])
        rows = []
        for aid, meta in acct.items():
            rows.append({
                "account_id": aid,
                "alert_count": meta["alert_count"],
                "max_score": round(meta["max_score"], 2),
                "patterns": ", ".join(sorted(meta["patterns"])) or "—",
            })
        top = pd.DataFrame(rows).sort_values(
            ["max_score", "alert_count"], ascending=False
        ).head(10)
        st.dataframe(top, use_container_width=True, hide_index=True)
    else:
        st.info("No alert accounts to rank yet.")

st.caption("Auto-refreshing every 30 seconds when enabled…")
auto = st.sidebar.checkbox("Auto-refresh (30s)", value=True)
if auto:
    time.sleep(30)
    st.rerun()
