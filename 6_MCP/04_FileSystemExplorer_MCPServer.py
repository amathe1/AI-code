# # ────────────────────────────────────────────────────────────
# # EXAMPLE 4 — FILE SYSTEM EXPLORER
# #   Concepts: os module usage, Prompts, path validation,
# #             reading / listing files safely
# # ────────────────────────────────────────────────────────────
 
# import os
# from mcp.server.fastmcp import FastMCP
 
# mcp = FastMCP("File Explorer")
 
# @mcp.tool()
# def list_files(directory: str = ".") -> list[str]:
#     """List files in a directory."""
#     if not os.path.isdir(directory):
#         raise ValueError(f"'{directory}' is not a valid directory.")
#     return os.listdir(directory)
 
# @mcp.tool()
# def read_file(filepath: str) -> str:
#     """Read and return the contents of a text file."""
#     if not os.path.isfile(filepath):
#         raise FileNotFoundError(f"File not found: {filepath}")
#     with open(filepath, "r", encoding="utf-8") as f:
#         return f.read()
 
# @mcp.tool()
# def write_file(filepath: str, content: str) -> str:
#     """Write content to a file (creates or overwrites)."""
#     with open(filepath, "w", encoding="utf-8") as f:
#         f.write(content)
#     return f"Written {len(content)} characters to '{filepath}'."
 
# @mcp.tool()
# def file_info(filepath: str) -> dict:
#     """Return size, extension, and modification time of a file."""
#     if not os.path.exists(filepath):
#         raise FileNotFoundError(f"Not found: {filepath}")
#     stat = os.stat(filepath)
#     return {
#         "name":      os.path.basename(filepath),
#         "extension": os.path.splitext(filepath)[1],
#         "size_bytes": stat.st_size,
#         "modified":  stat.st_mtime,
#     }
 
# @mcp.prompt()
# def summarize_file_prompt(filepath: str) -> str:
#     """Returns a prompt asking Claude to summarize a file."""
#     return f"Please read '{filepath}' and give me a concise summary."

# if __name__ == "__main__":
 
#     print("\n" + "=" * 55)
#     print("EXAMPLE 4 — File Explorer")
#     print("=" * 55)
#     write_file("/tmp/test.txt", "Hello from MCP File Server!")
#     print(read_file("/tmp/test.txt"))
#     print(file_info("/tmp/test.txt"))
 
#     print("\n" + "=" * 55)

import os
import sys
from mcp.server.fastmcp import FastMCP
 
def log(msg):
    print(msg, file=sys.stderr, flush=True)
 
mcp = FastMCP("File Explorer")
 
@mcp.tool()
def list_files(directory: str = ".") -> list[str]:
    """List all files and folders in a directory."""
    if not os.path.isdir(directory):
        raise ValueError(f"\'{directory}\' is not a valid directory.")
    return os.listdir(directory)
 
@mcp.tool()
def read_file(filepath: str) -> str:
    """Read and return the contents of a text file."""
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()
 
@mcp.tool()
def write_file(filepath: str, content: str) -> str:
    """Write content to a file (creates or overwrites)."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Written {len(content)} characters to \'{filepath}\'."
 
@mcp.tool()
def file_info(filepath: str) -> dict:
    """Return size, extension, and modification time of a file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Not found: {filepath}")
    stat = os.stat(filepath)
    return {
        "name":       os.path.basename(filepath),
        "extension":  os.path.splitext(filepath)[1],
        "size_bytes": stat.st_size,
        "modified":   stat.st_mtime,
    }
 
if __name__ == "__main__":
    log("File Explorer MCP Server starting...")
    mcp.run(transport="stdio")