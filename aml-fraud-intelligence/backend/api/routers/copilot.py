"""
GenAI Copilot API.
POST /copilot/chat                  — streamed investigator Q&A
POST /copilot/explain/{account_id} — explain why account was flagged
POST /copilot/sar/{account_id}     — generate SAR draft
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.models.account import AccountRiskProfile
from core.security import verify_api_key
from db.redis.cache import get_risk_profile
from db.snowflake.session import run_sync, execute_query
from genai.copilot import explain_account, chat_stream, summarise_fund_flow
from genai.sar_generator import generate_sar

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/chat")
async def copilot_chat(
    body: dict,
    _: str = Depends(verify_api_key),
):
    """
    Streaming RAG-powered investigator Q&A.
    Returns Server-Sent Events stream.
    """
    question = body.get("question", "")
    account_id = body.get("account_id")

    async def stream():
        async for chunk in chat_stream(question, account_id=account_id):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/explain/{account_id}")
async def explain_flagging(account_id: str, _: str = Depends(verify_api_key)):
    """Explain why an account was flagged in formal AML language."""
    risk_profile = await get_risk_profile(account_id) or {}

    # Fetch recent transactions summary from Snowflake
    sql = """
    SELECT id, amount, transaction_type, channel, timestamp, aml_label
    FROM transactions
    WHERE sender_account_id = :account_id OR receiver_account_id = :account_id
    ORDER BY timestamp DESC
    LIMIT 10
    """
    txns = await run_sync(execute_query, sql, {"account_id": account_id})
    tx_summary = "\n".join(
        f"[{t.get('timestamp', '')[:10]}] ${t.get('amount', 0):,.2f} {t.get('transaction_type', '')} "
        f"({t.get('aml_label') or 'normal'})"
        for t in txns
    )

    explanation = await explain_account(account_id, risk_profile, tx_summary)
    return {"account_id": account_id, "explanation": explanation}


@router.post("/sar/{account_id}")
async def generate_sar_report(
    account_id: str,
    body: dict = {},
    _: str = Depends(verify_api_key),
):
    """Generate a Suspicious Activity Report (SAR) draft for FIU submission."""
    risk_profile = await get_risk_profile(account_id) or {}

    sql = """
    SELECT * FROM transactions
    WHERE sender_account_id = :account_id AND is_flagged = TRUE
    ORDER BY timestamp DESC LIMIT 20
    """
    transactions = await run_sync(execute_query, sql, {"account_id": account_id})
    notes = body.get("notes", "")

    sar = await generate_sar(account_id, risk_profile, transactions, notes=notes)
    return sar.model_dump()
