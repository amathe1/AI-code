"""
Module 07 — Access Control
============================
Data source : pgvector (PostgreSQL + HNSW index)
Hierarchy   : public → internal → confidential → most_confidential
Techniques  : Pre-filter | Post-filter | Defense-in-Depth
Metrics     : docs_searched, latency, memory_mb, cost_estimate

Run:
    cd rag_system && python 07_access_control.py
"""

import os, sys, time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# ENV_PATH = Path(__file__).parent / ".env"

# def load_env(path):
#     if not path.exists(): return {}
#     loaded = {}
#     with open(path) as f:
#         for line in f:
#             line = line.strip()
#             if not line or line.startswith("#") or "=" not in line: continue
#             k, _, v = line.partition("=")
#             k = k.strip(); v = v.strip()
#             if " #" in v: v = v[:v.index(" #")].strip()
#             if len(v)>=2 and v[0] in('"',"'") and v[0]==v[-1]: v=v[1:-1]
#             if k and k not in os.environ:
#                 os.environ[k]=v; loaded[k]=v
#     return loaded

# load_env(ENV_PATH)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_HOST = os.getenv("PGVECTOR_HOST","localhost")
DB_PORT = int(os.getenv("PGVECTOR_PORT","5432"))
DB_NAME = os.getenv("PGVECTOR_DB","ecommerce_rag")
DB_USER = os.getenv("PGVECTOR_USER","raguser")
DB_PASS = os.getenv("PGVECTOR_PASS","ragpass123")

HIERARCHY = {
    "public"           : 0,
    "internal"         : 1,
    "confidential"     : 2,
    "most_confidential": 3,
}

ROLE_ACCESS = {
    "anonymous"  : ["public"],
    "customer"   : ["public"],
    "agent"      : ["public","internal"],
    "supervisor" : ["public","internal","confidential"],
    "admin"      : ["public","internal","confidential","most_confidential"],
}


def get_conn():
    try:
        import psycopg2
        from pgvector.psycopg2 import register_vector
        conn = psycopg2.connect(host=DB_HOST,port=DB_PORT,dbname=DB_NAME,
                                user=DB_USER,password=DB_PASS,connect_timeout=5)
        register_vector(conn)
        return conn
    except Exception as e:
        print(f"\n  [ERROR] Cannot connect to pgvector: {e}")
        print("  Run: docker ps | grep pgvector_rag")
        sys.exit(1)


def embed_query(text: str, client) -> list:
    return client.embeddings.create(
        model="text-embedding-3-small", input=[text]).data[0].embedding


def db_count_by_access(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT access_level, COUNT(*)
            FROM document_chunks GROUP BY access_level ORDER BY access_level;
        """)
        return dict(cur.fetchall())


# ── Pre-filter: WHERE clause before HNSW scan ─────────────────────────────────
def pre_filter_search(conn, qvec, allowed: list, k=5) -> tuple[list, dict]:
    vec = f"[{','.join(str(round(x,8)) for x in qvec)}]"
    with conn.cursor() as cur:
        cur.execute("SET hnsw.ef_search = 100;")
        t0 = time.perf_counter()
        cur.execute("""
            SELECT chunk_id, section_id, section_title, text, access_level,
                   1-(embedding <=> %s::vector) AS score
            FROM document_chunks
            WHERE access_level = ANY(%s)
            ORDER BY embedding <=> %s::vector LIMIT %s;
        """, (vec, allowed, vec, k))
        rows = cur.fetchall()
        lat  = (time.perf_counter()-t0)*1000

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM document_chunks WHERE access_level=ANY(%s);",
                    (allowed,))
        searched = cur.fetchone()[0]

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM document_chunks;")
        total = cur.fetchone()[0]

    results = [{"chunk_id":r[0],"section_id":r[1],"section_title":r[2],
                "text":r[3],"access_level":r[4],"score":round(float(r[5]),4)}
               for r in rows]
    metrics = {
        "approach"     : "pre_filter",
        "docs_searched": searched,
        "total_docs"   : total,
        "latency_ms"   : round(lat,2),
        "memory_mb"    : round(searched*1536*4/1024/1024,3),
        "cost_estimate": f"${searched*0.000001:.6f}",
    }
    return results, metrics


# ── Post-filter: HNSW scan all, filter after ──────────────────────────────────
def post_filter_search(conn, qvec, allowed: list, k=5, oversample=3) -> tuple[list,dict]:
    vec = f"[{','.join(str(round(x,8)) for x in qvec)}]"
    with conn.cursor() as cur:
        cur.execute("SET hnsw.ef_search = 100;")
        t0 = time.perf_counter()
        cur.execute("""
            SELECT chunk_id, section_id, section_title, text, access_level,
                   1-(embedding <=> %s::vector) AS score
            FROM document_chunks
            ORDER BY embedding <=> %s::vector LIMIT %s;
        """, (vec, vec, k*oversample))
        all_rows = cur.fetchall()
        lat = (time.perf_counter()-t0)*1000

    rows = [r for r in all_rows if r[4] in allowed][:k]
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM document_chunks;")
        total = cur.fetchone()[0]

    results = [{"chunk_id":r[0],"section_id":r[1],"section_title":r[2],
                "text":r[3],"access_level":r[4],"score":round(float(r[5]),4)}
               for r in rows]
    metrics = {
        "approach"     : "post_filter",
        "docs_searched": total,
        "total_docs"   : total,
        "latency_ms"   : round(lat,2),
        "memory_mb"    : round(total*1536*4/1024/1024,3),
        "cost_estimate": f"${total*0.000001:.6f}",
    }
    return results, metrics


# ── Defense-in-Depth double check ─────────────────────────────────────────────
def defense_in_depth(results: list, user_role: str) -> tuple[list,list]:
    allowed   = set(ROLE_ACCESS.get(user_role,[]))
    user_max  = max(HIERARCHY.get(a,0) for a in allowed)
    approved, rejected = [], []
    for r in results:
        lvl = r.get("access_level","public")
        if lvl in allowed and HIERARCHY.get(lvl,0) <= user_max:
            approved.append(r)
        else:
            rejected.append({**r,"rejection_reason":
                             "hierarchy_violation" if lvl in allowed else "access_denied"})
    return approved, rejected


def run():
    print("="*65)
    print("  MODULE 07 — Access Control")
    print("  Data source: pgvector (PostgreSQL)")
    print("="*65)

    if not OPENAI_API_KEY:
        print("\n  [ERROR] OPENAI_API_KEY not set in .env"); sys.exit(1)

    import openai
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    conn   = get_conn()

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM document_chunks;")
        total = cur.fetchone()[0]
    print(f"\n  Connected — {total} chunks in pgvector")

    # Access level distribution from DB
    dist = db_count_by_access(conn)
    print(f"\n  Access Level Distribution (from pgvector)")
    for lvl, num in HIERARCHY.items():
        count = dist.get(lvl, 0)
        print(f"    Level {num} — {lvl:<20} : {count:>3} chunks")

    print(f"\n  Role Permissions")
    for role, levels in ROLE_ACCESS.items():
        accessible = sum(dist.get(l,0) for l in levels)
        print(f"    {role:<14} sees: {', '.join(levels):<45} ({accessible} chunks)")

    # Embed a test query
    qvec = embed_query("return policy for prime members damaged item", client)

    # ── Benchmark all roles ────────────────────────────────────────────────────
    print(f"\n  Pre-Filter vs Post-Filter — pgvector HNSW")
    print(f"  {'Role':<14} {'Approach':<14} {'Docs Searched':>14} "
          f"{'Latency':>10} {'Memory':>10} {'Cost':>12}")
    print(f"  {'─'*72}")

    for role, allowed in ROLE_ACCESS.items():
        _, pre_m  = pre_filter_search(conn,  qvec, allowed)
        _, post_m = post_filter_search(conn, qvec, allowed)
        for m in [pre_m, post_m]:
            print(f"  {role:<14} {m['approach']:<14} "
                  f"{m['docs_searched']:>14,} "
                  f"{m['latency_ms']:>8.2f}ms "
                  f"{m['memory_mb']:>8.3f}MB "
                  f"{m['cost_estimate']:>12}")

    # ── Defense-in-Depth demo ─────────────────────────────────────────────────
    print(f"\n  Defense-in-Depth (double-check after retrieval)")
    print(f"  Scenario: customer role queries — should only see 'public'")
    # Post-filter may return confidential if filter fails; double-check catches it
    all_results, _ = post_filter_search(conn, qvec, ["public","internal","confidential"])
    approved, rejected = defense_in_depth(all_results, "customer")
    print(f"    Raw results from DB    : {len(all_results)}")
    print(f"    After double-check     : {len(approved)} approved, {len(rejected)} blocked")
    for r in rejected:
        print(f"      BLOCKED [{r['chunk_id']}] level={r['access_level']} "
              f"reason={r['rejection_reason']}")

    # ── Pre vs Post trade-off table ────────────────────────────────────────────
    print(f"\n  Decision Guide")
    print(f"  {'Dimension':<25} {'Pre-Filter':<28} {'Post-Filter'}")
    print(f"  {'─'*75}")
    rows = [
        ("SQL WHERE clause",   "Yes — before HNSW scan",       "No — scans all rows"),
        ("Docs scored",        "Only allowed docs",             "All docs then filter"),
        ("Latency",            "Lower (fewer vectors scored)",  "Higher (full scan)"),
        ("Recall",             "May miss boundary docs",        "Better recall"),
        ("Security risk",      "Minimal — filter is in DB",     "Risk if app filter fails"),
        ("Recommended for",    "Large corpus, strict access",   "Small corpus, max recall"),
    ]
    for r in rows:
        print(f"  {r[0]:<25} {r[1]:<28} {r[2]}")

    conn.close()
    print(f"\n  Module 07 complete.")


if __name__ == "__main__":
    run()