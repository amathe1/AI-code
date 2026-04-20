"""
Module 08 — Hybrid Search: Semantic + BM25 + RRF
===================================================
Data source : pgvector for semantic search (HNSW)
              BM25 on text fetched from pgvector
Techniques  : Semantic | BM25 | RRF (Reciprocal Rank Fusion)
Metrics     : Precision@K, Recall@K, Latency p50/p90/p95/p99

Run:
    cd rag_system && python 08_hybrid_search.py
"""

import os, sys, time, math, statistics
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
#             k,_,v = line.partition("="); k=k.strip(); v=v.strip()
#             if " #" in v: v=v[:v.index(" #")].strip()
#             if len(v)>=2 and v[0] in('"',"'") and v[0]==v[-1]: v=v[1:-1]
#             if k and k not in os.environ: os.environ[k]=v; loaded[k]=v
#     return loaded

# load_env(ENV_PATH)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_HOST = os.getenv("PGVECTOR_HOST","localhost")
DB_PORT = int(os.getenv("PGVECTOR_PORT","5432"))
DB_NAME = os.getenv("PGVECTOR_DB","ecommerce_rag")
DB_USER = os.getenv("PGVECTOR_USER","raguser")
DB_PASS = os.getenv("PGVECTOR_PASS","ragpass123")

RRF_K   = 60
N_RUNS  = 30    # latency percentile runs

TEST_QUERIES = [
    {"query":"What is the return window for Prime members?",           "relevant":["sec_005"]},
    {"query":"How does Prime same-day delivery work?",                  "relevant":["sec_004"]},
    {"query":"My item arrived damaged, what should I do?",             "relevant":["sec_006"]},
    {"query":"Can I cancel my order after placing it?",                "relevant":["sec_003"]},
    {"query":"How many coins do I earn per dollar as a Prime member?", "relevant":["sec_012"]},
]


def get_conn():
    try:
        import psycopg2
        from pgvector.psycopg2 import register_vector
        conn = psycopg2.connect(host=DB_HOST,port=DB_PORT,dbname=DB_NAME,
                                user=DB_USER,password=DB_PASS,connect_timeout=5)
        register_vector(conn)
        return conn
    except Exception as e:
        print(f"\n  [ERROR] pgvector connection failed: {e}"); sys.exit(1)


def embed_query(text: str, client) -> list:
    return client.embeddings.create(
        model="text-embedding-3-small", input=[text]).data[0].embedding


def load_all_chunks(conn) -> list[dict]:
    """Fetch all chunks from pgvector for BM25 indexing."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT chunk_id, section_id, section_title, text, access_level, token_count
            FROM document_chunks ORDER BY id;
        """)
        rows = cur.fetchall()
    return [{"chunk_id":r[0],"section_id":r[1],"section_title":r[2],
              "text":r[3],"access_level":r[4],"token_count":r[5]} for r in rows]


# ── 1. Semantic search via pgvector HNSW ──────────────────────────────────────
def semantic_search(conn, qvec: list, k=5) -> list[dict]:
    vec = f"[{','.join(str(round(x,8)) for x in qvec)}]"
    with conn.cursor() as cur:
        cur.execute("SET hnsw.ef_search = 100;")
        cur.execute("""
            SELECT chunk_id, section_id, section_title, text, access_level,
                   1-(embedding <=> %s::vector) AS score
            FROM document_chunks
            WHERE access_level = ANY(%s)
            ORDER BY embedding <=> %s::vector LIMIT %s;
        """, (vec, ["public","internal","confidential"], vec, k))
        rows = cur.fetchall()
    results = [{"chunk_id":r[0],"section_id":r[1],"section_title":r[2],
                "text":r[3],"access_level":r[4],"score":round(float(r[5]),4),
                "rank_semantic":i+1} for i,r in enumerate(rows)]
    return results


# ── 2. BM25 search on in-memory corpus ────────────────────────────────────────
class BM25Index:
    def __init__(self, chunks: list[dict]):
        from rank_bm25 import BM25Okapi
        self.chunks  = chunks
        self.corpus  = [c["text"].lower().split() for c in chunks]
        self.bm25    = BM25Okapi(self.corpus)

    def search(self, query: str, k: int = 5) -> list[dict]:
        tokens = query.lower().split()
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
        results = []
        for rank,(idx,score) in enumerate(ranked):
            results.append({**self.chunks[idx],
                            "score":round(float(score),4),
                            "rank_bm25":rank+1})
        return results


# ── 3. RRF merge ─────────────────────────────────────────────────────────────
def rrf_merge(sem: list[dict], bm25: list[dict], k=5) -> list[dict]:
    scores: dict[str,float] = {}
    data  : dict[str,dict]  = {}
    for rank,r in enumerate(sem,1):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid,0) + 1/(RRF_K+rank)
        data[cid]   = r
    for rank,r in enumerate(bm25,1):
        cid = r["chunk_id"]
        scores[cid] = scores.get(cid,0) + 1/(RRF_K+rank)
        if cid not in data: data[cid]=r
    merged = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
    return [{**data[cid],"score":round(s,6)} for cid,s in merged]


# ── Metrics ───────────────────────────────────────────────────────────────────
def precision_at_k(res, rel, k):
    return sum(1 for r in res[:k] if r.get("section_id") in rel)/k

def recall_at_k(res, rel, k):
    return len({r.get("section_id") for r in res[:k]} & set(rel))/max(len(rel),1)

def pcts(lats):
    s=sorted(lats); n=len(s)
    def p(pct): return round(s[max(0,int(n*pct/100)-1)],3)
    return {"p50":p(50),"p90":p(90),"p95":p(95),"p99":p(99),
            "mean":round(sum(s)/n,3)}


def benchmark_query(query, relevant, conn, bm25_idx, client, k=5):
    qvec = embed_query(query, client)

    sem_lats, bm25_lats, rrf_lats = [], [], []
    sem_res = bm25_res = rrf_res = None

    for _ in range(N_RUNS):
        t0=time.perf_counter(); sem_res=semantic_search(conn,qvec,k)
        sem_lats.append((time.perf_counter()-t0)*1000)

        t0=time.perf_counter(); bm25_res=bm25_idx.search(query,k)
        bm25_lats.append((time.perf_counter()-t0)*1000)

        t0=time.perf_counter(); rrf_res=rrf_merge(sem_res,bm25_res,k)
        rrf_lats.append((time.perf_counter()-t0)*1000)

    out={}
    for tech,res,lats in [("semantic",sem_res,sem_lats),
                           ("bm25",bm25_res,bm25_lats),
                           ("rrf",rrf_res,rrf_lats)]:
        out[tech]={"precision@1":precision_at_k(res,relevant,1),
                   "precision@3":precision_at_k(res,relevant,3),
                   "precision@5":precision_at_k(res,relevant,5),
                   "recall@5"   :recall_at_k(res,relevant,5),
                   "latency"    :pcts(lats),
                   "results"    :res}
    return out


def run():
    print("="*65)
    print("  MODULE 08 — Hybrid Search")
    print("  Data source: pgvector (semantic) + BM25 (keyword) + RRF (fusion)")
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

    # Load all chunks for BM25 (BM25 needs all text in memory)
    print("  Loading chunks from pgvector for BM25 index ...")
    chunks   = load_all_chunks(conn)
    bm25_idx = BM25Index(chunks)
    print(f"  BM25 index built on {len(chunks)} chunks")

    agg = {t:{"p@1":[],"p@3":[],"p@5":[],"r@5":[],
               "p50":[],"p90":[],"p95":[],"p99":[]}
           for t in ["semantic","bm25","rrf"]}

    for tq in TEST_QUERIES:
        q, rel = tq["query"], tq["relevant"]
        print(f"\n  Query: '{q}'")
        print(f"  {'─'*60}")
        print(f"  {'Technique':<12} {'P@1':>5} {'P@3':>5} {'P@5':>5} "
              f"{'R@5':>5} {'p50':>7} {'p90':>7} {'p95':>7} {'p99':>7}")
        print(f"  {'─'*65}")

        bench = benchmark_query(q, rel, conn, bm25_idx, client)
        for tech,m in bench.items():
            lat=m["latency"]
            print(f"  {tech:<12} {m['precision@1']:>5.3f} {m['precision@3']:>5.3f} "
                  f"{m['precision@5']:>5.3f} {m['recall@5']:>5.3f} "
                  f"{lat['p50']:>7.2f} {lat['p90']:>7.2f} "
                  f"{lat['p95']:>7.2f} {lat['p99']:>7.2f}")
            agg[tech]["p@1"].append(m["precision@1"])
            agg[tech]["p@3"].append(m["precision@3"])
            agg[tech]["p@5"].append(m["precision@5"])
            agg[tech]["r@5"].append(m["recall@5"])
            agg[tech]["p50"].append(lat["p50"])
            agg[tech]["p90"].append(lat["p90"])
            agg[tech]["p95"].append(lat["p95"])
            agg[tech]["p99"].append(lat["p99"])

    def avg(lst): return round(sum(lst)/max(len(lst),1),4)

    print(f"\n  Aggregate — mean across {len(TEST_QUERIES)} queries")
    print(f"  {'─'*65}")
    print(f"  {'Technique':<12} {'P@1':>5} {'P@3':>5} {'P@5':>5} "
          f"{'R@5':>5} {'p50':>7} {'p90':>7} {'p95':>7} {'p99':>7}")
    print(f"  {'─'*65}")
    for tech,m in agg.items():
        print(f"  {tech:<12} {avg(m['p@1']):>5.3f} {avg(m['p@3']):>5.3f} "
              f"{avg(m['p@5']):>5.3f} {avg(m['r@5']):>5.3f} "
              f"{avg(m['p50']):>7.2f} {avg(m['p90']):>7.2f} "
              f"{avg(m['p95']):>7.2f} {avg(m['p99']):>7.2f}")

    best = max(agg.items(), key=lambda x: avg(x[1]["p@5"]))
    print(f"\n  Best Precision@5: {best[0].upper()}")
    print(f"  Recommendation  : RRF combines semantic + keyword signals.")
    print(f"                    Use RRF in production for best overall recall.")

    conn.close()
    print(f"\n  Module 08 complete.")


if __name__ == "__main__":
    run()