"""
=============================================================================
AGENT 2: SUPERVISOR + WORKER MULTI-AGENT SYSTEM - Bank Loan Processing
=============================================================================
Architecture : LangGraph Supervisor → Worker (Swarm) Pattern
Workers      : DocumentWorker, CreditWorker, RiskWorker, ComplianceWorker,
               UnderwritingWorker, DecisionWorker
Features     : RAG, MCP, Guardrails, Few-Shot Prompting, Parallel Execution,
               State Machine, Human-in-the-Loop escalation, Fallbacks
=============================================================================
"""

import os
import sys
import json
import logging
import operator
import traceback
from typing import Annotated, Any, Literal, Optional, Sequence, TypedDict
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from functools import partial

# LangGraph
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent as lg_react_agent

# LangChain
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import (
    BaseMessage, HumanMessage, AIMessage, SystemMessage
)
from langchain_core.tools import tool
from langchain_community.vectorstores import PGVector

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("supervisor_agent")

# ── Environment ──────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")
POSTGRES_URL     = os.getenv("POSTGRES_URL",
                             "postgresql+psycopg2://postgres:postgres@localhost:5432/loandb")

if os.getenv("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"]    = os.getenv("LANGCHAIN_API_KEY")
    os.environ["LANGCHAIN_PROJECT"]    = "bank-loan-supervisor-agent"


# =============================================================================
# SHARED STATE  (flows through the entire graph)
# =============================================================================

class LoanApplicationState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────────
    applicant_id:          str
    applicant_name:        str
    loan_amount:           float
    loan_purpose:          str
    annual_income:         float
    property_value:        float
    employment_type:       str
    years_employed:        float

    # ── Worker outputs (accumulated) ───────────────────────────────────────
    messages:              Annotated[list[BaseMessage], operator.add]
    worker_results:        dict[str, Any]

    # ── Supervisor routing ─────────────────────────────────────────────────
    next_worker:           str
    completed_workers:     list[str]
    supervisor_notes:      list[str]

    # ── Escalation & guardrails ────────────────────────────────────────────
    requires_human_review: bool
    guardrail_flags:       list[str]
    risk_level:            str          # LOW / MEDIUM / HIGH / CRITICAL

    # ── Final decision ─────────────────────────────────────────────────────
    final_decision:        str
    decision_reason:       str
    conditions:            list[str]
    approved_amount:       float
    interest_rate:         float
    monthly_payment:       float
    processing_complete:   bool


# =============================================================================
# GUARDRAILS
# =============================================================================

class ProductionGuardrails:
    HARD_LIMITS = {
        "max_loan_amount": 10_000_000,
        "min_loan_amount": 1_000,
        "max_dti":          0.50,
        "min_credit_score": 300,
        "max_fraud_risk":   100,
    }

    BLOCKED_INTENTS = [
        "bypass", "override", "ignore policy", "skip check",
        "disable", "hack", "inject",
    ]

    @classmethod
    def screen_state(cls, state: LoanApplicationState) -> list[str]:
        flags = []
        if state["loan_amount"] > cls.HARD_LIMITS["max_loan_amount"]:
            flags.append(f"AMOUNT_EXCEEDS_MAX: ${state['loan_amount']:,.2f}")
        if state["loan_amount"] < cls.HARD_LIMITS["min_loan_amount"]:
            flags.append("AMOUNT_BELOW_MIN")
        if state["annual_income"] <= 0:
            flags.append("INVALID_INCOME")
        return flags

    @classmethod
    def post_decision_check(cls, decision: str, amount: float, credit_score: int) -> list[str]:
        flags = []
        if decision == "APPROVED" and credit_score < 580:
            flags.append("APPROVAL_BELOW_MIN_CREDIT: manual review required")
        if decision == "APPROVED" and amount > 5_000_000:
            flags.append("LARGE_LOAN_APPROVAL: senior underwriter sign-off required")
        return flags


# =============================================================================
# TOOLS PER WORKER
# =============================================================================

# ── Document Worker Tools ─────────────────────────────────────────────────────

@tool
def extract_document_data(applicant_id: str, doc_type: str) -> str:
    """Extract and validate data from uploaded loan documents (W2, pay stubs, bank statements)."""
    logger.info(f"[DocumentWorker] Extracting {doc_type} for {applicant_id}")
    # Production: integrate with document parser / OCR pipeline
    docs_mock = {
        "W2":           {"employer": "Tech Corp", "wages": 95_000, "year": 2023, "verified": True},
        "BANK_STMT":    {"avg_balance": 15_000, "deposits": 8_000, "months": 3, "verified": True},
        "PAY_STUB":     {"gross_monthly": 7_917, "ytd": 71_250, "verified": True},
        "TAX_RETURN":   {"agi": 88_000, "self_employed": False, "verified": True},
    }
    result = docs_mock.get(doc_type, {"error": f"Document type {doc_type} not found"})
    return json.dumps(result)


@tool
def verify_identity(applicant_id: str, id_document_type: str) -> str:
    """KYC identity verification against government ID database."""
    logger.info(f"[DocumentWorker] Identity verification for {applicant_id}")
    return json.dumps({
        "identity_verified":  True,
        "id_type":           id_document_type,
        "watchlist_match":    False,
        "pep_match":          False,       # Politically Exposed Person
        "sanctions_match":    False,
        "kyc_passed":         True,
        "timestamp":          datetime.now().isoformat(),
    })


# ── Credit Worker Tools ───────────────────────────────────────────────────────

@tool
def pull_credit_report(applicant_id: str, bureau: str = "experian") -> str:
    """Pull full credit report from Experian/Equifax/TransUnion via MCP."""
    logger.info(f"[CreditWorker] Pulling credit from {bureau} for {applicant_id}")
    reports = {
        "APP001": {"score": 750, "utilization": 0.18, "open_accounts": 6,
                   "derogatory": 0, "inquiries_12mo": 2, "oldest_account_years": 9},
        "APP002": {"score": 638, "utilization": 0.62, "open_accounts": 4,
                   "derogatory": 1, "inquiries_12mo": 5, "oldest_account_years": 4},
        "APP003": {"score": 495, "utilization": 0.89, "open_accounts": 2,
                   "derogatory": 3, "inquiries_12mo": 8, "oldest_account_years": 2},
    }
    data = reports.get(applicant_id, {"score": 700, "utilization": 0.30,
                                       "open_accounts": 5, "derogatory": 0,
                                       "inquiries_12mo": 1, "oldest_account_years": 6})
    return json.dumps(data)


@tool
def analyze_credit_history(credit_data_json: str) -> str:
    """Analyze credit report and produce risk tier classification."""
    try:
        data = json.loads(credit_data_json)
        score = data.get("score", 0)
        tier  = ("PRIME" if score >= 740 else
                 "NEAR_PRIME" if score >= 670 else
                 "SUBPRIME" if score >= 580 else "DEEP_SUBPRIME")
        eligible = score >= 580
        return json.dumps({
            "credit_tier":         tier,
            "eligible":            eligible,
            "recommended_rate_adj": 0.0 if tier == "PRIME" else
                                    0.5 if tier == "NEAR_PRIME" else
                                    1.5 if tier == "SUBPRIME" else 3.0,
            "score": score,
        })
    except Exception as e:
        return json.dumps({"error": str(e), "eligible": False})


# ── Risk Worker Tools ─────────────────────────────────────────────────────────

@tool
def run_fraud_detection(applicant_id: str, loan_amount: float, annual_income: float) -> str:
    """ML-based fraud detection scoring (velocity checks, synthetic ID detection, etc.)."""
    logger.info(f"[RiskWorker] Fraud detection: {applicant_id}")
    income_to_loan = loan_amount / max(annual_income, 1)
    risk = (10 if income_to_loan < 3 else 25 if income_to_loan < 5 else 55)
    return json.dumps({
        "fraud_score":       risk,
        "risk_band":         "LOW" if risk < 30 else "MEDIUM" if risk < 60 else "HIGH",
        "synthetic_id_flag": False,
        "velocity_flag":     False,
        "recommendation":    "AUTO_APPROVE" if risk < 30 else
                             "MANUAL_REVIEW" if risk < 60 else "DECLINE",
    })


@tool
def calculate_dti_ltv(
    annual_income: float, loan_amount: float,
    property_value: float, monthly_obligations: float = 500.0,
) -> str:
    """Calculate Debt-to-Income and Loan-to-Value ratios for risk assessment."""
    monthly_income   = annual_income / 12
    rate             = 0.07 / 12
    n                = 360
    monthly_payment  = loan_amount * (rate * (1+rate)**n) / ((1+rate)**n - 1)
    dti              = (monthly_payment + monthly_obligations) / monthly_income
    ltv              = (loan_amount / property_value * 100) if property_value > 0 else 0

    qm_eligible = dti <= 0.43
    ltv_flag    = ltv > 80

    return json.dumps({
        "dti_ratio":       round(dti, 4),
        "ltv_ratio":       round(ltv, 2),
        "monthly_payment": round(monthly_payment, 2),
        "qm_eligible":     qm_eligible,
        "requires_pmi":    ltv_flag,
        "dti_band":        "GOOD" if dti <= 0.36 else
                           "ACCEPTABLE" if dti <= 0.43 else
                           "HIGH" if dti <= 0.50 else "EXCEEDS_LIMIT",
    })


# ── Compliance Worker Tools ───────────────────────────────────────────────────

@tool
def run_regulatory_checks(applicant_id: str, loan_amount: float,
                           loan_purpose: str, state: str = "CA") -> str:
    """HMDA, CRA, Fair Lending, RESPA, TILA compliance checks."""
    logger.info(f"[ComplianceWorker] Regulatory checks: {applicant_id}")
    return json.dumps({
        "hmda_reportable":     loan_amount >= 25_000,
        "cra_credit":          loan_purpose in ["Primary residence purchase", "Home refinance"],
        "fair_lending_flag":   False,
        "respa_disclosure_req": True,
        "tila_disclosure_req": True,
        "state_usury_check":   True,          # within state rate cap
        "compliance_passed":   True,
        "required_disclosures": ["LE", "CD", "TRID"],   # Loan Estimate, Closing Disclosure
    })


@tool
def query_policy_rag(question: str) -> str:
    """Query bank's loan policy knowledge base via RAG for compliance guidance."""
    logger.info(f"[ComplianceWorker] RAG query: {question[:80]}...")
    # Production: uses PGVector retriever
    policy_kb = {
        "interest rate": "Base rate 6.75% + risk tier adjustment. Spread: 0%-3%. Max APR: 9.75%",
        "ltv limit": "Primary: 80% (95% with PMI). Investment: 70%. Commercial: 65%",
        "dti limit": "QM max 43%. Non-QM portfolio up to 50% with compensating factors",
        "minimum score": "Conventional 620; FHA 580; VA 0 (service requirement); Jumbo 720",
        "documentation": "Full doc required > $500K. Alt-doc available $150K-$500K with 720+ score",
    }
    result = next((v for k, v in policy_kb.items() if k in question.lower()),
                  "Refer to underwriting manual Section 4.2 for detailed guidelines.")
    return f"POLICY GUIDANCE: {result}"


# ── Underwriting Worker Tools ─────────────────────────────────────────────────

@tool
def run_automated_underwriting(
    credit_score: int, dti: float, ltv: float,
    fraud_score: int, loan_amount: float, loan_purpose: str,
) -> str:
    """
    Automated Underwriting System (AUS) – mirrors Fannie Mae DU / Freddie Mac LP logic.
    Returns AUS finding and recommended conditions.
    """
    logger.info("[UnderwritingWorker] Running AUS")
    conditions = []
    finding    = "APPROVE/ELIGIBLE"

    if credit_score < 620:
        finding = "REFER"
        conditions.append("Credit score below 620 – manual underwrite required")
    if dti > 0.43:
        finding = "REFER"
        conditions.append("DTI exceeds 43% QM limit – portfolio product evaluation needed")
    if ltv > 95:
        finding = "INELIGIBLE"
        conditions.append("LTV exceeds 95% maximum")
    if fraud_score >= 60:
        finding = "REFER WITH CAUTION"
        conditions.append("Elevated fraud risk – third-party fraud review required")
    if loan_amount > 726_200:
        conditions.append("Jumbo loan – non-conforming product required")

    return json.dumps({
        "aus_finding":    finding,
        "eligible":       "INELIGIBLE" not in finding,
        "conditions":     conditions,
        "recommended_product": (
            "CONVENTIONAL_CONFORMING" if loan_amount <= 726_200 and credit_score >= 620
            else "JUMBO" if loan_amount > 726_200
            else "FHA" if credit_score >= 580 else "NON-QM_PORTFOLIO"
        ),
    })


# ── Decision Worker Tools ─────────────────────────────────────────────────────

@tool
def compute_final_terms(
    loan_amount: float, credit_score: int, ltv: float,
    loan_purpose: str, term_years: int = 30,
) -> str:
    """Price the loan and compute final approved terms."""
    base_rate  = 6.75
    adj        = (0.0 if credit_score >= 740 else
                  0.25 if credit_score >= 700 else
                  0.75 if credit_score >= 660 else
                  1.25 if credit_score >= 620 else 2.5)
    ltv_adj    = 0.25 if ltv > 80 else 0.0
    final_rate = base_rate + adj + ltv_adj

    r = final_rate / 100 / 12
    n = term_years * 12
    pmt = loan_amount * (r * (1+r)**n) / ((1+r)**n - 1) if r else loan_amount / n

    return json.dumps({
        "approved_amount":   loan_amount,
        "interest_rate_pct": round(final_rate, 3),
        "term_years":        term_years,
        "monthly_payment":   round(pmt, 2),
        "total_cost":        round(pmt * n, 2),
        "apr":               round(final_rate + 0.12, 3),   # simplified APR
    })


# =============================================================================
# LLM  (shared across workers)
# =============================================================================

def get_llm(temperature: float = 0.1) -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o",
        temperature=temperature,
        openai_api_key=OPENAI_API_KEY,
        request_timeout=60,
        max_retries=3,
    )


# =============================================================================
# WORKER NODES
# =============================================================================

# Few-shot prompting prefix injected into each worker
FEW_SHOT_PREFIX = """
## FEW-SHOT EXAMPLES

### Example 1 – Strong applicant
Q: Applicant credit score 760, income $120K, loan $400K, 30yr mortgage
A: Credit PRIME tier. DTI ~28%. LTV 75%. AUS: APPROVE/ELIGIBLE. Rate 6.75%. Monthly $2,661.

### Example 2 – Borderline applicant
Q: Applicant credit score 635, income $58K, loan $220K, refinance
A: Credit NEAR_PRIME. DTI 38%. LTV 88% (PMI required). AUS: REFER – manual review. Rate 7.5%.

### Example 3 – Decline case
Q: Applicant credit score 510, income $30K, loan $180K
A: Credit DEEP_SUBPRIME. DTI 52% (exceeds QM 43%). AUS: INELIGIBLE. Decision: DECLINED.

---
"""


def document_worker_node(state: LoanApplicationState) -> dict:
    """Worker: Document extraction + KYC verification."""
    logger.info("[DocumentWorker] Starting document processing")
    try:
        llm   = get_llm()
        tools = [extract_document_data, verify_identity]
        agent = lg_react_agent(llm, tools)

        prompt = (
            f"{FEW_SHOT_PREFIX}"
            f"You are the Document Processing Specialist for loan application {state['applicant_id']}.\n"
            f"Applicant: {state['applicant_name']}, Income: ${state['annual_income']:,.2f}\n\n"
            f"Tasks:\n"
            f"1. Extract W2 and BANK_STMT documents for applicant {state['applicant_id']}\n"
            f"2. Verify identity using DRIVERS_LICENSE\n"
            f"3. Summarize findings as JSON with keys: docs_verified, income_confirmed, kyc_passed\n"
        )

        result  = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        content = result["messages"][-1].content

        return {
            "worker_results": {**state.get("worker_results", {}),
                               "document_worker": content},
            "completed_workers": state.get("completed_workers", []) + ["document_worker"],
            "messages": [AIMessage(content=f"[DocumentWorker] {content}")],
        }
    except Exception as e:
        logger.error(f"[DocumentWorker] Failed: {e}")
        return {
            "worker_results": {**state.get("worker_results", {}),
                               "document_worker": f"ERROR: {e}"},
            "completed_workers": state.get("completed_workers", []) + ["document_worker"],
            "guardrail_flags":   state.get("guardrail_flags", []) + ["DOC_WORKER_FAILED"],
        }


def credit_worker_node(state: LoanApplicationState) -> dict:
    """Worker: Credit bureau pull + analysis."""
    logger.info("[CreditWorker] Starting credit analysis")
    try:
        llm   = get_llm()
        tools = [pull_credit_report, analyze_credit_history]
        agent = lg_react_agent(llm, tools)

        prompt = (
            f"{FEW_SHOT_PREFIX}"
            f"You are the Credit Analysis Specialist for applicant {state['applicant_id']}.\n\n"
            f"Tasks:\n"
            f"1. Pull credit report from Experian for {state['applicant_id']}\n"
            f"2. Analyze the credit history for risk tier classification\n"
            f"3. Return JSON: {{credit_score, credit_tier, eligible, rate_adjustment}}\n"
        )

        result  = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        content = result["messages"][-1].content

        return {
            "worker_results": {**state.get("worker_results", {}),
                               "credit_worker": content},
            "completed_workers": state.get("completed_workers", []) + ["credit_worker"],
            "messages": [AIMessage(content=f"[CreditWorker] {content}")],
        }
    except Exception as e:
        logger.error(f"[CreditWorker] Failed: {e}")
        return {
            "worker_results": {**state.get("worker_results", {}),
                               "credit_worker": f"ERROR: {e}"},
            "completed_workers": state.get("completed_workers", []) + ["credit_worker"],
            "guardrail_flags":   state.get("guardrail_flags", []) + ["CREDIT_WORKER_FAILED"],
        }


def risk_worker_node(state: LoanApplicationState) -> dict:
    """Worker: Fraud detection + DTI/LTV calculations."""
    logger.info("[RiskWorker] Starting risk assessment")
    try:
        llm   = get_llm()
        tools = [run_fraud_detection, calculate_dti_ltv]
        agent = lg_react_agent(llm, tools)

        prompt = (
            f"{FEW_SHOT_PREFIX}"
            f"You are the Risk Assessment Specialist for applicant {state['applicant_id']}.\n"
            f"Loan: ${state['loan_amount']:,.2f} | Income: ${state['annual_income']:,.2f} "
            f"| Property: ${state['property_value']:,.2f}\n\n"
            f"Tasks:\n"
            f"1. Run fraud detection for {state['applicant_id']}\n"
            f"2. Calculate DTI and LTV ratios\n"
            f"3. Return JSON: {{fraud_score, dti_ratio, ltv_ratio, risk_level}}\n"
        )

        result  = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        content = result["messages"][-1].content

        # Derive overall risk level from results
        risk_level = "MEDIUM"   # default; supervisor can override
        if "HIGH" in content.upper():
            risk_level = "HIGH"
        elif "LOW" in content.upper() and "MEDIUM" not in content.upper():
            risk_level = "LOW"

        return {
            "worker_results": {**state.get("worker_results", {}),
                               "risk_worker": content},
            "completed_workers": state.get("completed_workers", []) + ["risk_worker"],
            "risk_level": risk_level,
            "messages":   [AIMessage(content=f"[RiskWorker] {content}")],
        }
    except Exception as e:
        logger.error(f"[RiskWorker] Failed: {e}")
        return {
            "worker_results": {**state.get("worker_results", {}),
                               "risk_worker": f"ERROR: {e}"},
            "completed_workers": state.get("completed_workers", []) + ["risk_worker"],
            "risk_level": "HIGH",   # fail-safe
            "guardrail_flags": state.get("guardrail_flags", []) + ["RISK_WORKER_FAILED"],
        }


def compliance_worker_node(state: LoanApplicationState) -> dict:
    """Worker: Regulatory compliance + policy RAG queries."""
    logger.info("[ComplianceWorker] Starting compliance review")
    try:
        llm   = get_llm()
        tools = [run_regulatory_checks, query_policy_rag]
        agent = lg_react_agent(llm, tools)

        prompt = (
            f"{FEW_SHOT_PREFIX}"
            f"You are the Compliance Officer for loan application {state['applicant_id']}.\n"
            f"Loan: ${state['loan_amount']:,.2f} for '{state['loan_purpose']}'\n\n"
            f"Tasks:\n"
            f"1. Run all regulatory checks (HMDA, CRA, RESPA, TILA)\n"
            f"2. Query policy for applicable interest rate limits\n"
            f"3. Query policy for DTI and LTV requirements\n"
            f"4. Return JSON: {{compliance_passed, disclosures_required, policy_notes}}\n"
        )

        result  = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        content = result["messages"][-1].content

        return {
            "worker_results": {**state.get("worker_results", {}),
                               "compliance_worker": content},
            "completed_workers": state.get("completed_workers", []) + ["compliance_worker"],
            "messages": [AIMessage(content=f"[ComplianceWorker] {content}")],
        }
    except Exception as e:
        logger.error(f"[ComplianceWorker] Failed: {e}")
        return {
            "worker_results": {**state.get("worker_results", {}),
                               "compliance_worker": f"ERROR: {e}"},
            "completed_workers": state.get("completed_workers", []) + ["compliance_worker"],
            "guardrail_flags": state.get("guardrail_flags", []) + ["COMPLIANCE_WORKER_FAILED"],
        }


def underwriting_worker_node(state: LoanApplicationState) -> dict:
    """Worker: AUS (Automated Underwriting System) evaluation."""
    logger.info("[UnderwritingWorker] Starting AUS evaluation")
    try:
        llm   = get_llm()
        tools = [run_automated_underwriting, query_policy_rag]
        agent = lg_react_agent(llm, tools)

        results = state.get("worker_results", {})
        credit_info = results.get("credit_worker", "{}")
        risk_info   = results.get("risk_worker", "{}")

        prompt = (
            f"{FEW_SHOT_PREFIX}"
            f"You are the Senior Underwriter for loan {state['applicant_id']}.\n"
            f"Credit findings: {credit_info[:300]}\n"
            f"Risk findings: {risk_info[:300]}\n"
            f"Loan: ${state['loan_amount']:,.2f} for '{state['loan_purpose']}'\n\n"
            f"Tasks:\n"
            f"1. Run AUS with best available credit_score, DTI, and LTV from prior worker results\n"
            f"   (Use credit_score=700, dti=0.35, ltv=75, fraud_score=15 if values unknown)\n"
            f"2. Query policy for this loan type requirements\n"
            f"3. Return JSON: {{aus_finding, eligible, conditions, recommended_product}}\n"
        )

        result  = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        content = result["messages"][-1].content

        requires_human = ("REFER" in content.upper() or
                          "CAUTION" in content.upper() or
                          state.get("risk_level") == "HIGH")

        return {
            "worker_results": {**results, "underwriting_worker": content},
            "completed_workers": state.get("completed_workers", []) + ["underwriting_worker"],
            "requires_human_review": requires_human,
            "messages": [AIMessage(content=f"[UnderwritingWorker] {content}")],
        }
    except Exception as e:
        logger.error(f"[UnderwritingWorker] Failed: {e}")
        return {
            "worker_results": {**state.get("worker_results", {}),
                               "underwriting_worker": f"ERROR: {e}"},
            "completed_workers": state.get("completed_workers", []) + ["underwriting_worker"],
            "requires_human_review": True,
            "guardrail_flags": state.get("guardrail_flags", []) + ["UW_WORKER_FAILED"],
        }


def decision_worker_node(state: LoanApplicationState) -> dict:
    """Worker: Final pricing + decisioning."""
    logger.info("[DecisionWorker] Rendering final decision")
    try:
        llm   = get_llm()
        tools = [compute_final_terms]
        agent = lg_react_agent(llm, tools)

        results = state.get("worker_results", {})
        uw_info = results.get("underwriting_worker", "{}")

        prompt = (
            f"{FEW_SHOT_PREFIX}"
            f"You are the Loan Decision Officer for application {state['applicant_id']}.\n"
            f"Underwriting finding: {uw_info[:400]}\n"
            f"Risk level: {state.get('risk_level', 'MEDIUM')}\n"
            f"Human review required: {state.get('requires_human_review', False)}\n"
            f"Guardrail flags: {state.get('guardrail_flags', [])}\n\n"
            f"Tasks:\n"
            f"1. Compute final loan terms for ${state['loan_amount']:,.2f} "
            f"   (use credit_score=700 if unknown)\n"
            f"2. Synthesise ALL worker findings into a final APPROVED / CONDITIONAL_APPROVAL / DECLINED decision\n"
            f"3. Return JSON: {{decision, conditions, monthly_payment, interest_rate, reason}}\n"
        )

        result  = agent.invoke({"messages": [HumanMessage(content=prompt)]})
        content = result["messages"][-1].content

        # Parse decision from output
        decision = "CONDITIONAL_APPROVAL"
        if "DECLINED" in content.upper():
            decision = "DECLINED"
        elif "APPROVED" in content.upper() and "CONDITIONAL" not in content.upper():
            decision = "APPROVED"

        # Post-decision guardrail
        post_flags = ProductionGuardrails.post_decision_check(
            decision, state["loan_amount"], 700)

        return {
            "worker_results": {**results, "decision_worker": content},
            "completed_workers": state.get("completed_workers", []) + ["decision_worker"],
            "final_decision": decision,
            "decision_reason": content[:500],
            "processing_complete": True,
            "guardrail_flags": state.get("guardrail_flags", []) + post_flags,
            "messages": [AIMessage(content=f"[DecisionWorker] FINAL: {decision}")],
        }
    except Exception as e:
        logger.error(f"[DecisionWorker] Failed: {e}")
        return {
            "final_decision": "SYSTEM_ERROR_MANUAL_REVIEW",
            "decision_reason": f"Decision worker failed: {e}",
            "processing_complete": True,
            "requires_human_review": True,
        }


# =============================================================================
# SUPERVISOR NODE
# =============================================================================

SUPERVISOR_SYSTEM = """You are the Loan Processing Supervisor orchestrating a team of specialist workers.

Workers available:
- document_worker   : KYC + document extraction
- credit_worker     : Credit bureau + analysis
- risk_worker       : Fraud + DTI/LTV risk
- compliance_worker : Regulatory + policy RAG
- underwriting_worker: AUS decisioning
- decision_worker   : Final terms + decision
- FINISH            : All work done

ROUTING RULES:
1. Always start with document_worker (KYC first)
2. Then credit_worker and risk_worker (can logically follow)
3. Then compliance_worker (uses risk results)
4. Then underwriting_worker (synthesises all above)
5. Finally decision_worker → FINISH

If guardrail_flags are critical, route to FINISH with manual review flag.
Output ONLY the next worker name as a JSON: {"next": "worker_name"}
"""


def supervisor_node(state: LoanApplicationState) -> dict:
    """Supervisor decides which worker runs next."""
    completed = set(state.get("completed_workers", []))
    flags     = state.get("guardrail_flags", [])

    # ── Hard stop: critical guardrail flags ─────────────────────────────────
    if any("EXCEEDS_MAX" in f or "BLOCKED" in f for f in flags):
        logger.warning("[Supervisor] Critical guardrail flag – routing to FINISH")
        return {
            "next_worker":        "FINISH",
            "final_decision":     "DECLINED",
            "decision_reason":    f"Guardrail violation: {flags}",
            "processing_complete": True,
        }

    # ── Deterministic routing ────────────────────────────────────────────────
    sequence = [
        "document_worker",
        "credit_worker",
        "risk_worker",
        "compliance_worker",
        "underwriting_worker",
        "decision_worker",
    ]
    for worker in sequence:
        if worker not in completed:
            logger.info(f"[Supervisor] → routing to {worker}")
            return {"next_worker": worker,
                    "supervisor_notes": state.get("supervisor_notes", []) +
                                        [f"Assigned {worker} at {datetime.now().isoformat()}"]}

    # All done
    return {"next_worker": "FINISH", "processing_complete": True}


# =============================================================================
# GRAPH BUILDER
# =============================================================================

def route_from_supervisor(state: LoanApplicationState) -> str:
    return state.get("next_worker", "FINISH")


def build_supervisor_graph() -> StateGraph:
    guardrails_obj = ProductionGuardrails()

    def guarded_supervisor(state):
        # Pre-flight guardrail
        flags = guardrails_obj.screen_state(state)
        if flags:
            state = {**state, "guardrail_flags": state.get("guardrail_flags", []) + flags}
        return supervisor_node(state)

    graph = StateGraph(LoanApplicationState)

    # ── Add nodes ────────────────────────────────────────────────────────────
    graph.add_node("supervisor",           guarded_supervisor)
    graph.add_node("document_worker",      document_worker_node)
    graph.add_node("credit_worker",        credit_worker_node)
    graph.add_node("risk_worker",          risk_worker_node)
    graph.add_node("compliance_worker",    compliance_worker_node)
    graph.add_node("underwriting_worker",  underwriting_worker_node)
    graph.add_node("decision_worker",      decision_worker_node)

    # ── Entry point ──────────────────────────────────────────────────────────
    graph.add_edge(START, "supervisor")

    # ── Supervisor conditional routing ───────────────────────────────────────
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "document_worker":     "document_worker",
            "credit_worker":       "credit_worker",
            "risk_worker":         "risk_worker",
            "compliance_worker":   "compliance_worker",
            "underwriting_worker": "underwriting_worker",
            "decision_worker":     "decision_worker",
            "FINISH":              END,
        },
    )

    # ── All workers report back to supervisor ─────────────────────────────────
    for worker in ["document_worker", "credit_worker", "risk_worker",
                   "compliance_worker", "underwriting_worker", "decision_worker"]:
        graph.add_edge(worker, "supervisor")

    return graph.compile(checkpointer=MemorySaver())


# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================

def run_loan_processing(application: dict) -> dict:
    """Run a loan application through the full Supervisor/Worker pipeline."""
    logger.info(f"=== Supervisor/Worker Pipeline: {application.get('applicant_id')} ===")

    initial_state: LoanApplicationState = {
        "applicant_id":          application["applicant_id"],
        "applicant_name":        application.get("applicant_name", "Unknown"),
        "loan_amount":           application["loan_amount"],
        "loan_purpose":          application.get("loan_purpose", "General"),
        "annual_income":         application["annual_income"],
        "property_value":        application.get("property_value", 0.0),
        "employment_type":       application.get("employment_type", "EMPLOYED"),
        "years_employed":        application.get("years_employed", 2.0),
        "messages":              [HumanMessage(content=f"Process loan for {application['applicant_id']}")],
        "worker_results":        {},
        "next_worker":           "",
        "completed_workers":     [],
        "supervisor_notes":      [],
        "requires_human_review": False,
        "guardrail_flags":       [],
        "risk_level":            "MEDIUM",
        "final_decision":        "",
        "decision_reason":       "",
        "conditions":            [],
        "approved_amount":       0.0,
        "interest_rate":         0.0,
        "monthly_payment":       0.0,
        "processing_complete":   False,
    }

    try:
        graph   = build_supervisor_graph()
        config  = {"configurable": {"thread_id": application["applicant_id"]}}
        result  = graph.invoke(initial_state, config=config)

        return {
            "applicant_id":          result["applicant_id"],
            "final_decision":        result.get("final_decision", "UNKNOWN"),
            "decision_reason":       result.get("decision_reason", "")[:300],
            "completed_workers":     result.get("completed_workers", []),
            "guardrail_flags":       result.get("guardrail_flags", []),
            "requires_human_review": result.get("requires_human_review", False),
            "risk_level":            result.get("risk_level", "MEDIUM"),
            "worker_results_keys":   list(result.get("worker_results", {}).keys()),
            "timestamp":             datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Pipeline failed: {traceback.format_exc()}")
        return {
            "applicant_id": application["applicant_id"],
            "final_decision": "SYSTEM_ERROR",
            "reason": str(e)[:300],
            "requires_human_review": True,
        }


if __name__ == "__main__":
    print("\n" + "="*70)
    print("  BANK LOAN SUPERVISOR/WORKER AGENT – Production Demo")
    print("="*70 + "\n")

    apps = [
        {
            "applicant_id":   "APP001",
            "applicant_name": "Sarah Johnson",
            "loan_amount":    350_000,
            "loan_purpose":   "Primary residence purchase",
            "annual_income":  95_000,
            "property_value": 437_500,
            "employment_type": "EMPLOYED",
            "years_employed": 5.0,
        },
        {
            "applicant_id":   "APP003",
            "applicant_name": "Elena Rodriguez",
            "loan_amount":    75_000,
            "loan_purpose":   "Small business loan",
            "annual_income":  45_000,
            "property_value": 0,
            "employment_type": "SELF_EMPLOYED",
            "years_employed": 2.0,
        },
    ]

    for app in apps:
        print(f"\n{'─'*60}")
        print(f"  Pipeline: {app['applicant_name']} ({app['applicant_id']})")
        print(f"{'─'*60}")
        result = run_loan_processing(app)
        print(json.dumps(result, indent=2))