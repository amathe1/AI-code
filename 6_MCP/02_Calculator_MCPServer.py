# # ────────────────────────────────────────────────────────────
# # EXAMPLE 2 — CALCULATOR SERVER
# #   Concepts: multiple tools, docstrings, basic error handling
# # ────────────────────────────────────────────────────────────
# from mcp.server.fastmcp import FastMCP
 
# mcp = FastMCP("Calculator")
 
# @mcp.tool()
# def add(a: float, b: float) -> float:
#     """Add two numbers."""
#     return a + b
 
# @mcp.tool()
# def subtract(a: float, b: float) -> float:
#     """Subtract b from a."""
#     return a - b
 
# @mcp.tool()
# def multiply(a: float, b: float) -> float:
#     """Multiply two numbers."""
#     return a * b
 
# @mcp.tool()
# def divide(a: float, b: float) -> float:
#     """Divide a by b. Raises error if b is zero."""
#     if b == 0:
#         raise ValueError("Cannot divide by zero.")
#     return a / b

# if __name__ == "__main__":
 
#     print("EXAMPLE 2 — Calculator")
#     print("=" * 55)
#     print("10 + 3 =", add(10, 3))
#     print("10 / 3 =", round(divide(10, 3), 4))
#     try:
#         divide(5, 0)
#     except ValueError as e:
#         print("Error caught:", e)
 
#     print("\n" + "=" * 55)

# ─────────────────────────────────────────────────────────
# CALCULATOR MCP SERVER
# Fixed: removed all print() to stdout — corrupts stdio pipe
# All logging goes to stderr only
# ─────────────────────────────────────────────────────────
import sys
from mcp.server.fastmcp import FastMCP
 
def log(msg):
    """Log to stderr only — stdout is reserved for MCP protocol."""
    print(msg, file=sys.stderr, flush=True)
 
mcp = FastMCP("Calculator")
 
@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b
 
@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b
 
@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b
 
@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide a by b. Raises error if b is zero."""
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b
 
if __name__ == "__main__":
    log("Calculator MCP Server starting...")
    mcp.run(transport="stdio")
 