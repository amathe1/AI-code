"""
Module 10 — Redis Query Cache
================================
Data source : pgvector (PostgreSQL + HNSW) for cache misses
Cache       : Redis — stores query results by SHA256 key
TTL         : 3600 seconds (1 hour, configurable)

Flow:
    Query → hash key → Redis GET
        HIT  → return cached results instantly
        MISS → pgvector HNSW search → store in Redis → return results

Run:
    docker run -d --name redis_rag -p 6379:6379 redis:7-alpine
    cd rag_system && python 10_redis_cache.py
"""

import os, sys, json, time, hashlib
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# ENV_PATH = Path(__file__).parent / ".env"

# def load_env(path):
#     if not path.exists(): return {}
#     loaded = {}
#     with open(path) as f:
#         for line in f:
#             line=line.strip()
#             if not line or line.startswith("#") or "=" not in line: continue
#             k,_,v=line.partition("="); k=k.strip(); v=v.strip()
#             if " #" in v: v=v[:v.index(" #")].strip()
#             if len(v)>=2 and v[0] in('"',"'") and v[0]==v[-1]: v=v[1:-1]
#             if k and k not in os.environ: os.environ[k]=v; loaded[k]=v
#     return loaded

# load_env(ENV_PATH)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_HOST    = os.getenv("PGVECTOR_HOST","localhost")
DB_PORT    = int(os.getenv("PGVECTOR_PORT","5432"))
DB_NAME    = os.getenv("PGVECTOR_DB","ecommerce_rag")
DB_USER    = os.getenv("PGVECTOR_USER","raguser")
DB_PASS    = os.getenv("PGVECTOR_PASS","ragpass123")
REDIS_HOST = os.getenv("REDIS_HOST","localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT","6379"))
REDIS_DB   = int(os.getenv("REDIS_DB","0"))
CACHE_TTL  = 3600   # 1 hour


def get_pg_conn():
    try:
        import psycopg2
        from pgvector.psycopg2 import register_vector
        conn = psycopg2.connect(host=DB_HOST,port=DB_PORT,dbname=DB_NAME,
                                user=DB_USER,password=DB_PASS,connect_timeout=5)
        register_vector(conn)
        return conn
    except Exception as e:
        print(f"\n  [ERROR] pgvector connection failed: {e}"); sys.exit(1)


def embed_query(text, client):
    return client.embeddings.create(
        model="text-embedding-3-small", input=[text]).data[0].embedding


def pgvector_search(conn, qvec, access: list, k=5) -> list[dict]:
    vec = f"[{','.join(str(round(x,8)) for x in qvec)}]"
    with conn.cursor() as cur:
        cur.execute("SET hnsw.ef_search = 100;")
        cur.execute("""
            SELECT chunk_id, section_id, section_title, text, access_level,
                   1-(embedding <=> %s::vector) AS score
            FROM document_chunks
            WHERE access_level = ANY(%s)
            ORDER BY embedding <=> %s::vector LIMIT %s;
        """, (vec, access, vec, k))
        rows = cur.fetchall()
    return [{"chunk_id":r[0],"section_id":r[1],"section_title":r[2],
              "text":r[3],"access_level":r[4],"score":round(float(r[5]),4)}
             for r in rows]


# ── Cache key ─────────────────────────────────────────────────────────────────
def cache_key(query: str, access: list, k: int) -> str:
    payload = f"{query.lower().strip()}|{','.join(sorted(access))}|{k}"
    return "rag:" + hashlib.sha256(payload.encode()).hexdigest()[:32]


# ── Redis Cache ───────────────────────────────────────────────────────────────
class RAGCache:
    def __init__(self):
        self._mem: dict = {}
        self.live = False
        try:
            import redis
            self.r = redis.Redis(host=REDIS_HOST,port=REDIS_PORT,
                                 db=REDIS_DB,socket_timeout=2,decode_responses=True)
            self.r.ping()
            self.live = True
            print(f"  ✓  Redis connected at {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            print(f"  ⚠  Redis unavailable ({e}) — using in-memory fallback")

    def get(self, key: str):
        if self.live:
            raw = self.r.get(key)
            return json.loads(raw) if raw else None
        return self._mem.get(key)

    def set(self, key: str, value: dict, ttl=CACHE_TTL):
        if self.live:
            self.r.setex(key, ttl, json.dumps(value))
        else:
            self._mem[key] = value

    def flush(self):
        if self.live: self.r.flushdb()
        else: self._mem.clear()

    def stats(self) -> dict:
        if self.live:
            info = self.r.info("stats")
            mem  = self.r.info("memory")
            keys = self.r.dbsize()
            return {"backend":"redis",
                    "keys"    : keys,
                    "hits"    : info.get("keyspace_hits",0),
                    "misses"  : info.get("keyspace_misses",0),
                    "memory"  : mem.get("used_memory_human","—")}
        return {"backend":"in-memory",
                "keys":len(self._mem), "hits":"—", "misses":"—"}


# ── Cached search: HIT → return, MISS → pgvector → cache → return ─────────────
def cached_search(query: str, pg_conn, cache: RAGCache,
                  client, access: list, k=5) -> tuple[list,str,float]:
    key = cache_key(query, access, k)

    # ── HIT ──────────────────────────────────────────────────────────────────
    t0  = time.perf_counter()
    hit = cache.get(key)
    if hit:
        lat = (time.perf_counter()-t0)*1000
        return hit["results"], "HIT", round(lat,3)

    # ── MISS: embed → pgvector → cache ───────────────────────────────────────
    t0      = time.perf_counter()
    qvec    = embed_query(query, client)
    results = pgvector_search(pg_conn, qvec, access, k)
    cache.set(key, {"query":query,"access":access,"k":k,"results":results})
    lat = (time.perf_counter()-t0)*1000
    return results, "MISS", round(lat,3)


def run():
    print("="*65)
    print("  MODULE 10 — Redis Query Cache")
    print("  Data source: pgvector (MISS) → Redis (HIT)")
    print("="*65)

    if not OPENAI_API_KEY:
        print("\n  [ERROR] OPENAI_API_KEY not set in .env"); sys.exit(1)

    import openai
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    print(f"\n  Connecting to pgvector ...")
    pg_conn = get_pg_conn()
    with pg_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM document_chunks;")
        total = cur.fetchone()[0]
    print(f"  ✓  pgvector — {total} chunks")

    cache = RAGCache()
    cache.flush()   # start clean for demo

    QUERIES = [
        ("What is the return policy for Prime members?",    ["public"]),
        ("How does same-day delivery work?",               ["public"]),
        ("What is the return policy for Prime members?",    ["public"]),  # ← HIT
        ("How does same-day delivery work?",               ["public"]),  # ← HIT
        ("Tell me about fraud prevention security measures", ["public","internal"]),
        ("What is the return policy for Prime members?",    ["public"]),  # ← HIT
        ("How do I cancel my order?",                       ["public"]),
        ("How does same-day delivery work?",               ["public"]),  # ← HIT
    ]

    print(f"\n  Running {len(QUERIES)} queries (some repeated to show cache HIT) ...\n")
    print(f"  {'#':<3} {'Status':<6} {'Latency':>10}  Query")
    print(f"  {'─'*65}")

    hit_lats, miss_lats = [], []
    hit_count = miss_count = 0

    for i,(q,access) in enumerate(QUERIES, 1):
        results, status, lat = cached_search(q, pg_conn, cache, client, access)
        note = "  ← cached" if status=="HIT" else f"  top={results[0]['section_id'] if results else '—'}"
        print(f"  {i:<3} {status:<6} {lat:>8.3f}ms  {q[:50]}...{note}")
        if status=="HIT":
            hit_lats.append(lat); hit_count+=1
        else:
            miss_lats.append(lat); miss_count+=1

    # ── Stats ──────────────────────────────────────────────────────────────────
    print(f"\n  Cache Stats")
    print(f"  {'─'*40}")
    stats = cache.stats()
    for k,v in stats.items():
        print(f"  {k:<20}: {v}")

    if hit_lats and miss_lats:
        avg_hit  = round(sum(hit_lats)/len(hit_lats),3)
        avg_miss = round(sum(miss_lats)/len(miss_lats),3)
        speedup  = round(avg_miss/max(avg_hit,0.001),1)
        print(f"\n  Performance")
        print(f"  {'─'*40}")
        print(f"  Queries           : {len(QUERIES)}  ({miss_count} MISS, {hit_count} HIT)")
        print(f"  Avg MISS latency  : {avg_miss} ms  (embed + pgvector HNSW)")
        print(f"  Avg HIT  latency  : {avg_hit} ms   (Redis GET only)")
        print(f"  Speedup           : {speedup}x faster on cache hit")

    print(f"\n  Cache Key Structure")
    sample = cache_key("What is the return policy?", ["public"], 5)
    print(f"  Format : rag:<sha256_32chars>")
    print(f"  Sample : {sample}")
    print(f"  TTL    : {CACHE_TTL}s ({CACHE_TTL//3600}h)")

    print(f"\n  Invalidation Strategy")
    print(f"  - Knowledge base updated  → flush all  (redis-cli FLUSHDB)")
    print(f"  - Single doc updated      → delete rag:* keys for that section")
    print(f"  - TTL expiry              → automatic after {CACHE_TTL//3600}h")
    print(f"  - Access level changed    → flush keys for affected role")

    pg_conn.close()
    print(f"\n  Module 10 complete.")


if __name__ == "__main__":
    run()