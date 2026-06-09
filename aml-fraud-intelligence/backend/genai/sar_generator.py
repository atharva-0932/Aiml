"""
Structured SAR (Suspicious Activity Report) generator.
Outputs a Pydantic-validated SAR schema ready for FIU submission.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from core.config import settings
from core.logging import get_logger
from genai.prompts import SYSTEM_PROMPT, SAR_DRAFT_TEMPLATE

log = get_logger(__name__)


class SARReport(BaseModel):
    case_id: str
    account_id: str
    investigation_date: str
    risk_tier: str
    subject_information: dict = Field(default_factory=dict)
    suspicious_activity_description: str = ""
    supporting_evidence: list[str] = Field(default_factory=list)
    aml_pattern_identified: str = ""
    recommended_action: Literal[
        "ESCALATE_TO_FIU", "ENHANCED_DUE_DILIGENCE", "CLOSE", "MONITOR"
    ] = "MONITOR"
    confidence_level: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    confidence_justification: str = ""
    generated_by: str = "AML Intelligence Platform v1.0"
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


async def generate_sar(
    account_id: str,
    risk_profile: dict,
    transactions: list[dict],
    notes: str = "",
) -> SARReport:
    """Generate a structured SAR for the given account."""
    import uuid

    evidence_context = _build_evidence_context(transactions, risk_profile)

    llm_sar = await _call_llm_for_sar(account_id, risk_profile, evidence_context, notes)

    return SARReport(
        case_id=str(uuid.uuid4()),
        account_id=account_id,
        investigation_date=datetime.now(timezone.utc).isoformat(),
        risk_tier=risk_profile.get("risk_tier", "HIGH"),
        subject_information={
            "account_id": account_id,
            "composite_score": risk_profile.get("composite_score"),
            "triggered_rules": risk_profile.get("triggered_rules", []),
        },
        suspicious_activity_description=llm_sar.get(
            "suspicious_activity_description",
            f"Account flagged with risk score {risk_profile.get('composite_score', 0):.1f}/100. "
            f"Patterns: {', '.join(risk_profile.get('triggered_rules', []))}.",
        ),
        supporting_evidence=llm_sar.get(
            "supporting_evidence",
            [f"Transaction {t['id']}: ${t.get('amount', 0):,.2f}" for t in transactions[:10]],
        ),
        aml_pattern_identified=llm_sar.get(
            "aml_pattern_identified",
            _infer_pattern(risk_profile),
        ),
        recommended_action=llm_sar.get("recommended_action", "ESCALATE_TO_FIU"),
        confidence_level=llm_sar.get("confidence_level", "HIGH"),
        confidence_justification=llm_sar.get(
            "confidence_justification",
            f"Composite score {risk_profile.get('composite_score', 0):.1f}/100 with "
            f"{len(risk_profile.get('triggered_rules', []))} rules triggered.",
        ),
    )


async def _call_llm_for_sar(
    account_id: str, risk_profile: dict, evidence_context: str, notes: str
) -> dict:
    try:
        from genai.copilot import _get_llm
        from langchain_core.messages import SystemMessage, HumanMessage

        llm = _get_llm()
        if llm is None:
            return {}

        prompt = SAR_DRAFT_TEMPLATE.format(
            account_id=account_id,
            investigation_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            risk_tier=risk_profile.get("risk_tier", "HIGH"),
            evidence_context=evidence_context,
            notes=notes or "No additional notes.",
        )

        response = await llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        text = response.content
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception as exc:
        log.warning("LLM SAR generation failed — using rule-based fallback", error=str(exc))
    return {}


def _build_evidence_context(transactions: list[dict], risk: dict) -> str:
    lines = [f"Risk Score: {risk.get('composite_score', 0):.1f}/100"]
    lines.append(f"Triggered Rules: {', '.join(risk.get('triggered_rules', []))}")
    lines.append("\nRecent Flagged Transactions:")
    for tx in transactions[:10]:
        lines.append(
            f"  [{tx.get('timestamp', 'N/A')[:10]}] "
            f"${tx.get('amount', 0):,.2f} | "
            f"{tx.get('transaction_type', '?')} | "
            f"Pattern: {tx.get('aml_label', 'unknown')}"
        )
    return "\n".join(lines)


def _infer_pattern(risk: dict) -> str:
    rules = set(risk.get("triggered_rules", []))
    if "circular_flow" in rules:
        return "Circular Fund Transfer (Integration Phase)"
    if "deep_layering" in rules:
        return "Transaction Layering"
    if "structuring_pattern" in rules:
        return "Currency Transaction Report Structuring (Smurfing)"
    if "mule_pattern" in rules:
        return "Mule Account Activity"
    if "dormant_activation" in rules:
        return "Dormant Account Reactivation"
    if "velocity_1h_breach" in rules or "velocity_24h_breach" in rules:
        return "Rapid Transaction Velocity Anomaly"
    return "Suspicious Financial Activity"
