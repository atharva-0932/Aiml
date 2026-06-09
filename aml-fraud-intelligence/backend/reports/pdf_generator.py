"""
PDF evidence report generator using WeasyPrint + Jinja2.
Produces professional investigation reports with risk scores,
transaction evidence, and AI-generated summaries.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from core.logging import get_logger

log = get_logger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "reports"


def _render_template(template_name: str, context: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template(template_name)
    return template.render(**context)


def generate_report(
    account_id: str,
    risk_profile: dict,
    transactions: list[dict],
    ai_summary: str = "",
    sar_data: dict | None = None,
    investigator_name: str = "AML Analyst",
    graph_image_b64: str | None = None,
) -> bytes:
    """
    Generate a PDF investigation report.
    Returns raw PDF bytes ready for download.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    context = {
        "case_id": f"CASE-{account_id[:8].upper()}",
        "account_id": account_id,
        "investigator_name": investigator_name,
        "report_date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "risk_tier": risk_profile.get("risk_tier", "HIGH"),
        "composite_score": round(risk_profile.get("composite_score", 0), 1),
        "anomaly_score": round(risk_profile.get("anomaly_score", 0) * 100, 1),
        "classifier_score": round(risk_profile.get("classifier_score", 0) * 100, 1),
        "graph_risk_score": round(risk_profile.get("graph_risk_score", 0) * 100, 1),
        "triggered_rules": risk_profile.get("triggered_rules", []),
        "transactions": transactions[:20],  # cap at 20 rows
        "ai_summary": ai_summary,
        "sar_data": sar_data or {},
        "graph_image_b64": graph_image_b64 or "",
        "risk_color": _risk_color(risk_profile.get("risk_tier", "LOW")),
    }

    html = _render_template("report.html", context)

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf()
        log.info("PDF report generated", account_id=account_id, size_kb=len(pdf_bytes) // 1024)
        return pdf_bytes
    except ImportError:
        log.warning("WeasyPrint not installed — returning HTML bytes")
        return html.encode("utf-8")
    except Exception as exc:
        log.error("PDF generation failed", error=str(exc))
        return html.encode("utf-8")


def _risk_color(tier: str) -> str:
    return {
        "CRITICAL": "#ff1744",
        "HIGH": "#ff6d00",
        "MEDIUM": "#ffd600",
        "LOW": "#00c853",
    }.get(tier, "#546e7a")
