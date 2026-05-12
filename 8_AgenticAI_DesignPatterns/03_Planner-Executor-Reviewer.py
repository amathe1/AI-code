"""
=============================================================================
AGENT 3: PLANNER → EXECUTOR → REVIEWER AGENT - Bank Loan Processing
=============================================================================
Architecture : Plan-Execute-Review (PER) Pattern via LangGraph
Phases       : Planner  → creates a dynamic step-by-step execution plan
               Executor → runs each step with the right tools
               Reviewer → validates outputs, triggers replanning if needed
Features     : RAG (PGVector hybrid retrieval), MCP Server integration,
               Production Guardrails, Advanced Prompting (Chain-of-Thought,
               Role-based, Self-critique), Automatic Fallbacks,
               LangSmith observability, Human-in-the-Loop on failure
=============================================================================
"""

import os
import sys
import json
import logging
import operator
import traceback
from typing import Annotated, Any, Literal, Optional, TypedDict
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# LangGraph
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

# LangChain core
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import (
    BaseMessage, HumanMessage, AIMessage, SystemMessage
)
from langchain_core.tools import tool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

# Vector store
from langchain_community.vectorstores import PGVector
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever

# ── Logging: all to stderr ────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("per_agent")

# ── Environment ───────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
POSTGRES_URL    = os.getenv("POSTGRES_URL",
                            "postgresql+psycopg2://postgres:postgres@localhost:5432/loandb")

if os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"]    = os.getenv("LANGSMITH_API_KEY")
    os.environ["LANGCHAIN_PROJECT"]    = "bank-loan-per-agent"


# =============================================================================
# EXECUTION PLAN SCHEMA
# =============================================================================

class ExecutionStep(TypedDict):
    step_id:     int
    name:        str
    description: str
    tool_name:   str
    inputs:      dict
    depends_on:  list[int]
    status:      str        # PENDING | RUNNING | DONE | FAILED | SKIPPED
    output:      Any
    retry_count: int


# =============================================================================
# GRAPH STATE
# =============================================================================

class PERState(TypedDict):
    # ── Application data ──────────────────────────────────────────────────
    applicant_id:    str
    applicant_name:  str
    loan_amount:     float
    loan_purpose:    str
    annual_income:   float
    property_value:  float
    credit_score:    int            # populated after credit step
    dti_ratio:       float
    fraud_score:     int

    # ── PER pipeline ──────────────────────────────────────────────────────
    execution_plan:  list[ExecutionStep]
    current_step:    int
    phase:           str            # PLANNING | EXECUTING | REVIEWING | DONE
    plan_version:    int            # increments on replanning

    # ── Messages & history ────────────────────────────────────────────────
    messages:        Annotated[list[BaseMessage], operator.add]
    step_results:    dict[str, Any]

    # ── Review & guardrail ────────────────────────────────────────────────
    reviewer_notes:  list[str]
    guardrail_flags: list[str]
    replan_needed:   bool
    replan_reason:   str
    human_review:    bool

    # ── Final output ──────────────────────────────────────────────────────
    final_decision:   str
    approved_amount:  float
    interest_rate:    float
    monthly_payment:  float
    conditions:       list[str]
    processing_done:  bool


# =============================================================================
# GUARDRAILS  (3-layer: input, runtime, output)
# =============================================================================

class ThreeLayerGuardrails:
    """
    Layer 1 – Input:   screen application fields before processing
    Layer 2 – Runtime: validate each tool output as it arrives
    Layer 3 – Output:  verify final decision consistency
    """

    # ── Layer 1 ──────────────────────────────────────────────────────────────
    @staticmethod
    def screen_input(state: PERState) -> list[str]:
        flags = []
        if state["loan_amount"] <= 0:
            flags.append("INVALID_LOAN_AMOUNT")
        if state["loan_amount"] > 10_000_000:
            flags.append("EXCEEDS_HARD_LIMIT_10M")
        if state["annual_income"] < 12_000:
            flags.append("INCOME_BELOW_MINIMUM")
        if not state["applicant_id"]:
            flags.append("MISSING_APPLICANT_ID")
        return flags

    # ── Layer 2 ──────────────────────────────────────────────────────────────
    @staticmethod
    def validate_tool_output(tool_name: str, output: Any) -> list[str]:
        flags = []
        try:
            if isinstance(output, str):
                data = json.loads(output)
            else:
                data = output

            if tool_name == "credit_bureau_lookup":
                score = data.get("score", -1)
                if not (300 <= score <= 850):
                    flags.append(f"INVALID_CREDIT_SCORE_{score}")

            if tool_name == "fraud_detection":
                risk = data.get("fraud_risk_score", -1)
                if risk >= 75:
                    flags.append("CRITICAL_FRAUD_RISK")

            if tool_name == "income_verification":
                if not data.get("verified"):
                    flags.append("INCOME_NOT_VERIFIED")

        except Exception:
            flags.append(f"TOOL_OUTPUT_PARSE_ERROR_{tool_name}")
        return flags

    # ── Layer 3 ──────────────────────────────────────────────────────────────
    @staticmethod
    def validate_output(state: PERState) -> list[str]:
        flags = []
        decision = state.get("final_decision", "")
        cs       = state.get("credit_score", 0)
        fraud    = state.get("fraud_score", 0)

        if decision == "APPROVED" and cs < 580:
            flags.append("APPROVAL_BELOW_MIN_CREDIT_SCORE")
        if decision == "APPROVED" and fraud >= 60:
            flags.append("APPROVAL_WITH_HIGH_FRAUD_RISK")
        if decision == "APPROVED" and state.get("dti_ratio", 0) > 0.50:
            flags.append("APPROVAL_EXCEEDS_MAX_DTI")
        return flags


# =============================================================================
# RAG RETRIEVER  (Hybrid BM25 + Semantic + Cross-encoder reranking)
# =============================================================================

_rag_retriever_cache = None

def get_hybrid_rag_retriever():
    """Build a production-grade hybrid RAG retriever with reranking."""
    global _rag_retriever_cache
    if _rag_retriever_cache:
        return _rag_retriever_cache

    try:
        embeddings   = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
        vectorstore  = PGVector(
            connection_string=POSTGRES_URL,
            embedding_function=embeddings,
            collection_name="loan_policy_docs",
        )
        dense_retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 6},
        )

        # Hybrid: BM25 (sparse) + Dense (semantic) ensemble
        # BM25 docs would be pre-loaded in production
        sparse_retriever = BM25Retriever.from_texts(
            texts=[
                "Minimum credit score for conventional loan is 620",
                "FHA loans require minimum 580 credit score with 3.5% down payment",
                "Maximum DTI ratio is 43% for Qualified Mortgage compliance",
                "LTV cannot exceed 80% without private mortgage insurance (PMI)",
                "Jumbo loans require minimum 720 credit score and 20% down payment",
                "Fraud risk score above 60 requires mandatory manual underwriting review",
                "Maximum loan term is 30 years for residential, 20 years for commercial",
                "Debt-to-income ratio calculated as total monthly obligations divided by gross monthly income",
                "Interest rate base is 6.75% adjusted by credit tier and LTV risk premium",
                "HELOCs and second mortgages capped at combined LTV of 90%",
            ],
            k=3,
        )

        ensemble = EnsembleRetriever(
            retrievers=[sparse_retriever, dense_retriever],
            weights=[0.4, 0.6],         # 40% BM25, 60% semantic
        )

        # Cross-encoder reranker (in production: use a fine-tuned model)
        try:
            compressor = CrossEncoderReranker(
                model=HuggingFaceCrossEncoder(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"),
                top_n=3,
            )
            retriever = ContextualCompressionRetriever(
                base_compressor=compressor,
                base_retriever=ensemble,
            )
        except Exception:
            retriever = ensemble   # fallback: no reranking

        _rag_retriever_cache = retriever
        logger.info("Hybrid RAG retriever initialized (BM25 + Semantic + Reranker)")
        return retriever

    except Exception as e:
        logger.warning(f"Full RAG unavailable – static fallback active: {e}")
        return None


def rag_query(question: str) -> str:
    """Query the hybrid RAG system with graceful fallback."""
    retriever = get_hybrid_rag_retriever()
    if retriever:
        try:
            docs    = retriever.invoke(question)
            context = "\n\n".join(f"[{i+1}] {d.page_content}" for i, d in enumerate(docs))
            return context
        except Exception as e:
            logger.warning(f"RAG query failed: {e}")

    # Static fallback policy bank
    fallback = {
        "credit score": "Min 620 conventional, 580 FHA, 720 jumbo",
        "dti":          "Max 43% QM; up to 50% non-QM with compensating factors",
        "ltv":          "Max 80% without PMI; 95% with PMI; 70% investment",
        "rate":         "6.75% base + 0-3% risk premium based on credit tier",
        "fraud":        "Score <30 auto-approve; 30-59 manual review; ≥60 decline",
    }
    match = next((v for k, v in fallback.items() if k in question.lower()), "See policy manual")
    return f"[FALLBACK POLICY] {match}"


# =============================================================================
# TOOL REGISTRY  (all tools available to the Executor)
# =============================================================================

@tool
def credit_bureau_lookup(applicant_id: str) -> str:
    """Retrieve credit score and credit report summary from bureau."""
    data = {
        "APP001": {"score": 755, "utilization": 0.16, "derogatory": 0, "inquiries": 1},
        "APP002": {"score": 638, "utilization": 0.58, "derogatory": 1, "inquiries": 4},
        "APP003": {"score": 502, "utilization": 0.85, "derogatory": 3, "inquiries": 7},
    }
    result = data.get(applicant_id, {"score": 710, "utilization": 0.25,
                                      "derogatory": 0, "inquiries": 2})
    return json.dumps(result)


@tool
def income_verification(applicant_id: str, stated_income: float) -> str:
    """Verify income through IRS/payroll records."""
    if stated_income < 12_000:
        return json.dumps({"verified": False, "reason": "Below minimum income threshold"})
    verified = stated_income * 0.96     # 4% tolerance
    return json.dumps({
        "verified":           True,
        "verified_income":    verified,
        "source":             "IRS_TAX_TRANSCRIPT",
        "employment_status":  "W2_EMPLOYED",
        "months_verified":    24,
    })


@tool
def fraud_detection(applicant_id: str, loan_amount: float, income: float) -> str:
    """Run ML fraud model: returns 0-100 risk score and triggered rules."""
    ratio = loan_amount / max(income, 1)
    score = min(100, int(ratio * 8))
    return json.dumps({
        "fraud_risk_score": score,
        "risk_band":        "LOW" if score < 30 else "MEDIUM" if score < 60 else "HIGH",
        "synthetic_id":     False,
        "rules_triggered":  ["HIGH_LOAN_TO_INCOME"] if score >= 45 else [],
    })


@tool
def appraisal_valuation(property_address: str, stated_value: float) -> str:
    """Order automated property valuation (AVM)."""
    avm_value = stated_value * 0.98     # AVM within 2% of stated
    return json.dumps({
        "avm_value":         avm_value,
        "stated_value":      stated_value,
        "variance_pct":      2.0,
        "confidence":        "HIGH",
        "zoning":            "RESIDENTIAL",
        "marketability":     "GOOD",
    })


@tool
def dti_ltv_calculator(
    loan_amount: float, annual_income: float,
    property_value: float, monthly_debts: float = 400.0,
) -> str:
    """Compute DTI and LTV ratios."""
    monthly_income  = annual_income / 12
    rate            = 0.0675 / 12
    n               = 360
    payment         = loan_amount * (rate * (1+rate)**n) / ((1+rate)**n - 1)
    dti             = (payment + monthly_debts) / monthly_income
    ltv             = (loan_amount / property_value * 100) if property_value > 0 else 0

    return json.dumps({
        "dti":             round(dti, 4),
        "ltv":             round(ltv, 2),
        "monthly_payment": round(payment, 2),
        "qm_compliant":    dti <= 0.43,
        "pmi_required":    ltv > 80,
    })


@tool
def policy_rag_lookup(question: str) -> str:
    """Query bank policy knowledge base using hybrid RAG retrieval."""
    return rag_query(question)


@tool
def aus_underwriting(
    credit_score: int, dti: float, ltv: float,
    fraud_score: int, loan_amount: float,
) -> str:
    """Automated Underwriting System – DU/LP equivalent."""
    conditions = []
    finding    = "APPROVE/ELIGIBLE"

    if credit_score < 580:
        finding = "INELIGIBLE"; conditions.append("Credit below FHA minimum")
    elif credit_score < 620:
        conditions.append("Manual underwrite required")
    if dti > 0.43:
        if finding != "INELIGIBLE":
            finding = "REFER/WITH_CONDITIONS"
        conditions.append("Non-QM portfolio product required")
    if ltv > 95:
        finding = "INELIGIBLE"; conditions.append("LTV too high")
    if fraud_score >= 60:
        finding = "REFER/WITH_CAUTION"; conditions.append("Fraud review required")

    return json.dumps({
        "finding":    finding,
        "eligible":   "INELIGIBLE" not in finding,
        "conditions": conditions,
        "product":    ("CONFORMING" if loan_amount <= 726_200 and credit_score >= 620
                       else "JUMBO" if loan_amount > 726_200 else "FHA"),
    })


@tool
def loan_pricing_engine(
    loan_amount: float, credit_score: int,
    ltv: float, term_years: int = 30,
) -> str:
    """Price the loan using bank's rate sheet logic."""
    base   = 6.75
    credit_adj = (0.0 if credit_score >= 740 else
                  0.375 if credit_score >= 700 else
                  0.875 if credit_score >= 660 else
                  1.5 if credit_score >= 620 else 3.0)
    ltv_adj = 0.25 if ltv > 80 else 0.0
    rate    = base + credit_adj + ltv_adj
    r       = rate / 100 / 12
    n       = term_years * 12
    payment = loan_amount * (r * (1+r)**n) / ((1+r)**n - 1) if r else loan_amount / n

    return json.dumps({
        "interest_rate":   round(rate, 3),
        "monthly_payment": round(payment, 2),
        "apr":             round(rate + 0.11, 3),
        "total_cost":      round(payment * n, 2),
    })


@tool
def compliance_check(applicant_id: str, loan_amount: float, loan_purpose: str) -> str:
    """HMDA / RESPA / TILA / Fair Lending compliance verification."""
    return json.dumps({
        "hmda_reportable":    loan_amount >= 25_000,
        "fair_lending_ok":    True,
        "respa_required":     True,
        "tila_required":      True,
        "compliance_passed":  True,
        "required_disclosures": ["LOAN_ESTIMATE", "CLOSING_DISCLOSURE"],
    })


# Tool name → callable map
TOOL_REGISTRY: dict[str, Any] = {
    "credit_bureau_lookup": credit_bureau_lookup,
    "income_verification":  income_verification,
    "fraud_detection":      fraud_detection,
    "appraisal_valuation":  appraisal_valuation,
    "dti_ltv_calculator":   dti_ltv_calculator,
    "policy_rag_lookup":    policy_rag_lookup,
    "aus_underwriting":     aus_underwriting,
    "loan_pricing_engine":  loan_pricing_engine,
    "compliance_check":     compliance_check,
}


# =============================================================================
# LLM FACTORY
# =============================================================================

def llm(temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o",
        temperature=temperature,
        openai_api_key=OPENAI_API_KEY,
        request_timeout=60,
        max_retries=3,
    )


# =============================================================================
# PHASE 1 – PLANNER
# =============================================================================

PLANNER_SYSTEM = """
You are the Senior Loan Processing Planner at FirstNational Bank.
Your job is to create a detailed, ordered execution plan for a loan application.

## CHAIN-OF-THOUGHT PLANNING RULES
1. Analyse the loan type, amount, and applicant profile.
2. Determine which tools are REQUIRED vs. OPTIONAL.
3. Order steps by dependency (e.g., credit must precede AUS).
4. Assign inputs precisely – never leave inputs ambiguous.
5. Flag any unusual aspects that warrant extra scrutiny.

## AVAILABLE TOOLS (executor will call these):
- credit_bureau_lookup(applicant_id)
- income_verification(applicant_id, stated_income)
- fraud_detection(applicant_id, loan_amount, income)
- appraisal_valuation(property_address, stated_value)
- dti_ltv_calculator(loan_amount, annual_income, property_value)
- policy_rag_lookup(question)
- aus_underwriting(credit_score, dti, ltv, fraud_score, loan_amount)
- loan_pricing_engine(loan_amount, credit_score, ltv, term_years)
- compliance_check(applicant_id, loan_amount, loan_purpose)

## OUTPUT FORMAT (strict JSON – no markdown, no preamble)
Return ONLY:
{
  "plan_summary": "One-line description of the plan",
  "risk_flags": ["list of any immediate concerns"],
  "steps": [
    {
      "step_id": 1,
      "name": "short_name",
      "description": "What and why",
      "tool_name": "exact_tool_name",
      "inputs": {"param": "value"},
      "depends_on": []
    }
  ]
}

MANDATORY STEPS (always include): credit check, income verification, fraud detection, 
compliance check, AUS underwriting, loan pricing.
INCLUDE appraisal only if property_value > 0.
INCLUDE policy RAG for interest rate, DTI, and LTV policy whenever uncertain.
"""


def planner_node(state: PERState) -> dict:
    """Phase 1: Generate a dynamic execution plan."""
    logger.info(f"[PLANNER] Creating execution plan for {state['applicant_id']}")

    # ── Layer 1 guardrail ────────────────────────────────────────────────────
    flags = ThreeLayerGuardrails.screen_input(state)
    if flags:
        logger.warning(f"[PLANNER] Input guardrail flags: {flags}")
        if "EXCEEDS_HARD_LIMIT_10M" in flags or "INVALID_LOAN_AMOUNT" in flags:
            return {
                "phase":           "DONE",
                "guardrail_flags": flags,
                "final_decision":  "DECLINED",
                "processing_done": True,
                "messages": [AIMessage(content=f"[PLANNER] BLOCKED by guardrail: {flags}")],
            }

    try:
        user_prompt = f"""
Plan a loan application assessment with these details:
- Applicant ID    : {state['applicant_id']}
- Applicant Name  : {state['applicant_name']}
- Loan Amount     : ${state['loan_amount']:,.2f}
- Loan Purpose    : {state['loan_purpose']}
- Annual Income   : ${state['annual_income']:,.2f}
- Property Value  : ${state['property_value']:,.2f}

Consider edge cases, risks, and compliance requirements.
"""
        response = llm(temperature=0.2).invoke([
            SystemMessage(content=PLANNER_SYSTEM),
            HumanMessage(content=user_prompt),
        ])

        # Parse JSON plan
        plan_text = response.content.strip()
        # Strip markdown fences if present
        if plan_text.startswith("```"):
            plan_text = "\n".join(plan_text.split("\n")[1:-1])

        plan_data = json.loads(plan_text)
        raw_steps = plan_data.get("steps", [])

        # Normalise into ExecutionStep TypedDicts
        steps: list[ExecutionStep] = []
        for s in raw_steps:
            steps.append({
                "step_id":     s["step_id"],
                "name":        s["name"],
                "description": s["description"],
                "tool_name":   s["tool_name"],
                "inputs":      s.get("inputs", {}),
                "depends_on":  s.get("depends_on", []),
                "status":      "PENDING",
                "output":      None,
                "retry_count": 0,
            })

        risk_flags = plan_data.get("risk_flags", [])

        logger.info(f"[PLANNER] Plan created: {len(steps)} steps | risks: {risk_flags}")

        return {
            "execution_plan":  steps,
            "current_step":    0,
            "plan_version":    1,
            "phase":           "EXECUTING",
            "guardrail_flags": state.get("guardrail_flags", []) + flags,
            "reviewer_notes":  [f"Plan v1 created: {plan_data.get('plan_summary','')}"],
            "messages": [AIMessage(
                content=f"[PLANNER] Execution plan created with {len(steps)} steps. "
                        f"Risk flags: {risk_flags}"
            )],
        }

    except Exception as e:
        logger.error(f"[PLANNER] Failed: {traceback.format_exc()}")
        # Fallback: hard-coded minimal plan
        fallback_steps = _build_fallback_plan(state)
        return {
            "execution_plan": fallback_steps,
            "current_step":   0,
            "plan_version":   1,
            "phase":          "EXECUTING",
            "reviewer_notes": [f"FALLBACK PLAN activated (planner error: {str(e)[:100]})"],
            "messages": [AIMessage(content=f"[PLANNER] Fallback plan activated: {e}")],
        }


def _build_fallback_plan(state: PERState) -> list[ExecutionStep]:
    """Minimal safe plan used when the LLM planner fails."""
    steps = [
        {"step_id": 1, "name": "credit_check",   "tool_name": "credit_bureau_lookup",
         "inputs": {"applicant_id": state["applicant_id"]}, "depends_on": []},
        {"step_id": 2, "name": "income_verify",  "tool_name": "income_verification",
         "inputs": {"applicant_id": state["applicant_id"],
                    "stated_income": state["annual_income"]}, "depends_on": [1]},
        {"step_id": 3, "name": "fraud_check",    "tool_name": "fraud_detection",
         "inputs": {"applicant_id": state["applicant_id"],
                    "loan_amount": state["loan_amount"],
                    "income": state["annual_income"]}, "depends_on": [1]},
        {"step_id": 4, "name": "dti_ltv",        "tool_name": "dti_ltv_calculator",
         "inputs": {"loan_amount": state["loan_amount"],
                    "annual_income": state["annual_income"],
                    "property_value": state["property_value"]}, "depends_on": [2]},
        {"step_id": 5, "name": "compliance",     "tool_name": "compliance_check",
         "inputs": {"applicant_id": state["applicant_id"],
                    "loan_amount": state["loan_amount"],
                    "loan_purpose": state["loan_purpose"]}, "depends_on": []},
        {"step_id": 6, "name": "aus",            "tool_name": "aus_underwriting",
         "inputs": {"credit_score": 700, "dti": 0.35, "ltv": 75.0,
                    "fraud_score": 20, "loan_amount": state["loan_amount"]}, "depends_on": [1,3,4]},
        {"step_id": 7, "name": "pricing",        "tool_name": "loan_pricing_engine",
         "inputs": {"loan_amount": state["loan_amount"], "credit_score": 700,
                    "ltv": 75.0}, "depends_on": [6]},
    ]
    return [{**s, "description": s["name"], "status": "PENDING",
             "output": None, "retry_count": 0} for s in steps]


# =============================================================================
# PHASE 2 – EXECUTOR
# =============================================================================

EXECUTOR_SYSTEM = """
You are the Loan Processing Executor. You run each step of the execution plan.

## ROLE
- Execute the assigned step using the provided tool and inputs.
- If a prior step's output is needed as input, extract the relevant values from step_results.
- If a tool call fails, retry once with adjusted inputs before reporting failure.
- NEVER fabricate data. If a tool returns an error, report it honestly.

## SELF-CRITIQUE BEFORE EXECUTION
Ask yourself:
1. Do I have all required inputs for this step?
2. Are the inputs valid and within expected ranges?
3. Does this step depend on a prior step that has completed successfully?
Only proceed if all three checks pass.

## OUTPUT
Return the raw tool output as-is. Include a brief observation: what the result means.
"""


def executor_node(state: PERState) -> dict:
    """Phase 2: Execute the current plan step."""
    plan         = state.get("execution_plan", [])
    current_idx  = state.get("current_step", 0)
    step_results = state.get("step_results", {})

    if current_idx >= len(plan):
        logger.info("[EXECUTOR] All steps complete → moving to REVIEWING")
        return {"phase": "REVIEWING"}

    step = plan[current_idx]
    logger.info(f"[EXECUTOR] Step {step['step_id']}: {step['name']} ({step['tool_name']})")

    # ── Dependency check ─────────────────────────────────────────────────────
    for dep_id in step.get("depends_on", []):
        dep_step = next((s for s in plan if s["step_id"] == dep_id), None)
        if dep_step and dep_step["status"] != "DONE":
            logger.warning(f"[EXECUTOR] Dependency step {dep_id} not done – skipping")
            plan[current_idx]["status"] = "SKIPPED"
            return {
                "execution_plan": plan,
                "current_step":   current_idx + 1,
                "messages": [AIMessage(content=f"[EXECUTOR] Step {step['step_id']} skipped (dependency not met)")],
            }

    # ── Resolve dynamic inputs from prior results ────────────────────────────
    inputs = _resolve_inputs(step["inputs"], step_results, state)

    # ── Execute with retry ───────────────────────────────────────────────────
    max_retries = 2
    output      = None
    error_msg   = None

    for attempt in range(max_retries):
        try:
            tool_fn = TOOL_REGISTRY.get(step["tool_name"])
            if not tool_fn:
                raise ValueError(f"Unknown tool: {step['tool_name']}")

            output = tool_fn.invoke(inputs)

            # ── Layer 2 guardrail ────────────────────────────────────────────
            rt_flags = ThreeLayerGuardrails.validate_tool_output(step["tool_name"], output)
            if rt_flags:
                logger.warning(f"[EXECUTOR] Runtime guardrail: {rt_flags}")
                existing = state.get("guardrail_flags", [])
                state = {**state, "guardrail_flags": existing + rt_flags}

            plan[current_idx]["status"]  = "DONE"
            plan[current_idx]["output"]  = output
            error_msg = None
            break

        except Exception as e:
            error_msg = str(e)
            logger.warning(f"[EXECUTOR] Step {step['step_id']} attempt {attempt+1} failed: {e}")
            plan[current_idx]["retry_count"] += 1
            if attempt == max_retries - 1:
                plan[current_idx]["status"] = "FAILED"
                output = json.dumps({"error": error_msg, "fallback": True})
                logger.error(f"[EXECUTOR] Step {step['step_id']} permanently failed")

    # ── Update step results & extract key fields ─────────────────────────────
    step_results[step["name"]] = output
    state_updates = _extract_key_fields(step["name"], output, state)

    next_idx  = current_idx + 1
    new_phase = "REVIEWING" if next_idx >= len(plan) else "EXECUTING"

    return {
        "execution_plan": plan,
        "current_step":   next_idx,
        "phase":          new_phase,
        "step_results":   step_results,
        **state_updates,
        "messages": [AIMessage(
            content=f"[EXECUTOR] Step {step['step_id']} ({step['name']}): "
                    f"{'DONE' if plan[current_idx]['status']=='DONE' else 'FAILED'}"
        )],
    }


def _resolve_inputs(inputs: dict, step_results: dict, state: PERState) -> dict:
    """
    Resolve input values – replace sentinel strings like '__credit_score__'
    with actual values from prior step results or state.
    """
    resolved = {}
    for k, v in inputs.items():
        if isinstance(v, str) and v.startswith("__") and v.endswith("__"):
            key = v.strip("__")
            # Try step results first, then state
            result_val = None
            for step_name, result_json in step_results.items():
                try:
                    data = json.loads(result_json) if isinstance(result_json, str) else result_json
                    if key in data:
                        result_val = data[key]
                        break
                except Exception:
                    pass
            resolved[k] = result_val if result_val is not None else state.get(key, v)
        else:
            resolved[k] = v
    return resolved


def _extract_key_fields(step_name: str, output: Any, state: PERState) -> dict:
    """Pull key values from tool outputs into state for downstream steps."""
    updates = {}
    try:
        data = json.loads(output) if isinstance(output, str) else output
        if step_name == "credit_check":
            updates["credit_score"] = data.get("score", state.get("credit_score", 700))
        if step_name == "fraud_check":
            updates["fraud_score"]  = data.get("fraud_risk_score", state.get("fraud_score", 50))
        if step_name == "dti_ltv":
            updates["dti_ratio"] = data.get("dti", state.get("dti_ratio", 0.35))
    except Exception:
        pass
    return updates


# =============================================================================
# PHASE 3 – REVIEWER
# =============================================================================

REVIEWER_SYSTEM = """
You are the Senior Loan Underwriter performing a quality-control review.

## ROLE
Review all execution step outputs and produce a FINAL loan decision.

## SELF-CRITIQUE CHECKLIST (mandatory – answer each explicitly)
1. Did all critical steps complete successfully? (credit, income, fraud, AUS)
2. Are there any guardrail violations that prevent approval?
3. Is the AUS finding consistent with the credit and risk data?
4. Is the proposed interest rate within bank policy limits?
5. Are all required compliance disclosures identified?
6. Is the decision justifiable to a regulator?

If any critical step FAILED, you MUST flag for human review.

## PROMPTING TECHNIQUE: Role-based + Self-critique + Chain-of-Thought
Think step by step, acting as both advocate (for the applicant) and skeptic (for the bank).
Show your reasoning before reaching the decision.

## OUTPUT FORMAT (strict JSON – no markdown, no preamble)
{
  "decision": "APPROVED | CONDITIONAL_APPROVAL | DECLINED | MANUAL_REVIEW_REQUIRED",
  "interest_rate": 7.125,
  "monthly_payment": 2350.00,
  "approved_amount": 350000,
  "conditions": ["list of conditions if any"],
  "reviewer_notes": ["key observations"],
  "requires_human_review": false,
  "replan_needed": false,
  "replan_reason": ""
}
"""


def reviewer_node(state: PERState) -> dict:
    """Phase 3: Review all results and render the final decision."""
    logger.info(f"[REVIEWER] Starting quality review for {state['applicant_id']}")

    plan         = state.get("execution_plan", [])
    step_results = state.get("step_results", {})
    flags        = state.get("guardrail_flags", [])

    # ── Build review context ─────────────────────────────────────────────────
    results_summary = {}
    failed_steps    = []

    for step in plan:
        if step["status"] == "DONE" and step["output"]:
            results_summary[step["name"]] = step["output"]
        elif step["status"] == "FAILED":
            failed_steps.append(step["name"])

    review_context = f"""
LOAN APPLICATION: {state['applicant_id']} ({state['applicant_name']})
Amount: ${state['loan_amount']:,.2f} | Purpose: {state['loan_purpose']}
Income: ${state['annual_income']:,.2f} | Property: ${state['property_value']:,.2f}

STEP RESULTS:
{json.dumps(results_summary, indent=2)[:3000]}

FAILED STEPS: {failed_steps}
GUARDRAIL FLAGS: {flags}
PLAN VERSION: {state.get('plan_version', 1)}
"""

    try:
        response = llm(temperature=0.0).invoke([
            SystemMessage(content=REVIEWER_SYSTEM),
            HumanMessage(content=review_context),
        ])

        review_text = response.content.strip()
        if review_text.startswith("```"):
            review_text = "\n".join(review_text.split("\n")[1:-1])

        review = json.loads(review_text)

        decision = review.get("decision", "MANUAL_REVIEW_REQUIRED")
        replan   = review.get("replan_needed", False)

        # ── Layer 3 guardrail ────────────────────────────────────────────────
        output_flags = ThreeLayerGuardrails.validate_output({
            **state,
            "final_decision": decision,
            "credit_score":   state.get("credit_score", 0),
            "fraud_score":    state.get("fraud_score", 0),
            "dti_ratio":      state.get("dti_ratio", 0),
        })

        if output_flags:
            logger.error(f"[REVIEWER] Output guardrail violated: {output_flags}")
            decision = "MANUAL_REVIEW_REQUIRED"
            review["conditions"] = review.get("conditions", []) + output_flags
            review["requires_human_review"] = True

        # If replanning requested and < 3 plans already, replan
        if replan and state.get("plan_version", 1) < 3:
            logger.info(f"[REVIEWER] Requesting replan: {review.get('replan_reason')}")
            return {
                "phase":        "PLANNING",
                "plan_version": state.get("plan_version", 1) + 1,
                "replan_needed": True,
                "replan_reason": review.get("replan_reason", ""),
                "reviewer_notes": state.get("reviewer_notes", []) + review.get("reviewer_notes", []),
                "messages": [AIMessage(content=f"[REVIEWER] Replanning requested: {review.get('replan_reason')}")],
            }

        return {
            "phase":           "DONE",
            "final_decision":  decision,
            "interest_rate":   review.get("interest_rate", 7.0),
            "monthly_payment": review.get("monthly_payment", 0.0),
            "approved_amount": review.get("approved_amount", state["loan_amount"]),
            "conditions":      review.get("conditions", []),
            "reviewer_notes":  state.get("reviewer_notes", []) + review.get("reviewer_notes", []),
            "human_review":    review.get("requires_human_review", False),
            "guardrail_flags": flags + output_flags,
            "processing_done": True,
            "messages": [AIMessage(content=f"[REVIEWER] FINAL DECISION: {decision}")],
        }

    except Exception as e:
        logger.error(f"[REVIEWER] Failed: {traceback.format_exc()}")
        # Fallback: safe conservative decision
        return {
            "phase":           "DONE",
            "final_decision":  "MANUAL_REVIEW_REQUIRED",
            "conditions":      [f"Reviewer error – escalated to underwriting: {str(e)[:100]}"],
            "human_review":    True,
            "processing_done": True,
            "reviewer_notes":  [f"FALLBACK: reviewer exception {str(e)[:100]}"],
            "messages": [AIMessage(content=f"[REVIEWER] FALLBACK – manual review required: {e}")],
        }


# =============================================================================
# GRAPH ROUTING
# =============================================================================

def route_by_phase(state: PERState) -> str:
    phase = state.get("phase", "PLANNING")
    if phase == "PLANNING":
        return "planner"
    if phase == "EXECUTING":
        return "executor"
    if phase == "REVIEWING":
        return "reviewer"
    return END


def route_after_executor(state: PERState) -> str:
    if state.get("phase") == "REVIEWING":
        return "reviewer"
    return "executor"


# =============================================================================
# GRAPH BUILDER
# =============================================================================

def build_per_graph():
    graph = StateGraph(PERState)

    graph.add_node("planner",  planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("reviewer", reviewer_node)

    # Entry → planner
    graph.add_edge(START, "planner")

    # Planner → executor or END (if guardrail blocked)
    graph.add_conditional_edges(
        "planner",
        lambda s: "executor" if s.get("phase") == "EXECUTING" else END,
        {"executor": "executor", END: END},
    )

    # Executor loops until all steps done, then → reviewer
    graph.add_conditional_edges(
        "executor",
        route_after_executor,
        {"executor": "executor", "reviewer": "reviewer"},
    )

    # Reviewer → replanning loop or END
    graph.add_conditional_edges(
        "reviewer",
        lambda s: "planner" if s.get("phase") == "PLANNING" else END,
        {"planner": "planner", END: END},
    )

    return graph.compile(checkpointer=MemorySaver())


# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================

def run_per_pipeline(application: dict) -> dict:
    """Run a loan application through the full Planner→Executor→Reviewer pipeline."""
    logger.info(f"=== PER Pipeline: {application.get('applicant_id')} ===")

    initial_state: PERState = {
        "applicant_id":    application["applicant_id"],
        "applicant_name":  application.get("applicant_name", "Unknown"),
        "loan_amount":     application["loan_amount"],
        "loan_purpose":    application.get("loan_purpose", "General"),
        "annual_income":   application["annual_income"],
        "property_value":  application.get("property_value", 0.0),
        "credit_score":    0,
        "dti_ratio":       0.0,
        "fraud_score":     0,
        "execution_plan":  [],
        "current_step":    0,
        "plan_version":    1,
        "phase":           "PLANNING",
        "messages":        [HumanMessage(content=f"Process loan for {application['applicant_id']}")],
        "step_results":    {},
        "reviewer_notes":  [],
        "guardrail_flags": [],
        "replan_needed":   False,
        "replan_reason":   "",
        "human_review":    False,
        "final_decision":  "",
        "approved_amount": 0.0,
        "interest_rate":   0.0,
        "monthly_payment": 0.0,
        "conditions":      [],
        "processing_done": False,
    }

    try:
        graph  = build_per_graph()
        config = {"configurable": {"thread_id": application["applicant_id"]},
                  "recursion_limit": 50}
        result = graph.invoke(initial_state, config=config)

        return {
            "applicant_id":    result["applicant_id"],
            "final_decision":  result.get("final_decision", "UNKNOWN"),
            "approved_amount": result.get("approved_amount", 0),
            "interest_rate":   result.get("interest_rate", 0),
            "monthly_payment": result.get("monthly_payment", 0),
            "conditions":      result.get("conditions", []),
            "reviewer_notes":  result.get("reviewer_notes", []),
            "guardrail_flags": result.get("guardrail_flags", []),
            "human_review":    result.get("human_review", False),
            "plan_version":    result.get("plan_version", 1),
            "steps_executed":  result.get("current_step", 0),
            "credit_score":    result.get("credit_score", 0),
            "dti_ratio":       result.get("dti_ratio", 0),
            "fraud_score":     result.get("fraud_score", 0),
            "timestamp":       datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"PER pipeline failed: {traceback.format_exc()}")
        return {
            "applicant_id":   application["applicant_id"],
            "final_decision": "SYSTEM_ERROR",
            "reason":         str(e)[:300],
            "human_review":   True,
            "timestamp":      datetime.now().isoformat(),
        }


# =============================================================================
# CLI DEMO
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  BANK LOAN PLANNER→EXECUTOR→REVIEWER AGENT – Production Demo")
    print("="*70 + "\n")

    test_cases = [
        {
            "applicant_id":   "APP001",
            "applicant_name": "Sarah Johnson",
            "loan_amount":    350_000,
            "loan_purpose":   "Primary residence purchase",
            "annual_income":  95_000,
            "property_value": 437_500,
        },
        {
            "applicant_id":   "APP002",
            "applicant_name": "Marcus Williams",
            "loan_amount":    200_000,
            "loan_purpose":   "Home refinance",
            "annual_income":  62_000,
            "property_value": 260_000,
        },
        {
            "applicant_id":   "APP003",
            "applicant_name": "Elena Rodriguez",
            "loan_amount":    75_000,
            "loan_purpose":   "Small business loan",
            "annual_income":  45_000,
            "property_value": 0,
        },
    ]

    for app in test_cases:
        print(f"\n{'─'*60}")
        print(f"  PER Pipeline: {app['applicant_name']} ({app['applicant_id']})")
        print(f"  Loan: ${app['loan_amount']:,.2f} | Income: ${app['annual_income']:,.2f}")
        print(f"{'─'*60}")
        result = run_per_pipeline(app)
        print(json.dumps(result, indent=2))

    print("\n" + "="*70 + "\n")