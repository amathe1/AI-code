# """
# ============================================================
#  MCP USE CASE 4: WEBSITE READER / WEB SCRAPER
#  Extract clean content from any public URL using FastMCP
# ============================================================
#  PREREQUISITES:
#    pip install fastmcp httpx beautifulsoup4 lxml

#  RUN:
#    python web_mcp_server.py
# ============================================================
# """

# import re
# import httpx
# from urllib.parse import urljoin, urlparse
# from bs4 import BeautifulSoup
# from mcp.server.fastmcp import FastMCP

# # ── Init FastMCP server ────────────────────────────────────
# mcp = FastMCP(name="web-reader")

# # Reasonable timeout for web requests
# REQUEST_TIMEOUT = 15

# HEADERS = {
#     "User-Agent": (
#         "Mozilla/5.0 (compatible; AgentBot/1.0; "
#         "+https://example.com/bot)"
#     )
# }


# # ══════════════════════════════════════════════════════════
# #  TOOL 1 — Read clean text content from any URL
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def read_webpage(url: str) -> dict:
#     """
#     Fetch a webpage and extract its clean, readable text content.
#     Strips away navigation, ads, and boilerplate HTML.

#     Args:
#         url: Full URL of the webpage to read (including https://)

#     Returns:
#         Dict with title, main text content, word count, and metadata
#     """
#     with httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
#         resp = client.get(url, headers=HEADERS)
#         resp.raise_for_status()
#         html = resp.text

#     soup = BeautifulSoup(html, "lxml")

#     # ── Remove noise elements ──────────────────────────────
#     for tag in soup(["script", "style", "nav", "footer", "header",
#                       "aside", "form", "noscript", "iframe"]):
#         tag.decompose()

#     # ── Extract title ──────────────────────────────────────
#     title = ""
#     if soup.title:
#         title = soup.title.get_text(strip=True)

#     # ── Extract meta description ───────────────────────────
#     meta_desc = ""
#     meta_tag = soup.find("meta", attrs={"name": "description"})
#     if meta_tag:
#         meta_desc = meta_tag.get("content", "")

#     # ── Extract main content (prefer article/main tags) ────
#     main_content = (
#         soup.find("article")
#         or soup.find("main")
#         or soup.find(id="content")
#         or soup.find(class_=re.compile(r"content|article|post|entry", re.I))
#         or soup.body
#     )

#     if main_content:
#         raw_text = main_content.get_text(separator="\n", strip=True)
#     else:
#         raw_text = soup.get_text(separator="\n", strip=True)

#     # ── Clean up excessive blank lines ────────────────────
#     lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
#     clean_text = "\n".join(lines)

#     return {
#         "url":         url,
#         "title":       title,
#         "description": meta_desc,
#         "content":     clean_text[:8000],   # cap at 8k chars
#         "word_count":  len(clean_text.split()),
#         "domain":      urlparse(url).netloc,
#     }


# # ══════════════════════════════════════════════════════════
# #  TOOL 2 — Extract all links from a webpage
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def extract_links(url: str, internal_only: bool = False) -> list[dict]:
#     """
#     Extract all hyperlinks found on a webpage.

#     Args:
#         url:           Full URL of the webpage
#         internal_only: If True, return only links on the same domain

#     Returns:
#         List of links with text label and href
#     """
#     with httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
#         resp = client.get(url, headers=HEADERS)
#         resp.raise_for_status()
#         html = resp.text

#     soup  = BeautifulSoup(html, "lxml")
#     base  = urlparse(url).netloc
#     links = []

#     for anchor in soup.find_all("a", href=True):
#         href  = anchor["href"].strip()
#         text  = anchor.get_text(strip=True)

#         # Resolve relative URLs
#         full_url = urljoin(url, href)
#         link_domain = urlparse(full_url).netloc

#         # Skip anchors, mailto, tel, javascript links
#         if any(href.startswith(p) for p in ("#", "mailto:", "tel:", "javascript:")):
#             continue

#         if internal_only and link_domain != base:
#             continue

#         links.append({
#             "text":   text[:120],
#             "url":    full_url,
#             "domain": link_domain,
#         })

#     # Deduplicate by URL
#     seen  = set()
#     unique = []
#     for link in links:
#         if link["url"] not in seen:
#             seen.add(link["url"])
#             unique.append(link)

#     return unique[:50]  # return max 50 links


# # ══════════════════════════════════════════════════════════
# #  TOOL 3 — Extract structured data: tables from a webpage
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def extract_tables(url: str) -> list[dict]:
#     """
#     Extract all HTML tables from a webpage as structured data.

#     Args:
#         url: Full URL of the webpage

#     Returns:
#         List of tables, each with headers and rows
#     """
#     with httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
#         resp = client.get(url, headers=HEADERS)
#         resp.raise_for_status()
#         html = resp.text

#     soup   = BeautifulSoup(html, "lxml")
#     tables = []

#     for i, table in enumerate(soup.find_all("table")):
#         headers = [th.get_text(strip=True) for th in table.find_all("th")]

#         rows = []
#         for tr in table.find_all("tr"):
#             cells = [td.get_text(strip=True) for td in tr.find_all("td")]
#             if cells:
#                 if headers:
#                     row = dict(zip(headers, cells))
#                 else:
#                     row = {f"col_{j}": v for j, v in enumerate(cells)}
#                 rows.append(row)

#         if rows:
#             tables.append({
#                 "table_index": i,
#                 "headers":     headers,
#                 "row_count":   len(rows),
#                 "rows":        rows[:100],  # cap at 100 rows
#             })

#     return tables


# # ══════════════════════════════════════════════════════════
# #  TOOL 4 — Fetch and summarize multiple URLs at once
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def batch_read_pages(urls: list[str]) -> list[dict]:
#     """
#     Fetch and extract text from multiple webpages in one call.

#     Args:
#         urls: List of URLs to fetch (max 5)

#     Returns:
#         List of page summaries (title + first 500 chars of content)
#     """
#     if len(urls) > 5:
#         raise ValueError("Maximum 5 URLs per batch request.")

#     results = []
#     for url in urls:
#         try:
#             page = read_webpage(url)
#             results.append({
#                 "url":     url,
#                 "title":   page["title"],
#                 "snippet": page["content"][:500],
#                 "words":   page["word_count"],
#                 "status":  "ok",
#             })
#         except Exception as exc:
#             results.append({
#                 "url":    url,
#                 "status": "error",
#                 "error":  str(exc),
#             })

#     return results


# # ── Entry point ────────────────────────────────────────────
# if __name__ == "__main__":
#     print("🚀 Web Reader MCP Server running...")
#     mcp.run()

import re
import sys
import httpx
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP
 
def log(msg):
    print(msg, file=sys.stderr, flush=True)
 
mcp = FastMCP(name="web-reader")
REQUEST_TIMEOUT = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AgentBot/1.0)"}
 
@mcp.tool()
def read_webpage(url: str) -> dict:
    """Fetch a webpage and extract its clean readable text content."""
    log(f"Reading: {url}")
    with httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
        resp = client.get(url, headers=HEADERS)
        resp.raise_for_status()
        html = resp.text
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script","style","nav","footer","header","aside","form","noscript"]):
        tag.decompose()
    title    = soup.title.get_text(strip=True) if soup.title else ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_tag.get("content","") if meta_tag else ""
    main_content = (
        soup.find("article") or soup.find("main")
        or soup.find(id="content") or soup.body
    )
    raw_text  = main_content.get_text(separator="\\n", strip=True) if main_content else ""
    lines     = [l.strip() for l in raw_text.splitlines() if l.strip()]
    clean_text = "\\n".join(lines)
    return {
        "url":         url,
        "title":       title,
        "description": meta_desc,
        "content":     clean_text[:8000],
        "word_count":  len(clean_text.split()),
        "domain":      urlparse(url).netloc,
    }
 
@mcp.tool()
def extract_links(url: str, internal_only: bool = False) -> list[dict]:
    """Extract all hyperlinks from a webpage."""
    with httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
        resp = client.get(url, headers=HEADERS)
        resp.raise_for_status()
        html = resp.text
    soup  = BeautifulSoup(html, "lxml")
    base  = urlparse(url).netloc
    seen, links = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urljoin(url, href)
        domain = urlparse(full).netloc
        if any(href.startswith(p) for p in ("#","mailto:","tel:","javascript:")):
            continue
        if internal_only and domain != base:
            continue
        if full not in seen:
            seen.add(full)
            links.append({"text": a.get_text(strip=True)[:100], "url": full})
    return links[:50]
 
@mcp.tool()
def extract_tables(url: str) -> list[dict]:
    """Extract all HTML tables from a webpage as structured data."""
    with httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT) as client:
        resp = client.get(url, headers=HEADERS)
        resp.raise_for_status()
        html = resp.text
    soup   = BeautifulSoup(html, "lxml")
    tables = []
    for i, table in enumerate(soup.find_all("table")):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if cells:
                rows.append(dict(zip(headers, cells)) if headers else {f"col_{j}":v for j,v in enumerate(cells)})
        if rows:
            tables.append({"table_index": i, "headers": headers, "rows": rows[:100]})
    return tables
 
if __name__ == "__main__":
    log("Web MCP Server starting...")
    mcp.run(transport="stdio")