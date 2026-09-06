"""Graph Investigation — account risk card + PyVis 2-hop network."""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from api_client import ApiError, get

st.set_page_config(page_title="Graph Investigation", page_icon="🕸️", layout="wide")
st.title("🕸️ Graph Investigation")
st.caption("2-hop Neo4j neighborhood via FastAPI")


def risk_color(score) -> str:
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "#4b8bff"
    if s > 70:
        return "#d62728"  # HIGH / CRITICAL
    if s >= 30:
        return "#ff7f0e"  # MEDIUM
    return "#2ca02c"  # LOW


account_id = st.text_input("Account ID", placeholder="Paste an account id from Explorer")
submit = st.button("Investigate", type="primary")

if not submit:
    st.info("Enter an account ID and click Investigate.")
    st.stop()

if not account_id.strip():
    st.error("Account ID is required.")
    st.stop()

account_id = account_id.strip()

try:
    risk = get(f"/graph/account/{account_id}")
    neighbors = get(f"/graph/neighbors/{account_id}")
except ApiError as exc:
    st.error(str(exc))
    st.stop()

st.subheader("Graph risk summary")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Graph risk", f"{float(risk.get('graph_risk') or 0):.1f}")
m2.metric("Cycles", risk.get("cycle_count", 0))
m3.metric("Mule", "Yes" if risk.get("is_mule") else "No")
m4.metric("PageRank", f"{float(risk.get('pagerank') or 0):.4f}")

flags = risk.get("flags") or []
if flags:
    st.write("Flags:", ", ".join(f"`{f}`" for f in flags))
else:
    st.write("Flags: none")

st.subheader("2-hop network")
nodes = neighbors.get("nodes") or []
edges = neighbors.get("edges") or []

if not nodes:
    st.warning("No graph neighbors returned for this account.")
    st.stop()

# Cap size for PyVis — full 2-hop neighborhoods can be thousands of nodes
MAX_NODES = 60
if len(nodes) > MAX_NODES:
    # Keep focal account + highest-risk neighbors
    focal = [n for n in nodes if n.get("id") == account_id]
    others = sorted(
        [n for n in nodes if n.get("id") != account_id],
        key=lambda n: float(n.get("risk_score") or 0),
        reverse=True,
    )
    nodes = (focal + others)[:MAX_NODES]
    keep = {n["id"] for n in nodes}
    edges = [e for e in edges if e.get("source") in keep and e.get("target") in keep]
    st.caption(f"Showing top {len(nodes)} nodes by risk (API returned a larger neighborhood).")

net = Network(height="600px", width="100%", directed=True, bgcolor="#0e1117", font_color="white")
net.barnes_hut()
for node in nodes:
    nid = node["id"]
    color = risk_color(node.get("risk_score"))
    label = str(nid)[:8]
    title = f"{nid}\\nrisk={node.get('risk_score')}"
    size = 28 if nid == account_id else 18
    net.add_node(nid, label=label, color=color, title=title, size=size)

for edge in edges:
    src, tgt = edge.get("source"), edge.get("target")
    if not src or not tgt:
        continue
    amount = edge.get("amount")
    try:
        edge_label = f"${float(amount):,.0f}" if amount is not None else ""
    except (TypeError, ValueError):
        edge_label = ""
    net.add_edge(src, tgt, title=edge_label, label=edge_label)

with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
    net.write_html(tmp.name, notebook=False)
    html = Path(tmp.name).read_text(encoding="utf-8")

components.html(html, height=620, scrolling=True)
st.caption(f"{len(nodes)} nodes · {len(edges)} edges")
