# 🤖 MCP Server Real-Time Use Cases — Complete Guide
> **4 production-ready MCP servers for Agentic AI systems using FastMCP**

---

## 📁 Project Structure

```
mcp_usecases/
├── 01_jira_mcp/
│   └── jira_mcp_server.py        ← Jira story reader
├── 02_github_mcp/
│   └── github_mcp_server.py      ← GitHub file reader
├── 03_database_mcp/
│   ├── setup_db.sh               ← Docker + PostgreSQL setup
│   └── database_mcp_server.py    ← Database query server
├── 04_web_mcp/
│   └── web_mcp_server.py         ← Website scraper
└── README.md                     ← This file
```

---

## ⚙️ What is FastMCP?

**FastMCP** is a Python framework for building MCP (Model Context Protocol) servers.
MCP lets AI agents (like Claude, GPT, etc.) call your tools at runtime — just like
calling functions — to interact with real-world systems.

```
AI Agent  ──── MCP Protocol ──── Your MCP Server ──── Jira / GitHub / DB / Web
```

Install it once across all use cases:
```bash
pip install fastmcp
```

---

## 🎫 USE CASE 1 — Jira Story Reader

**Scenario:** An AI agent reads Jira tickets to understand sprint tasks and auto-generate summaries.

### Step 1 — Install dependencies
```bash
pip install fastmcp httpx
```

### Step 2 — Get your Jira API Token
1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token** → give it a name → copy the token

### Step 3 — Set environment variables
```bash
export JIRA_URL="https://yourcompany.atlassian.net"
export JIRA_EMAIL="you@company.com"
export JIRA_API_TOKEN="your_api_token_here"
```

### Step 4 — Run the MCP server
```bash
cd 01_jira_mcp/
python jira_mcp_server.py
```

### Step 5 — Test the tools (example calls)
```python
# Via MCP client or directly:
get_jira_issue("PROJ-42")
# → Returns: summary, description, status, assignee, story_points

search_jira_issues('project=PROJ AND status="In Progress"', max_results=5)
# → Returns: list of matching issues

get_issue_comments("PROJ-42")
# → Returns: all comments with authors and timestamps
```

### Available Tools
| Tool | Description |
|------|-------------|
| `get_jira_issue(issue_key)` | Fetch full details of one issue |
| `search_jira_issues(jql)` | Search issues using JQL query |
| `get_issue_comments(issue_key)` | Get all comments on an issue |

---

## 🐙 USE CASE 2 — GitHub File Reader

**Scenario:** An AI agent reads source code files and READMEs from GitHub to answer questions about a codebase.

### Step 1 — Install dependencies
```bash
pip install fastmcp httpx
```

### Step 2 — Get your GitHub Personal Access Token
1. Go to: https://github.com/settings/tokens
2. Click **Generate new token (classic)**
3. Select scope: `repo` (read-only access is enough)
4. Copy the token

### Step 3 — Set environment variable
```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

### Step 4 — Run the MCP server
```bash
cd 02_github_mcp/
python github_mcp_server.py
```

### Step 5 — Test the tools (example calls)
```python
# Read a specific file
read_github_file("openai", "openai-python", "README.md")
# → Returns: full file content as a string

# List all files in root of a repo
list_repo_files("anthropics", "anthropic-sdk-python")
# → Returns: list of files and directories

# Search code across the repo
search_github_code("microsoft", "vscode", "webview", max_results=5)
# → Returns: files that contain the keyword

# Get repo metadata
get_repo_info("huggingface", "transformers")
# → Returns: stars, forks, language, description
```

### Available Tools
| Tool | Description |
|------|-------------|
| `read_github_file(owner, repo, file_path)` | Read file content |
| `list_repo_files(owner, repo, path)` | List directory contents |
| `search_github_code(owner, repo, keyword)` | Search code by keyword |
| `get_repo_info(owner, repo)` | Get repo metadata |

---

## 🗄️ USE CASE 3 — PostgreSQL Database Reader

**Scenario:** An AI agent queries a company database to answer questions like  
"Who are the engineers?" or "Which projects are over budget?"

### Step 1 — Install dependencies
```bash
pip install fastmcp psycopg2-binary
```

### Step 2 — Start PostgreSQL via Docker (creates tables + sample data)
```bash
cd 03_database_mcp/
chmod +x setup_db.sh
./setup_db.sh
```

This script automatically:
- Pulls the `postgres:15-alpine` Docker image
- Starts a container named `mcp-postgres`
- Creates the `agentdb` database
- Creates 3 tables: `employees`, `projects`, `tasks`
- Inserts sample data into all tables

### Step 3 — Set environment variables
```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=agentdb
export DB_USER=agentuser
export DB_PASS=agentpass
```

### Step 4 — Run the MCP server
```bash
python database_mcp_server.py
```

### Step 5 — Test the tools (example calls)
```python
# Get all employees in Engineering
get_employees(department="Engineering")
# → Returns: Alice, Bob, Eva, Henry with roles and salaries

# Get all active projects
get_projects(status="active")
# → Returns: projects with owner name and budget

# Get tasks for project ID 1
get_tasks_for_project(project_id=1)
# → Returns: tasks sorted by priority with assignee names

# Run a custom SQL query
run_query("SELECT name, salary FROM employees WHERE salary > 100000")
# → Returns: employees earning more than 100k

# Department salary breakdown
get_department_summary()
# → Returns: avg/min/max salary per department
```

### Available Tools
| Tool | Description |
|------|-------------|
| `get_employees(department)` | List employees, optional dept filter |
| `get_projects(status)` | List projects, optional status filter |
| `get_tasks_for_project(project_id)` | Tasks for a specific project |
| `run_query(sql)` | Run any SELECT query |
| `get_department_summary()` | Salary stats per department |

### Database Schema
```
employees       projects          tasks
──────────      ──────────        ──────────
id              id                id
name            name              project_id → projects.id
department      status            title
role            budget            status
salary          start_date        assignee_id → employees.id
hire_date       end_date          priority
email           owner_id →        due_date
                employees.id
```

### Stop the Docker container when done
```bash
docker rm -f mcp-postgres
```

---

## 🌐 USE CASE 4 — Website Reader / Web Scraper

**Scenario:** An AI agent reads and extracts content from any public webpage — documentation sites, news articles, or competitor product pages.

### Step 1 — Install dependencies
```bash
pip install fastmcp httpx beautifulsoup4 lxml
```

### Step 2 — No API keys needed!
This server works on any public URL without authentication.

### Step 3 — Run the MCP server
```bash
cd 04_web_mcp/
python web_mcp_server.py
```

### Step 4 — Test the tools (example calls)
```python
# Read clean text from a webpage
read_webpage("https://docs.python.org/3/library/asyncio.html")
# → Returns: title, clean text content, word count

# Extract all links from a page
extract_links("https://news.ycombinator.com", internal_only=True)
# → Returns: list of links with label and URL

# Extract tables from a page (e.g., Wikipedia)
extract_tables("https://en.wikipedia.org/wiki/Python_(programming_language)")
# → Returns: structured table data with headers and rows

# Read multiple pages at once
batch_read_pages([
    "https://www.bbc.com/news",
    "https://techcrunch.com",
    "https://arxiv.org"
])
# → Returns: title + 500-char snippet for each page
```

### Available Tools
| Tool | Description |
|------|-------------|
| `read_webpage(url)` | Extract clean text from a URL |
| `extract_links(url, internal_only)` | Get all hyperlinks |
| `extract_tables(url)` | Extract HTML tables as structured data |
| `batch_read_pages(urls)` | Read up to 5 URLs in one call |

---

## 🔗 Connecting to an AI Agent (Claude / LangChain / etc.)

All 4 servers speak the standard **MCP stdio protocol**.  
Connect them to any MCP-compatible client:

### Claude Desktop (claude_desktop_config.json)
```json
{
  "mcpServers": {
    "jira": {
      "command": "python",
      "args": ["/path/to/01_jira_mcp/jira_mcp_server.py"],
      "env": {
        "JIRA_URL": "https://yourcompany.atlassian.net",
        "JIRA_EMAIL": "you@company.com",
        "JIRA_API_TOKEN": "your_token"
      }
    },
    "github": {
      "command": "python",
      "args": ["/path/to/02_github_mcp/github_mcp_server.py"],
      "env": { "GITHUB_TOKEN": "ghp_your_token" }
    },
    "database": {
      "command": "python",
      "args": ["/path/to/03_database_mcp/database_mcp_server.py"],
      "env": {
        "DB_HOST": "localhost", "DB_NAME": "agentdb",
        "DB_USER": "agentuser", "DB_PASS": "agentpass"
      }
    },
    "web": {
      "command": "python",
      "args": ["/path/to/04_web_mcp/web_mcp_server.py"]
    }
  }
}
```

### LangChain / Python Agent
```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["jira_mcp_server.py"],
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("get_jira_issue", {"issue_key": "PROJ-42"})
        print(result)
```

---

## 📦 All Dependencies (install once)
```bash
pip install fastmcp httpx psycopg2-binary beautifulsoup4 lxml
```

---

## 🧠 How FastMCP Works (Quick Reference)

```python
from fastmcp import FastMCP

mcp = FastMCP(name="my-server")   # 1. Create server

@mcp.tool()                        # 2. Decorate a function as a tool
def my_tool(arg: str) -> dict:     #    Type hints = auto schema generation
    """Docstring becomes tool description for the AI agent."""
    return {"result": arg}

mcp.run()                          # 3. Start the MCP server (stdio by default)
```

That's all there is to it. FastMCP handles:
- JSON schema generation from type hints
- MCP protocol communication
- Tool discovery by AI agents
