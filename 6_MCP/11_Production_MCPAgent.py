"""
============================================================
 HOW LLM INTERACTS WITH MCP SERVER IN PRODUCTION
 Using OpenAI GPT-4 + Weather MCP Server
============================================================

 THE FLOW:
 ┌─────────┐    ┌─────────┐    ┌────────────┐    ┌──────────┐
 │  User   │───▶│ Python  │───▶│  OpenAI    │───▶│   MCP    │
 │ Question│    │  Agent  │    │  GPT-4     │    │  Server  │
 └─────────┘    └─────────┘    └────────────┘    └──────────┘
                     │               │                 │
                     │   1. Send user question         │
                     │──────────────▶│                 │
                     │   2. GPT decides to call tool   │
                     │◀──────────────│                 │
                     │   3. Agent calls MCP tool       │
                     │────────────────────────────────▶│
                     │   4. MCP returns weather data   │
                     │◀────────────────────────────────│
                     │   5. Send tool result to GPT    │
                     │──────────────▶│                 │
                     │   6. GPT gives final answer     │
                     │◀──────────────│                 │
                     │   7. Show answer to user        │

 INSTALL:
   pip install openai mcp httpx python-dotenv

 .env FILE:
   OPENAI_API_KEY=your_openai_key
   SERPAPI_KEY=your_serpapi_key

 RUN:
   python 11_Production_MCPAgent.py
============================================================
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ── Load .env from the SAME folder as this script ─────────
# FIX 1: Use explicit path so .env is always found
#         regardless of which directory you run from
load_dotenv(Path(__file__).parent / ".env")

# ── API Keys ───────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# FIX 2: Was "SERPAPI_API_KEY" — correct key name is "SERPAPI_KEY"
SERPAPI_KEY    = os.getenv("SERPAPI_API_KEY")

# ── Full path to your MCP server file ─────────────────────
# FIX 3: Was "05_Weather_MCPServer." (typo — missing 'py')
#         Also use full absolute path so subprocess always finds it
MCP_SERVER_FILE = str(Path(__file__).parent / "05_Weather_MCPServer.py")

# ── Full path to venv Python executable ───────────────────
# Using sys.executable ensures we use the SAME python
# that is running this script (correct venv, correct packages)
PYTHON_EXE = sys.executable

# ── OpenAI Client ─────────────────────────────────────────
openai_client = OpenAI(api_key=OPENAI_API_KEY)


# ══════════════════════════════════════════════════════════
#  STEP 1 — CONNECT TO MCP SERVER
#  Start the MCP server as a subprocess and connect to it.
#  The agent talks to MCP via stdio (stdin/stdout pipe).
# ══════════════════════════════════════════════════════════
async def connect_to_mcp_server():
    """
    Connect to the Weather MCP Server.
    Returns: StdioServerParameters
    """
    server_params = StdioServerParameters(
        command=PYTHON_EXE,         # FIX: use exact venv python path
        args=[MCP_SERVER_FILE],     # FIX: full path + correct filename
        env={
            "SERPAPI_KEY": SERPAPI_KEY,   # pass API key to server
            "PATH": os.environ.get("PATH", ""),  # inherit system PATH
        }
    )
    return server_params


# ══════════════════════════════════════════════════════════
#  STEP 2 — DISCOVER MCP TOOLS
#  Ask the MCP server: "what tools do you have?"
#  Convert MCP tool format → OpenAI function calling format
# ══════════════════════════════════════════════════════════
def mcp_tools_to_openai_format(mcp_tools) -> list[dict]:
    """
    Convert MCP tool definitions → OpenAI function calling format.

    MCP Tool format:
    {
        name: "get_weather",
        description: "Get current weather...",
        inputSchema: { type: "object", properties: {...} }
    }

    OpenAI format:
    {
        type: "function",
        function: {
            name: "get_weather",
            description: "Get current weather...",
            parameters: { type: "object", properties: {...} }
        }
    }
    """
    openai_tools = []
    for tool in mcp_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name":        tool.name,
                "description": tool.description,
                # MCP uses inputSchema, OpenAI uses parameters
                "parameters":  tool.inputSchema,
            }
        })
    return openai_tools


# ══════════════════════════════════════════════════════════
#  STEP 3 — CALL MCP TOOL
#  When OpenAI says "call get_weather with city=Hyderabad",
#  we forward that call to the MCP server and get the result.
# ══════════════════════════════════════════════════════════
async def call_mcp_tool(session: ClientSession, tool_name: str, tool_args: dict) -> str:
    """
    Execute a tool on the MCP server.

    Args:
        session:   active MCP session
        tool_name: tool to call e.g. 'get_weather'
        tool_args: arguments e.g. {'city': 'Hyderabad'}

    Returns:
        Tool result as a string (sent back to OpenAI)
    """
    print(f"\n   🔧 Calling MCP tool : {tool_name}")
    print(f"   📥 With arguments  : {tool_args}")

    # Call the tool on MCP server
    result = await session.call_tool(tool_name, tool_args)

    # Extract text content from MCP result
    result_text = ""
    for content in result.content:
        if hasattr(content, "text"):
            result_text += content.text

    print(f"   📤 MCP Response    : {result_text[:200]}...")
    return result_text


# ══════════════════════════════════════════════════════════
#  STEP 4 — THE MAIN AGENT LOOP
#  This is the core of how LLM + MCP work together:
#
#  Round 1: Send question to GPT → GPT says "call this tool"
#  Round 2: Call MCP tool → get result → send back to GPT
#  Round 3: GPT reads tool result → gives final answer
# ══════════════════════════════════════════════════════════
async def run_agent(user_question: str):
    """
    Run the full LLM ↔ MCP agent loop.

    Args:
        user_question: Natural language question from user
    """
    print("\n" + "="*60)
    print(f" USER: {user_question}")
    print("="*60)

    # ── Connect to MCP Server ─────────────────────────────
    server_params = await connect_to_mcp_server()

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            # Initialize the MCP connection
            await session.initialize()
            print("\n✅ Connected to MCP Server")

            # ── Discover available tools ──────────────────
            tools_response = await session.list_tools()
            mcp_tools      = tools_response.tools
            openai_tools   = mcp_tools_to_openai_format(mcp_tools)

            print(f"\n📋 Available MCP Tools:")
            for tool in mcp_tools:
                print(f"   - {tool.name}: {tool.description[:60]}...")

            # ── Build initial message for OpenAI ─────────
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful weather assistant. "
                        "Use the available tools to answer weather questions. "
                        "Always provide temperatures in both Celsius and Fahrenheit."
                    )
                },
                {
                    "role": "user",
                    "content": user_question
                }
            ]

            # ══════════════════════════════════════════════
            #  AGENT LOOP
            #  Keep running until OpenAI gives a final text
            #  response (no more tool calls needed).
            # ══════════════════════════════════════════════
            print("\n🤖 Sending question to OpenAI GPT-4...")

            while True:

                # ── Call OpenAI with tools ─────────────────
                # OpenAI will either:
                # A) Return a text answer (done!)
                # B) Return tool_calls (needs MCP data first)
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",        # or "gpt-4o"
                    messages=messages,
                    tools=openai_tools,         # tell GPT what tools exist
                    tool_choice="auto",         # GPT decides when to use tools
                )

                message = response.choices[0].message

                # ── Check if GPT wants to call a tool ────
                if message.tool_calls:

                    print(f"\n🧠 GPT decided to call {len(message.tool_calls)} tool(s):")

                    # Add GPT's tool call decision to message history
                    messages.append({
                        "role":       "assistant",
                        "content":    message.content,
                        "tool_calls": [
                            {
                                "id":       tc.id,
                                "type":     "function",
                                "function": {
                                    "name":      tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in message.tool_calls
                        ]
                    })

                    # ── Execute each tool call on MCP ──────
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)

                        # Forward to MCP server → get result
                        tool_result = await call_mcp_tool(
                            session, tool_name, tool_args
                        )

                        # Add tool result to message history
                        # GPT will read this in the next round
                        messages.append({
                            "role":         "tool",
                            "tool_call_id": tool_call.id,
                            "content":      tool_result,
                        })

                    # Loop back → send tool results to GPT
                    print("\n🔄 Sending MCP results back to GPT...")
                    continue

                # ── GPT gave final text answer ────────────
                # No tool_calls means GPT has all the data
                # it needs and is giving the final response
                else:
                    final_answer = message.content
                    print("\n" + "="*60)
                    print(" FINAL ANSWER:")
                    print("="*60)
                    print(final_answer)
                    print("="*60)
                    return final_answer


# ══════════════════════════════════════════════════════════
#  RUN EXAMPLE QUESTIONS
# ══════════════════════════════════════════════════════════
async def main():

    # Example 1 — Simple weather query
    await run_agent(
        "What is the current weather in Hyderabad?"
    )

    # Example 2 — Comparison query (GPT calls compare_weather tool)
    await run_agent(
        "Which city is hotter right now — Hyderabad or Mumbai?"
    )

    # Example 3 — Complex query (GPT decides what tool to use)
    await run_agent(
        "Should I carry an umbrella in Delhi today?"
    )


if __name__ == "__main__":

    # ── Startup checks before running ─────────────────────
    print("\n" + "="*60)
    print(" STARTUP CHECKS")
    print("="*60)
    print(f" Python exe      : {PYTHON_EXE}")
    print(f" MCP Server file : {MCP_SERVER_FILE}")
    print(f" Server exists   : {Path(MCP_SERVER_FILE).exists()}")
    print(f" OPENAI_API_KEY  : {'SET ✅' if OPENAI_API_KEY else 'NOT SET ❌'}")
    print(f" SERPAPI_KEY     : {'SET ✅' if SERPAPI_KEY    else 'NOT SET ❌'}")
    print("="*60)

    # ── Stop early if anything is missing ─────────────────
    if not OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY missing in .env — exiting")
        sys.exit(1)

    if not SERPAPI_KEY:
        print("❌ SERPAPI_KEY missing in .env — exiting")
        sys.exit(1)

    if not Path(MCP_SERVER_FILE).exists():
        print(f"❌ MCP server file not found: {MCP_SERVER_FILE}")
        print(f"   Make sure 05_Weather_MCPServer.py is in the same folder")
        sys.exit(1)

    print("\n✅ All checks passed — starting agent...\n")
    asyncio.run(main())