"""Copilot Chat — LangChain RAG investigator assistant."""
import streamlit as st
import httpx, os, json
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

st.set_page_config(page_title="Copilot | AML", layout="wide", page_icon="🤖")
st.markdown("""<style>
[data-testid="stAppViewContainer"]{background:#0d1117}
[data-testid="stSidebar"]{background:#161b22}
h1,h2,h3,p,label,span{color:#c9d1d9!important}
.stTextArea textarea{background:#161b22!important;color:#c9d1d9!important}
.chat-msg{padding:10px 14px;border-radius:8px;margin:6px 0;line-height:1.6}
.user-msg{background:#21262d;border-left:3px solid #00e5ff}
.bot-msg{background:#161b22;border-left:3px solid #ff6d00}
</style>""", unsafe_allow_html=True)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev-key")
HEADERS = {"X-API-Key": API_KEY}

st.title("🤖 AI Investigator Copilot")
st.markdown("*Powered by LangChain + RAG. Ask anything about flagged accounts and transactions.*")
st.markdown("---")

# ── Example queries ───────────────────────────────────────────────────────────
with st.expander("💡 Example queries"):
    st.markdown("""
    - "Why was account `{account_id}` flagged?"
    - "Explain the suspicious fund flow for this account."
    - "Summarise all linked accounts and transactions."
    - "Generate an FIU investigation summary."
    - "What is the layering pattern for account X?"
    """)

col1, col2 = st.columns([3, 1])
with col1:
    account_context = st.text_input("Account ID (optional — adds context)", key="copilot_acct")
with col2:
    st.markdown("")
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []
        st.rerun()

# ── Chat history ──────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for msg in st.session_state.chat_history:
    role_class = "user-msg" if msg["role"] == "user" else "bot-msg"
    icon = "🧑" if msg["role"] == "user" else "🤖"
    st.markdown(
        f'<div class="chat-msg {role_class}">{icon} {msg["content"]}</div>',
        unsafe_allow_html=True,
    )

# ── Input ─────────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask the AML investigator copilot...")
if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    st.markdown(
        f'<div class="chat-msg user-msg">🧑 {user_input}</div>',
        unsafe_allow_html=True,
    )

    response_placeholder = st.empty()
    full_response = ""

    try:
        with httpx.Client(base_url=BACKEND_URL, headers=HEADERS, timeout=60.0) as client:
            with client.stream(
                "POST", "/api/v1/copilot/chat",
                json={"question": user_input, "account_id": account_context or None},
            ) as resp:
                for line in resp.iter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk == "[DONE]":
                            break
                        full_response += chunk
                        response_placeholder.markdown(
                            f'<div class="chat-msg bot-msg">🤖 {full_response}▌</div>',
                            unsafe_allow_html=True,
                        )
        response_placeholder.markdown(
            f'<div class="chat-msg bot-msg">🤖 {full_response}</div>',
            unsafe_allow_html=True,
        )
        st.session_state.chat_history.append({"role": "assistant", "content": full_response})
    except Exception as e:
        err_msg = f"Copilot unavailable: {e}. Ensure the backend is running and GEMINI_API_KEY is set."
        response_placeholder.error(err_msg)
        st.session_state.chat_history.append({"role": "assistant", "content": err_msg})

# ── SAR Generation ────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("📄 Generate SAR Draft")
sar_account = st.text_input("Account ID for SAR", key="sar_acct")
sar_notes = st.text_area("Investigation notes (optional)")
if st.button("Generate SAR") and sar_account:
    with st.spinner("Generating Suspicious Activity Report..."):
        try:
            from dashboard.utils.api_client import generate_sar
            sar = generate_sar(sar_account, sar_notes)
            st.success("SAR generated")
            st.json(sar)
        except Exception as e:
            st.error(f"SAR generation failed: {e}")
