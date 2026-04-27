# """
# ============================================================
#  MCP USE CASE 2: GITHUB FILE READER
#  Read files and repo content from GitHub using FastMCP
# ============================================================
#  PREREQUISITES:
#    pip install fastmcp httpx

#  SETUP:
#    export GITHUB_TOKEN="ghp_your_personal_access_token"

#  HOW TO GET GITHUB TOKEN:
#    1. Go to https://github.com/settings/tokens
#    2. Click "Generate new token (classic)"
#    3. Select scopes: repo (full), read:org
#    4. Copy and export as GITHUB_TOKEN

#  RUN:
#    python github_mcp_server.py
# ============================================================
# """
# from dotenv import load_dotenv
# load_dotenv()

# import os
# import base64
# import httpx
# from mcp.server.fastmcp import FastMCP

# # ── Init FastMCP server ────────────────────────────────────
# mcp = FastMCP(name="github-reader")

# GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
# GITHUB_API   = "https://api.github.com"

# def _headers() -> dict:
#     return {
#         "Authorization": f"Bearer {GITHUB_TOKEN}",
#         "Accept":        "application/vnd.github+json",
#         "X-GitHub-Api-Version": "2022-11-28",
#     }


# # ══════════════════════════════════════════════════════════
# #  TOOL 1 — Read a file from a GitHub repository
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def read_github_file(owner: str, repo: str, file_path: str, branch: str = "main") -> dict:
#     """
#     Read the content of a specific file from a GitHub repository.

#     Args:
#         owner:     GitHub username or org, e.g. 'microsoft'
#         repo:      Repository name, e.g. 'vscode'
#         file_path: Path to file inside repo, e.g. 'README.md'
#         branch:    Branch name (default: 'main')

#     Returns:
#         Dict with file name, path, size, content, and sha
#     """
#     url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{file_path}"
#     params = {"ref": branch}

#     with httpx.Client() as client:
#         resp = client.get(url, headers=_headers(), params=params)
#         resp.raise_for_status()
#         data = resp.json()

#     # GitHub returns content as base64-encoded string
#     raw_content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")

#     return {
#         "name":         data["name"],
#         "path":         data["path"],
#         "size_bytes":   data["size"],
#         "sha":          data["sha"],
#         "branch":       branch,
#         "html_url":     data["html_url"],
#         "content":      raw_content,
#         "encoding":     data["encoding"],
#     }


# # ══════════════════════════════════════════════════════════
# #  TOOL 2 — List files in a directory of a repo
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def list_repo_files(owner: str, repo: str, path: str = "", branch: str = "main") -> list[dict]:
#     """
#     List all files and directories at a given path in a GitHub repo.

#     Args:
#         owner:  GitHub username or org
#         repo:   Repository name
#         path:   Directory path inside repo ('' for root)
#         branch: Branch name (default: 'main')

#     Returns:
#         List of file/directory entries with name, type, size, and URL
#     """
#     url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
#     params = {"ref": branch}

#     with httpx.Client() as client:
#         resp = client.get(url, headers=_headers(), params=params)
#         resp.raise_for_status()
#         items = resp.json()

#     return [
#         {
#             "name":     item["name"],
#             "type":     item["type"],           # 'file' or 'dir'
#             "size":     item.get("size", 0),
#             "path":     item["path"],
#             "html_url": item["html_url"],
#             "sha":      item["sha"],
#         }
#         for item in items
#     ]


# # ══════════════════════════════════════════════════════════
# #  TOOL 3 — Search code inside a repository
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def search_github_code(owner: str, repo: str, keyword: str, branch: str = "main") -> list[dict]:
#     """
#     Search for a keyword across all files in a GitHub repository
#     by recursively reading the file tree.

#     Args:
#         owner:   GitHub username or org  e.g. 'gvbigdata'
#         repo:    Repository name         e.g. 'GenAI_AgenticAI_RAG'
#         keyword: Search keyword          e.g. 'embedding'
#         branch:  Branch name             (default: 'main')

#     Returns:
#         List of matching files with path and matched lines
#     """
#     # ── Step 1: Get full file tree ─────────────────────────
#     tree_url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}"
#     params   = {"recursive": "1"}

#     print(f"\n{'='*50}")
#     print(f"Fetching file tree for : {owner}/{repo}")
#     print(f"Searching keyword      : {keyword}")
#     print(f"{'='*50}")

#     with httpx.Client(follow_redirects=True) as client:
#         resp = client.get(tree_url, headers=_headers(), params=params)

#         print(f"Tree Status : {resp.status_code}")

#         if resp.status_code == 404:
#             return [{"error": f"Repo not found: {owner}/{repo}"}]
#         elif resp.status_code == 403:
#             return [{"error": "Rate limit exceeded - wait 60 seconds"}]

#         resp.raise_for_status()
#         tree = resp.json()

#     # ── Step 2: Filter only text/code files ───────────────
#     code_extensions = {
#         ".py", ".js", ".ts", ".java", ".go", ".rb", ".rs",
#         ".cpp", ".c", ".h", ".cs", ".php", ".md", ".txt",
#         ".yaml", ".yml", ".json", ".toml", ".sh", ".ipynb"
#     }

#     files = [
#         item for item in tree.get("tree", [])
#         if item["type"] == "blob"
#         and any(item["path"].endswith(ext) for ext in code_extensions)
#         and item.get("size", 0) < 500000   # skip files > 500KB
#     ]

#     print(f"Total files to search : {len(files)}")

#     # ── Step 3: Read each file and search for keyword ──────
#     matches = []

#     with httpx.Client(follow_redirects=True) as client:
#         for file in files[:30]:   # limit to 30 files to avoid rate limit
#             file_url = (
#                 f"https://raw.githubusercontent.com"
#                 f"/{owner}/{repo}/{branch}/{file['path']}"
#             )
#             try:
#                 r = client.get(file_url, headers=_headers())
#                 if r.status_code != 200:
#                     continue

#                 content = r.text
#                 if keyword.lower() in content.lower():
#                     # Find matching lines
#                     matched_lines = [
#                         f"Line {i+1}: {line.strip()}"
#                         for i, line in enumerate(content.splitlines())
#                         if keyword.lower() in line.lower()
#                     ][:5]   # max 5 matching lines per file

#                     matches.append({
#                         "path":          file["path"],
#                         "html_url":      f"https://github.com/{owner}/{repo}/blob/{branch}/{file['path']}",
#                         "matched_lines": matched_lines,
#                         "total_matches": len([
#                             l for l in content.splitlines()
#                             if keyword.lower() in l.lower()
#                         ]),
#                     })

#             except Exception as e:
#                 print(f"Skipping {file['path']}: {e}")
#                 continue

#     if not matches:
#         return [{"message": f"No files found containing '{keyword}' in {owner}/{repo}"}]

#     print(f"Files matched : {len(matches)}")
#     return matches


# # ══════════════════════════════════════════════════════════
# #  TOOL 4 — Get repo metadata
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def get_repo_info(owner: str, repo: str) -> dict:
#     """
#     Get metadata and statistics for a GitHub repository.

#     Args:
#         owner: GitHub username or org
#         repo:  Repository name

#     Returns:
#         Dict with repo description, stars, forks, language, and more
#     """
#     url = f"{GITHUB_API}/repos/{owner}/{repo}"

#     with httpx.Client() as client:
#         resp = client.get(url, headers=_headers())
#         resp.raise_for_status()
#         data = resp.json()

#     return {
#         "full_name":       data["full_name"],
#         "description":     data.get("description", ""),
#         "language":        data.get("language", ""),
#         "stars":           data["stargazers_count"],
#         "forks":           data["forks_count"],
#         "open_issues":     data["open_issues_count"],
#         "default_branch":  data["default_branch"],
#         "visibility":      data["visibility"],
#         "html_url":        data["html_url"],
#         "created_at":      data["created_at"],
#         "updated_at":      data["updated_at"],
#     }


# # ── Entry point ────────────────────────────────────────────
# if __name__ == "__main__":
#     print("🚀 GitHub MCP Server running...")
#     mcp.run()

"""
GITHUB MCP SERVER
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

load_dotenv(Path(__file__).parent / ".env")

def log(msg):
    print(msg, file=sys.stderr, flush=True)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API   = "https://api.github.com"

log(f"GITHUB_TOKEN: {'SET' if GITHUB_TOKEN else 'NOT SET'}")

mcp = FastMCP(name="github-reader")


def _headers() -> dict:
    return {
        "Authorization":        f"Bearer {GITHUB_TOKEN}",
        "Accept":               "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@mcp.tool()
def read_github_file(owner: str, repo: str, file_path: str, branch: str = "main") -> dict:
    """
    Read the content of a file from a GitHub repository.

    Args:
        owner:     GitHub username or org e.g. 'gvbigdata'
        repo:      Repository name e.g. 'GenAI_AgenticAI_RAG'
        file_path: Path to file e.g. 'README.md'
        branch:    Branch name (default: 'main')

    Returns:
        Dict with file name, path, size, and content
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{file_path}"
    log(f"Reading file: {owner}/{repo}/{file_path}")

    with httpx.Client() as client:
        resp = client.get(url, headers=_headers(), params={"ref": branch})
        resp.raise_for_status()
        data = resp.json()

    raw_content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return {
        "name":       data["name"],
        "path":       data["path"],
        "size_bytes": data["size"],
        "branch":     branch,
        "html_url":   data["html_url"],
        "content":    raw_content,
    }


@mcp.tool()
def list_repo_files(owner: str, repo: str, path: str = "", branch: str = "main") -> list[dict]:
    """
    List all files and directories at a given path in a GitHub repo.

    Args:
        owner:  GitHub username or org
        repo:   Repository name
        path:   Directory path ('' for root)
        branch: Branch name (default: 'main')

    Returns:
        List of files and directories
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    log(f"Listing files: {owner}/{repo}/{path}")

    with httpx.Client() as client:
        resp = client.get(url, headers=_headers(), params={"ref": branch})
        resp.raise_for_status()
        items = resp.json()

    return [
        {
            "name":     item["name"],
            "type":     item["type"],
            "size":     item.get("size", 0),
            "path":     item["path"],
            "html_url": item["html_url"],
        }
        for item in items
    ]


@mcp.tool()
def search_github_code(owner: str, repo: str, keyword: str, branch: str = "main") -> list[dict]:
    """
    Search for a keyword across all files in a GitHub repository.

    Args:
        owner:   GitHub username or org
        repo:    Repository name
        keyword: Search keyword e.g. 'embedding'
        branch:  Branch name (default: 'main')

    Returns:
        List of files containing the keyword with matching lines
    """
    tree_url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}"
    log(f"Searching '{keyword}' in {owner}/{repo}")

    with httpx.Client(follow_redirects=True) as client:
        resp = client.get(tree_url, headers=_headers(), params={"recursive": "1"})
        if resp.status_code == 404:
            return [{"error": f"Repo not found: {owner}/{repo}"}]
        resp.raise_for_status()
        tree = resp.json()

    code_extensions = {
        ".py", ".js", ".ts", ".java", ".go", ".md", ".txt",
        ".yaml", ".yml", ".json", ".toml", ".sh", ".ipynb"
    }
    files = [
        item for item in tree.get("tree", [])
        if item["type"] == "blob"
        and any(item["path"].endswith(ext) for ext in code_extensions)
        and item.get("size", 0) < 500000
    ]

    matches = []
    with httpx.Client(follow_redirects=True) as client:
        for file in files[:30]:
            file_url = (
                f"https://raw.githubusercontent.com"
                f"/{owner}/{repo}/{branch}/{file['path']}"
            )
            try:
                r = client.get(file_url, headers=_headers())
                if r.status_code != 200:
                    continue
                content = r.text
                if keyword.lower() in content.lower():
                    matched_lines = [
                        f"Line {i+1}: {line.strip()}"
                        for i, line in enumerate(content.splitlines())
                        if keyword.lower() in line.lower()
                    ][:5]
                    matches.append({
                        "path":          file["path"],
                        "html_url":      f"https://github.com/{owner}/{repo}/blob/{branch}/{file['path']}",
                        "matched_lines": matched_lines,
                    })
            except Exception:
                continue

    if not matches:
        return [{"message": f"No files found containing '{keyword}' in {owner}/{repo}"}]
    return matches


@mcp.tool()
def get_repo_info(owner: str, repo: str) -> dict:
    """
    Get metadata for a GitHub repository.

    Args:
        owner: GitHub username or org
        repo:  Repository name

    Returns:
        Dict with stars, forks, language, description
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    log(f"Getting repo info: {owner}/{repo}")

    with httpx.Client() as client:
        resp = client.get(url, headers=_headers())
        resp.raise_for_status()
        data = resp.json()

    return {
        "full_name":   data["full_name"],
        "description": data.get("description", ""),
        "language":    data.get("language", ""),
        "stars":       data["stargazers_count"],
        "forks":       data["forks_count"],
        "open_issues": data["open_issues_count"],
        "html_url":    data["html_url"],
        "updated_at":  data["updated_at"],
    }


if __name__ == "__main__":
    log("GitHub MCP Server starting...")
    mcp.run(transport="stdio")