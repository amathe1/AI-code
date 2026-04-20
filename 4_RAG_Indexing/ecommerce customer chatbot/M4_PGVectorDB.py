"""
Module 04 — pgvector + HNSW Indexing
=======================================

COMMON ERRORS & FIXES
======================

Error 1: "vector type not found in the database"
  Cause : Plain PostgreSQL container — pgvector extension not installed.
  Fix   : Use the pgvector image, NOT the plain postgres image.

  WRONG:  docker run -d --name pg postgres:16          ← no vector support
  RIGHT:  docker run -d --name pgvector_rag pgvector/pgvector:pg16  ← correct

Error 2: "connection refused"
  Cause : Container not running or wrong port.
  Fix   : Check with  docker ps  and wait ~15 seconds after starting.

Error 3: "password authentication failed"
  Cause : Container started with different credentials.
  Fix   : docker rm -f pgvector_rag  then restart with the command below.


SETUP COMMANDS
==============

# 1. Remove any existing container with the same name
docker rm -f pgvector_rag 2>/dev/null || true

# 2. Start the CORRECT image (pgvector/pgvector:pg16, not postgres:16)
docker run -d \\
  --name pgvector_rag \\
  -e POSTGRES_DB=ecommerce_rag \\
  -e POSTGRES_USER=raguser \\
  -e POSTGRES_PASSWORD=ragpass123 \\
  -p 5432:5432 \\
  pgvector/pgvector:pg16

# 3. Wait for PostgreSQL to be ready (~15 seconds)
docker exec pgvector_rag pg_isready -U raguser -d ecommerce_rag

# 4. Run this module
python 04_pgvector.py


Run:
    cd rag_system && python 04_pgvector.py

    -- Connect to the database
docker exec -it pgvector_rag psql -U raguser -d ecommerce_rag

-- Clear all rows
TRUNCATE TABLE document_chunks;

-- Verify it's empty
SELECT COUNT(*) FROM document_chunks;

-- Exit
\q
"""

import os, json, time, sys
import numpy as np
from pathlib import Path

DB_HOST = os.getenv("PGVECTOR_HOST", "localhost")
DB_PORT = int(os.getenv("PGVECTOR_PORT", "5432"))
DB_NAME = os.getenv("PGVECTOR_DB",   "ecommerce_rag")
DB_USER = os.getenv("PGVECTOR_USER", "raguser")
DB_PASS = os.getenv("PGVECTOR_PASS", "ragpass123")

EMBED_DIM = 1536
DATA_PATH = Path(__file__).parent / "embeddings.json"


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTIC HELPER
# ─────────────────────────────────────────────────────────────────────────────
def diagnose_connection() -> dict:
    """
    Connect without pgvector and check what's available.
    Returns a dict explaining the exact problem.
    """
    result = {"connected": False, "pg_version": None,
              "vector_available": False, "vector_installed": False,
              "error": None}
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            dbname=DB_NAME, user=DB_USER, password=DB_PASS,
            connect_timeout=5
        )
        result["connected"] = True

        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            result["pg_version"] = cur.fetchone()[0][:70]

            # Is pgvector available (compiled into the server)?
            cur.execute("SELECT COUNT(*) FROM pg_available_extensions WHERE name='vector';")
            result["vector_available"] = cur.fetchone()[0] > 0

            # Is it already installed in this database?
            cur.execute("SELECT COUNT(*) FROM pg_extension WHERE extname='vector';")
            result["vector_installed"] = cur.fetchone()[0] > 0

        conn.close()
    except Exception as e:
        result["error"] = str(e)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# CONNECTION + SETUP
# ─────────────────────────────────────────────────────────────────────────────
def install_extension():
    """
    Install the vector extension using a plain psycopg2 connection
    (no pgvector Python package needed at this stage).
    Must be called BEFORE get_connection() / register_vector().
    """
    import psycopg2
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )
    conn.autocommit = True          # CREATE EXTENSION cannot run inside a transaction
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    conn.close()


def get_connection():
    import psycopg2
    from pgvector.psycopg2 import register_vector
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )
    register_vector(conn)           # safe now — extension is installed
    return conn


def setup_schema(conn):
    """Create extension, table, HNSW index, and metadata indexes."""
    ddl_steps = [
        ("Enable pgvector extension",
         "CREATE EXTENSION IF NOT EXISTS vector;"),

        ("Create document_chunks table",
         f"""
         CREATE TABLE IF NOT EXISTS document_chunks (
             id            SERIAL PRIMARY KEY,
             chunk_id      TEXT    NOT NULL UNIQUE,
             section_id    TEXT    NOT NULL,
             section_title TEXT,
             section_num   TEXT,
             text          TEXT    NOT NULL,
             token_count   INT,
             char_count    INT,
             strategy      TEXT,
             chunk_index   INT,
             source        TEXT    DEFAULT 'ecommerce_knowledge_base.pdf',
             access_level  TEXT    DEFAULT 'public',
             has_tables    BOOLEAN DEFAULT FALSE,
             page_start    INT,
             embedding     vector({EMBED_DIM}),
             created_at    TIMESTAMPTZ DEFAULT NOW()
         );
         """),

        ("Create HNSW index (m=16, ef_construction=200)",
         """
         CREATE INDEX IF NOT EXISTS hnsw_embedding_idx
           ON document_chunks
           USING hnsw (embedding vector_cosine_ops)
           WITH (m = 16, ef_construction = 200);
         """),

        ("Create access_level index",
         "CREATE INDEX IF NOT EXISTS idx_access_level ON document_chunks (access_level);"),

        ("Create section_id index",
         "CREATE INDEX IF NOT EXISTS idx_section_id ON document_chunks (section_id);"),

        ("Create has_tables index",
         "CREATE INDEX IF NOT EXISTS idx_has_tables ON document_chunks (has_tables);"),
    ]

    for label, sql in ddl_steps:
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        ms = (time.perf_counter()-t0)*1000
        print(f"    ✓  {label}  ({ms:.0f}ms)")


# ─────────────────────────────────────────────────────────────────────────────
# INSERT
# ─────────────────────────────────────────────────────────────────────────────
INSERT_SQL = """
INSERT INTO document_chunks
  (chunk_id, section_id, section_title, section_num, text, token_count,
   char_count, strategy, chunk_index, source, access_level, has_tables,
   page_start, embedding)
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (chunk_id) DO UPDATE SET
  text      = EXCLUDED.text,
  embedding = EXCLUDED.embedding,
  access_level = EXCLUDED.access_level;
"""


def insert_chunks(conn, chunks: list[dict]) -> dict:
    t0 = time.perf_counter()
    inserted = 0
    with conn.cursor() as cur:
        for c in chunks:
            m = c.get("metadata", {})
            cur.execute(INSERT_SQL, (
                c["chunk_id"],
                c["section_id"],
                c["section_title"],
                m.get("section_num", ""),
                c["text"],
                c.get("token_count", 0),
                c.get("char_count",  0),
                c.get("strategy",    "recursive_fallback"),
                c.get("chunk_index", 0),
                m.get("source", "ecommerce_knowledge_base.pdf"),
                m.get("access_level", "public"),
                bool(m.get("has_tables", False)),
                m.get("page_start", 1),
                c["embedding"],
            ))
            inserted += 1
    conn.commit()
    elapsed = (time.perf_counter()-t0)*1000
    return {"inserted": inserted, "elapsed_ms": round(elapsed, 1)}


# ─────────────────────────────────────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────────────────────────────────────
def similarity_search(conn, query_vec: list[float],
                      access_levels: list[str],
                      top_k: int = 5,
                      ef_search: int = 100) -> tuple[list[dict], float]:
    vec_str = f"[{','.join(str(x) for x in query_vec)}]"
    with conn.cursor() as cur:
        cur.execute(f"SET hnsw.ef_search = {ef_search};")
        t0 = time.perf_counter()
        cur.execute("""
            SELECT
                chunk_id,
                section_title,
                text,
                access_level,
                token_count,
                1 - (embedding <=> %s::vector) AS cosine_similarity
            FROM document_chunks
            WHERE access_level = ANY(%s)
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (vec_str, access_levels, vec_str, top_k))
        rows    = cur.fetchall()
        elapsed = (time.perf_counter()-t0)*1000

    results = [
        {
            "chunk_id"      : r[0],
            "section_title" : r[1],
            "text"          : r[2],
            "access_level"  : r[3],
            "token_count"   : r[4],
            "score"         : round(r[5], 4),
        }
        for r in rows
    ]
    return results, round(elapsed, 2)


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE STATS
# ─────────────────────────────────────────────────────────────────────────────
def get_stats(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM document_chunks;")
        total = cur.fetchone()[0]

        cur.execute("SELECT pg_size_pretty(pg_total_relation_size('document_chunks'));")
        table_size = cur.fetchone()[0]

        cur.execute("""
            SELECT indexname,
                   indexdef,
                   pg_size_pretty(pg_relation_size(indexname::regclass)) AS size
            FROM pg_indexes
            WHERE tablename = 'document_chunks'
            ORDER BY indexname;
        """)
        indexes = cur.fetchall()

        cur.execute("""
            SELECT access_level, COUNT(*) AS n
            FROM document_chunks
            GROUP BY access_level
            ORDER BY access_level;
        """)
        by_access = cur.fetchall()

    return {
        "total_rows"  : total,
        "table_size"  : table_size,
        "indexes"     : [(r[0], r[2]) for r in indexes],
        "by_access"   : dict(by_access),
    }


# ─────────────────────────────────────────────────────────────────────────────
# HNSW ef_search BENCHMARK
# ─────────────────────────────────────────────────────────────────────────────
def benchmark_ef_search(conn, sample_vec: list[float]) -> list[dict]:
    """
    Show how ef_search trades recall vs latency.
    Higher ef_search → more graph nodes explored → better recall, higher latency.
    """
    results = []
    for ef in [10, 50, 100, 200, 400]:
        rows, lat = similarity_search(
            conn, sample_vec,
            access_levels=["public", "internal", "confidential"],
            top_k=5, ef_search=ef
        )
        results.append({
            "ef_search"  : ef,
            "latency_ms" : lat,
            "top_score"  : rows[0]["score"] if rows else 0.0,
            "results_n"  : len(rows),
        })
    return results


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def print_fix_instructions(diag: dict):
    print(f"\n  ╔══════════════════════════════════════════════════════╗")
    print(f"  ║  HOW TO FIX THIS ERROR                               ║")
    print(f"  ╚══════════════════════════════════════════════════════╝")

    if not diag["connected"]:
        print(f"""
  Problem : Cannot connect to PostgreSQL at {DB_HOST}:{DB_PORT}
  Reason  : Container is not running or is using a different port.

  Fix:
    # Remove any old container with this name
    docker rm -f pgvector_rag

    # Start the correct pgvector image
    docker run -d \\
      --name pgvector_rag \\
      -e POSTGRES_DB=ecommerce_rag \\
      -e POSTGRES_USER=raguser \\
      -e POSTGRES_PASSWORD=ragpass123 \\
      -p 5432:5432 \\
      pgvector/pgvector:pg16

    # Wait 15 seconds then verify
    docker exec pgvector_rag pg_isready -U raguser -d ecommerce_rag

    # Re-run this module
    python 04_pgvector.py
""")

    elif not diag["vector_available"]:
        print(f"""
  Problem : Connected to PostgreSQL but pgvector extension is NOT available.
  Reason  : You started a plain 'postgres' image instead of 'pgvector/pgvector'.

  PostgreSQL version: {diag.get('pg_version', 'unknown')}

  Fix:
    # Stop and remove the plain postgres container
    docker rm -f pgvector_rag   (or whatever your container is named)

    # Start the CORRECT image
    docker run -d \\
      --name pgvector_rag \\
      -e POSTGRES_DB=ecommerce_rag \\
      -e POSTGRES_USER=raguser \\
      -e POSTGRES_PASSWORD=ragpass123 \\
      -p 5432:5432 \\
      pgvector/pgvector:pg16     ← THIS IMAGE, not postgres:16

    # Wait 15 seconds then re-run
    python 04_pgvector.py

  Key difference:
    postgres:16           →  plain PostgreSQL, no vector type
    pgvector/pgvector:pg16 →  PostgreSQL + pgvector extension compiled in
""")

    elif not diag["vector_installed"]:
        print(f"""
  Problem : pgvector is available but not yet installed in this database.
  Reason  : The 'CREATE EXTENSION vector' statement may have failed.

  PostgreSQL version: {diag.get('pg_version', 'unknown')}

  Fix (manual):
    docker exec -it pgvector_rag psql -U raguser -d ecommerce_rag
    > CREATE EXTENSION IF NOT EXISTS vector;
    > \\q

    Then re-run:
    python 04_pgvector.py
""")


def run():
    print("=" * 60)
    print("  MODULE 04 — pgvector + HNSW Indexing")
    print("=" * 60)

    # ── Step 1: Diagnose connection ───────────────────────────────────────────
    print(f"\n  Diagnosing connection to {DB_HOST}:{DB_PORT}/{DB_NAME} ...")
    diag = diagnose_connection()

    if diag["connected"]:
        print(f"  ✓  Connected to PostgreSQL")
        print(f"     Version : {diag.get('pg_version', '')}")
        print(f"     pgvector available  : {diag['vector_available']}")
        print(f"     pgvector installed  : {diag['vector_installed']}")
    else:
        print(f"  ✗  Connection failed: {diag['error']}")

    # If not connected or extension not available, print instructions and exit
    if not diag["connected"] or not diag["vector_available"]:
        print_fix_instructions(diag)
        sys.exit(1)

    # ── Step 2: Load embeddings data ──────────────────────────────────────────
    if not DATA_PATH.exists():
        print(f"\n  [ERROR] {DATA_PATH} not found. Run module 03 first.")
        sys.exit(1)

    data   = json.loads(DATA_PATH.read_text())
    chunks = data["chunks"]
    print(f"\n  Loaded {len(chunks)} chunks from {DATA_PATH.name}")

    # ── Step 3: Install extension FIRST (plain connection, autocommit) ─────────
    #   CREATE EXTENSION cannot run inside a transaction block and must happen
    #   before register_vector() is called — that is why the old code failed.
    print(f"\n  Installing pgvector extension ...")
    try:
        install_extension()
        print(f"  ✓  CREATE EXTENSION vector  (idempotent — safe to re-run)")
    except Exception as e:
        print(f"  [ERROR] Could not install extension: {e}")
        sys.exit(1)

    # ── Step 4: Connect with pgvector type registered ─────────────────────────
    print(f"\n  Setting up schema ...")
    try:
        conn = get_connection()
    except Exception as e:
        print(f"  [ERROR] Could not register pgvector type: {e}")
        print(f"  Fix:  pip install pgvector  (then re-run)")
        sys.exit(1)

    # ── Step 5: Create table + HNSW index + metadata indexes ─────────────────
    setup_schema(conn)

    # ── Step 6: Insert chunks ─────────────────────────────────────────────────
    print(f"\n  Inserting {len(chunks)} chunks ...")
    insert_stats = insert_chunks(conn, chunks)
    print(f"  ✓  Inserted {insert_stats['inserted']} chunks in {insert_stats['elapsed_ms']} ms")

    # ── Step 7: Verify database stats ────────────────────────────────────────
    stats = get_stats(conn)
    print(f"\n  Database Stats")
    print(f"    Rows         : {stats['total_rows']}")
    print(f"    Table size   : {stats['table_size']}")
    print(f"    By access    : {stats['by_access']}")
    print(f"    Indexes      :")
    for idx_name, idx_size in stats["indexes"]:
        print(f"      {idx_name:<35} {idx_size}")

    # ── Step 8: Sample search ─────────────────────────────────────────────────
    print(f"\n  Sample search (access=public, top-5) ...")
    rng        = np.random.default_rng(42)
    sample_vec = rng.standard_normal(EMBED_DIM).tolist()
    sample_vec = (np.array(sample_vec) / np.linalg.norm(sample_vec)).tolist()

    results, lat = similarity_search(conn, sample_vec, ["public"], top_k=5, ef_search=100)
    print(f"  Search latency: {lat} ms")
    for r in results[:3]:
        print(f"    [{r['chunk_id']}] score={r['score']}  {r['text'][:60]}...")

    # ── Step 9: HNSW ef_search benchmark ─────────────────────────────────────
    print(f"\n  HNSW ef_search Benchmark")
    print(f"  (higher ef_search = better recall, higher latency)")
    print(f"  {'ef_search':>10} {'latency_ms':>12} {'top_score':>10}")
    print(f"  {'─'*36}")
    bench = benchmark_ef_search(conn, sample_vec)
    for b in bench:
        print(f"  {b['ef_search']:>10} {b['latency_ms']:>11.2f}ms {b['top_score']:>10.4f}")

    # ── Done ──────────────────────────────────────────────────────────────────
    conn.close()
    print(f"\n  Module 04 complete.")
    print(f"  Data is now in PostgreSQL and ready for hybrid search (module 08).")


if __name__ == "__main__":
    run()