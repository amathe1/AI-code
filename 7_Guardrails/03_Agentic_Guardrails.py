"""
============================================================
 AGENTIC AI GUARDRAILS — Bank Loan AI System
============================================================

THEORY:
-------
Agentic AI guardrails are the most complex — they protect
systems that take AUTONOMOUS MULTI-STEP ACTIONS.

Unique risks compared to RAG and MCP:
  - Recursive loops (agent calls itself forever)
  - Unintended side effects (agent takes wrong action)
  - Goal misalignment (optimizes wrong objective)
  - Privilege escalation (gains unintended access)
  - Cascading failures (one bad step corrupts all future steps)

GUARDRAIL CHECKPOINTS:

[Start]
  │
  ▼
┌──────────────────────┐
│ 1. GOAL GUARDRAIL    │ ← Is the goal valid and safe?
│    - Format check    │   (runs once at start)
│    - Dangerous ops   │
│    - LLM risk assess │
│    - Human approval  │
└─────────┬────────────┘
          │
          ▼ (enter loop)
┌──────────────────────┐
│ 2. STEP GUARDRAIL    │ ← Is this action safe?
│    - Whitelist       │   (runs before EVERY step)
│    - Max steps       │
│    - Runtime limit   │
│    - Loop detection  │
│    - Error threshold │
│    - Human approval  │
└─────────┬────────────┘
          │
     (execute action)
          │
          ▼
┌──────────────────────┐
│ 3. TERMINATION GUARD │ ← Should agent stop?
│    - Max steps       │   (runs after every step)
│    - Goal achieved   │
│    - Error count     │
│    - LLM assessment  │
└─────────┬────────────┘
          │  (if not done, loop back to Step Guardrail)
          │  (if done, proceed)
          ▼
┌──────────────────────┐
│ 4. AUDIT GUARDRAIL   │ ← Final safety review
│    - Full audit log  │   (runs once at end)
│    - Irreversible ops│
│    - Human review    │
│    - Side effect log │
└──────────────────────┘

<<<Goal Guardrails>>>

1️⃣ Format Check (runs once at start)
🧠 Theory

Validates whether the goal/request is structured, clear, and actionable.

👉 Ensures:

Required components are present
No ambiguity
Proper format (JSON, instruction schema, etc.)

💡 Example

Expected format:

{
  "goal": "...",
  "constraints": "...",
  "output_format": "..."
}

User provides:

"Do something with data"

Problem
Vague, unstructured ❌

Guardrail action

“Please provide a clear goal with required fields (goal, constraints, output format)”

🧩 Analogy

🗺️ Starting a journey
You can’t begin without a clear destination and plan

2️⃣ Dangerous Operations

🧠 Theory

Detects whether the goal involves high-risk or harmful actions.

👉 Examples:

Deleting data
Financial transactions
System modifications

💡 Example

User goal:

“Automatically remove all inactive user accounts”

Problem
Destructive action ❌

Guardrail action
Flag or block:

“This goal involves potentially destructive operations”

🧩 Analogy

⚠️ Heavy machinery warning
Before operating, system checks:
“Is this safe to proceed?”

3️⃣ LLM Risk Assessment

🧠 Theory

Uses an LLM (or classifier) to evaluate:

Risk level of the goal
Ambiguity
Ethical concerns

👉 Outputs something like:

Low risk ✅
Medium risk ⚠️
High risk 🚨

💡 Example

Goal:

“Collect user feedback and summarize”

→ Low risk ✅

Goal:

“Scrape competitor data and replicate strategy”

→ High risk 🚨

Guardrail action
Based on score:
Allow
Restrict
Escalate

🧩 Analogy

🛂 Airport security screening
Every passenger is assessed:

Low risk → pass
High risk → further checks

4️⃣ Human Approval
🧠 Theory

Requires manual confirmation for sensitive or high-risk goals.

👉 Ensures:

Human-in-the-loop control
Accountability

💡 Example

Goal:

“Send bulk emails to all customers”

Risk
Spam / compliance issues ❌

Guardrail action
Pause execution:

“Awaiting human approval before proceeding”

🧩 Analogy

✍️ Manager approval for critical actions
Some decisions must be signed off before execution.

🔗 Combined Agentic Goal Guardrail Flow

User Goal
   ↓
[Format Check]
   ↓
[Dangerous Operations Detection]
   ↓
[LLM Risk Assessment]
   ↓
[Human Approval (if needed)]
   ↓
Agent Execution Starts

⚠️ What Happens If You Skip These?

❌ No Format Check
Agent misunderstands goal

❌ No Dangerous Ops Check
Destructive actions executed

❌ No Risk Assessment
Unsafe goals slip through

❌ No Human Approval
No control over critical actions

💡 Production Insight

In real systems, this layer is implemented using:

JSON schema validation (format check)
Rule engines (dangerous ops)
LLM classifiers (risk scoring)
Approval workflows (Slack / email / dashboard)

🚀 Final Mental Model

Think of this as:

🚦 “Go / No-Go Decision Before Starting the Mission”

Like a rocket launch:

System checks everything
If anything looks risky → HOLD 🚫
Only then → LAUNCH 🚀

<<<Step Guardrails>>>

1️⃣ STEP GUARDRAIL — Is this action safe?
🧠 Theory

A central checkpoint before every step:

Validates the planned action
Ensures it aligns with goal + policies
Acts like a runtime “gatekeeper”

💡 Example

Agent decides:

“Download all user data and send externally”

Problem
Unsafe step ❌

Guardrail action
Block or modify step:

“This action violates policy and is not allowed”

🧩 Analogy

🚦 Traffic signal at every junction
Even if your journey is valid, each turn must be checked before proceeding

2️⃣ Whitelist (runs before EVERY step)
🧠 Theory

Only allows actions/tools that are pre-approved at each step.

💡 Example

Allowed actions:

read_data
generate_summary

Agent tries:

delete_database

Guardrail action
Deny step immediately

🧩 Analogy

🎮 Game rules
You can only use allowed moves, not invent new ones

3️⃣ Max Steps
🧠 Theory

Limits how many steps an agent can take in a single task.

👉 Prevents:

Infinite reasoning loops
Over-complex execution

💡 Example

Limit:

Max 10 steps

Agent reaches step 11

Guardrail action

“Maximum step limit reached. Stopping execution.”

🧩 Analogy

🧭 Treasure hunt with limited moves
You only get 10 chances to reach the goal

4️⃣ Runtime Limit

🧠 Theory

Restricts total execution time of the agent.

💡 Example

Limit:

30 seconds

Agent runs for 45 seconds

Guardrail action

“Execution timed out”

🧩 Analogy

⏱️ Exam time limit
You must finish within the allotted time

5️⃣ Loop Detection
🧠 Theory

Detects repeated patterns indicating the agent is stuck in a loop.

💡 Example

Agent repeatedly:

Fetch data
Re-fetch same data
Repeat…
Problem
Infinite loop ❌

Guardrail action
Stop execution:

“Loop detected. Terminating process.”

🧩 Analogy

🔄 GPS rerouting loop
If you keep circling the same road, system says:
“Something’s wrong—stop and re-evaluate”

6️⃣ Error Threshold
🧠 Theory

Stops execution if too many errors occur consecutively or cumulatively.

💡 Example

Limit:

Max 3 errors

Agent encounters:

API failure
Validation error
Timeout

Guardrail action

“Error threshold exceeded. Stopping execution.”

🧩 Analogy

⚠️ Machine auto-shutdown
If a machine fails repeatedly, it shuts down to prevent damage

7️⃣ Human Approval
🧠 Theory

Requires manual approval at specific steps, not just at the beginning.

👉 Useful for:

High-impact intermediate actions
Financial or data-sensitive steps

💡 Example

Agent step:

“Send report to all customers”

Guardrail action
Pause:

“Waiting for human approval before proceeding”

🧩 Analogy

✍️ Multi-level approval workflow

Even mid-process, some steps need manager sign-off

🔗 Combined Step Guardrail Flow

Agent Step Planned
   ↓
[Step Safety Check]
   ↓
[Whitelist Validation]
   ↓
[Max Steps Check]
   ↓
[Runtime Limit Check]
   ↓
[Loop Detection]
   ↓
[Error Threshold Check]
   ↓
[Human Approval (if needed)]
   ↓
Execute Step / Block

⚠️ What Happens If You Skip These?

❌ No Step Guardrail
Unsafe actions executed mid-process

❌ No Whitelist
Unauthorized tools used

❌ No Max Steps
Infinite reasoning loops

❌ No Runtime Limit
System hangs / high cost

❌ No Loop Detection
Agent stuck forever

❌ No Error Threshold
Repeated failures without stopping

❌ No Human Approval
Critical actions executed blindly

💡 Production Insight

In real-world systems, these are implemented using:

Agent state tracking
Execution monitors
Observability tools (logs, traces)
Policy engines
Human-in-the-loop workflows

🚀 Final Mental Model

Think of step guardrails as:

🧭 Real-time navigation control during execution

Not just:

“Is the plan safe?” (goal guardrails)

But:

“Is every step along the way still safe?”

<<<Termination Guardrails>>>

1️⃣ Max Steps (runs after every step)
🧠 Theory

Defines a hard upper limit on how many steps an agent can execute.

👉 Even if everything is valid, the agent must stop after a certain number of steps.

💡 Example

Limit:

Max steps = 10

Agent reaches:

Step 10 → OK
Step 11 → ❌ stop

Guardrail action

“Maximum steps reached. Terminating execution.”

🧩 Analogy

🎯 Limited moves in a game
You only get a fixed number of turns—after that, the game ends.

2️⃣ Goal Achieved
🧠 Theory

Checks whether the original objective has been successfully completed.

👉 If yes:

Stop immediately
Avoid unnecessary extra steps

💡 Example

Goal:

“Generate a summary report”

Agent:

Retrieves data
Creates report ✅

Problem (without guardrail)
Agent continues doing irrelevant steps ❌

Guardrail action

“Goal achieved. Stopping execution.”

🧩 Analogy

🏁 Race finish line
Once you cross the finish line, you don’t keep running.

3️⃣ Error Count
🧠 Theory

Tracks total number of errors during execution and stops if it exceeds a threshold.

💡 Example

Limit:

Max errors = 3

Agent encounters:

API failure
Timeout
Validation error

Guardrail action

“Too many errors. Terminating process.”

🧩 Analogy

⚠️ Machine safety shutdown
If a machine fails repeatedly, it stops to prevent damage.

4️⃣ LLM Assessment
🧠 Theory

Uses an LLM (or evaluator) to decide:

Is the task complete?
Is further execution useful?
Is the agent stuck or drifting?

💡 Example

Agent keeps generating similar outputs repeatedly.

LLM evaluates:

“No meaningful progress detected”

Guardrail action

“Stopping execution due to lack of progress.”

🧩 Analogy

🧠 Human supervisor
Someone watching and saying:
“Enough—you’re done or not making progress.”

🔗 Combined Termination Guardrail Flow

After Each Step
   ↓
[Max Steps Check]
   ↓
[Goal Achieved Check]
   ↓
[Error Count Check]
   ↓
[LLM Assessment]
   ↓
Continue OR Terminate

⚠️ What Happens If You Skip These?

❌ No Max Steps
Infinite execution → high cost

❌ No Goal Check
Agent keeps working unnecessarily

❌ No Error Count
Endless retries without success

❌ No LLM Assessment
Agent stuck in low-value loops

💡 Production Insight

In real systems, combine:

Deterministic rules (steps, errors)
Intelligent checks (LLM evaluation)

👉 This gives both:

Control
Flexibility

🚀 Final Mental Model

Think of termination guardrails as:

🛑 “Stop conditions in an automated system”

Like:

Cooking timer → stops when done
Elevator → stops at the right floor
Navigation → ends when destination is reached

<<<Audit Guardrails>>>

1️⃣ Full Audit Log (runs once at end)
🧠 Theory

Captures a complete record of everything that happened:

Inputs
Decisions
Tool calls
Outputs
Errors

👉 This creates end-to-end traceability

💡 Example

At the end of a workflow, system logs:

{
  "user_request": "...",
  "steps_executed": [...],
  "tools_used": [...],
  "final_output": "...",
  "timestamp": "..."
}

Why it matters
Debugging
Compliance audits
Reproducibility

🧩 Analogy

📹 CCTV recording
Everything is recorded so you can review what happened later

2️⃣ Irreversible Operations
🧠 Theory

Flags actions that cannot be undone:

Data deletion
Financial transactions
External communications

👉 These require special attention

💡 Example

System performed:

“Deleted 10,000 records”

Guardrail action

Highlight in audit log:

“⚠️ Irreversible operation detected”

🧩 Analogy

🧨 Breaking a glass
Once broken, you can’t restore it back

3️⃣ Human Review
🧠 Theory

Triggers manual review after execution, especially for:

High-risk workflows
Sensitive outcomes

👉 Ensures:

Accountability
Final validation

💡 Example

After completing task:

“Report generated and sent to clients”

Guardrail action

Send for review:

“Awaiting human validation before final confirmation”

🧩 Analogy

✍️ Final approval signature
Even after work is done, someone must sign off

4️⃣ Side Effect Log
🧠 Theory

Tracks indirect effects of actions:

Data updates
Notifications sent
External API calls
State changes

👉 Not just what was intended, but what actually changed

💡 Example

Workflow result:

Report generated
Email sent
Database updated
Guardrail action

Log:

{
  "side_effects": [
    "email_sent",
    "database_updated",
    "notification_triggered"
  ]
}
🧩 Analogy

🌊 Ripple effect in water
One action creates multiple downstream effects

🔗 Combined Audit Guardrail Flow

Workflow Completed
   ↓
[Full Audit Log Generated]
   ↓
[Irreversible Ops Identified]
   ↓
[Side Effects Captured]
   ↓
[Human Review (if required)]
   ↓
Final Approval / Archive

⚠️ What Happens If You Skip These?

❌ No Audit Log
No traceability → hard to debug

❌ No Irreversible Ops Tracking
Risky actions go unnoticed

❌ No Human Review
No accountability

❌ No Side Effect Logging
Hidden impacts → system inconsistency

💡 Production Insight

In real systems, this layer is implemented using:

Logging frameworks
Observability tools (traces, spans)
Audit databases
Approval workflows

👉 Often integrated with:

Compliance systems
Governance dashboards

🚀 Final Mental Model

Think of audit guardrails as:

📊 “Final report + compliance check after execution”

Like:

Bank transaction statement
Flight black box recording
Medical operation report

Everything is:

Recorded
Reviewed
Verified

============================================================
"""

import os
import re
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client         = OpenAI(api_key=OPENAI_API_KEY)


class AgentGuardrails:
    """
    Comprehensive guardrails for Agentic AI systems.
    Designed for multi-step autonomous agents (LangGraph, etc.)

    Usage:
        guards = AgentGuardrails(max_steps=10, max_errors=3)

        # Once at start:
        goal_ok = guards.validate_goal(goal, context)

        # Before every step:
        step_ok = guards.validate_step(action, state)

        # After every step:
        stop = guards.should_terminate(state, goal)
        if stop["should_stop"]:
            break

        # Once at end:
        audit = guards.audit_final_output(final_result)
    """

    # ── Actions the agent is allowed to take ──────────────
    ALLOWED_ACTIONS = {
        "retrieve_documents":  {"risk": "low",    "reversible": True},
        "calculate_emi":       {"risk": "low",    "reversible": True},
        "check_eligibility":   {"risk": "low",    "reversible": True},
        "fetch_rates":         {"risk": "low",    "reversible": True},
        "generate_answer":     {"risk": "low",    "reversible": True},
        "evaluate_response":   {"risk": "low",    "reversible": True},
        "send_notification":   {"risk": "medium", "reversible": False},
        "create_application":  {"risk": "high",   "reversible": False},
        "update_record":       {"risk": "high",   "reversible": False},
        "schedule_callback":   {"risk": "medium", "reversible": True},
    }

    # ── High-risk actions that require human approval ──────
    REQUIRES_HUMAN_APPROVAL = [
        "create_application",
        "update_record",
        "send_notification",
    ]

    # ── Dangerous goal keywords ────────────────────────────
    DANGEROUS_KEYWORDS = [
        "delete all", "drop database", "override security",
        "bypass authentication", "send to all users",
        "mass update", "truncate table",
    ]

    def __init__(self, max_steps: int = 10, max_errors: int = 3):
        """
        Args:
            max_steps:  Hard limit on agent loop iterations
            max_errors: Max errors before forced termination
        """
        self.max_steps   = max_steps
        self.max_errors  = max_errors
        self.step_count  = 0
        self.error_count = 0
        self.action_log  = []         # complete audit trail
        self.state_hashes= []         # for loop detection
        self.start_time  = time.time()
        self.max_runtime = 120        # seconds max

    # ──────────────────────────────────────────────────────
    # GUARDRAIL 1 — Goal Validation (runs once at start)
    # ──────────────────────────────────────────────────────
    def validate_goal(self, goal: str, context: dict) -> dict:
        """
        4-check goal guardrail (runs once before agent starts).

        Check 1: Goal length and format
        Check 2: Dangerous operation keywords
        Check 3: LLM-based risk assessment
        Check 4: High-risk goals flagged for human review
        """
        result = {
            "passed":     True,
            "reason":     None,
            "risk_level": "low",
            "concerns":   [],
            "checks":     [],
        }

        # ── Check 1: Format ────────────────────────────────
        if len(goal.strip()) < 10:
            result["passed"] = False
            result["reason"] = "Goal too vague — please provide more detail"
            result["checks"].append({"name": "goal_format", "passed": False})
            return result
        result["checks"].append({"name": "goal_format", "passed": True})

        # ── Check 2: Dangerous keyword scan ───────────────
        for kw in self.DANGEROUS_KEYWORDS:
            if kw.lower() in goal.lower():
                result["passed"] = False
                result["reason"] = f"Dangerous operation detected in goal: '{kw}'"
                result["checks"].append({"name": "dangerous_goal", "passed": False, "keyword": kw})
                return result
        result["checks"].append({"name": "dangerous_goal", "passed": True})

        # ── Check 3: LLM risk assessment ──────────────────
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Assess the risk of this agent goal for a bank loan system.
Return JSON only:
{
  "risk_level": "low" | "medium" | "high" | "critical",
  "concerns": ["concern1", "concern2"],
  "safe_to_proceed": true/false
}"""
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Goal: {goal}\n\n"
                            f"Context: {json.dumps(context, default=str)}"
                        )
                    }
                ],
                temperature=0,
                max_tokens=150,
            )
            raw  = resp.choices[0].message.content.strip()
            raw  = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)

            result["risk_level"] = data.get("risk_level", "low")
            result["concerns"]   = data.get("concerns", [])

            if not data.get("safe_to_proceed", True) or data.get("risk_level") == "critical":
                result["passed"] = False
                result["reason"] = f"Critical risk goal: {data.get('concerns', [])}"
                result["checks"].append({"name": "risk_assessment", "passed": False})
                return result

            result["checks"].append({
                "name":       "risk_assessment",
                "passed":     True,
                "risk_level": result["risk_level"],
                "concerns":   result["concerns"],
            })

        except Exception:
            result["checks"].append({"name": "risk_assessment", "passed": True, "note": "skipped"})

        # ── Check 4: Flag medium/high for human review ────
        if result["risk_level"] in ["high", "medium"]:
            result["requires_human_approval"] = True
            result["checks"].append({
                "name":  "human_approval_flag",
                "passed":True,
                "note":  f"Risk={result['risk_level']} — flagged for human review before proceeding",
            })

        return result

    # ──────────────────────────────────────────────────────
    # GUARDRAIL 2 — Per-Step Validation (runs before EVERY step)
    # ──────────────────────────────────────────────────────
    def validate_step(self, action: str, state: dict) -> dict:
        """
        6-check step guardrail (runs before every agent action).

        Check 1: Action whitelist
        Check 2: Max steps not exceeded
        Check 3: Max runtime not exceeded
        Check 4: Loop detection via state hashing
        Check 5: Error threshold not exceeded
        Check 6: Human approval for high-risk actions
        """
        result = {"passed": True, "reason": None, "checks": []}
        self.step_count += 1

        # ── Check 1: Action whitelist ──────────────────────
        if action not in self.ALLOWED_ACTIONS:
            result["passed"] = False
            result["reason"] = f"Action '{action}' is not in the allowed list"
            result["checks"].append({"name": "action_whitelist", "passed": False})
            self._log_action(action, state, "blocked_not_allowed")
            return result
        result["checks"].append({
            "name":   "action_whitelist",
            "passed": True,
            "risk":   self.ALLOWED_ACTIONS[action]["risk"],
        })

        # ── Check 2: Max steps ─────────────────────────────
        if self.step_count > self.max_steps:
            result["passed"] = False
            result["reason"] = f"Max steps exceeded: {self.step_count}/{self.max_steps}"
            result["checks"].append({"name": "max_steps", "passed": False})
            self._log_action(action, state, "blocked_max_steps")
            return result
        result["checks"].append({
            "name":    "max_steps",
            "passed":  True,
            "current": self.step_count,
            "max":     self.max_steps,
        })

        # ── Check 3: Max runtime ───────────────────────────
        elapsed = time.time() - self.start_time
        if elapsed > self.max_runtime:
            result["passed"] = False
            result["reason"] = f"Max runtime exceeded: {elapsed:.0f}s/{self.max_runtime}s"
            result["checks"].append({"name": "max_runtime", "passed": False})
            return result
        result["checks"].append({
            "name":    "max_runtime",
            "passed":  True,
            "elapsed": round(elapsed, 1),
        })

        # ── Check 4: Loop detection ────────────────────────
        # Hash current state → compare against recent history
        # If same hash seen in last 5 states → infinite loop detected
        state_hash = hashlib.md5(
            json.dumps(state, sort_keys=True, default=str).encode()
        ).hexdigest()

        if state_hash in self.state_hashes[-5:]:
            result["passed"] = False
            result["reason"] = (
                "Infinite loop detected — agent is repeating the same state. "
                "Terminating for safety."
            )
            result["checks"].append({"name": "loop_detection", "passed": False})
            self._log_action(action, state, "blocked_loop")
            return result
        self.state_hashes.append(state_hash)
        result["checks"].append({"name": "loop_detection", "passed": True})

        # 🧠 Full Example Walkthrough
        #     Scenario: Agent stuck in loop
        #     Step 1:
        #     state = {"step": "retry_api", "attempt": 1}

        #     Hash added:

        #     self.state_hashes = ["h1"]
        #     Step 2:
        #     state = {"step": "retry_api", "attempt": 2}
        #     self.state_hashes = ["h1", "h2"]
        #     Step 3:
        #     state = {"step": "retry_api", "attempt": 1}
        #     Hash = "h1" again
        #     "h1" is in last 5 states → LOOP DETECTED
        #     Output:
        #     {
        #     "passed": False,
        #     "reason": "Infinite loop detected — agent is repeating the same state. Terminating for safety.",
        #     "checks": [
        #         {"name": "loop_detection", "passed": False}
        #     ]
        #     }
        #     🔁 Why hashing instead of direct comparison?

        #     Comparing full states is:

        #     ❌ slow
        #     ❌ error-prone (ordering issues)

        #     Hashing gives:

        #     ✅ fast comparison
        #     ✅ fixed-size representation
        #     ✅ consistent matching
        #     ⚠️ Important Design Insights
        #     1. Only last 5 states checked
        #     self.state_hashes[-5:]
        #     Avoids false positives from long history
        #     Focuses on recent loops
        #     2. MD5 is used (not for security)
        #     Here it's used for fingerprinting, not encryption
        #     Faster than stronger hashes like SHA256
        #     3. Possible limitation

        #     If state changes slightly:

        #     {"step": "retry", "attempt": 1}
        #     {"step": "retry", "attempt": 2}

        #     → Different hashes → loop not detected

        #     👉 Advanced systems use:

        #     similarity checks
        #     semantic state comparison
        #     🏦 Real-world Use Case (Agentic AI / MCP)

        #     In your loan processing pipeline, this prevents:

        #     🔁 endless retry loops (API failures)
        #     🔁 repeated validation cycles
        #     🔁 stuck decision nodes
        #     🚀 Simple Analogy

        #     Think of this like:

        #     👉 A security system watching your steps

        #     If you walk:
        #     Room A → Room B → Room A → Room B → Room A

        #     It detects:
        #     👉 “You are going in circles” → stops you

        # ── Check 5: Error threshold ───────────────────────
        if self.error_count >= self.max_errors:
            result["passed"] = False
            result["reason"] = (
                f"Error threshold exceeded: {self.error_count}/{self.max_errors} errors. "
                "Terminating to prevent cascading failures."
            )
            result["checks"].append({"name": "error_threshold", "passed": False})
            return result
        result["checks"].append({
            "name":   "error_threshold",
            "passed": True,
            "errors": self.error_count,
            "max":    self.max_errors,
        })

        # ── Check 6: Human approval for high-risk ─────────
        if action in self.REQUIRES_HUMAN_APPROVAL:
            result["requires_approval"] = True
            result["checks"].append({
                "name":   "human_approval_required",
                "passed": True,
                "action": action,
                "note":   f"Action '{action}' is irreversible — requires human sign-off",
            })

        # Log approved action
        self._log_action(action, state, "approved")
        return result

    # ──────────────────────────────────────────────────────
    # GUARDRAIL 3 — Termination Check (runs after every step)
    # ──────────────────────────────────────────────────────
    def should_terminate(self, state: dict, goal: str) -> dict:
        """
        4-check termination guardrail (runs after each step).

        Check 1: Max steps reached
        Check 2: Too many errors
        Check 3: Runtime exceeded
        Check 4: LLM assessment of goal completion
        """
        result = {
            "should_stop":   False,
            "reason":        None,
            "goal_achieved": False,
            "checks":        [],
        }

        # ── Check 1: Max steps ─────────────────────────────
        if self.step_count >= self.max_steps:
            result["should_stop"] = True
            result["reason"]      = f"Reached maximum steps: {self.max_steps}"
            result["checks"].append({"name": "max_steps_termination", "terminate": True})
            return result

        # ── Check 2: Error count ───────────────────────────
        if self.error_count >= self.max_errors:
            result["should_stop"] = True
            result["reason"]      = f"Error limit reached: {self.error_count}/{self.max_errors}"
            result["checks"].append({"name": "error_termination", "terminate": True})
            return result

        # ── Check 3: Runtime ───────────────────────────────
        elapsed = time.time() - self.start_time
        if elapsed > self.max_runtime:
            result["should_stop"] = True
            result["reason"]      = f"Runtime limit: {elapsed:.0f}s/{self.max_runtime}s"
            result["checks"].append({"name": "runtime_termination", "terminate": True})
            return result

        # ── Check 4: LLM goal completion assessment ────────
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Assess if the agent goal has been achieved.
Return JSON only:
{"goal_achieved": true/false, "reason": "one sentence explanation"}"""
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Goal: {goal}\n\n"
                            f"Current state:\n{json.dumps(state, default=str)[:500]}"
                        )
                    }
                ],
                temperature=0,
                max_tokens=100,
            )
            raw  = resp.choices[0].message.content.strip()
            raw  = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)

            if data.get("goal_achieved", False):
                result["should_stop"]    = True
                result["goal_achieved"]  = True
                result["reason"]         = f"Goal achieved: {data.get('reason', '')}"
                result["checks"].append({"name": "goal_achieved", "terminate": True})
            else:
                result["checks"].append({"name": "goal_check", "terminate": False})

        except Exception:
            result["checks"].append({"name": "goal_check", "terminate": False, "note": "skipped"})

        return result

    # ──────────────────────────────────────────────────────
    # GUARDRAIL 4 — Final Output Audit (runs once at end)
    # ──────────────────────────────────────────────────────
    def audit_final_output(self, final_result: dict) -> dict:
        """
        Final audit guardrail (runs once when agent finishes).

        - Generates complete action audit trail
        - Flags any irreversible actions taken
        - Marks if human review is required
        - Returns sanitized final result
        """
        irreversible = [
            log for log in self.action_log
            if not self.ALLOWED_ACTIONS.get(log["action"], {}).get("reversible", True)
        ]

        audit = {
            "total_steps":          self.step_count,
            "total_errors":         self.error_count,
            "elapsed_seconds":      round(time.time() - self.start_time, 2),
            "actions_taken":        self.action_log,
            "irreversible_actions": irreversible,
            "requires_human_review":len(irreversible) > 0,
            "final_result":         final_result,
        }

        print(f"\n{'='*55}")
        print(f" Agent Audit Report")
        print(f"{'='*55}")
        print(f"  Steps taken       : {audit['total_steps']}")
        print(f"  Errors            : {audit['total_errors']}")
        print(f"  Elapsed           : {audit['elapsed_seconds']}s")
        print(f"  Irreversible ops  : {len(irreversible)}")
        print(f"  Human review      : {'⚠️  YES' if audit['requires_human_review'] else '✅ No'}")

        if irreversible:
            print(f"\n  Irreversible actions taken:")
            for log in irreversible:
                print(f"    Step {log['step']}: {log['action']} @ {log['timestamp']}")

        return audit

    # ──────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────
    def record_error(self):
        """Call this when a step fails — increments error counter."""
        self.error_count += 1

    def _log_action(self, action: str, state: dict, status: str):
        """Append every action to the audit log."""
        self.action_log.append({
            "step":       self.step_count,
            "action":     action,
            "status":     status,
            "timestamp":  datetime.now().isoformat(),
            "state_keys": list(state.keys()),
        })


# ══════════════════════════════════════════════════════════
#  DEMO
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "█"*55)
    print("  AGENTIC AI GUARDRAILS — TEST CASES")
    print("█"*55)

    guards = AgentGuardrails(max_steps=6, max_errors=2)

    goal    = "Process home loan application for customer Anil Kumar"
    context = {"customer": "Anil Kumar", "loan_type": "home", "amount": 5_000_000}

    print(f"\n[Goal] {goal}")

    # ── Stage 1: Validate Goal ─────────────────────────────
    print("\n[Stage 1] Goal Guardrail...")
    goal_result = guards.validate_goal(goal, context)
    print(f"  Status     : {'✅ PASS' if goal_result['passed'] else '❌ BLOCK'}")
    print(f"  Risk level : {goal_result.get('risk_level', 'low')}")
    if not goal_result["passed"]:
        print(f"  Reason     : {goal_result['reason']}")
        exit()

    # ── Stage 2 + 3: Step loop ─────────────────────────────
    agent_steps = [
        ("retrieve_documents", {"customer": "Anil Kumar", "step": 1, "docs": ["id", "income"]}),
        ("calculate_emi",      {"customer": "Anil Kumar", "step": 2, "emi": 42000}),
        ("check_eligibility",  {"customer": "Anil Kumar", "step": 3, "foir": 0.45, "eligible": True}),
        ("generate_answer",    {"customer": "Anil Kumar", "step": 4, "answer": "Eligible for Rs 50L"}),
        ("unknown_action",     {"customer": "Anil Kumar", "step": 5}),   # ← should be blocked
    ]

    for action, state in agent_steps:
        print(f"\n[Step {guards.step_count + 1}] Action: {action}")

        # Per-step guardrail
        step_ok = guards.validate_step(action, state)
        print(f"  Step Guard : {'✅ PASS' if step_ok['passed'] else '❌ BLOCK'}")
        if not step_ok["passed"]:
            print(f"  Reason     : {step_ok['reason']}")
            guards.record_error()
            continue
        if step_ok.get("requires_approval"):
            print(f"  ⚠️  Human approval required for this action")

        # Termination check
        term = guards.should_terminate(state, goal)
        if term["should_stop"]:
            icon = "🏁" if term["goal_achieved"] else "🛑"
            print(f"\n  {icon} Terminate: {term['reason']}")
            break

    # ── Stage 4: Audit ─────────────────────────────────────
    guards.audit_final_output({"status": "completed", "eligible": True, "max_loan": 5_000_000})