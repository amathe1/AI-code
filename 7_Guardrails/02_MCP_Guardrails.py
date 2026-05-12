"""
============================================================
 MCP TOOL GUARDRAILS — Bank Loan AI System
============================================================

THEORY:
-------
MCP (Model Context Protocol) guardrails protect the tool
calling pipeline at 3 key checkpoints:

[LLM Tool Decision]
    │
    ▼
┌─────────────────────────┐
│ 1. TOOL SELECTION GUARD │ ← Is this tool allowed?
│    - Blocked tool list  │   Does user have permission?
│    - Whitelist check    │   Rate limit enforced?
│    - Permission by role │
│    - Rate limiting      │
└──────────┬──────────────┘
           │
    [Parameter Extraction]
           │
           ▼
┌─────────────────────────┐
│ 2. PARAMETER GUARDRAIL  │ ← Are params valid and safe?
│    - Required fields    │
│    - Type validation    │
│    - Range checking     │
│    - Pattern matching   │
│    - Allowed values     │
│    - Injection in params│
└──────────┬──────────────┘
           │
    [Tool Execution]
           │
           ▼
┌─────────────────────────┐
│ 3. RESULT GUARDRAIL     │ ← Is the result safe to return?
│    - Error detection    │
│    - Numeric sanity     │
│    - Data sanitization  │
│    - PII in results     │
└──────────┬──────────────┘
           │
    [Return to LLM]

WHY THESE MATTER:
- Tool selection guard prevents calling dangerous or unauthorized tools
- Parameter guard stops SQL injection, bad data, and out-of-range inputs
- Result guard ensures tool output is safe before LLM reads it

<<<Tool selection Guardrails>>>

1️⃣ Blocked Tool List

🧠 Theory

Defines a list of tools/actions that are strictly forbidden, regardless of user request.

👉 Even if:

User asks for it
LLM suggests it

➡️ System must never execute those tools

💡 Example

Available tools:

send_email
delete_records
generate_report

Blocked list:

❌ delete_records

User asks:

“Delete all customer data”

Guardrail action
Tool call is blocked immediately

Response:

“This action is not permitted.”

🧩 Analogy

🔐 “Do Not Touch” switch
Even employees can’t press it—it's hard-blocked.

2️⃣ Whitelist Check

🧠 Theory

Only allows execution of tools that are explicitly approved (whitelisted).

👉 Opposite of blacklist:

Instead of blocking bad tools
You allow only known safe tools

💡 Example

Whitelist:

✅ generate_invoice
✅ check_order_status

User request triggers:

access_database_admin

Guardrail action
Reject because it’s not in whitelist

🧩 Analogy

🎟️ VIP guest list
Only names on the list can enter—everyone else is denied.

3️⃣ Permission by Role

🧠 Theory

Tool access depends on user role or identity.

👉 Different roles → different permissions:

Admin
Manager
Viewer

💡 Example

Role	Allowed Tools
Admin	All tools
User	View-only tools

User role: Viewer
Request:

“Update employee salary”

Guardrail action

Deny action:

“You don’t have permission for this operation.”

🧩 Analogy

🏢 Office access badge

Employee → limited floors
Admin → full access

4️⃣ Rate Limiting

🧠 Theory

Restricts how frequently tools can be used.

👉 Prevents:

Abuse
System overload
Cost spikes

💡 Example

Limit:

Max 5 API calls per minute

User/system tries:

20 tool calls in 10 seconds

Guardrail action
Block excess calls

Return:

“Rate limit exceeded. Please try again later.”

🧩 Analogy

🚰 Water tap with flow control
You can’t open it fully all the time—it controls how much flows per second.

🔗 Combined Tool Guardrail Flow

Agent decides to call tool
   ↓
[Blocked Tool List Check]
   ↓
[Whitelist Check]
   ↓
[Permission by Role]
   ↓
[Rate Limiting]
   ↓
Tool Execution Allowed / Denied

⚠️ What Happens If You Skip These?

❌ No Blocked Tool List
Dangerous operations executed

❌ No Whitelist
Unknown/unverified tools triggered

❌ No Role-Based Permission
Unauthorized access (security breach)

❌ No Rate Limiting
API abuse, cost explosion, system crash

💡 Production Insight

In real systems, combine all four:

Blocked list → hard safety
Whitelist → controlled execution
Permissions → user-level security
Rate limit → system stability

🚀 Final Mental Model

Think of this layer as:

🛂 Security gate before action execution

Like an airport:

Some items banned (blocked tools)
Only ticket holders allowed (whitelist)
Passport checked (role)
Entry flow controlled (rate limit)


<<<Parameter Guardrails>>>

1️⃣ Required Fields

🧠 Theory

Ensures all mandatory parameters are present before processing.

👉 Prevents:

Incomplete requests
Runtime failures

💡 Example

API expects:

{
  "name": "...",
  "email": "...",
  "age": ...
}

User sends:

{
  "name": "Anil"
}

Problem
Missing email and age ❌

Guardrail action

“Missing required fields: email, age”

🧩 Analogy

📝 Job application form
You can’t submit without filling mandatory fields marked with (*)

2️⃣ Type Validation

🧠 Theory

Checks whether input values match the expected data type:

String
Integer
Boolean
Date, etc.

💡 Example

Expected:

"age": integer

User sends:

"age": "twenty five"

Problem
Wrong type ❌

Guardrail action

“Invalid type: age must be a number”

🧩 Analogy

🔢 Calculator input
You can’t input text in a number field

3️⃣ Range Checking

🧠 Theory

Ensures values fall within an acceptable range.

💡 Example

Expected:

"age": 18–60

User sends:

"age": 150

Problem
Unrealistic / invalid ❌

Guardrail action

“Age must be between 18 and 60”

🧩 Analogy

🚗 Speed limit
You can’t drive at 300 km/h in city limits

4️⃣ Pattern Matching

🧠 Theory

Validates input using specific formats (regex patterns).

💡 Example

Expected email format:

example@domain.com

User sends:

anil#gmail

Problem
Invalid format ❌

Guardrail action

“Invalid email format”

🧩 Analogy

📧 Postal address format
If PIN code or address format is wrong, delivery fails.

5️⃣ Allowed Values

🧠 Theory

Restricts input to a predefined set of valid options.

💡 Example

Expected:

"plan": ["basic", "premium", "enterprise"]

User sends:

"plan": "gold"

Problem
Not in allowed list ❌

Guardrail action

“Invalid value. Allowed: basic, premium, enterprise”

🧩 Analogy

🍽️ Menu ordering
You can only order items on the menu, not anything else.

6️⃣ Injection in Params

🧠 Theory

Detects malicious content embedded inside parameters:

SQL injection
Command injection
Hidden instructions

💡 Example

User sends:

"name": "Anil; DROP TABLE users;"

Problem
Malicious payload ❌

Guardrail action
Sanitize or reject:

“Invalid input detected”

🧩 Analogy

🛃 Airport luggage scan
Even if luggage looks normal, it’s scanned for hidden threats

🔗 Combined Validation Flow

Incoming Parameters
   ↓
[Required Fields Check]
   ↓
[Type Validation]
   ↓
[Range Checking]
   ↓
[Pattern Matching]
   ↓
[Allowed Values Check]
   ↓
[Injection Detection]
   ↓
Safe Structured Input

⚠️ What Happens If You Skip These?

❌ Missing required fields
System crashes / incomplete processing

❌ Wrong types
Runtime errors

❌ No range check
Invalid or absurd data

❌ No pattern validation
Broken formats (emails, IDs)

❌ No allowed values
Unexpected system behavior

❌ No injection protection
Security vulnerabilities 🚨

💡 Production Insight

In real systems, this layer is implemented using:

JSON schema validation
Pydantic / Marshmallow
API gateway validation
Custom validation pipelines

🚀 Final Mental Model

Think of this as:

🧾 Form validation before submission

Like any serious system:

You validate everything
Before allowing it to proceed

<<<Result Guardrails>>>

1️⃣ Error Detection

🧠 Theory

Identifies whether the system output contains:

Execution errors
API failures
Incomplete responses

👉 Instead of blindly passing errors to users, the system detects and handles them gracefully

💡 Example

Tool returns:

{
  "status": "error",
  "message": "Service unavailable"
}
Problem
Raw error exposed to user ❌

Guardrail action
Convert into safe response:

“The system is temporarily unavailable. Please try again later.”

🧩 Analogy

🧑‍🍳 Restaurant kitchen mistake
If a dish burns, you don’t serve it—you fix or remake it

2️⃣ Numeric Sanity

🧠 Theory

Checks whether numeric outputs are:

Logical
Within realistic bounds
Not corrupted or miscalculated

💡 Example

System calculates:

Total price: -5000

Problem
Negative price doesn’t make sense ❌

Guardrail action
Flag or correct:

“Unexpected calculation result. Re-evaluating…”

🧩 Analogy

🧮 Bill at a store
If your bill shows negative ₹5000, you’d question it immediately.

3️⃣ Data Sanitization

🧠 Theory

Cleans output by:

Removing unwanted characters
Stripping unsafe content
Formatting properly

💡 Example

Output:

Hello <script>alert('hack')</script>

Problem
Unsafe script injection ❌

Guardrail action

Sanitized output:

Hello

🧩 Analogy

🚿 Washing vegetables before cooking
Even fresh vegetables are cleaned before use.

4️⃣ PII in Results

🧠 Theory

Ensures that sensitive data is not leaked in the final output, even if:

It came from tools
It exists in databases
It was part of intermediate processing

💡 Example

Tool returns:

{
  "name": "Anil",
  "phone": "9876543210"
}

Problem
Personal data exposed ❌

Guardrail action

Mask it:

{
  "name": "Anil",
  "phone": "***masked***"
}

🧩 Analogy

📄 Sharing a document with redacted sections
Sensitive parts are hidden before sharing

🔗 Combined Post-Processing Guardrail Flow

Tool / System Output
   ↓
[Error Detection]
   ↓
[Numeric Sanity Check]
   ↓
[Data Sanitization]
   ↓
[PII Leakage Check]
   ↓
Safe Final Response

⚠️ What Happens If You Skip These?

❌ No Error Detection
Users see raw system failures

❌ No Numeric Sanity
Illogical outputs (negative values, huge spikes)

❌ No Data Sanitization
Security risks (scripts, injections)

❌ No PII Protection
Data privacy violations 🚨

💡 Production Insight

In real-world systems, this layer is implemented using:

Response validators
Business rule engines
Regex + parsing sanitizers
Privacy filters (NER-based masking)

🚀 Final Mental Model

Think of this as:

📦 Final quality check before delivery

Like an e-commerce system:

Product packed
Quality checked
Sensitive info removed
Then shipped

============================================================
"""

import os
import re
import json
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


class MCPToolGuardrails:
    """
    Complete guardrail suite for MCP Tool servers.
    Validates tool selection, parameters, and results.

    Usage:
        guardrails = MCPToolGuardrails(user_role="customer")

        # Stage 1 — before calling tool
        sel = guardrails.validate_tool_selection(tool_name)

        # Stage 2 — validate parameters
        par = guardrails.validate_parameters(tool_name, params)

        # Stage 3 — validate tool result
        res = guardrails.validate_result(tool_name, tool_result)
    """

    # ── Tool whitelist with schema + permissions ───────────
    ALLOWED_TOOLS = {
        "calculate_emi": {
            "risk":         "low",
            "requires_auth":False,
            "description":  "Calculate EMI for a loan",
            "params": {
                "principal":     {"type": float, "min": 10000,   "max": 100_000_000},
                "annual_rate":   {"type": float, "min": 1.0,     "max": 50.0},
                "tenure_months": {"type": int,   "min": 6,       "max": 360},
            },
        },
        "check_credit_score": {
            "risk":         "high",
            "requires_auth":True,
            "description":  "Check CIBIL credit score",
            "params": {
                "pan_number":     {"type": str, "pattern": r"^[A-Z]{5}\d{4}[A-Z]$"},
                "applicant_name": {"type": str, "min_len": 3, "max_len": 100},
            },
        },
        "get_property_valuation": {
            "risk":         "medium",
            "requires_auth":False,
            "description":  "Get property market valuation",
            "params": {
                "property_address": {"type": str,   "min_len": 10},
                "area_sqft":        {"type": float, "min": 100, "max": 100_000},
                "city":             {"type": str,   "min_len": 3},
            },
        },
        "get_gold_price": {
            "risk":         "low",
            "requires_auth":False,
            "description":  "Fetch live gold price",
            "params": {
                "karat": {"type": int, "allowed_values": [18, 22, 24]},
            },
        },
        "get_current_interest_rates": {
            "risk":         "low",
            "requires_auth":False,
            "description":  "Get current loan interest rates",
            "params": {
                "loan_type": {
                    "type": str,
                    "allowed_values": [
                        "home", "car", "gold", "personal",
                        "education", "vehicle", "all"
                    ],
                },
            },
        },
        "check_loan_eligibility": {
            "risk":         "low",
            "requires_auth":False,
            "description":  "Check FOIR-based loan eligibility",
            "params": {
                "monthly_income":  {"type": float, "min": 5000,    "max": 10_000_000},
                "existing_emis":   {"type": float, "min": 0,       "max": 5_000_000},
                "loan_amount":     {"type": float, "min": 10000,   "max": 100_000_000},
                "tenure_months":   {"type": int,   "min": 6,       "max": 360},
                "annual_rate":     {"type": float, "min": 1.0,     "max": 50.0},
            },
        },
        "get_application_status": {
            "risk":         "medium",
            "requires_auth":True,
            "description":  "Check loan application status",
            "params": {
                "application_id": {"type": str, "min_len": 3, "max_len": 20},
            },
        },
    }

    # ── Tools permanently blocked — never callable ─────────
    BLOCKED_TOOLS = [
        "delete_record", "drop_table", "admin_override",
        "bypass_kyc", "modify_credit_score", "execute_sql",
        "export_all_data", "reset_database",
    ]

    # ── SQL / code injection patterns ─────────────────────
    INJECTION_PATTERNS = [
        r";\s*DROP",     r";\s*DELETE",   r";\s*INSERT",
        r"OR\s+1\s*=\s*1", r"UNION\s+SELECT",
        r"<\s*script",   r"javascript:",  r"eval\s*\(",
        r"__import__",   r"\.\.\./",
    ]

    def __init__(self, user_role: str = "customer"):
        """
        Args:
            user_role: 'customer' | 'agent' | 'admin'
                       Controls which high-risk tools can be accessed.
        """
        self.user_role  = user_role
        self.call_count = {}    # {tool_minute_key: count} for rate limiting
        self.rate_limit = 10    # max calls per tool per minute

    # ──────────────────────────────────────────────────────
    # GUARDRAIL 1 — Tool Selection Validation
    # ──────────────────────────────────────────────────────
    def validate_tool_selection(self, tool_name: str) -> dict:
        """
        4-check tool selection guardrail.

        Check 1: Blocked list — permanently forbidden tools
        Check 2: Whitelist   — only known tools allowed
        Check 3: Permission  — role-based access control
        Check 4: Rate limit  — max N calls per minute
        """
        result = {"passed": True, "reason": None, "checks": []}

        # ── Check 1: Blocked list ──────────────────────────
        if tool_name in self.BLOCKED_TOOLS:
            result["passed"] = False
            result["reason"] = f"Tool '{tool_name}' is permanently blocked"
            result["checks"].append({"name": "blocked_list", "passed": False})
            return result
        result["checks"].append({"name": "blocked_list", "passed": True})

        # ── Check 2: Whitelist ─────────────────────────────
        if tool_name not in self.ALLOWED_TOOLS:
            result["passed"] = False
            result["reason"] = f"Tool '{tool_name}' is not in the allowed list"
            result["checks"].append({"name": "whitelist", "passed": False})
            return result
        result["checks"].append({"name": "whitelist", "passed": True})

        tool_cfg = self.ALLOWED_TOOLS[tool_name]

        # ── Check 3: Role-based permission ────────────────
        requires_auth = tool_cfg.get("requires_auth", False)
        if requires_auth and self.user_role == "customer":
            result["passed"] = False
            result["reason"] = (
                f"Tool '{tool_name}' requires agent/admin role. "
                f"Current role: '{self.user_role}'"
            )
            result["checks"].append({
                "name":   "permission",
                "passed": False,
                "risk":   tool_cfg.get("risk"),
            })
            return result
        result["checks"].append({
            "name":   "permission",
            "passed": True,
            "risk":   tool_cfg.get("risk"),
        })
        # 🧠 Full Example Walkthrough
        # ❌ Case 1: Customer tries restricted tool
        # self.user_role = "customer"

        # tool_cfg = {
        #     "name": "approve_loan",
        #     "requires_auth": True,
        #     "risk": "high"
        # }
        # Flow:
        # requires_auth = True
        # User = "customer"
        # Condition TRUE → BLOCK
        # Output:
        # {
        # "passed": False,
        # "reason": "Tool 'approve_loan' requires agent/admin role. Current role: 'customer'",
        # "checks": [
        #     {
        #     "name": "permission",
        #     "passed": False,
        #     "risk": "high"
        #     }
        # ]
        # }
        # ✅ Case 2: Agent uses restricted tool
        # self.user_role = "agent"
        # Flow:
        # requires_auth = True
        # User = "agent"
        # Condition FALSE → ALLOW
        # Output:
        # {
        # "checks": [
        #     {
        #     "name": "permission",
        #     "passed": True,
        #     "risk": "high"
        #     }
        # ]
        # }
        # ✅ Case 3: Public tool (no auth required)
        # tool_cfg = {
        #     "name": "check_balance",
        #     "requires_auth": False,
        #     "risk": "low"
        # }
        # Anyone (even customer) can use it
        # 🔁 Key Concept: Guardrail Pattern

        # This follows a common production pattern:

        # Check → Validate → Block or Allow → Log

        # ── Check 4: Rate limiting (per tool, per minute) ──
        minute_key= f"{tool_name}_{int(time.time() // 60)}"
        self.call_count[minute_key] = self.call_count.get(minute_key, 0) + 1

        if self.call_count[minute_key] > self.rate_limit:
            result["passed"] = False
            result["reason"] = (
                f"Rate limit exceeded for '{tool_name}': "
                f"{self.call_count[minute_key]}/{self.rate_limit} per minute"
            )
            result["checks"].append({"name": "rate_limit", "passed": False})
            return result
        result["checks"].append({
            "name":              "rate_limit",
            "passed":            True,
            "calls_this_minute": self.call_count[minute_key],
        })

        return result

        # 🧠 Full Example Walkthrough
        # Setup:
        # self.rate_limit = 3
        # tool_name = "transfer_money"
        # ⏱️ Calls within same minute
        # ✅ Call 1:
        # count = 1 → allowed
        # {
        # "passed": True,
        # "checks": [{"name": "rate_limit", "passed": True, "calls_this_minute": 1}]
        # }
        # ✅ Call 2:
        # count = 2 → allowed
        # ✅ Call 3:
        # count = 3 → allowed
        # ❌ Call 4:
        # count = 4 > 3 → BLOCKED

        # Output:

        # {
        # "passed": False,
        # "reason": "Rate limit exceeded for 'transfer_money': 4/3 per minute",
        # "checks": [{"name": "rate_limit", "passed": False}]
        # }
        # 🔁 Key Concept: Time Bucketing

        # Instead of tracking every second:

        # 👉 It groups calls into 1-minute buckets

        # Time	Bucket ID
        # 10:01:10	10:01
        # 10:01:45	10:01
        # 10:02:01	10:02

    # ──────────────────────────────────────────────────────
    # GUARDRAIL 2 — Parameter Validation
    # ──────────────────────────────────────────────────────
    def validate_parameters(self, tool_name: str, params: dict) -> dict:
        """
        6-check parameter guardrail.

        Check 1: Required params present
        Check 2: Type coercion and validation
        Check 3: Numeric range (min/max)
        Check 4: String length (min_len/max_len)
        Check 5: Regex pattern matching
        Check 6: Allowed values list
        Check 7: Injection in string params
        """
        result = {
            "passed":           True,
            "reason":           None,
            "sanitized_params": params.copy(),
            "checks":           [],
        }

        if tool_name not in self.ALLOWED_TOOLS:
            result["passed"] = False
            result["reason"] = f"Unknown tool: {tool_name}"
            return result

        schema = self.ALLOWED_TOOLS[tool_name]["params"]

        for param_name, param_schema in schema.items():
            value = params.get(param_name)

            # ── Check 1: Required param ────────────────────
            if value is None:
                result["passed"] = False
                result["reason"] = f"Required parameter missing: '{param_name}'"
                result["checks"].append({"name": f"required_{param_name}", "passed": False})
                return result

            # ── Check 2: Type validation + coercion ────────
            expected_type = param_schema.get("type")
            if expected_type and not isinstance(value, expected_type):
                try:
                    value = expected_type(value)
                    result["sanitized_params"][param_name] = value
                except (ValueError, TypeError):
                    result["passed"] = False
                    result["reason"] = (
                        f"Wrong type for '{param_name}': "
                        f"expected {expected_type.__name__}, got {type(value).__name__}"
                    )
                    result["checks"].append({"name": f"type_{param_name}", "passed": False})
                    return result
            result["checks"].append({"name": f"type_{param_name}", "passed": True})

            # ── Check 3: Numeric range ─────────────────────
            if isinstance(value, (int, float)):
                min_v = param_schema.get("min")
                max_v = param_schema.get("max")
                if min_v is not None and value < min_v:
                    result["passed"] = False
                    result["reason"] = f"'{param_name}' = {value} is below minimum {min_v}"
                    result["checks"].append({"name": f"range_{param_name}", "passed": False})
                    return result
                if max_v is not None and value > max_v:
                    result["passed"] = False
                    result["reason"] = f"'{param_name}' = {value} exceeds maximum {max_v}"
                    result["checks"].append({"name": f"range_{param_name}", "passed": False})
                    return result
                result["checks"].append({"name": f"range_{param_name}", "passed": True})

            # ── String checks ──────────────────────────────
            if isinstance(value, str):

                # ── Check 4: String length ─────────────────
                min_len = param_schema.get("min_len", 0)
                max_len = param_schema.get("max_len", 10_000)
                if not (min_len <= len(value) <= max_len):
                    result["passed"] = False
                    result["reason"] = (
                        f"'{param_name}' length {len(value)} "
                        f"out of range [{min_len}, {max_len}]"
                    )
                    result["checks"].append({"name": f"length_{param_name}", "passed": False})
                    return result

                # ── Check 5: Regex pattern ─────────────────
                pattern = param_schema.get("pattern")
                if pattern and not re.match(pattern, value, re.IGNORECASE):
                    result["passed"] = False
                    result["reason"] = f"'{param_name}' does not match required format"
                    result["checks"].append({"name": f"pattern_{param_name}", "passed": False})
                    return result

                result["checks"].append({"name": f"string_{param_name}", "passed": True})

                # ── Check 7: Injection in strings ──────────
                for inj in self.INJECTION_PATTERNS:
                    if re.search(inj, value, re.IGNORECASE):
                        result["passed"] = False
                        result["reason"] = f"Injection attempt in '{param_name}'"
                        result["checks"].append({"name": f"injection_{param_name}", "passed": False})
                        return result

            # ── Check 6: Allowed values ────────────────────
            allowed = param_schema.get("allowed_values")
            if allowed is not None and value not in allowed:
                result["passed"] = False
                result["reason"] = (
                    f"'{param_name}' = '{value}' not in allowed values: {allowed}"
                )
                result["checks"].append({"name": f"allowed_{param_name}", "passed": False})
                return result
            if allowed:
                result["checks"].append({"name": f"allowed_{param_name}", "passed": True})

        return result

    # ──────────────────────────────────────────────────────
    # GUARDRAIL 3 — Result Validation
    # ──────────────────────────────────────────────────────
    def validate_result(self, tool_name: str, tool_result: dict) -> dict:
        """
        3-check result guardrail.

        Check 1: No error field in result
        Check 2: Numeric sanity (tool-specific)
        Check 3: Sanitize internal fields before returning
        """
        validation = {
            "passed":     True,
            "reason":     None,
            "safe_result":tool_result,
            "checks":     [],
        }

        # ── Check 1: Error field detection ────────────────
        if "error" in tool_result:
            validation["passed"] = False
            validation["reason"] = f"Tool returned error: {tool_result['error']}"
            validation["checks"].append({"name": "no_error", "passed": False})
            return validation
        validation["checks"].append({"name": "no_error", "passed": True})

        # ── Check 2: Tool-specific numeric sanity ──────────
        if tool_name == "calculate_emi":
            emi       = tool_result.get("monthly_emi", 0)
            principal = tool_result.get("principal", 1)
            if emi <= 0:
                validation["passed"] = False
                validation["reason"] = "EMI is zero or negative — calculation error"
                validation["checks"].append({"name": "emi_sanity", "passed": False})
                return validation
            if emi > principal:
                validation["passed"] = False
                validation["reason"] = "EMI exceeds principal — calculation error"
                validation["checks"].append({"name": "emi_sanity", "passed": False})
                return validation
            validation["checks"].append({"name": "emi_sanity", "passed": True})

        # ── Check 3: Strip internal/debug fields ───────────
        internal_keys = ["_debug", "_internal_id", "db_record", "_raw_response"]
        safe = {k: v for k, v in tool_result.items() if k not in internal_keys}
        validation["safe_result"] = safe
        validation["checks"].append({"name": "sanitize", "passed": True})

        return validation

    # ──────────────────────────────────────────────────────
    # FULL PIPELINE — run all 3 stages
    # ──────────────────────────────────────────────────────
    def run_full_pipeline(
        self,
        tool_name:   str,
        params:      dict,
        tool_result: dict,
    ) -> dict:
        """Run all 3 MCP guardrail stages in sequence."""
        print(f"\n{'='*55}")
        print(f" MCP Guardrails: {tool_name}")
        print(f"{'='*55}")

        # Stage 1
        print("\n[Stage 1] Tool Selection...")
        sel = self.validate_tool_selection(tool_name)
        print(f"  Status : {'✅ PASS' if sel['passed'] else '❌ BLOCK'}")
        if not sel["passed"]:
            return {"blocked": True, "stage": "tool_selection", "reason": sel["reason"]}

        # Stage 2
        print("[Stage 2] Parameters...")
        par = self.validate_parameters(tool_name, params)
        print(f"  Status : {'✅ PASS' if par['passed'] else '❌ BLOCK'}")
        if not par["passed"]:
            return {"blocked": True, "stage": "parameters", "reason": par["reason"]}

        # Stage 3
        print("[Stage 3] Result...")
        res = self.validate_result(tool_name, tool_result)
        print(f"  Status : {'✅ PASS' if res['passed'] else '❌ BLOCK'}")
        if not res["passed"]:
            return {"blocked": True, "stage": "result", "reason": res["reason"]}

        return {"blocked": False, "safe_result": res["safe_result"]}


# ══════════════════════════════════════════════════════════
#  DEMO
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    guardrails = MCPToolGuardrails(user_role="customer")

    print("\n" + "█"*55)
    print("  MCP TOOL GUARDRAILS — TEST CASES")
    print("█"*55)

    test_cases = [
        # (tool_name, params, label)
        ("calculate_emi",
         {"principal": 5_000_000, "annual_rate": 8.5, "tenure_months": 240},
         "valid EMI calculation"),

        ("calculate_emi",
         {"principal": -1000, "annual_rate": 8.5, "tenure_months": 240},
         "negative principal"),

        ("delete_record",
         {"id": 123},
         "blocked tool"),

        ("get_gold_price",
         {"karat": 22},
         "valid gold price"),

        ("get_gold_price",
         {"karat": 15},
         "invalid karat"),

        ("check_credit_score",
         {"pan_number": "ABCDE1234F", "applicant_name": "Anil Kumar"},
         "auth required for customer role"),

        ("calculate_emi",
         {"principal": 5_000_000, "annual_rate": 8.5, "tenure_months": 240, "sql": "'; DROP TABLE loans;--"},
         "SQL injection in params"),
    ]

    for tool, params, label in test_cases:
        print(f"\n[{label}]")
        print(f"  Tool   : {tool}")

        # Stage 1
        sel = guardrails.validate_tool_selection(tool)
        if not sel["passed"]:
            print(f"  Status : ❌ BLOCK (tool selection)")
            print(f"  Reason : {sel['reason']}")
            continue

        # Stage 2
        par = guardrails.validate_parameters(tool, params)
        print(f"  Status : {'✅ PASS' if par['passed'] else '❌ BLOCK (parameters)'}")
        if not par["passed"]:
            print(f"  Reason : {par['reason']}")
        else:
            print(f"  Checks : {len(par['checks'])} passed")