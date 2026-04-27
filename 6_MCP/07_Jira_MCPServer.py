# """
# ============================================================
#  MCP USE CASE 1: JIRA STORY READER
#  Real-time Jira story fetching using FastMCP
# ============================================================
#  PREREQUISITES:
#    pip install fastmcp httpx

#  SETUP:
#    export JIRA_URL="https://yourcompany.atlassian.net"
#    export JIRA_EMAIL="you@company.com"
#    export JIRA_API_TOKEN="your_api_token_here"

#  HOW TO GET JIRA API TOKEN:
#    1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
#    2. Click "Create API token"
#    3. Copy and export as JIRA_API_TOKEN
#    https://anilkds85.atlassian.net?continue=https%3A%2F%2Fanilkds85.atlassian.net%2Fwelcome%2Fsoftware&atlOrigin=eyJpIjoiMGViN2I1ZTY0ODRlNDdiOGIxYWZhNzc1ZGJiMGZkMGUiLCJwIjoiaiJ9
#    gvbigdata@gmail.com
#    JIRA_API_TOKEN = REMOVED 
#  RUN:
#    python jira_mcp_server.py
# ============================================================
# """
# from dotenv import load_dotenv
# load_dotenv()

# import os
# print("JIRA_URL   :", os.getenv("JIRA_URL"))
# print("JIRA_EMAIL :", os.getenv("JIRA_EMAIL"))
# print("JIRA_TOKEN :", os.getenv("JIRA_API_TOKEN", "NOT FOUND ❌")[:15])

# import os
# import base64
# import httpx
# from mcp.server.fastmcp import FastMCP


# # ── Init FastMCP server ────────────────────────────────────
# mcp = FastMCP(name="jira-reader")

# # ── Config (from env vars) ─────────────────────────────────
# JIRA_URL   = os.getenv("JIRA_URL")
# JIRA_EMAIL = os.getenv("JIRA_EMAIL")
# JIRA_TOKEN = os.getenv("JIRA_API_TOKEN")

# def _auth_header() -> dict:
#     """Build Basic Auth header from email + token."""
#     creds = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
#     return {
#         "Authorization": f"Basic {creds}",
#         "Content-Type":  "application/json",
#     }

# @mcp.tool()
# def list_projects() -> list[dict]:
#     """List all Jira projects and their keys."""
#     url = f"{JIRA_URL}/rest/api/3/project"

#     with httpx.Client() as client:
#         resp = client.get(url, headers=_auth_header())
#         print(f"Status Code : {resp.status_code}")
#         print(f"Response    : {resp.text[:500]}")
#         resp.raise_for_status()
#         projects = resp.json()

#     return [
#         {
#             "key":  p["key"],
#             "name": p["name"],
#             "type": p.get("projectTypeKey", ""),
#             "id":   p["id"],
#         }
#         for p in projects
#     ]


# # ══════════════════════════════════════════════════════════
# #  TOOL 1 — Get a single Jira issue by key
# # ══════════════════════════════════════════════════════════
# #issue_key=KAN-1
# @mcp.tool()
# def get_jira_issue(issue_key: str) -> dict:
#     url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
#     headers = _auth_header()

#     print(f"\n{'='*50}")
#     print(f"URL        : {url}")
#     print(f"Email      : {JIRA_EMAIL}")
#     print(f"Token      : {JIRA_TOKEN[:10]}...")
#     print(f"{'='*50}")

#     with httpx.Client() as client:
#         resp = client.get(url, headers=headers)

#         print(f"Status Code : {resp.status_code}")
#         print(f"Response    : {resp.text[:500]}")

#         if resp.status_code == 401:
#             return {"error": "401 Unauthorized - Check your JIRA_EMAIL and JIRA_API_TOKEN"}
#         elif resp.status_code == 404:
#             return {"error": f"404 Not Found - Issue {issue_key} does not exist"}
#         elif resp.status_code == 403:
#             return {"error": "403 Forbidden - You dont have permission to view this issue"}
#         elif not resp.text.strip():
#             return {"error": f"Empty response from Jira - Status code: {resp.status_code}"}

#         resp.raise_for_status()
#         data = resp.json()

#     fields = data.get("fields", {})
#     assignee = fields.get("assignee") or {}
#     story_points = (
#         fields.get("story_points")
#         or fields.get("customfield_10016")
#         or fields.get("customfield_10028")
#     )

#     return {
#         "key":          data["key"],
#         "summary":      fields.get("summary", ""),
#         "description":  _extract_description(fields.get("description")),
#         "status":       fields.get("status", {}).get("name", "Unknown"),
#         "priority":     fields.get("priority", {}).get("name", "None"),
#         "assignee":     assignee.get("displayName", "Unassigned"),
#         "story_points": story_points,
#         "issue_type":   fields.get("issuetype", {}).get("name", ""),
#         "labels":       fields.get("labels", []),
#         "url":          f"{JIRA_URL}/browse/{data['key']}",
#     }

# def _auth_header() -> dict:
#     creds = base64.b64encode(
#         f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()
#     ).decode()
#     return {
#         "Authorization": f"Basic {creds}",
#         "Accept":        "application/json",      # ← make sure this line exists
#         "Content-Type":  "application/json",
#     }
# # ══════════════════════════════════════════════════════════
# #  TOOL 2 — Search Jira issues with JQL
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def search_jira_issues(jql: str, max_results: int = 10) -> list[dict]:
#     """
#     Search Jira using JQL (Jira Query Language).

#     Args:
#         jql:         JQL query string e.g. 'project=KAN AND status="In Progress"'
#         max_results: Maximum number of results to return (default 10)

#     Returns:
#         List of issue summaries
#     """
#     url = f"{JIRA_URL}/rest/api/3/search/jql"   # ← updated endpoint

#     params = {
#         "jql":        jql,
#         "maxResults": max_results,
#         "fields":     "summary,status,assignee,priority,issuetype",
#     }

#     print(f"\n{'='*50}")
#     print(f"URL : {url}")
#     print(f"JQL : {jql}")
#     print(f"{'='*50}")

#     with httpx.Client(follow_redirects=False) as client:
#         resp = client.get(url, headers=_auth_header(), params=params)  # ← GET not POST

#         print(f"Status Code : {resp.status_code}")
#         print(f"Response    : {resp.text[:500]}")

#         if resp.status_code == 400:
#             return [{"error": f"Bad JQL: {resp.text}"}]
#         elif resp.status_code == 401:
#             return [{"error": "Unauthorized - check your token"}]

#         resp.raise_for_status()
#         data = resp.json()

#     issues = []
#     for issue in data.get("issues", []):
#         f = issue["fields"]
#         issues.append({
#             "key":      issue["key"],
#             "summary":  f.get("summary", ""),
#             "status":   f.get("status", {}).get("name", ""),
#             "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
#             "type":     f.get("issuetype", {}).get("name", ""),
#             "url":      f"{JIRA_URL}/browse/{issue['key']}",
#         })

#     return issues


# # ══════════════════════════════════════════════════════════
# #  TOOL 3 — Get all comments on an issue
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def get_issue_comments(issue_key: str) -> list[dict]:
#     """
#     Fetch all comments for a Jira issue.

#     Args:
#         issue_key: Jira issue key e.g. 'KAN-1'

#     Returns:
#         List of comments with author, body, and creation time
#     """
#     url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/comment"

#     print(f"\n{'='*50}")
#     print(f"URL       : {url}")
#     print(f"Issue Key : {issue_key}")
#     print(f"{'='*50}")

#     with httpx.Client(follow_redirects=False) as client:
#         resp = client.get(url, headers=_auth_header())

#         print(f"Status Code : {resp.status_code}")
#         print(f"Response    : {resp.text[:500]}")

#         if resp.status_code == 404:
#             return [{"error": f"Issue {issue_key} not found"}]
#         elif resp.status_code == 401:
#             return [{"error": "Unauthorized - check your token"}]
#         elif resp.status_code == 403:
#             return [{"error": "Forbidden - no permission to view comments"}]
#         elif resp.status_code == 410:
#             return [{"error": "Endpoint deprecated - needs update"}]

#         resp.raise_for_status()
#         data = resp.json()

#     comments = data.get("comments", [])

#     # ── No comments on this ticket ─────────────────────────
#     if not comments:
#         return [{"message": f"No comments found on {issue_key}"}]

#     return [
#         {
#             "author":  c.get("author", {}).get("displayName", "Unknown"),
#             "body":    _extract_description(c.get("body")),
#             "created": c.get("created", ""),
#             "updated": c.get("updated", ""),
#         }
#         for c in comments
#     ]


# # ── Helpers ────────────────────────────────────────────────
# def _extract_description(adf_node) -> str:
#     """Recursively extract plain text from Atlassian Document Format (ADF)."""
#     if adf_node is None:
#         return ""
#     if isinstance(adf_node, str):
#         return adf_node
#     if isinstance(adf_node, dict):
#         if adf_node.get("type") == "text":
#             return adf_node.get("text", "")
#         return " ".join(
#             _extract_description(child)
#             for child in adf_node.get("content", [])
#         )
#     return ""


# # ── Entry point ────────────────────────────────────────────
# if __name__ == "__main__":
#     print("🚀 Jira MCP Server running...")
#     mcp.run()

"""
JIRA MCP SERVER
Fixed: removed all print() to stdout — corrupts stdio pipe
All logging redirected to stderr only
"""
import os
import sys
import base64
import httpx
from pathlib import Path
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ── Load .env from same folder as this file ───────────────
load_dotenv(Path(__file__).parent / ".env")

def log(msg):
    """Log to stderr only — stdout is reserved for MCP protocol."""
    print(msg, file=sys.stderr, flush=True)

# ── Config ─────────────────────────────────────────────────
JIRA_URL   = os.getenv("JIRA_URL", "")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_TOKEN = os.getenv("JIRA_API_TOKEN", "")

log(f"JIRA_URL   : {JIRA_URL}")
log(f"JIRA_EMAIL : {JIRA_EMAIL}")
log(f"JIRA_TOKEN : {'SET' if JIRA_TOKEN else 'NOT SET'}")

mcp = FastMCP(name="jira-reader")


def _auth_header() -> dict:
    """Build Basic Auth header from email + token."""
    creds = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Accept":        "application/json",
        "Content-Type":  "application/json",
    }


def _extract_description(adf_node) -> str:
    """Recursively extract plain text from Atlassian Document Format."""
    if adf_node is None:
        return ""
    if isinstance(adf_node, str):
        return adf_node
    if isinstance(adf_node, dict):
        if adf_node.get("type") == "text":
            return adf_node.get("text", "")
        return " ".join(
            _extract_description(child)
            for child in adf_node.get("content", [])
        )
    return ""


@mcp.tool()
def get_jira_issue(issue_key: str) -> dict:
    """
    Fetch full details of a Jira issue by key.

    Args:
        issue_key: Jira issue key e.g. 'KAN-1', 'KAN-2'

    Returns:
        Dict with summary, status, priority, assignee and description
    """
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"
    log(f"Fetching issue: {url}")

    with httpx.Client() as client:
        resp = client.get(url, headers=_auth_header())
        log(f"Status: {resp.status_code}")

        if resp.status_code == 401:
            return {"error": "401 Unauthorized - check JIRA_EMAIL and JIRA_API_TOKEN"}
        elif resp.status_code == 404:
            return {"error": f"404 Not Found - Issue {issue_key} does not exist"}
        elif resp.status_code == 403:
            return {"error": "403 Forbidden - no permission to view this issue"}
        elif not resp.text.strip():
            return {"error": f"Empty response - Status: {resp.status_code}"}

        resp.raise_for_status()
        data = resp.json()

    fields       = data.get("fields", {})
    assignee     = fields.get("assignee") or {}
    story_points = (
        fields.get("story_points")
        or fields.get("customfield_10016")
        or fields.get("customfield_10028")
    )

    return {
        "key":          data["key"],
        "summary":      fields.get("summary", ""),
        "description":  _extract_description(fields.get("description")),
        "status":       fields.get("status", {}).get("name", "Unknown"),
        "priority":     fields.get("priority", {}).get("name", "None"),
        "assignee":     assignee.get("displayName", "Unassigned"),
        "story_points": story_points,
        "issue_type":   fields.get("issuetype", {}).get("name", ""),
        "labels":       fields.get("labels", []),
        "url":          f"{JIRA_URL}/browse/{data['key']}",
    }


@mcp.tool()
def search_jira_issues(jql: str, max_results: int = 10) -> list[dict]:
    """
    Search Jira using JQL (Jira Query Language).

    Args:
        jql:         JQL query e.g. 'project=KAN AND status="In Progress"'
        max_results: Max results to return (default 10)

    Returns:
        List of matching issues
    """
    url    = f"{JIRA_URL}/rest/api/3/search/jql"
    params = {
        "jql":        jql,
        "maxResults": max_results,
        "fields":     "summary,status,assignee,priority,issuetype",
    }
    log(f"JQL search: {jql}")

    with httpx.Client(follow_redirects=False) as client:
        resp = client.get(url, headers=_auth_header(), params=params)
        log(f"Status: {resp.status_code}")

        if resp.status_code == 400:
            return [{"error": f"Bad JQL: {resp.text}"}]
        elif resp.status_code == 401:
            return [{"error": "Unauthorized - check your token"}]

        resp.raise_for_status()
        data = resp.json()

    issues = []
    for issue in data.get("issues", []):
        f = issue["fields"]
        issues.append({
            "key":      issue["key"],
            "summary":  f.get("summary", ""),
            "status":   f.get("status", {}).get("name", ""),
            "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
            "type":     f.get("issuetype", {}).get("name", ""),
            "url":      f"{JIRA_URL}/browse/{issue['key']}",
        })
    return issues


@mcp.tool()
def get_issue_comments(issue_key: str) -> list[dict]:
    """
    Fetch all comments for a Jira issue.

    Args:
        issue_key: Jira issue key e.g. 'KAN-1'

    Returns:
        List of comments with author, body, and creation time
    """
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/comment"
    log(f"Fetching comments for: {issue_key}")

    with httpx.Client(follow_redirects=False) as client:
        resp = client.get(url, headers=_auth_header())
        log(f"Status: {resp.status_code}")

        if resp.status_code == 404:
            return [{"error": f"Issue {issue_key} not found"}]
        elif resp.status_code == 401:
            return [{"error": "Unauthorized - check your token"}]
        elif resp.status_code == 403:
            return [{"error": "Forbidden - no permission to view comments"}]

        resp.raise_for_status()
        data = resp.json()

    comments = data.get("comments", [])
    if not comments:
        return [{"message": f"No comments found on {issue_key}"}]

    return [
        {
            "author":  c.get("author", {}).get("displayName", "Unknown"),
            "body":    _extract_description(c.get("body")),
            "created": c.get("created", ""),
        }
        for c in comments
    ]


if __name__ == "__main__":
    log("Jira MCP Server starting...")
    mcp.run(transport="stdio")