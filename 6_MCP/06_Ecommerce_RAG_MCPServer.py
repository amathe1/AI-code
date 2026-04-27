# ────────────────────────────────────────────────────────────
# EXAMPLE 6 — ECOMMERCE RAG HELPER  (intermediate, realistic)
#   Concepts: SQLite for orders, semantic intent detection,
#             Resources with URI templates, Prompts,
#             structured tool responses, combining tools
# ────────────────────────────────────────────────────────────
 
import sqlite3
import re
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP
 
mcp = FastMCP("Ecommerce Assistant")
 
# ── Tiny in-memory SQLite with seed data ──────────────────
 
def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            id          TEXT PRIMARY KEY,
            customer    TEXT,
            product     TEXT,
            status      TEXT,
            amount      REAL,
            created_at  TEXT
        );
        INSERT OR IGNORE INTO orders VALUES
          ('ORD001','Alice','Laptop','shipped',   75000, '2025-04-10'),
          ('ORD002','Alice','Mouse', 'delivered', 1500,  '2025-04-01'),
          ('ORD003','Bob',  'Phone', 'processing',45000, '2025-04-14'),
          ('ORD004','Bob',  'Case',  'cancelled', 800,   '2025-04-05');
    """)
    return conn
 
_db = _get_db()
 
# ── Intent helpers (reuse M6 logic) ───────────────────────
 
_CANCEL_PAT = re.compile(
    r"cancel|abort|stop\s+order|withdraw\s+order|undo\s+order", re.I
)
_STATUS_PAT = re.compile(
    r"status|where\s+is|track|shipped|deliver", re.I
)
 
def _detect_intent(query: str) -> str:
    if _CANCEL_PAT.search(query): return "cancel"
    if _STATUS_PAT.search(query): return "status"
    return "general"
 
# ── Tools ─────────────────────────────────────────────────
 
@mcp.tool()
def get_order(order_id: str) -> dict:
    """Fetch full details of a single order by ID."""
    row = _db.execute(
        "SELECT * FROM orders WHERE id = ?", (order_id.upper(),)
    ).fetchone()
    if not row:
        raise ValueError(f"Order '{order_id}' not found.")
    return dict(row)
 
@mcp.tool()
def get_customer_orders(customer_name: str) -> list[dict]:
    """List all orders for a given customer."""
    rows = _db.execute(
        "SELECT * FROM orders WHERE customer = ?", (customer_name,)
    ).fetchall()
    return [dict(r) for r in rows]
 
@mcp.tool()
def cancel_order(order_id: str) -> dict:
    """
    Cancel an order if eligible.
    Orders already 'shipped' or 'delivered' cannot be cancelled.
    """
    order = get_order(order_id)
 
    if order["status"] in ("shipped", "delivered"):
        return {
            "success": False,
            "message": (
                f"Order {order_id} cannot be cancelled — "
                f"it is already {order['status']}. "
                "Please initiate a return instead."
            ),
        }
 
    if order["status"] == "cancelled":
        return {"success": False, "message": f"Order {order_id} is already cancelled."}
 
    _db.execute(
        "UPDATE orders SET status = 'cancelled' WHERE id = ?",
        (order_id.upper(),)
    )
    return {
        "success":  True,
        "order_id": order_id,
        "message":  f"Order {order_id} cancelled successfully. Refund of ₹{order['amount']} will be processed in 5–7 days.",
    }
 
@mcp.tool()
def handle_customer_query(customer: str, query: str) -> dict:
    """
    Smart dispatcher: detects intent from natural language,
    fetches relevant order data, and returns a structured response.
    Uses the same intent logic as M6_QueryProcessing.
    """
    intent  = _detect_intent(query)
    orders  = get_customer_orders(customer)
 
    if not orders:
        return {"intent": intent, "message": f"No orders found for {customer}."}
 
    if intent == "cancel":
        # Find the most recent cancellable order
        cancellable = [o for o in orders if o["status"] == "processing"]
        if cancellable:
            result = cancel_order(cancellable[0]["id"])
            return {"intent": "cancel", **result}
        return {
            "intent":  "cancel",
            "success": False,
            "message": "No cancellable orders found. Orders must be in 'processing' status.",
        }
 
    if intent == "status":
        return {
            "intent":  "status",
            "orders":  [{"id": o["id"], "product": o["product"], "status": o["status"]} for o in orders],
            "message": f"Found {len(orders)} order(s) for {customer}.",
        }
 
    return {
        "intent":  "general",
        "orders":  orders,
        "message": f"{customer} has {len(orders)} order(s) total.",
    }
 
# ── Resources (expose data as readable URIs) ──────────────
 
@mcp.resource("orders://{customer}/all")
def customer_orders_resource(customer: str) -> str:
    """URI template: orders://Alice/all → formatted order list."""
    orders = get_customer_orders(customer)
    if not orders:
        return f"No orders for {customer}."
    lines = [f"Orders for {customer}:"]
    for o in orders:
        lines.append(f"  {o['id']} | {o['product']:<12} | {o['status']:<12} | ₹{o['amount']}")
    return "\n".join(lines)
 
# ── Prompts (reusable LLM prompt templates) ───────────────
 
@mcp.prompt()
def order_support_prompt(customer: str, issue: str) -> str:
    """Generate a support prompt pre-filled with customer context."""
    orders = get_customer_orders(customer)
    order_summary = "\n".join(
        f"- {o['id']}: {o['product']} ({o['status']})" for o in orders
    )
    return (
        f"You are a helpful ecommerce support agent.\n\n"
        f"Customer: {customer}\n"
        f"Their orders:\n{order_summary}\n\n"
        f"Customer issue: {issue}\n\n"
        f"Resolve this helpfully and concisely."
    )
 
 
# ────────────────────────────────────────────────────────────
# QUICK DEMO  (run directly to see output)
# ────────────────────────────────────────────────────────────
 
if __name__ == "__main__":
 
    print("\n" + "=" * 55)
    print("EXAMPLE 6 — Ecommerce Assistant")
    print("=" * 55)
    print("\nFetch order ORD001:")
    print(get_order("ORD001"))
 
    print("\nAlice's orders:")
    for o in get_customer_orders("Alice"):
        print(f"  {o['id']} | {o['product']} | {o['status']}")
 
    print("\nCancel ORD003 (processing):")
    print(cancel_order("ORD003"))
 
    print("\nCancel ORD001 (already shipped):")
    print(cancel_order("ORD001"))
 
    print("\nSmart query — 'I want to cancel my order':")
    print(handle_customer_query("Bob", "I want to cancel my order"))
 
    print("\nSmart query — 'where is my order?':")
    print(handle_customer_query("Alice", "where is my order?"))
 
    print("\nGenerated support prompt:")
    print(order_support_prompt("Alice", "My laptop hasn't arrived yet"))