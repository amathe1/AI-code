# ────────────────────────────────────────────────────────────
# EXAMPLE 1 — HELLO WORLD  (absolute basics)
#   Concepts: FastMCP, @mcp.tool, plain return value
# ────────────────────────────────────────────────────────────
from mcp.server.fastmcp import FastMCP
 
mcp = FastMCP("Hello Server")
 
@mcp.tool()
def say_hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}! Welcome to MCP."
 
@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

if __name__ == "__main__":
 
    print("=" * 55)
    print("EXAMPLE 1 — Hello World")
    print("=" * 55)
    print(say_hello("Arun"))
    print(add_numbers(10, 20))
 
    print("\n" + "=" * 55)