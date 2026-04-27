# 🚀 Deploy MCP Server — Complete Guide
> Share your MCP server with others via GitHub + Cloud Deployment

---

## 📋 Overview — 3 Ways to Share Your MCP Server

| Method | Best For | Cost | Difficulty |
|--------|----------|------|------------|
| **GitHub + Local Run** | Developers who clone and run | Free | Easy |
| **Deploy to Railway** | Remote access via URL | Free tier | Medium |
| **Deploy to Render** | Remote access via URL | Free tier | Medium |

---

## ═══════════════════════════════════════
## METHOD 1 — GitHub (Others Clone & Run)
## ═══════════════════════════════════════

### Step 1 — Structure your project folder

```
GenAI_MCP_Servers/
├── servers/
│   ├── jira_mcp_server.py
│   ├── github_mcp_server.py
│   ├── database_mcp_server.py
│   └── web_mcp_server.py
├── .env.example          ← template (never commit real .env)
├── .gitignore
├── requirements.txt
└── README.md
```

---

### Step 2 — Create `.env.example` (template for others)

```properties
# Jira Configuration
JIRA_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=your_jira_api_token_here

# GitHub Configuration
GITHUB_TOKEN=ghp_your_github_token_here

# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=agentdb
DB_USER=agentuser
DB_PASS=agentpass
```

---

### Step 3 — Create `.gitignore`

```gitignore
# Never commit these
.env
__pycache__/
*.pyc
*.pyo
.venv/
venv/
*.egg-info/
.DS_Store
```

---

### Step 4 — Create `requirements.txt`

```txt
fastmcp>=2.0.0
mcp>=1.0.0
httpx>=0.27.0
python-dotenv>=1.0.0
psycopg2-binary>=2.9.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
```

---

### Step 5 — Create `README.md` for others

```markdown
# MCP Servers — Agentic AI

4 MCP servers for Agentic AI systems.

## Quick Start

# 1. Clone the repo
git clone https://github.com/gvbigdata/GenAI_MCP_Servers.git
cd GenAI_MCP_Servers

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env template and fill in your values
cp .env.example .env

# 4. Run any MCP server
mcp dev servers/jira_mcp_server.py
mcp dev servers/github_mcp_server.py
mcp dev servers/database_mcp_server.py
mcp dev servers/web_mcp_server.py
```

---

### Step 6 — Push to GitHub

```powershell
# Initialize git
cd your_project_folder
git init

# Add all files
git add .

# Verify .env is NOT included
git status    # .env should NOT appear here

# Commit
git commit -m "Add 4 MCP servers for Agentic AI"

# Add remote and push
git remote add origin https://github.com/gvbigdata/GenAI_MCP_Servers.git
git push -u origin main
```

---

### How Others Use It (Local Run)

```powershell
# Clone
git clone https://github.com/gvbigdata/GenAI_MCP_Servers.git

# Install
pip install -r requirements.txt

# Setup env
cp .env.example .env
# Edit .env with their own credentials

# Run
mcp dev servers/jira_mcp_server.py
```

---

## ═══════════════════════════════════════
## METHOD 2 — Deploy to Railway (Remote URL)
## ═══════════════════════════════════════

This gives others a live URL like:
`https://your-mcp-server.railway.app`

### Step 1 — Update server to use SSE transport

Add this to the bottom of each server file:

```python
# Change mcp.run() to use SSE for remote access
if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
```

---

### Step 2 — Create `Procfile` in project root

```
web: python servers/jira_mcp_server.py
```

---

### Step 3 — Deploy to Railway

```powershell
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Set environment variables on Railway
railway variables set JIRA_URL=https://anilkds85.atlassian.net
railway variables set JIRA_EMAIL=gvbigdata@gmail.com
railway variables set JIRA_API_TOKEN=your_token_here

# Deploy
railway up
```

---

### Step 4 — Others connect via URL

After deployment Railway gives you a URL like:
```
https://jira-mcp-server-production.up.railway.app
```

Others add it to their `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jira": {
      "url": "https://jira-mcp-server-production.up.railway.app/sse"
    }
  }
}
```

---

## ═══════════════════════════════════════
## METHOD 3 — Deploy to Render (Free Tier)
## ═══════════════════════════════════════

### Step 1 — Create `render.yaml` in project root

```yaml
services:
  - type: web
    name: jira-mcp-server
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python servers/jira_mcp_server.py
    envVars:
      - key: JIRA_URL
        value: https://anilkds85.atlassian.net
      - key: JIRA_EMAIL
        value: gvbigdata@gmail.com
      - key: JIRA_API_TOKEN
        sync: false    # set manually in Render dashboard
      - key: PORT
        value: 8000
```

---

### Step 2 — Deploy

1. Go to → `https://render.com`
2. Click **New** → **Web Service**
3. Connect your GitHub repo
4. Render auto-detects `render.yaml`
5. Click **Deploy**
6. Set secret env vars in Render dashboard

---

### Step 3 — Others connect via URL

```json
{
  "mcpServers": {
    "jira": {
      "url": "https://jira-mcp-server.onrender.com/sse"
    }
  }
}
```

---

## ═══════════════════════════════════════
## HOW OTHERS CONNECT — All Options
## ═══════════════════════════════════════

### Option A — Claude Desktop Config

File location:
```
Windows : %APPDATA%\Claude\claude_desktop_config.json
Mac     : ~/Library/Application Support/Claude/claude_desktop_config.json
```

```json
{
  "mcpServers": {
    "jira": {
      "command": "python",
      "args": ["path/to/jira_mcp_server.py"],
      "env": {
        "JIRA_URL": "https://anilkds85.atlassian.net",
        "JIRA_EMAIL": "gvbigdata@gmail.com",
        "JIRA_API_TOKEN": "their_own_token"
      }
    },
    "github": {
      "command": "python",
      "args": ["path/to/github_mcp_server.py"],
      "env": {
        "GITHUB_TOKEN": "their_own_token"
      }
    },
    "web": {
      "command": "python",
      "args": ["path/to/web_mcp_server.py"]
    }
  }
}
```

---

### Option B — Remote URL (after Railway/Render deploy)

```json
{
  "mcpServers": {
    "jira-remote": {
      "url": "https://your-server.railway.app/sse"
    }
  }
}
```

---

### Option C — Python Agent (LangChain / LlamaIndex)

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio

async def use_mcp_server():
    server_params = StdioServerParameters(
        command="python",
        args=["jira_mcp_server.py"],
        env={
            "JIRA_URL":        "https://anilkds85.atlassian.net",
            "JIRA_EMAIL":      "gvbigdata@gmail.com",
            "JIRA_API_TOKEN":  "token_here",
        }
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Tools:", [t.name for t in tools])

            # Call a tool
            result = await session.call_tool(
                "get_jira_issue",
                {"issue_key": "KAN-1"}
            )
            print("Result:", result)

asyncio.run(use_mcp_server())
```

---

## ═══════════════════════════════════════
## SECURITY — Important Before Sharing
## ═══════════════════════════════════════

```
✅ DO
   - Commit .env.example with placeholder values
   - Add .env to .gitignore
   - Use environment variables for all secrets
   - Let users provide their own API tokens
   - Add rate limiting for public deployments

❌ NEVER
   - Commit .env file to GitHub
   - Hardcode API tokens in server files
   - Share your personal Jira/GitHub tokens
   - Deploy a shared Jira token (everyone uses same account)
```

---

## Quick Command Reference

```powershell
# Push to GitHub
git add .
git commit -m "your message"
git push origin main

# Deploy to Railway
railway up

# Others install and run
git clone https://github.com/gvbigdata/GenAI_MCP_Servers.git
pip install -r requirements.txt
cp .env.example .env
mcp dev servers/jira_mcp_server.py
```
