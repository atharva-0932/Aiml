"""
Prompt templates for the AML investigator copilot.
All prompts use formal financial investigation language.
"""

SYSTEM_PROMPT = """You are an expert AML (Anti-Money Laundering) investigation assistant 
at a Tier-1 financial institution. You assist compliance officers and financial intelligence 
analysts investigate suspicious financial activity.

Your responses must be:
- Precise and evidence-based
- Written in formal financial investigation language
- Referenced to specific transaction IDs, amounts, and timestamps when available
- Compliant with FATF, FinCEN, and FIU reporting standards
- Never speculative without data support

You have access to: transaction records, risk scores, graph analytics results, 
triggered rule names, and SHAP feature importances."""


EXPLAIN_FLAGGING_TEMPLATE = """
Account ID: {account_id}
Composite Risk Score: {composite_score}/100  (Tier: {risk_tier})

Model Scores:
- XGBoost Fraud Probability: {classifier_score:.1%}
- Isolation Forest Anomaly Score: {anomaly_score:.1%}
- Graph Risk Score: {graph_risk_score:.1%}

Triggered Detection Rules: {triggered_rules}

Recent Transactions Summary:
{tx_summary}

Graph Analytics:
- PageRank Score: {pagerank_score:.4f}
- In-Degree: {graph_in_degree} | Out-Degree: {graph_out_degree}
- Cycle Membership: {cycle_membership}
- Max Hop Depth: {hop_depth}

SHAP Feature Contributions (top drivers):
{shap_summary}

Explain in 3 paragraphs why this account was flagged. Reference specific evidence 
from the data above. Use formal AML investigation language suitable for an FIU report.
Structure: (1) Account behaviour summary, (2) Pattern analysis, (3) Risk assessment.
"""

SAR_DRAFT_TEMPLATE = """
Generate a Suspicious Activity Report (SAR) in structured format for FIU submission.

Subject Account: {account_id}
Investigation Date: {investigation_date}
Risk Classification: {risk_tier}
Investigator: Automated AI System v1.0

Evidence:
{evidence_context}

Investigation Notes:
{notes}

Output a complete SAR with these sections:
1. SUBJECT INFORMATION
2. SUSPICIOUS ACTIVITY DESCRIPTION (what, when, how much, pattern type)
3. SUPPORTING EVIDENCE (list transaction IDs, amounts, dates)
4. AML PATTERN IDENTIFIED (structuring / layering / circular / mule / dormant)
5. RECOMMENDED ACTION (ESCALATE_TO_FIU / ENHANCED_DUE_DILIGENCE / CLOSE / MONITOR)
6. CONFIDENCE LEVEL (HIGH / MEDIUM / LOW) with justification

Respond in JSON format matching the SAR schema.
"""

FUND_FLOW_SUMMARY_TEMPLATE = """
Summarise the suspicious fund movement pattern for account {account_id}.

Transaction Chain:
{chain_data}

Graph Path:
{graph_path}

Provide:
1. A plain-English narrative of how funds moved
2. The estimated total amount laundered
3. The suspected typology (placement/layering/integration phase)
4. Key red flags identified
5. Jurisdictions involved
"""

INVESTIGATOR_QA_TEMPLATE = """
{system_context}

Question from investigator: {question}

Relevant context retrieved:
{retrieved_context}

Provide a concise, factual answer. If the answer requires information not in the 
context, say so explicitly rather than speculating.
"""
