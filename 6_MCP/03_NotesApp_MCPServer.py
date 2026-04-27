
# from mcp.server.fastmcp import FastMCP
# mcp = FastMCP("Notes App")
 
# _notes: dict[str, str] = {}          # { title: content }
 
# @mcp.tool()
# def add_note(title: str, content: str) -> str:
#     """Save a new note."""
#     _notes[title] = content
#     return f"Note '{title}' saved."
 
# @mcp.tool()
# def get_note(title: str) -> str:
#     """Retrieve a note by title."""
#     return _notes.get(title, f"No note found with title '{title}'.")
 
# @mcp.tool()
# def delete_note(title: str) -> str:
#     """Delete a note by title."""
#     if title in _notes:
#         del _notes[title]
#         return f"Note '{title}' deleted."
#     return f"Note '{title}' not found."
 
# @mcp.resource("notes://all")
# def list_all_notes() -> str:
#     """Resource: returns all notes as formatted text."""
#     if not _notes:
#         return "No notes yet."
#     return "\n\n".join(f"[{t}]\n{c}" for t, c in _notes.items())

# if __name__ == "__main__":
 
#     print("\n" + "=" * 55)
#     print("EXAMPLE 3 — Notes App")
#     print("=" * 55)
#     print(add_note("shopping", "Milk, Eggs, Bread"))
#     print(add_note("todo",     "Finish MCP tutorial"))
#     print(get_note("shopping"))
#     print(delete_note("shopping"))
#     print(get_note("shopping"))
 
#     print("\n" + "=" * 55)

import sys
from mcp.server.fastmcp import FastMCP
 
def log(msg):
    print(msg, file=sys.stderr, flush=True)
 
mcp = FastMCP("Notes App")
_notes: dict[str, str] = {}
 
@mcp.tool()
def add_note(title: str, content: str) -> str:
    """Save a new note with a title and content."""
    _notes[title] = content
    log(f"Note saved: {title}")
    return f"Note \'{title}\' saved."
 
@mcp.tool()
def get_note(title: str) -> str:
    """Retrieve a note by its title."""
    return _notes.get(title, f"No note found with title \'{title}\'.")
 
@mcp.tool()
def list_notes() -> list[str]:
    """List all saved note titles."""
    return list(_notes.keys()) if _notes else ["No notes saved yet."]
 
@mcp.tool()
def delete_note(title: str) -> str:
    """Delete a note by title."""
    if title in _notes:
        del _notes[title]
        return f"Note \'{title}\' deleted."
    return f"Note \'{title}\' not found."
 
if __name__ == "__main__":
    log("Notes MCP Server starting...")
    mcp.run(transport="stdio")