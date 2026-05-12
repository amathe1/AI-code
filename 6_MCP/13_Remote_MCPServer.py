"""
cd "D:\GenAI Content\AI code\6_MCP"

git init
git add .
git status          # verify .env is NOT listed
git commit -m "Add MCP servers for Agentic AI"
git remote add origin https://github.com/amathe1/AI-code.git
git push -u origin main

Calculator MCP Client — Server loaded from GitHub
pip install openai mcp python-dotenv
Add OPENAI_API_KEY to .env
Run: python 13_Remote_MCPServer.py
"""

import os
import sys
import json
import asyncio
import subprocess
import tempfile
import shutil
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv(Path(__file__).parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── GitHub config ─────────────────────────────────────────
GITHUB_REPO    = "https://github.com/amathe1/AI-code.git"
SERVER_FILE    = "02_Calculator_MCPServer.py"   # file name inside repo


async def main():
    question = "What is 25 multiplied by 48?"
    print(f"Question : {question}")

    # ── Step 1: Clone repo from GitHub ────────────────────
    temp_dir = tempfile.mkdtemp(prefix="mcp_")
    print(f"Cloning  : {GITHUB_REPO}")
    subprocess.run(
        ["git", "clone", "--depth=1", GITHUB_REPO, temp_dir],
        capture_output=True,
    )

    # ── Step 2: Find server file in cloned repo ───────────
    # Search recursively in case it's inside a subfolder
    matches = list(Path(temp_dir).rglob(SERVER_FILE))
    if not matches:
        print(f"❌ {SERVER_FILE} not found in repo")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return

    server_file = str(matches[0])
    print(f"Found    : {server_file}")

    # ── Step 3: Start MCP server from cloned file ─────────
    params = StdioServerParameters(
        command=sys.executable,
        args=[server_file],
        env={"PATH": os.environ.get("PATH", "")}
    )

    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # ── Get tools ─────────────────────────────
                tools = await session.list_tools()
                print(f"Tools    : {[t.name for t in tools.tools]}")

                openai_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name":        t.name,
                            "description": t.description,
                            "parameters":  t.inputSchema,
                        }
                    }
                    for t in tools.tools
                ]

                # ── Ask OpenAI ────────────────────────────
                client   = OpenAI(api_key=OPENAI_API_KEY)
                messages = [
                    {"role": "system", "content": "Use tools to answer math questions."},
                    {"role": "user",   "content": question},
                ]

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                )
                message = response.choices[0].message

                # ── Call MCP tool ─────────────────────────
                if message.tool_calls:
                    tc        = message.tool_calls[0]
                    tool_name = tc.function.name
                    tool_args = json.loads(tc.function.arguments)
                    print(f"Calling  : {tool_name}({tool_args})")

                    result      = await session.call_tool(tool_name, tool_args)
                    result_text = result.content[0].text
                    print(f"Result   : {result_text}")

                    messages += [
                        {
                            "role": "assistant", "content": message.content,
                            "tool_calls": [{"id": tc.id, "type": "function",
                                            "function": {"name": tc.function.name,
                                                         "arguments": tc.function.arguments}}]
                        },
                        {"role": "tool", "tool_call_id": tc.id, "content": result_text},
                    ]
                    final  = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
                    answer = final.choices[0].message.content
                else:
                    answer = message.content

                print(f"Answer   : {answer}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("Cleaned up temp folder ✅")


if __name__ == "__main__":
    asyncio.run(main())