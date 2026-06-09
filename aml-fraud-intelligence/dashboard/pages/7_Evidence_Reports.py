"""Evidence Report Generator — download PDF investigation reports."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

st.set_page_config(page_title="Evidence Reports | AML", layout="wide", page_icon="📄")
st.markdown("""<style>
[data-testid="stAppViewContainer"]{background:#0d1117}
[data-testid="stSidebar"]{background:#161b22}
h1,h2,h3,p,label,span{color:#c9d1d9!important}
.stButton button{background:#00e5ff;color:#0d1117;font-weight:700;border:none;border-radius:6px}
</style>""", unsafe_allow_html=True)

st.title("📄 Evidence Report Generator")
st.markdown("*Generate professional PDF investigation reports for flagged accounts.*")
st.markdown("---")

from dashboard.utils.api_client import get_flagged_transactions, generate_report, generate_sar

@st.cache_data(ttl=30)
def load_accounts():
    txns = get_flagged_transactions(limit=200)
    if not txns:
        return []
    return list({t.get("sender_account_id") for t in txns if t.get("sender_account_id")})

accounts = load_accounts()

col1, col2 = st.columns([2, 1])
with col1:
    if accounts:
        account_id = st.selectbox("Select Account", options=accounts)
    else:
        account_id = st.text_input("Account ID")
with col2:
    investigator = st.text_input("Investigator Name", value="AML Analyst")

st.markdown("---")

gen_col1, gen_col2 = st.columns(2)

with gen_col1:
    st.subheader("📋 PDF Investigation Report")
    st.markdown("""
    Includes:
    - Risk score breakdown (XGBoost, Isolation Forest, Graph)
    - Transaction evidence table
    - Triggered detection rules
    - AI-generated investigation summary
    - Recommended action
    """)
    if st.button("🔽 Generate & Download PDF", use_container_width=True) and account_id:
        with st.spinner("Generating PDF report (AI summary + WeasyPrint)..."):
            try:
                pdf_bytes = generate_report(account_id, investigator)
                st.success("Report generated!")
                st.download_button(
                    label="📥 Download PDF Report",
                    data=pdf_bytes,
                    file_name=f"aml_report_{account_id[:8]}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"Report generation failed: {e}\n\nEnsure WeasyPrint is installed and backend is running.")

with gen_col2:
    st.subheader("📑 SAR Draft (JSON)")
    st.markdown("""
    Generates:
    - Subject information
    - Suspicious activity description
    - Supporting evidence list
    - AML pattern identification
    - Recommended FIU action
    - Confidence level + justification
    """)
    sar_notes = st.text_area("Investigation notes", height=80, key="report_notes")
    if st.button("🤖 Generate SAR Draft", use_container_width=True) and account_id:
        with st.spinner("Generating SAR via AI..."):
            try:
                sar = generate_sar(account_id, sar_notes)
                st.success("SAR generated")
                st.json(sar)

                import json
                sar_str = json.dumps(sar, indent=2)
                st.download_button(
                    label="📥 Download SAR JSON",
                    data=sar_str,
                    file_name=f"sar_{account_id[:8]}.json",
                    mime="application/json",
                )
            except Exception as e:
                st.error(f"SAR generation failed: {e}")

st.markdown("---")
st.markdown("### Recent Reports")
st.info("Generated reports are saved to `data/reports/`. Check the container volume or local data directory.")
