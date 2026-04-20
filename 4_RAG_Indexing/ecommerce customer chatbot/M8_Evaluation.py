"""
Module 09 — Evaluation Metrics
================================
Data source : pgvector (PostgreSQL + HNSW index)
Standard    : Precision@K, Recall@K, MRR, NDCG@5
RAGAS       : Faithfulness, Answer Relevancy, Context Precision, Context Recall

Run:
    cd rag_system && python 09_evaluation.py
"""

import os, sys, time, math
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
DB_HOST = os.getenv("PGVECTOR_HOST","localhost")
DB_PORT = int(os.getenv("PGVECTOR_PORT","5432"))
DB_NAME = os.getenv("PGVECTOR_DB","ecommerce_rag")
DB_USER = os.getenv("PGVECTOR_USER","raguser")
DB_PASS = os.getenv("PGVECTOR_PASS","ragpass123")

EVAL_SET = [
    {
        "query"           : "What is the return window for Prime members?",
        "relevant_sections":["sec_005"],
        "ground_truth"    : "Prime members have a 30-day return window from delivery, extended to 60 days November through January.",
        "generated_answer": "Prime members can return items within 30 days of delivery. During the holiday season (November to January), this window extends to 60 days.",
    },
    {
        "query"           : "How does Prime same-day delivery work?",
        "relevant_sections":["sec_004"],
        "ground_truth"    : "Prime members get free same-day delivery in 40+ metros if they order by 12 PM local time. Delivery arrives by 9 PM the same day.",
        "generated_answer": "Prime members can get same-day delivery in 40+ metro areas for free if they order before noon. Orders arrive by 9 PM that evening.",
    },
    {
        "query"           : "What should I do if my item arrives damaged?",
        "relevant_sections":["sec_006"],
        "ground_truth"    : "Take 3 photos (outer packaging, damage close-up, item label) and report within 48 hours. ShopNow issues replacement or refund immediately without requiring return.",
        "generated_answer": "If your item arrives damaged, take photos of the packaging and the damage, then report it within 48 hours. ShopNow will send a replacement or issue a refund without making you return the item.",
    },
    {
        "query"           : "Can I cancel my order and within what time window?",
        "relevant_sections":["sec_003"],
        "ground_truth"    : "Orders can be cancelled free within 30 minutes of placement. After 30 minutes cancellation is not guaranteed as the order enters the picking queue.",
        "generated_answer": "Yes, you can cancel an order for free within 30 minutes of placing it. After that window, cancellation cannot be guaranteed as fulfilment may have already started.",
    },
    {
        "query"           : "How many ShopNow Coins do I earn as a Prime member?",
        "relevant_sections":["sec_012"],
        "ground_truth"    : "Prime members earn 2 Coins per $1 spent. Standard members earn 1 Coin per $1 spent. 1 Coin = $0.01.",
        "generated_answer": "As a Prime member, you earn 2 ShopNow Coins per dollar spent, compared to 1 Coin per dollar for Standard members. Each Coin is worth one cent.",
    },
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


def embed_query(text, client):
    return client.embeddings.create(
        model="text-embedding-3-small", input=[text]).data[0].embedding


def pgvector_search(conn, qvec, k=5) -> list[dict]:
    vec = f"[{','.join(str(round(x,8)) for x in qvec)}]"
    with conn.cursor() as cur:
        cur.execute("SET hnsw.ef_search = 100;")
        cur.execute("""
            SELECT chunk_id, section_id, section_title, text, access_level,
                   1-(embedding <=> %s::vector) AS score
            FROM document_chunks
            ORDER BY embedding <=> %s::vector LIMIT %s;
        """, (vec, vec, k))
        rows = cur.fetchall()
    return [{"chunk_id":r[0],"section_id":r[1],"section_title":r[2],
              "text":r[3],"access_level":r[4],"score":round(float(r[5]),4)}
             for r in rows]


# ── Standard IR Metrics ────────────────────────────────────────────────────────
def precision_at_k(res, rel, k):
    return round(sum(1 for r in res[:k] if r["section_id"] in rel)/k, 4)

def recall_at_k(res, rel, k):
    return round(len({r["section_id"] for r in res[:k]} & set(rel))/max(len(rel),1), 4)

def mrr(res, rel):
    for rank,r in enumerate(res,1):
        if r["section_id"] in rel: return round(1/rank,4)
    return 0.0

def ndcg_at_k(res, rel, k):
    dcg  = sum(1/math.log2(rk+1) for rk,r in enumerate(res[:k],1) if r["section_id"] in rel)
    idcg = sum(1/math.log2(rk+1) for rk in range(1,min(len(rel),k)+1))
    return round(dcg/idcg,4) if idcg else 0.0


# ── RAGAS-style Metrics ────────────────────────────────────────────────────────
FAITHFULNESS_PROMPT = """Given the contexts below, score what fraction of statements
in the answer are directly supported by the contexts.
Return ONLY a float between 0.0 and 1.0. No explanation.

Contexts:
{contexts}

Answer:
{answer}"""

RELEVANCY_PROMPT = """Score how well this answer addresses the question.
Return ONLY a float between 0.0 and 1.0. No explanation.

Question: {question}
Answer: {answer}"""


def llm_score(prompt: str, client) -> float:
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0, max_tokens=10)
        return float(resp.choices[0].message.content.strip())
    except Exception:
        return 0.0


def ragas_faithfulness(answer: str, contexts: list[str], client) -> float:
    ctx = "\n\n".join(contexts[:3])
    return llm_score(FAITHFULNESS_PROMPT.format(contexts=ctx, answer=answer), client)


def ragas_answer_relevancy(question: str, answer: str, client) -> float:
    return llm_score(RELEVANCY_PROMPT.format(question=question, answer=answer), client)


def ragas_context_precision(res: list[dict], relevant: list[str]) -> float:
    hits = sum(1 for r in res if r["section_id"] in relevant)
    return round(hits/max(len(res),1), 4)


def ragas_context_recall(res: list[dict], ground_truth: str) -> float:
    gt_words  = set(ground_truth.lower().split())
    ctx_words = set(" ".join(r["text"] for r in res).lower().split())
    return round(len(gt_words & ctx_words)/max(len(gt_words),1), 4)


def run():
    print("="*65)
    print("  MODULE 09 — Evaluation Metrics")
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
    print(f"  Evaluating {len(EVAL_SET)} queries ...\n")

    all_p1,all_p3,all_p5=[],[],[]
    all_r5,all_mrr,all_ndcg=[],[],[]
    all_faith,all_rel,all_ctx_p,all_ctx_r=[],[],[],[]

    print(f"  {'Query':<50} {'P@1':>5} {'P@3':>5} {'P@5':>5} "
          f"{'R@5':>5} {'MRR':>5} {'NDCG':>5}")
    print(f"  {'─'*78}")

    for item in EVAL_SET:
        q   = item["query"]
        rel = item["relevant_sections"]
        gt  = item["ground_truth"]
        gen = item["generated_answer"]

        t0  = time.perf_counter()
        qv  = embed_query(q, client)
        res = pgvector_search(conn, qv, k=5)
        lat = (time.perf_counter()-t0)*1000

        p1    = precision_at_k(res, rel, 1)
        p3    = precision_at_k(res, rel, 3)
        p5    = precision_at_k(res, rel, 5)
        r5    = recall_at_k(res,   rel, 5)
        _mrr  = mrr(res, rel)
        _ndcg = ndcg_at_k(res, rel, 5)

        ctxs  = [r["text"] for r in res]
        faith = ragas_faithfulness(gen, ctxs, client)
        rel_s = ragas_answer_relevancy(q, gen, client)
        ctx_p = ragas_context_precision(res, rel)
        ctx_r = ragas_context_recall(res, gt)

        all_p1.append(p1); all_p3.append(p3); all_p5.append(p5)
        all_r5.append(r5); all_mrr.append(_mrr); all_ndcg.append(_ndcg)
        all_faith.append(faith); all_rel.append(rel_s)
        all_ctx_p.append(ctx_p); all_ctx_r.append(ctx_r)

        print(f"  {q[:48]:<50} {p1:>5.3f} {p3:>5.3f} {p5:>5.3f} "
              f"{r5:>5.3f} {_mrr:>5.3f} {_ndcg:>5.3f}  ({lat:.0f}ms)")
        print(f"  {'':50} RAGAS: faith={faith:.3f} rel={rel_s:.3f} "
              f"ctx_p={ctx_p:.3f} ctx_r={ctx_r:.3f}")

    def avg(lst): return round(sum(lst)/max(len(lst),1),4)

    print(f"\n  Aggregate Averages (n={len(EVAL_SET)})")
    print(f"  {'─'*45}")
    print(f"  Precision@1          : {avg(all_p1)}")
    print(f"  Precision@3          : {avg(all_p3)}")
    print(f"  Precision@5          : {avg(all_p5)}")
    print(f"  Recall@5             : {avg(all_r5)}")
    print(f"  MRR                  : {avg(all_mrr)}")
    print(f"  NDCG@5               : {avg(all_ndcg)}")
    print(f"\n  RAGAS Metrics")
    print(f"  {'─'*45}")
    print(f"  Faithfulness         : {avg(all_faith)}")
    print(f"  Answer Relevancy     : {avg(all_rel)}")
    print(f"  Context Precision    : {avg(all_ctx_p)}")
    print(f"  Context Recall       : {avg(all_ctx_r)}")

    TARGETS = [
        ("Precision@5",      avg(all_p5),   0.60),
        ("Recall@5",         avg(all_r5),   0.70),
        ("MRR",              avg(all_mrr),  0.55),
        ("NDCG@5",           avg(all_ndcg), 0.65),
        ("Faithfulness",     avg(all_faith),0.80),
        ("Answer Relevancy", avg(all_rel),  0.75),
        ("Context Precision",avg(all_ctx_p),0.60),
        ("Context Recall",   avg(all_ctx_r),0.70),
    ]
    print(f"\n  Score Targets")
    print(f"  {'Metric':<22} {'Target':>8} {'Actual':>8}  Status")
    print(f"  {'─'*48}")
    passed = 0
    for name,actual,target in TARGETS:
        status = "PASS" if actual>=target else "FAIL"
        if actual>=target: passed+=1
        print(f"  {name:<22} {target:>8.2f} {actual:>8.4f}  {status}")

    print(f"\n  Result: {passed}/{len(TARGETS)} targets met")

    conn.close()
    print(f"\n  Module 09 complete.")


if __name__ == "__main__":
    run()