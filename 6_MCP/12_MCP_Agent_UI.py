"""
============================================================
 STREAMLIT UI — Multi-MCP Agent with Multi-Intent Routing
 Handles questions that span multiple MCP servers.
 e.g. "what is 2+2 and weather in Hyderabad?"
      → calls Calculator + Weather servers both
============================================================
 INSTALL:
   pip install streamlit openai mcp httpx python-dotenv plotly
   pip install psycopg2-binary beautifulsoup4 lxml

 RUN:
   streamlit run 12_MCP_Agent_UI.py
============================================================
"""

import os
import sys
import json
import time
import asyncio
from pathlib import Path
from dotenv import load_dotenv

import streamlit as st
import plotly.graph_objects as go
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ── Load .env ─────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SERPAPI_KEY    = os.getenv("SERPAPI_API_KEY", "")
PYTHON_EXE     = sys.executable
MCP_DIR        = Path(__file__).parent

# ── OpenAI pricing gpt-4o-mini per 1M tokens ──────────────
COST_INPUT_PER_1M  = 0.150
COST_OUTPUT_PER_1M = 0.600

# ── MCP Server Registry ────────────────────────────────────
MCP_SERVERS = {
    "weather": {
        "file":        "05_Weather_MCPServer.py",
        "label":       "🌤️ Weather Server",
        "color":       "#3B82F6",
        "description": "Fetches real-time weather for any city using SerpAPI.",
        "env":         {"SERPAPI_KEY": SERPAPI_KEY},
    },
    "jira": {
        "file":        "07_Jira_MCPServer.py",
        "label":       "🎫 Jira Server",
        "color":       "#8B5CF6",
        "description": "Reads Jira issues, searches tickets by JQL, fetches comments.",
        "env": {
            "JIRA_URL":       os.getenv("JIRA_URL", ""),
            "JIRA_EMAIL":     os.getenv("JIRA_EMAIL", ""),
            "JIRA_API_TOKEN": os.getenv("JIRA_API_TOKEN", ""),
        },
    },
    "github": {
        "file":        "08_GitHub_MCPServer.py",
        "label":       "🐙 GitHub Server",
        "color":       "#10B981",
        "description": "Reads files from GitHub repositories and searches code.",
        "env":         {"GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", "")},
    },
    "database": {
        "file":        "09_DB_MCPServer.py",
        "label":       "🗄️ Database Server",
        "color":       "#F59E0B",
        "description": "Queries PostgreSQL database with employee and project records.",
        "env": {
            "DB_HOST": os.getenv("DB_HOST", "localhost"),
            "DB_NAME": os.getenv("DB_NAME", "agentdb"),
            "DB_USER": os.getenv("DB_USER", "agentuser"),
            "DB_PASS": os.getenv("DB_PASS", "agentpass"),
        },
    },
    "web": {
        "file":        "10_Web_MCPServer.py",
        "label":       "🌐 Web Scraper Server",
        "color":       "#EF4444",
        "description": "Reads and scrapes content from any public webpage URL.",
        "env":         {},
    },
    "calculator": {
        "file":        "02_Calculator_MCPServer.py",
        "label":       "🔢 Calculator Server",
        "color":       "#06B6D4",
        "description": "Performs math: addition, subtraction, multiplication, division.",
        "env":         {},
    },
    "notes": {
        "file":        "03_NotesApp_MCPServer.py",
        "label":       "📝 Notes Server",
        "color":       "#F97316",
        "description": "Saves, retrieves and deletes personal notes by title.",
        "env":         {},
    },
    "files": {
        "file":        "04_FileSystemExplorer_MCPServer.py",
        "label":       "📁 File Explorer Server",
        "color":       "#84CC16",
        "description": "Lists, reads and writes files on the local filesystem.",
        "env":         {},
    },
}


# ══════════════════════════════════════════════════════════
#  LLM MULTI-INTENT ROUTER
#  Key improvement: returns LIST of servers, not just one.
#  "what is 2+2 and weather in Hyderabad?" → [calculator, weather]
# ══════════════════════════════════════════════════════════
def llm_route(question: str, openai_client: OpenAI) -> tuple:
    """
    Use OpenAI to detect ALL intents in the question and
    return a list of servers needed to answer it fully.

    Returns: (server_keys_list, reasons_dict, routing_cost, routing_time)
    """
    server_list = "\n".join([
        f"- {key}: {cfg['description']}"
        for key, cfg in MCP_SERVERS.items()
    ])

    system_prompt = f"""
You are an intelligent router for a multi-server AI agent.

Your job is to read the user's question and identify ALL servers
needed to answer it completely.

A question can require MULTIPLE servers. Examples:
- "what is 2+2 and weather in Hyderabad?" → ["calculator", "weather"]
- "get Jira ticket KAN-1 and check GitHub repo" → ["jira", "github"]
- "what is 10*5?" → ["calculator"]
- "weather in Mumbai?" → ["weather"]
- "show employees and calculate their average salary" → ["database", "calculator"]

Available servers:
{server_list}

Rules:
- Identify ALL servers needed to fully answer the question
- Return minimum servers required — don't add unnecessary ones
- Each server in the list must be one of the exact keys above

Respond ONLY with valid JSON in this exact format — no extra text:
{{
  "servers": ["server_key_1", "server_key_2"],
  "reasons": {{
    "server_key_1": "why this server is needed",
    "server_key_2": "why this server is needed"
  }}
}}
""".strip()

    t0 = time.time()
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": question},
        ],
        temperature=0,
        max_tokens=200,
    )
    routing_time = round(time.time() - t0, 3)

    raw = response.choices[0].message.content.strip()

    # ── Parse JSON ────────────────────────────────────────
    try:
        # Strip markdown code fences if present
        clean = raw.replace("```json", "").replace("```", "").strip()
        parsed      = json.loads(clean)
        server_keys = parsed.get("servers", [])
        reasons     = parsed.get("reasons", {})
    except (json.JSONDecodeError, Exception):
        server_keys = ["web"]
        reasons     = {"web": "Fallback: could not parse routing response"}

    # ── Validate all keys exist ───────────────────────────
    valid_keys = [k for k in server_keys if k in MCP_SERVERS]
    if not valid_keys:
        valid_keys = ["web"]
        reasons    = {"web": "No valid server keys found, defaulting to web"}

    # ── Routing cost ──────────────────────────────────────
    usage = response.usage
    cost  = (usage.prompt_tokens / 1_000_000) * COST_INPUT_PER_1M + \
            (usage.completion_tokens / 1_000_000) * COST_OUTPUT_PER_1M

    return valid_keys, reasons, cost, routing_time


# ══════════════════════════════════════════════════════════
#  SINGLE MCP SERVER AGENT CALL
#  Connects to ONE server, runs agent loop, returns result
# ══════════════════════════════════════════════════════════
async def run_single_server(server_key: str, question: str,
                            openai_client: OpenAI, sub_question: str = None):
    """
    Run agent loop against one MCP server.
    sub_question: the specific part of the question for this server.

    Returns: (answer, lineage, token_usage)
    """
    cfg         = MCP_SERVERS[server_key]
    server_file = str(MCP_DIR / cfg["file"])
    lineage     = []
    token_usage = {"input": 0, "output": 0}
    query       = sub_question or question   # use sub-question if provided

    # ── Check server file ─────────────────────────────────
    if not Path(server_file).exists():
        err = f"Server file not found: {cfg['file']}"
        lineage.append({"type": "error", "server": cfg["label"], "msg": err})
        return f"Error: {err}", lineage, token_usage

    # ── Build env ─────────────────────────────────────────
    env = {
        **cfg["env"],
        "PATH":       os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "TEMP":       os.environ.get("TEMP", ""),
    }
    env = {k: v for k, v in env.items() if v}

    server_params = StdioServerParameters(
        command=PYTHON_EXE,
        args=[server_file],
        env=env,
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:

                # ── Connect ───────────────────────────────
                t0 = time.time()
                await session.initialize()
                connect_time = round(time.time() - t0, 3)
                lineage.append({
                    "type":   "connect",
                    "server": cfg["label"],
                    "time":   connect_time,
                    "msg":    f"Connected to {cfg['label']} in {connect_time}s",
                })

                # ── Discover tools ────────────────────────
                t1 = time.time()
                tools_resp = await session.list_tools()
                mcp_tools  = tools_resp.tools
                disco_time = round(time.time() - t1, 3)
                tool_names = [t.name for t in mcp_tools]
                lineage.append({
                    "type":   "discover",
                    "server": cfg["label"],
                    "time":   disco_time,
                    "tools":  tool_names,
                    "msg":    f"Found {len(tool_names)} tools: {', '.join(tool_names)}",
                })

                # ── OpenAI tools format ───────────────────
                openai_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name":        t.name,
                            "description": t.description,
                            "parameters":  t.inputSchema,
                        }
                    }
                    for t in mcp_tools
                ]

                # ── Agent loop ────────────────────────────
                messages = [
                    {
                        "role": "system",
                        "content": (
                            f"You are a helpful AI assistant with access to {cfg['label']}. "
                            "Use the available tools to answer the user's question. "
                            "Be concise and accurate."
                        )
                    },
                    {"role": "user", "content": query}
                ]

                final_answer = ""

                for loop in range(5):

                    # ── LLM call ──────────────────────────
                    t2 = time.time()
                    response = openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        tools=openai_tools,
                        tool_choice="auto",
                    )
                    llm_time = round(time.time() - t2, 3)

                    usage = response.usage
                    token_usage["input"]  += usage.prompt_tokens
                    token_usage["output"] += usage.completion_tokens

                    lineage.append({
                        "type":   "llm_call",
                        "server": cfg["label"],
                        "time":   llm_time,
                        "tokens": {
                            "input":  usage.prompt_tokens,
                            "output": usage.completion_tokens,
                        },
                        "msg": (
                            f"LLM call #{loop+1} — "
                            f"{usage.prompt_tokens} in + {usage.completion_tokens} out "
                            f"in {llm_time}s"
                        ),
                    })

                    message = response.choices[0].message

                    if message.tool_calls:
                        messages.append({
                            "role":       "assistant",
                            "content":    message.content,
                            "tool_calls": [
                                {
                                    "id":   tc.id,
                                    "type": "function",
                                    "function": {
                                        "name":      tc.function.name,
                                        "arguments": tc.function.arguments,
                                    }
                                }
                                for tc in message.tool_calls
                            ]
                        })

                        for tc in message.tool_calls:
                            tool_name = tc.function.name
                            tool_args = json.loads(tc.function.arguments)

                            t3 = time.time()
                            result    = await session.call_tool(tool_name, tool_args)
                            tool_time = round(time.time() - t3, 3)

                            result_text = "".join(
                                c.text for c in result.content
                                if hasattr(c, "text")
                            )

                            lineage.append({
                                "type":     "tool_call",
                                "server":   cfg["label"],
                                "tool":     tool_name,
                                "args":     tool_args,
                                "time":     tool_time,
                                "response": result_text[:500],
                                "msg":      f"Tool '{tool_name}' → {tool_time}s",
                            })

                            messages.append({
                                "role":         "tool",
                                "tool_call_id": tc.id,
                                "content":      result_text,
                            })
                    else:
                        final_answer = message.content
                        lineage.append({
                            "type":   "final",
                            "server": cfg["label"],
                            "msg":    f"{cfg['label']} produced its answer ✅",
                        })
                        break

                return final_answer, lineage, token_usage

    except Exception as e:
        err_msg = str(e)
        lineage.append({
            "type":   "error",
            "server": cfg["label"],
            "msg":    err_msg,
        })
        return f"Error from {cfg['label']}: {err_msg}", lineage, token_usage


# ══════════════════════════════════════════════════════════
#  MULTI-SERVER ORCHESTRATOR
#  Splits the question into sub-questions per server,
#  runs all servers, then synthesises one final answer.
# ══════════════════════════════════════════════════════════
async def run_multi_server(server_keys: list, reasons: dict,
                           question: str, openai_client: OpenAI):
    """
    Run multiple MCP servers for a multi-intent question.
    Returns: (final_answer, all_lineage, total_tokens)
    """
    all_lineage   = []
    total_tokens  = {"input": 0, "output": 0}
    server_results = {}

    # ── Split question per server using LLM ───────────────
    if len(server_keys) > 1:
        split_prompt = f"""
The user asked: "{question}"

This question needs {len(server_keys)} different servers:
{chr(10).join(f'- {k}: {reasons.get(k,"")}' for k in server_keys)}

For each server, extract the exact sub-question that server should answer.

Respond ONLY with valid JSON:
{{
  {", ".join(f'"{k}": "sub-question for {k}"' for k in server_keys)}
}}
""".strip()

        split_resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": split_prompt}],
            temperature=0,
            max_tokens=200,
        )
        total_tokens["input"]  += split_resp.usage.prompt_tokens
        total_tokens["output"] += split_resp.usage.completion_tokens

        try:
            raw = split_resp.choices[0].message.content.strip()
            clean = raw.replace("```json", "").replace("```", "").strip()
            sub_questions = json.loads(clean)
        except Exception:
            sub_questions = {k: question for k in server_keys}
    else:
        sub_questions = {server_keys[0]: question}

    # ── Run each server sequentially ─────────────────────
    for key in server_keys:
        sub_q = sub_questions.get(key, question)
        answer, lineage, tokens = await run_single_server(
            key, question, openai_client, sub_question=sub_q
        )
        server_results[key] = {"answer": answer, "sub_q": sub_q}
        all_lineage.extend(lineage)
        total_tokens["input"]  += tokens["input"]
        total_tokens["output"] += tokens["output"]

    # ── Synthesise final answer from all server results ───
    if len(server_keys) > 1:
        synthesis_parts = "\n\n".join([
            f"From {MCP_SERVERS[k]['label']}:\n"
            f"Question: {server_results[k]['sub_q']}\n"
            f"Answer: {server_results[k]['answer']}"
            for k in server_keys
        ])

        synthesis_resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Combine the following answers from different servers "
                        "into one clear, well-structured response for the user. "
                        "Address each part of their original question."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Original question: {question}\n\n"
                        f"Server answers:\n{synthesis_parts}"
                    )
                }
            ],
            temperature=0.3,
            max_tokens=800,
        )
        total_tokens["input"]  += synthesis_resp.usage.prompt_tokens
        total_tokens["output"] += synthesis_resp.usage.completion_tokens
        final_answer = synthesis_resp.choices[0].message.content

        all_lineage.append({
            "type":   "synthesis",
            "msg":    f"Synthesised answers from {len(server_keys)} servers into final response",
            "tokens": {
                "input":  synthesis_resp.usage.prompt_tokens,
                "output": synthesis_resp.usage.completion_tokens,
            }
        })
    else:
        final_answer = server_results[server_keys[0]]["answer"]

    return final_answer, all_lineage, total_tokens


# ══════════════════════════════════════════════════════════
#  LINEAGE GRAPH
# ══════════════════════════════════════════════════════════
def build_lineage_graph(lineage: list, server_keys: list,
                        routing_time: float, total_cost: float):
    """Build Plotly execution flow graph showing all servers used."""

    nodes  = []
    colors = []

    # User node
    nodes.append("👤 User\nQuestion")
    colors.append("#1E293B")

    # Router node
    nodes.append(f"🧭 LLM Router\n({routing_time}s)")
    colors.append("#7C3AED")

    # One node per MCP server
    for key in server_keys:
        cfg = MCP_SERVERS[key]
        tool_calls = sum(
            1 for s in lineage
            if s.get("type") == "tool_call" and s.get("server") == cfg["label"]
        )
        nodes.append(f"{cfg['label']}\n({tool_calls} tool calls)")
        colors.append(cfg["color"])

    # OpenAI synthesis node (if multiple servers)
    if len(server_keys) > 1:
        nodes.append("🤖 OpenAI\nSynthesis")
        colors.append("#7C3AED")

    # Final answer
    nodes.append("✅ Final\nAnswer")
    colors.append("#059669")

    n     = len(nodes)
    x_pos = [i / (n - 1) for i in range(n)]
    y_pos = [0.5] * n

    edge_x, edge_y = [], []
    for i in range(n - 1):
        edge_x += [x_pos[i], x_pos[i + 1], None]
        edge_y += [y_pos[i], y_pos[i + 1], None]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        mode="lines",
        line=dict(width=2, color="#334155"),
        hoverinfo="none",
    ))

    fig.add_trace(go.Scatter(
        x=x_pos, y=y_pos,
        mode="markers+text",
        marker=dict(
            size=[28] * n,
            color=colors,
            line=dict(width=2, color="#FFFFFF"),
        ),
        text=nodes,
        textposition="bottom center",
        textfont=dict(size=9, color="#E2E8F0"),
        hovertemplate="%{text}<extra></extra>",
    ))

    fig.update_layout(
        paper_bgcolor="#0F172A",
        plot_bgcolor="#0F172A",
        showlegend=False,
        height=260,
        margin=dict(l=30, r=30, t=40, b=80),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   range=[0.1, 0.9]),
        title=dict(
            text=(
                f"Execution Flow  ·  "
                f"Servers: {len(server_keys)}  ·  "
                f"Total Cost: ${total_cost:.6f}"
            ),
            font=dict(color="#94A3B8", size=12),
            x=0.5,
        ),
    )
    return fig


# ══════════════════════════════════════════════════════════
#  STREAMLIT APP
# ══════════════════════════════════════════════════════════
def main():
    st.set_page_config(
        page_title="MCP Agent Hub",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;700;800&display=swap');
    html, body, [class*="css"] {
        font-family: 'Syne', sans-serif; background: #0F172A; color: #E2E8F0;
    }
    .stApp { background: #0F172A; }
    .main-title {
        font-size: 2.6rem; font-weight: 800; letter-spacing: -1.5px;
        background: linear-gradient(135deg, #60A5FA 0%, #A78BFA 50%, #34D399 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .sub-title {
        color: #475569; font-size: 0.9rem; margin-top: -8px;
        font-family: 'JetBrains Mono', monospace;
    }
    .route-box {
        background: #1E293B; border: 1px solid #334155;
        border-left: 4px solid #8B5CF6; border-radius: 10px;
        padding: 14px 18px; margin: 12px 0;
        font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;
    }
    .server-tag {
        display: inline-block; padding: 3px 10px; border-radius: 20px;
        font-size: 0.8rem; font-weight: 600; margin: 3px;
        background: #1E293B; border: 1px solid #334155; color: #E2E8F0;
    }
    .metric-card {
        background: #1E293B; border-radius: 10px; padding: 14px;
        text-align: center; border: 1px solid #334155;
    }
    .metric-value { font-size: 1.4rem; font-weight: 700; color: #60A5FA; }
    .metric-label {
        font-size: 0.72rem; color: #64748B; margin-top: 2px;
        font-family: 'JetBrains Mono', monospace;
    }
    .lineage-row {
        background: #1E293B; border-radius: 8px; padding: 10px 14px;
        margin-bottom: 5px; font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem; color: #CBD5E1; border-left: 3px solid #334155;
    }
    .lineage-row.connect   { border-color: #3B82F6; }
    .lineage-row.discover  { border-color: #06B6D4; }
    .lineage-row.llm       { border-color: #8B5CF6; }
    .lineage-row.tool      { border-color: #10B981; }
    .lineage-row.final     { border-color: #059669; }
    .lineage-row.synthesis { border-color: #F59E0B; }
    .lineage-row.error     { border-color: #EF4444; color: #FCA5A5; }
    .answer-box {
        background: #1E293B; border: 1px solid #334155; border-radius: 12px;
        padding: 20px 24px; font-size: 1rem; line-height: 1.8; color: #E2E8F0;
    }
    .server-card {
        background: #1E293B; border-radius: 8px; padding: 10px 14px;
        margin-bottom: 6px; border-left: 3px solid; font-size: 0.82rem;
    }
    .stButton > button {
        background: linear-gradient(135deg, #3B82F6, #8B5CF6) !important;
        color: white !important; border: none !important;
        border-radius: 8px !important; font-weight: 700 !important;
        font-family: 'Syne', sans-serif !important; width: 100% !important;
    }
    .stTextArea textarea {
        background: #1E293B !important; color: #E2E8F0 !important;
        border: 1px solid #334155 !important; border-radius: 10px !important;
    }
    div[data-testid="stSidebar"] { background: #0F172A !important; }
    </style>
    """, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────
    st.markdown('<p class="main-title">⚡ MCP Agent Hub</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-title">Multi-intent routing → multiple MCP servers → synthesised answer</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Sidebar ───────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🗂️ MCP Servers")
        for key, cfg in MCP_SERVERS.items():
            exists = (MCP_DIR / cfg["file"]).exists()
            st.markdown(f"""
            <div class="server-card" style="border-color:{cfg['color']}">
                <b>{'✅' if exists else '❌'} {cfg['label']}</b><br>
                <span style="color:#94A3B8;font-size:0.78rem">{cfg['description']}</span>
            </div>""", unsafe_allow_html=True)

        st.divider()
        st.markdown("### 💡 Example Questions")
        examples = [
            "What is 2+2 and weather in Hyderabad?",
            "Get Jira ticket KAN-2 and check GitHub repo gvbigdata/GenAI_AgenticAI_RAG",
            "What is the weather in Mumbai?",
            "Calculate 45 multiplied by 89",
            "Show all Engineering employees from database",
            "Read https://en.wikipedia.org/wiki/RAG",
            "Save a note titled Meeting: standup at 3pm",
        ]
        for ex in examples:
            label = ex[:52] + "…" if len(ex) > 52 else ex
            if st.button(label, key=ex):
                st.session_state["prefill"] = ex

    # ── Main input ────────────────────────────────────────
    prefill  = st.session_state.pop("prefill", "")
    question = st.text_area(
        "Ask anything — multi-intent questions use multiple servers automatically:",
        value=prefill,
        height=110,
        placeholder=(
            "e.g. What is 2+2 and weather in Hyderabad?  |  "
            "Get KAN-2 Jira ticket and list GitHub files"
        ),
    )

    run_btn = st.button("▶ Run Agent", use_container_width=True)

    if not run_btn or not question.strip():
        st.markdown("""
        <div style="background:#1E293B;border-radius:10px;padding:20px;
                    border:1px dashed #334155;color:#475569;text-align:center;margin-top:16px">
            <b style="font-size:1rem;color:#94A3B8">Multi-Intent Support</b><br><br>
            Ask questions that span multiple servers in one go.<br>
            <b style="color:#60A5FA">"What is 2+2 and weather in Hyderabad?"</b><br>
            → Calculator + Weather servers run in parallel → one combined answer
        </div>
        """, unsafe_allow_html=True)
        return

    if not OPENAI_API_KEY:
        st.error("❌ OPENAI_API_KEY not set in .env")
        return

    openai_client = OpenAI(api_key=OPENAI_API_KEY)

    # ── STEP 1: LLM Multi-Intent Routing ─────────────────
    with st.spinner("🧭 Detecting intents and routing..."):
        server_keys, reasons, routing_cost, routing_time = llm_route(
            question, openai_client
        )

    # ── Show routing result ───────────────────────────────
    server_tags = "".join([
        f'<span class="server-tag" style="border-color:{MCP_SERVERS[k]["color"]}">'
        f'{MCP_SERVERS[k]["label"]}</span>'
        for k in server_keys
    ])
    reasons_text = "<br>".join([
        f"• <b>{MCP_SERVERS[k]['label']}</b>: {reasons.get(k,'')}"
        for k in server_keys
    ])
    st.markdown(f"""
    <div class="route-box">
        <div style="margin-bottom:8px">
            <b style="color:#A78BFA">🧭 Routed to {len(server_keys)} server(s):</b>
            &nbsp;{server_tags}
        </div>
        <div style="color:#94A3B8;font-size:0.82rem">{reasons_text}</div>
        <div style="color:#475569;font-size:0.75rem;margin-top:8px">
            Routing time: {routing_time}s &nbsp;|&nbsp;
            Routing cost: ${routing_cost:.6f}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── STEP 2: Run all servers ───────────────────────────
    label_str = " + ".join(MCP_SERVERS[k]["label"] for k in server_keys)
    with st.spinner(f"Running: {label_str}..."):
        t_start = time.time()
        final_answer, lineage, token_usage = asyncio.run(
            run_multi_server(server_keys, reasons, question, openai_client)
        )
        total_time = round(time.time() - t_start, 3)

    # ── Cost ──────────────────────────────────────────────
    agent_cost = (token_usage["input"]  / 1_000_000) * COST_INPUT_PER_1M + \
                 (token_usage["output"] / 1_000_000) * COST_OUTPUT_PER_1M
    total_cost = routing_cost + agent_cost
    tool_calls = sum(1 for s in lineage if s["type"] == "tool_call")

    # ── Metrics ───────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    cols = st.columns(6)
    metrics = [
        (f"{total_time}s",              "⏱ Total Time"),
        (f"{len(server_keys)}",         "🖥️ Servers Used"),
        (str(token_usage["input"]),     "📥 Input Tokens"),
        (str(token_usage["output"]),    "📤 Output Tokens"),
        (f"${total_cost:.6f}",          "💰 Total Cost"),
        (str(tool_calls),               "🔧 Tool Calls"),
    ]
    for col, (value, label) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{value}</div>
                <div class="metric-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Lineage Graph ─────────────────────────────────────
    st.markdown("### 🗺️ Execution Lineage")
    fig = build_lineage_graph(lineage, server_keys, routing_time, total_cost)
    st.plotly_chart(fig, use_container_width=True)

    # ── Detailed Steps ────────────────────────────────────
    with st.expander("📋 Step-by-Step Lineage", expanded=True):
        st.markdown(f"""
        <div class="lineage-row">
            <b>Step 0 — LLM Multi-Intent Router</b>
            &nbsp;|&nbsp; ⏱ {routing_time}s
            &nbsp;|&nbsp; 💰 ${routing_cost:.6f}<br>
            Detected {len(server_keys)} intent(s): {", ".join(server_keys)}
        </div>""", unsafe_allow_html=True)

        for i, step in enumerate(lineage, 1):
            stype = step.get("type", "")

            if stype == "connect":
                st.markdown(f"""
                <div class="lineage-row connect">
                    <b>Step {i} — Connect [{step.get('server','')}]</b>
                    &nbsp;|&nbsp; ⏱ {step['time']}s<br>
                    {step['msg']}
                </div>""", unsafe_allow_html=True)

            elif stype == "discover":
                st.markdown(f"""
                <div class="lineage-row discover">
                    <b>Step {i} — Tool Discovery [{step.get('server','')}]</b>
                    &nbsp;|&nbsp; ⏱ {step['time']}s<br>
                    Tools: <b>{', '.join(step.get('tools', []))}</b>
                </div>""", unsafe_allow_html=True)

            elif stype == "llm_call":
                t = step.get("tokens", {})
                st.markdown(f"""
                <div class="lineage-row llm">
                    <b>Step {i} — LLM Call [{step.get('server','')}]</b>
                    &nbsp;|&nbsp; ⏱ {step['time']}s<br>
                    📥 {t.get('input',0)} in + 📤 {t.get('output',0)} out tokens
                </div>""", unsafe_allow_html=True)

            elif stype == "tool_call":
                args_str = json.dumps(step.get("args", {}))
                resp_str = step.get("response", "")[:250]
                st.markdown(f"""
                <div class="lineage-row tool">
                    <b>Step {i} — Tool: {step['tool']} [{step.get('server','')}]</b>
                    &nbsp;|&nbsp; ⏱ {step['time']}s<br>
                    📥 Args: <code>{args_str}</code><br>
                    📤 Response: {resp_str}
                </div>""", unsafe_allow_html=True)

            elif stype == "final":
                st.markdown(f"""
                <div class="lineage-row final">
                    <b>Step {i} — Answer Ready [{step.get('server','')}] ✅</b>
                </div>""", unsafe_allow_html=True)

            elif stype == "synthesis":
                t = step.get("tokens", {})
                st.markdown(f"""
                <div class="lineage-row synthesis">
                    <b>Step {i} — Multi-Server Synthesis 🔀</b><br>
                    {step['msg']}<br>
                    Tokens: {t.get('input',0)} in + {t.get('output',0)} out
                </div>""", unsafe_allow_html=True)

            elif stype == "error":
                st.markdown(f"""
                <div class="lineage-row error">
                    <b>Step {i} — Error ❌ [{step.get('server','')}]</b><br>
                    {step['msg']}
                </div>""", unsafe_allow_html=True)

    # ── Final Answer ──────────────────────────────────────
    st.markdown("### 💬 Answer")
    if final_answer:
        st.markdown(
            f'<div class="answer-box">{final_answer}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.error("No answer generated. Check lineage steps for errors.")

    # ── History ───────────────────────────────────────────
    if "history" not in st.session_state:
        st.session_state["history"] = []
    st.session_state["history"].append({
        "q": question, "a": final_answer or "Error",
        "servers": [MCP_SERVERS[k]["label"] for k in server_keys],
        "cost": total_cost, "time": total_time,
    })

    if len(st.session_state["history"]) > 1:
        with st.expander("🕓 Previous Questions"):
            for h in reversed(st.session_state["history"][:-1]):
                st.markdown(
                    f"**Q:** {h['q']}  \n"
                    f"**Servers:** `{'`, `'.join(h['servers'])}`  |  "
                    f"⏱ {h['time']}s  |  💰 ${h['cost']:.6f}"
                )
                st.caption(h["a"][:200] + "..." if len(h["a"]) > 200 else h["a"])
                st.divider()


if __name__ == "__main__":
    main()