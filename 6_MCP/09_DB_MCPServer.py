# """
# ============================================================
#  MCP USE CASE 3: POSTGRESQL DATABASE READER
#  Query a live PostgreSQL database using FastMCP
# ============================================================
#  PREREQUISITES:
#    pip install fastmcp psycopg2-binary

#  SETUP:
#    1. Run setup_db.sh first to create the Docker container
#    2. Export env variables shown by setup_db.sh

#  RUN:
#    python database_mcp_server.py
# ============================================================
# """
# from dotenv import load_dotenv
# load_dotenv()

# import os
# import psycopg2
# import psycopg2.extras
# from contextlib import contextmanager
# from mcp.server.fastmcp import FastMCP

# # ── Init FastMCP server ────────────────────────────────────
# mcp = FastMCP(name="database-reader")

# # ── DB Connection Config (from env vars) ───────────────────
# DB_CONFIG = {
#     "host":     os.getenv("DB_HOST", "localhost"),
#     "port":     int(os.getenv("DB_PORT", "5432")),
#     "dbname":   os.getenv("DB_NAME", "agentdb"),
#     "user":     os.getenv("DB_USER", "agentuser"),
#     "password": os.getenv("DB_PASS", "agentpass"),
# }

# @contextmanager
# def get_db():
#     """Context manager: opens a DB connection, yields cursor, always closes."""
#     conn = psycopg2.connect(**DB_CONFIG)
#     try:
#         with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
#             yield cur
#         conn.commit()
#     finally:
#         conn.close()


# # ══════════════════════════════════════════════════════════
# #  TOOL 1 — List all employees (optionally filter by dept)
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def get_employees(department: str = "") -> list[dict]:
#     """
#     Retrieve all employees, optionally filtered by department.

#     Args:
#         department: Department name to filter by ('' = all departments)

#     Returns:
#         List of employee records
#     """
#     with get_db() as cur:
#         if department:
#             cur.execute(
#                 "SELECT * FROM employees WHERE LOWER(department) = LOWER(%s) ORDER BY name",
#                 (department,)
#             )
#         else:
#             cur.execute("SELECT * FROM employees ORDER BY department, name")

#         rows = cur.fetchall()

#     # Convert RealDictRow → plain dict for JSON serialization
#     return [dict(row) for row in rows]


# # ══════════════════════════════════════════════════════════
# #  TOOL 2 — Get all active projects with owner info
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def get_projects(status: str = "") -> list[dict]:
#     """
#     Retrieve projects, optionally filtered by status.

#     Args:
#         status: 'active', 'completed', or 'on-hold'  ('' = all)

#     Returns:
#         List of project records with owner name
#     """
#     with get_db() as cur:
#         query = """
#             SELECT
#                 p.id, p.name, p.status, p.budget,
#                 p.start_date, p.end_date,
#                 e.name AS owner_name, e.email AS owner_email
#             FROM projects p
#             LEFT JOIN employees e ON e.id = p.owner_id
#         """
#         if status:
#             cur.execute(query + " WHERE p.status = %s ORDER BY p.name", (status,))
#         else:
#             cur.execute(query + " ORDER BY p.status, p.name")

#         rows = cur.fetchall()

#     return [dict(row) for row in rows]


# # ══════════════════════════════════════════════════════════
# #  TOOL 3 — Get tasks for a specific project
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def get_tasks_for_project(project_id: int) -> list[dict]:
#     """
#     Retrieve all tasks belonging to a specific project.

#     Args:
#         project_id: The integer ID of the project

#     Returns:
#         List of task records with assignee name
#     """
#     with get_db() as cur:
#         cur.execute("""
#             SELECT
#                 t.id, t.title, t.status, t.priority, t.due_date,
#                 e.name AS assignee_name,
#                 p.name AS project_name
#             FROM tasks t
#             LEFT JOIN employees e ON e.id = t.assignee_id
#             LEFT JOIN projects  p ON p.id = t.project_id
#             WHERE t.project_id = %s
#             ORDER BY
#                 CASE t.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
#                 t.due_date
#         """, (project_id,))
#         rows = cur.fetchall()

#     return [dict(row) for row in rows]


# # ══════════════════════════════════════════════════════════
# #  TOOL 4 — Run a safe read-only SQL query
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def run_query(sql: str) -> list[dict]:
#     """
#     Execute a custom READ-ONLY SQL SELECT query and return results.
#     Only SELECT statements are allowed for safety.

#     Args:
#         sql: A valid PostgreSQL SELECT statement

#     Returns:
#         List of result rows as dicts
#     """
#     # Safety guard — only allow SELECT queries
#     stripped = sql.strip().upper()
#     if not stripped.startswith("SELECT"):
#         raise ValueError("Only SELECT queries are allowed.")

#     with get_db() as cur:
#         cur.execute(sql)
#         rows = cur.fetchall()

#     return [dict(row) for row in rows]


# # ══════════════════════════════════════════════════════════
# #  TOOL 5 — Get department salary summary
# # ══════════════════════════════════════════════════════════
# @mcp.tool()
# def get_department_summary() -> list[dict]:
#     """
#     Get headcount and salary statistics grouped by department.

#     Returns:
#         List of department summaries with avg/min/max salary and count
#     """
#     with get_db() as cur:
#         cur.execute("""
#             SELECT
#                 department,
#                 COUNT(*)           AS headcount,
#                 ROUND(AVG(salary)) AS avg_salary,
#                 MIN(salary)        AS min_salary,
#                 MAX(salary)        AS max_salary,
#                 SUM(salary)        AS total_payroll
#             FROM employees
#             GROUP BY department
#             ORDER BY headcount DESC
#         """)
#         rows = cur.fetchall()

#     return [dict(row) for row in rows]


# # ── Entry point ────────────────────────────────────────────
# if __name__ == "__main__":
#     print("🚀 Database MCP Server running...")
#     mcp.run()

import os
import sys
import psycopg2
import psycopg2.extras
from pathlib import Path
from contextlib import contextmanager
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
 
load_dotenv(Path(__file__).parent / ".env")
 
def log(msg):
    """Log to stderr only — stdout is reserved for MCP protocol."""
    print(msg, file=sys.stderr, flush=True)
 
# ── DB Config ──────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "dbname":   os.getenv("DB_NAME", "agentdb"),
    "user":     os.getenv("DB_USER", "agentuser"),
    "password": os.getenv("DB_PASS", "agentpass"),
}
 
# ── Use separate variables to avoid f-string quote issues ──
db_name = DB_CONFIG["dbname"]
db_host = DB_CONFIG["host"]
log(f"DB: {db_name} @ {db_host}")
 
mcp = FastMCP(name="database-reader")
 
 
@contextmanager
def get_db():
    """Open a DB connection, yield cursor, always close."""
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    finally:
        conn.close()
 
 
@mcp.tool()
def get_employees(department: str = "") -> list[dict]:
    """
    Retrieve employees, optionally filtered by department.
 
    Args:
        department: Department name ('' = all departments)
 
    Returns:
        List of employee records
    """
    with get_db() as cur:
        if department:
            cur.execute(
                "SELECT * FROM employees WHERE LOWER(department)=LOWER(%s) ORDER BY name",
                (department,)
            )
        else:
            cur.execute("SELECT * FROM employees ORDER BY department, name")
        return [dict(r) for r in cur.fetchall()]
 
 
@mcp.tool()
def get_projects(status: str = "") -> list[dict]:
    """
    Retrieve projects, optionally filtered by status.
 
    Args:
        status: 'active', 'completed', or 'on-hold' ('' = all)
 
    Returns:
        List of project records with owner name
    """
    with get_db() as cur:
        query = """
            SELECT p.id, p.name, p.status, p.budget,
                   p.start_date, p.end_date,
                   e.name AS owner_name
            FROM projects p
            LEFT JOIN employees e ON e.id = p.owner_id
        """
        if status:
            cur.execute(query + " WHERE p.status=%s ORDER BY p.name", (status,))
        else:
            cur.execute(query + " ORDER BY p.status, p.name")
        return [dict(r) for r in cur.fetchall()]
 
 
@mcp.tool()
def get_tasks_for_project(project_id: int) -> list[dict]:
    """
    Retrieve all tasks for a specific project.
 
    Args:
        project_id: Integer ID of the project
 
    Returns:
        List of task records with assignee name
    """
    with get_db() as cur:
        cur.execute("""
            SELECT t.id, t.title, t.status, t.priority, t.due_date,
                   e.name AS assignee_name,
                   p.name AS project_name
            FROM tasks t
            LEFT JOIN employees e ON e.id = t.assignee_id
            LEFT JOIN projects  p ON p.id = t.project_id
            WHERE t.project_id = %s
            ORDER BY
                CASE t.priority
                    WHEN 'high'   THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END
        """, (project_id,))
        return [dict(r) for r in cur.fetchall()]
 
 
@mcp.tool()
def run_query(sql: str) -> list[dict]:
    """
    Execute a read-only SELECT query.
 
    Args:
        sql: A valid PostgreSQL SELECT statement
 
    Returns:
        List of result rows as dicts
    """
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")
    with get_db() as cur:
        cur.execute(sql)
        return [dict(r) for r in cur.fetchall()]
 
 
@mcp.tool()
def get_department_summary() -> list[dict]:
    """
    Get headcount and salary stats grouped by department.
 
    Returns:
        List with avg, min, max salary and headcount per department
    """
    with get_db() as cur:
        cur.execute("""
            SELECT
                department,
                COUNT(*)           AS headcount,
                ROUND(AVG(salary)) AS avg_salary,
                MIN(salary)        AS min_salary,
                MAX(salary)        AS max_salary
            FROM employees
            GROUP BY department
            ORDER BY headcount DESC
        """)
        return [dict(r) for r in cur.fetchall()]
 
 
if __name__ == "__main__":
    log("Database MCP Server starting...")
    mcp.run(transport="stdio")