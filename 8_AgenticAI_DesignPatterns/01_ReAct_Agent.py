"""
=============================================================================
AGENT 1: REACT AGENT - Bank Loan Processing
=============================================================================
Architecture : ReAct (Reasoning + Acting) Pattern
Use Case     : End-to-end loan application processing with dynamic tool calls
Features     : RAG, MCP Tools, Guardrails, Chain-of-Thought Prompting, Fallbacks
pip install nest_asyncio
=============================================================================
"""

import os
import sys
import json
import time
import logging
import traceback
import re
from typing import Any, Optional
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# LangChain / LangGraph
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain.agents import AgentExecutor, create_react_agent
from langchain_community.vectorstores import PGVector
from langchain_core.prompts import PromptTemplate
from langchain_mcp_adapters.client import MultiServerMCPClient

# ── Logging: ALL output to stderr so stdout stays clean ──────────────────────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("react_agent")

# ── Environment ──────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")
POSTGRES_URL     = os.getenv("POSTGRES_URL",
                             "postgresql+psycopg2://postgres:postgres@localhost:5432/loandb")
LANGSMITH_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")

if LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"]    = LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"]    = "bank-loan-react-agent"

# =============================================================================
# GUARDRAILS
# =============================================================================

class LoanGuardrails:
    """Input/output guardrails for loan processing safety."""

    BLOCKED_PATTERNS = [
        "bypass credit check", "skip verification", "ignore policy",
        "override system", "admin override", "disable guardrail",
    ]

    MAX_LOAN_AMOUNT  = 10_000_000   # $10M hard cap
    MIN_CREDIT_SCORE = 300
    MAX_CREDIT_SCORE = 850
    MIN_INCOME       = 12_000       # annual

    @staticmethod
    def validate_input(query: str) -> tuple[bool, str]:
        q = query.lower()
        for pattern in LoanGuardrails.BLOCKED_PATTERNS:
            if pattern in q:
                return False, f"GUARDRAIL BLOCKED: Disallowed pattern detected – '{pattern}'"
        if len(query) > 5_000:
            return False, "GUARDRAIL BLOCKED: Input too long (max 5000 chars)"
        return True, ""

    @staticmethod
    def validate_loan_amount(amount: float) -> tuple[bool, str]:
        if amount <= 0:
            return False, "Loan amount must be positive"
        if amount > LoanGuardrails.MAX_LOAN_AMOUNT:
            return False, f"Loan amount ${amount:,.2f} exceeds max ${LoanGuardrails.MAX_LOAN_AMOUNT:,.2f}"
        return True, ""

    @staticmethod
    def validate_credit_score(score: int) -> tuple[bool, str]:
        if not (LoanGuardrails.MIN_CREDIT_SCORE <= score <= LoanGuardrails.MAX_CREDIT_SCORE):
            return False, f"Credit score {score} out of valid range (300-850)"
        return True, ""

    @staticmethod
    def sanitize_output(response: str) -> str:
        sensitive = ["SSN", "social security", "password", "secret_key"]
        for term in sensitive:
            response = response.replace(term, "[REDACTED]")
        return response


# =============================================================================
# RAG SETUP
# =============================================================================

def get_rag_retriever():
    """Build a PGVector RAG retriever from loan policy documents."""
    try:
        embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
        vectorstore = PGVector(
            connection_string=POSTGRES_URL,
            embedding_function=embeddings,
            collection_name="loan_policy_docs",
        )
        return vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 4, "fetch_k": 10, "lambda_mult": 0.7},
        )
    except Exception as e:
        logger.warning(f"RAG retriever unavailable – using fallback: {e}")
        return None


# =============================================================================
# MCP CLIENT (financial tools)
# =============================================================================

async def _async_get_mcp_tools() -> list:
    """Async helper – MultiServerMCPClient.get_tools() is a coroutine."""
    mcp_config = {
        "credit_bureau": {
            "command": sys.executable,
            "args": ["mcp_servers/credit_bureau_server.py"],
            "transport": "stdio",
        },
        "income_verifier": {
            "command": sys.executable,
            "args": ["mcp_servers/income_verifier_server.py"],
            "transport": "stdio",
        },
        "fraud_detector": {
            "command": sys.executable,
            "args": ["mcp_servers/fraud_detector_server.py"],
            "transport": "stdio",
        },
    }
    async with MultiServerMCPClient(mcp_config) as client:
        return await client.get_tools()


def get_mcp_tools() -> list:
    """
    Load MCP tools synchronously.

    MultiServerMCPClient.get_tools() is async. We handle two scenarios:
    1. No running event loop  → asyncio.run() creates one and drives it to completion.
    2. Running loop already   → use nest_asyncio (Jupyter / async frameworks) or
                                fall back gracefully so the agent still works with
                                its built-in mock tools.
    """
    try:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            # Normal synchronous context (plain Python script, PowerShell, etc.)
            return asyncio.run(_async_get_mcp_tools())
        else:
            # Already inside a running loop (Jupyter, FastAPI, etc.)
            # Try nest_asyncio; if unavailable, skip MCP gracefully.
            try:
                import nest_asyncio
                nest_asyncio.apply()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, _async_get_mcp_tools())
                    return future.result(timeout=30)
            except ImportError:
                logger.warning(
                    "nest_asyncio not installed and a loop is already running. "
                    "MCP tools skipped. Install nest_asyncio to enable them."
                )
                return []

    except Exception as e:
        logger.warning(f"MCP tools unavailable – using built-in mock tools: {e}")
        return []


# =============================================================================
# TOOLS (ReAct tool set)
# =============================================================================

guardrails = LoanGuardrails()
rag_retriever = get_rag_retriever()


# =============================================================================
# TOOL INPUT HELPER
# =============================================================================
# Root cause of all prior errors: older LangChain versions (the _parse_input
# bug) wrap the entire Action Input JSON string as the VALUE of the first
# parameter name, e.g.  {"applicant_id": '{"applicant_id":"APP003","annual_income":45000}'}
# instead of unpacking it.  The only 100% reliable fix is to give every
# multi-param tool a SINGLE string parameter and parse JSON inside the body.
# Single-param tools (only one arg) are not affected by the bug.

def _parse(raw: str, required: list[str]) -> dict:
    """
    Parse the raw tool_input string into a dict.
    Handles three formats the LLM may produce:
      1. Clean JSON dict  : {"applicant_id": "APP003", "annual_income": 45000}
      2. Nested JSON bug  : the entire JSON blob is the value of the first key
      3. Plain string     : "APP003"  (single-param tools only)
    """
    # Already a dict (LangChain sometimes pre-parses)
    if isinstance(raw, dict):
        data = raw
    else:
        raw = str(raw).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try extracting a JSON object from inside the string
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group())
                except Exception:
                    data = {}
            else:
                # Plain string – map to first required key
                data = {required[0]: raw} if required else {}

    # If first-key-wrapping bug: the value of required[0] is itself a JSON string
    if required and required[0] in data:
        val = data[required[0]]
        if isinstance(val, str) and val.strip().startswith("{"):
            try:
                inner = json.loads(val)
                if isinstance(inner, dict) and len(inner) > 1:
                    data = inner          # unwrap the nested blob
            except Exception:
                pass

    return data


# =============================================================================
# TOOLS  (single-string-input pattern – immune to LangChain _parse_input bug)
# =============================================================================

@tool
def fetch_credit_score(applicant_id: str) -> str:
    """
    Fetch credit score from the credit bureau.
    Input: applicant_id string, e.g.  APP003
    Returns credit score, history length, and derogatory marks.
    """
    # Single param – no parsing needed, but still strip quotes/whitespace
    applicant_id = str(applicant_id).strip().strip('"').strip("'")
    logger.info(f"[TOOL] fetch_credit_score: {applicant_id}")
    try:
        mock_data = {
            "APP001": {"score": 750, "history_years": 8,  "derogatory_marks": 0},
            "APP002": {"score": 620, "history_years": 3,  "derogatory_marks": 2},
            "APP003": {"score": 480, "history_years": 1,  "derogatory_marks": 4},
        }
        data = mock_data.get(applicant_id,
                             {"score": 700, "history_years": 5, "derogatory_marks": 1})
        ok, msg = guardrails.validate_credit_score(data["score"])
        if not ok:
            return f"ERROR: {msg}"
        return json.dumps(data)
    except Exception as e:
        logger.error(f"fetch_credit_score failed: {e}")
        return json.dumps({"error": str(e), "fallback": "Unable to retrieve credit score"})


@tool
def verify_income(tool_input: str) -> str:
    """
    Verify applicant income through payroll/tax records.
    Input must be a JSON string: {"applicant_id": "APP003", "annual_income": 45000}
    Returns verified income, employment status, and DTI ratio.
    """
    p = _parse(tool_input, ["applicant_id", "annual_income"])
    applicant_id  = str(p.get("applicant_id", "UNKNOWN"))
    annual_income = float(p.get("annual_income", p.get("stated_annual_income", 0)))
    logger.info(f"[TOOL] verify_income: {applicant_id}, income=${annual_income:,.2f}")
    try:
        if annual_income < guardrails.MIN_INCOME:
            return json.dumps({"verified": False, "reason": "Income below minimum threshold"})
        return json.dumps({
            "verified":           True,
            "verified_income":    round(annual_income * 0.97, 2),
            "employment_status":  "Full-time employed",
            "dti_ratio":          0.32,
            "income_match_pct":   97,
        })
    except Exception as e:
        logger.error(f"verify_income failed: {e}")
        return json.dumps({"error": str(e), "fallback": "Income verification failed"})


@tool
def check_fraud_indicators(tool_input: str) -> str:
    """
    Run fraud detection on loan application.
    Input must be a JSON string: {"applicant_id": "APP003", "loan_amount": 75000}
    Returns fraud risk score (0-100) and triggered rules.
    """
    p = _parse(tool_input, ["applicant_id", "loan_amount"])
    applicant_id = str(p.get("applicant_id", "UNKNOWN"))
    loan_amount  = float(p.get("loan_amount", 0))
    logger.info(f"[TOOL] check_fraud_indicators: {applicant_id}, amount=${loan_amount:,.2f}")
    try:
        ok, msg = guardrails.validate_loan_amount(loan_amount)
        if not ok:
            return json.dumps({"fraud_risk": 100, "reason": msg})
        risk_score  = 15 if loan_amount < 500_000 else 35
        rules_fired = [] if risk_score < 30 else ["HIGH_AMOUNT_FIRST_LOAN"]
        return json.dumps({
            "fraud_risk_score": risk_score,
            "risk_level":       "LOW" if risk_score < 30 else "MEDIUM" if risk_score < 60 else "HIGH",
            "rules_fired":      rules_fired,
            "recommendation":   "PROCEED" if risk_score < 60 else "MANUAL_REVIEW",
        })
    except Exception as e:
        logger.error(f"check_fraud_indicators failed: {e}")
        return json.dumps({"error": str(e), "fallback": "Fraud check failed – route to manual review"})


@tool
def query_loan_policy(question: str) -> str:
    """
    Query the bank's internal loan policy RAG knowledge base.
    Input: a plain question string, e.g.  What is the maximum DTI allowed?
    Returns policy guidance on rates, LTV, DTI, and eligibility.
    """
    # Single param – safe as-is
    logger.info(f"[TOOL] query_loan_policy: {question[:80]}")
    try:
        if rag_retriever:
            docs = rag_retriever.invoke(question)
            return "POLICY CONTEXT:\n" + "\n\n".join(d.page_content for d in docs[:3])
        fallback = {
            "max_ltv":            "80% primary residence; 70% investment property",
            "min_credit_score":   "620 conventional; 580 FHA",
            "max_dti":            "43% Qualified Mortgage; 50% non-QM portfolio",
            "interest_rate_range":"6.5%–8.5% depending on risk tier",
            "max_term":           "30 years residential; 20 years commercial",
        }
        return f"POLICY FALLBACK (RAG unavailable):\n{json.dumps(fallback, indent=2)}"
    except Exception as e:
        logger.error(f"query_loan_policy failed: {e}")
        return "Unable to retrieve policy. Apply conservative defaults."


@tool
def calculate_loan_metrics(tool_input: str) -> str:
    """
    Calculate monthly payment, total interest, and affordability metrics.
    Input must be a JSON string:
    {"principal": 75000, "annual_rate_pct": 7.5, "term_years": 30, "annual_income": 45000}
    Required before making any loan approval decision.
    """
    p = _parse(tool_input, ["principal", "annual_rate_pct", "term_years", "annual_income"])
    try:
        principal       = float(p.get("principal", p.get("loan_amount", 0)))
        annual_rate_pct = float(p.get("annual_rate_pct", p.get("rate", 7.5)))
        term_years      = int(float(p.get("term_years", 30)))
        annual_income   = float(p.get("annual_income", 1))
    except Exception as e:
        return json.dumps({"error": f"Invalid inputs: {e}"})

    logger.info(f"[TOOL] calculate_loan_metrics: ${principal:,.2f} @ {annual_rate_pct}% / {term_years}yr")
    try:
        r = annual_rate_pct / 100 / 12
        n = term_years * 12
        payment = (principal * (r * (1+r)**n) / ((1+r)**n - 1)) if r else (principal / n)
        total   = payment * n
        pti     = (payment / (annual_income / 12)) * 100
        return json.dumps({
            "monthly_payment":       round(payment, 2),
            "total_interest":        round(total - principal, 2),
            "total_paid":            round(total, 2),
            "payment_to_income_pct": round(pti, 2),
            "affordability": ("AFFORDABLE" if pti < 28 else
                              "STRETCHED"  if pti < 36 else "HIGH_RISK"),
        })
    except Exception as e:
        logger.error(f"calculate_loan_metrics failed: {e}")
        return json.dumps({"error": str(e)})


@tool
def make_loan_decision(tool_input: str) -> str:
    """
    Final loan decisioning tool. Call this LAST after all other checks.
    Input must be a JSON string:
    {"applicant_id": "APP003", "credit_score": 480, "dti_ratio": 0.32,
     "fraud_risk_score": 15, "loan_amount": 75000, "affordability": "HIGH_RISK"}
    Returns APPROVED / CONDITIONAL_APPROVAL / DECLINED with reason codes.
    """
    p = _parse(tool_input, ["applicant_id", "credit_score", "dti_ratio",
                             "fraud_risk_score", "loan_amount", "affordability"])
    applicant_id     = str(p.get("applicant_id", "UNKNOWN"))
    credit_score     = int(float(p.get("credit_score", 0)))
    dti_ratio        = float(p.get("dti_ratio", 0))
    fraud_risk_score = int(float(p.get("fraud_risk_score", 0)))
    loan_amount      = float(p.get("loan_amount", 0))
    affordability    = str(p.get("affordability", "UNKNOWN"))
    logger.info(f"[TOOL] make_loan_decision: {applicant_id}")
    try:
        reasons    = []
        conditions = []

        # Hard declines
        if credit_score < 580:
            reasons.append("Credit score below minimum (580)")
        if fraud_risk_score >= 60:
            reasons.append("High fraud risk score")
        if dti_ratio > 0.50:
            reasons.append("DTI exceeds 50% hard cap")

        if reasons:
            return json.dumps({
                "decision": "DECLINED",
                "reason_codes": reasons,
                "applicant_id": applicant_id,
                "timestamp": datetime.now().isoformat(),
            })

        # Conditional approvals
        if credit_score < 620:
            conditions.append("Requires co-signer")
        if dti_ratio > 0.43:
            conditions.append("Exceeds QM DTI – portfolio loan product only")
        if affordability == "HIGH_RISK":
            conditions.append("Stress test at +200bps required")
        if fraud_risk_score >= 30:
            conditions.append("Manual review required")

        decision = "CONDITIONAL_APPROVAL" if conditions else "APPROVED"

        return json.dumps({
            "decision": decision,
            "conditions": conditions,
            "approved_amount": loan_amount,
            "applicant_id": applicant_id,
            "timestamp": datetime.now().isoformat(),
            "valid_for_days": 90,
        })
    except Exception as e:
        logger.error(f"make_loan_decision failed: {e}")
        return json.dumps({"decision": "ERROR", "reason": str(e)})


# =============================================================================
# REACT AGENT SYSTEM PROMPT (Chain-of-Thought + ReAct)
# =============================================================================

REACT_SYSTEM_PROMPT = """You are an expert Bank Loan Officer AI Agent for FirstNational Bank.
You use the ReAct (Reasoning + Acting) pattern: reason step-by-step, then act with tools.

## YOUR ROLE
Process loan applications by systematically gathering facts through tools and applying bank policy.

## CHAIN-OF-THOUGHT INSTRUCTIONS
For EVERY loan application:
1. THINK: What information do I need? What tools should I call and in what order?
2. ACT: Call tools one at a time, using outputs to inform next steps.
3. OBSERVE: Critically evaluate each tool's output before proceeding.
4. REPEAT: Continue until you have all required data.
5. CONCLUDE: Apply policy rules and render a final decision.

## MANDATORY TOOL SEQUENCE WITH EXACT PARAMETER NAMES
Call tools in this exact order, using these exact parameter names:

  Step 1 → fetch_credit_score(applicant_id="APP003")
  Step 2 → verify_income(applicant_id="APP003", annual_income=45000)
             ↑ IMPORTANT: second param is "annual_income" (a plain number, NOT a JSON string)
  Step 3 → check_fraud_indicators(applicant_id="APP003", loan_amount=75000)
             ↑ loan_amount must be a plain number, NOT a string
  Step 4 → query_loan_policy(question="What are the interest rate and DTI requirements?")
  Step 5 → calculate_loan_metrics(principal=75000, annual_rate_pct=7.5, term_years=30, annual_income=45000)
             ↑ ALL four params are plain numbers
  Step 6 → make_loan_decision(applicant_id="APP003", credit_score=480, dti_ratio=0.35,
                               fraud_risk_score=15, loan_amount=75000, affordability="STRETCHED")

## CRITICAL RULES FOR TOOL CALLS
- ALWAYS pass numbers as plain numbers: 45000 not "45000" and NOT a JSON object
- NEVER pass the entire application as a JSON string to a single parameter
- Extract individual values from the application and pass them as separate parameters
- Use values from prior tool outputs when available (e.g. credit_score from Step 1 output)

## GUARDRAIL RULES (NEVER VIOLATE)
- NEVER approve loans > $10,000,000
- NEVER skip fraud check before approval
- NEVER approve applicants with fraud_risk_score ≥ 60 without escalation
- NEVER disclose other applicants' data
- ALWAYS cite the policy source for your interest rate quotes
- If any tool returns an ERROR, flag it and use conservative fallback values

## OUTPUT FORMAT
After completing all tool calls, produce a structured decision report:
```
LOAN DECISION REPORT
====================
Applicant ID   : [ID]
Decision       : [APPROVED / CONDITIONAL_APPROVAL / DECLINED]
Loan Amount    : $[amount]
Monthly Payment: $[payment]
Key Factors    : [bullet list]
Conditions     : [if any]
Next Steps     : [what the applicant should do]
```

## TONE
Professional, empathetic, and transparent. Explain decisions clearly.
"""


# =============================================================================
# REACT AGENT BUILDER
# =============================================================================

def _make_tool_descriptions(tools: list) -> str:
    """Format tool list for the ReAct prompt."""
    lines = []
    for t in tools:
        lines.append(f"{t.name}: {t.description}")
    return "\n".join(lines)


def _make_tool_names(tools: list) -> str:
    return ", ".join(t.name for t in tools)


# ---------------------------------------------------------------------------
# Custom ReAct prompt that enforces JSON dict Action Input format.
# This replaces hub.pull("hwchase17/react") to avoid the LLM producing
# positional tuple syntax like ("APP003", 45000) which Pydantic rejects.
# ---------------------------------------------------------------------------
REACT_PROMPT_TEMPLATE = """{system_message}

You have access to the following tools:

{tools}

Use the following format EXACTLY – do not deviate:

Question: the input question you must answer
Thought: reason about what to do next
Action: the tool name to call (must be one of [{tool_names}])
Action Input: a JSON object with named keys, e.g. {{"applicant_id": "APP001", "annual_income": 95000}}
              NEVER use positional tuples like ("APP001", 95000)
              ALWAYS use a JSON dict with explicit key names
Observation: the result of the action
... (Thought/Action/Action Input/Observation can repeat up to 12 times)
Thought: I now have all the information needed to give the final answer
Final Answer: the final answer to the original input question

IMPORTANT – Action Input rules:
- Must always be a valid JSON object: {{"key": value, ...}}
- String values use double quotes: "APP003"
- Numbers are bare: 45000  (not "45000")
- Never wrap in parentheses or square brackets

Begin!

Question: {input}
Thought: {agent_scratchpad}"""


def _build_react_prompt(tools: list) -> PromptTemplate:
    return PromptTemplate(
        input_variables=["input", "agent_scratchpad"],
        partial_variables={
            "system_message": REACT_SYSTEM_PROMPT,
            "tools":          _make_tool_descriptions(tools),
            "tool_names":     _make_tool_names(tools),
        },
        template=REACT_PROMPT_TEMPLATE,
    )


def _tuple_safe_error_handler(error: Exception) -> str:
    """
    handle_parsing_errors callback.
    When the LLM outputs a tuple like ("APP003", 45000) instead of a JSON
    dict, we return a corrective instruction so the LLM self-corrects on
    the next iteration instead of crashing.
    """
    err_str = str(error)
    if "tuple" in err_str.lower() or "positional" in err_str.lower() or "Field required" in err_str:
        return (
            "Parsing error: Action Input must be a JSON object with named keys, "
            'for example {"applicant_id": "APP003", "annual_income": 45000}. '
            "Do NOT use tuple syntax like (\"APP003\", 45000). "
            "Please retry the same Action with a properly formatted JSON dict."
        )
    return f"Parsing error: {err_str}. Please reformat your Action Input as a JSON dict and retry."


def build_react_agent():
    """Assemble the ReAct agent with custom prompt and tuple-safe error handling."""
    model = ChatOpenAI(
        model="gpt-4o",
        temperature=0.1,
        openai_api_key=OPENAI_API_KEY,
        request_timeout=60,
        max_retries=3,
    )

    tools = [
        fetch_credit_score,
        verify_income,
        check_fraud_indicators,
        query_loan_policy,
        calculate_loan_metrics,
        make_loan_decision,
    ]

    # Try to extend with live MCP tools
    mcp_tools = get_mcp_tools()
    if mcp_tools:
        tools.extend(mcp_tools)
        logger.info(f"Loaded {len(mcp_tools)} MCP tools")

    # Custom prompt – no hub dependency, enforces JSON dict Action Input
    prompt = _build_react_prompt(tools)

    agent = create_react_agent(model, tools, prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=_tuple_safe_error_handler,  # self-correcting on tuple errors
        max_iterations=15,
        max_execution_time=120,
        early_stopping_method="generate",
        return_intermediate_steps=True,
    )
    return executor


# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================

def process_loan_application(application: dict) -> dict:
    """
    Process a single loan application through the ReAct agent.

    Parameters
    ----------
    application : dict with keys:
        applicant_id, applicant_name, loan_amount, loan_purpose,
        stated_annual_income, property_value (optional)

    Returns
    -------
    dict with decision, reasoning, and metadata
    """
    applicant_id = application.get("applicant_id", "UNKNOWN")
    logger.info(f"=== Processing loan application: {applicant_id} ===")

    # ── Input guardrail ──────────────────────────────────────────────────────
    query = (
        f"Process loan application for applicant {applicant_id} "
        f"({application.get('applicant_name', 'N/A')}). "
        f"Loan amount requested: ${application.get('loan_amount', 0):,.2f} "
        f"for {application.get('loan_purpose', 'unspecified purpose')}. "
        f"Stated annual income: ${application.get('stated_annual_income', 0):,.2f}. "
        f"Property value: ${application.get('property_value', 0):,.2f}. "
        f"Please run the full loan assessment and provide a decision."
    )

    ok, block_msg = guardrails.validate_input(query)
    if not ok:
        logger.warning(f"Input blocked: {block_msg}")
        return {"decision": "BLOCKED", "reason": block_msg, "applicant_id": applicant_id}

    # ── Run ReAct agent ──────────────────────────────────────────────────────
    try:
        agent_executor = build_react_agent()
        result = agent_executor.invoke({"input": query})

        output = guardrails.sanitize_output(result.get("output", ""))
        steps  = result.get("intermediate_steps", [])

        logger.info(f"Agent completed with {len(steps)} reasoning steps")
        return {
            "applicant_id": applicant_id,
            "output":       output,
            "steps_count":  len(steps),
            "status":       "COMPLETED",
            "timestamp":    datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"ReAct agent failed for {applicant_id}: {traceback.format_exc()}")
        # ── Fallback: structured decline with reason ─────────────────────────
        return {
            "applicant_id": applicant_id,
            "decision":     "SYSTEM_ERROR_MANUAL_REVIEW",
            "reason":       f"Agent error – application routed to underwriting team: {str(e)[:200]}",
            "status":       "FALLBACK",
            "timestamp":    datetime.now().isoformat(),
        }


# =============================================================================
# CLI DEMO
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  BANK LOAN REACT AGENT – Production Demo")
    print("="*70 + "\n")

    test_applications = [
        {
            "applicant_id":        "APP001",
            "applicant_name":      "Sarah Johnson",
            "loan_amount":         350_000,
            "loan_purpose":        "Primary residence purchase",
            "stated_annual_income": 95_000,
            "property_value":      437_500,
        },
        {
            "applicant_id":        "APP002",
            "applicant_name":      "Marcus Williams",
            "loan_amount":         200_000,
            "loan_purpose":        "Home refinance",
            "stated_annual_income": 62_000,
            "property_value":      260_000,
        },
        {
            "applicant_id":        "APP003",
            "applicant_name":      "Elena Rodriguez",
            "loan_amount":         75_000,
            "loan_purpose":        "Small business loan",
            "stated_annual_income": 45_000,
            "property_value":      0,
        },
    ]

    for app in test_applications:
        print(f"\n{'─'*60}")
        print(f"  Processing: {app['applicant_name']} ({app['applicant_id']})")
        print(f"{'─'*60}")
        result = process_loan_application(app)
        print(f"\n[RESULT]\n{json.dumps(result, indent=2)}")
        time.sleep(1)   # rate-limit courtesy

    print("\n" + "="*70 + "\n")