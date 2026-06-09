"""
Report generation API.
POST /reports/generate — generate PDF evidence report and return as download
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from core.security import verify_api_key
from db.redis.cache import get_risk_profile
from db.snowflake.session import run_sync, execute_query
from genai.copilot import explain_account
from reports.pdf_generator import generate_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate")
async def generate_evidence_report(
    body: dict,
    _: str = Depends(verify_api_key),
):
    """
    Generate a PDF investigation report for an account.
    Returns binary PDF for download.
    """
    account_id = body.get("account_id", "")
    investigator = body.get("investigator_name", "AML Analyst")

    risk_profile = await get_risk_profile(account_id) or {
        "composite_score": 0, "risk_tier": "UNKNOWN",
        "triggered_rules": [], "anomaly_score": 0,
        "classifier_score": 0, "graph_risk_score": 0,
    }

    sql = """
    SELECT id, sender_account_id, receiver_account_id, amount, currency,
           transaction_type, channel, timestamp, is_flagged, aml_label
    FROM transactions
    WHERE sender_account_id = :account_id OR receiver_account_id = :account_id
    ORDER BY timestamp DESC LIMIT 30
    """
    transactions = await run_sync(execute_query, sql, {"account_id": account_id})

    # AI summary (best-effort — returns fallback if LLM not configured)
    tx_summary = "\n".join(
        f"${t.get('amount', 0):,.2f} {t.get('transaction_type', '')} on {str(t.get('timestamp', ''))[:10]}"
        for t in transactions[:5]
    )
    ai_summary = await explain_account(account_id, risk_profile, tx_summary)

    pdf_bytes = generate_report(
        account_id=account_id,
        risk_profile=risk_profile,
        transactions=transactions,
        ai_summary=ai_summary,
        investigator_name=investigator,
    )

    filename = f"aml_report_{account_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
