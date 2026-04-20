"""
Module 11 — Golden Dataset & Continuous Evaluation Pipeline
=============================================================
Data source : pgvector (PostgreSQL + HNSW index)
Step 1      : Questions per section (hardcoded + LLM generated)
Step 2      : Ground truth answers via LLM
Step 3      : Categorise queries
Step 4      : Continuous evaluation pipeline (queries pgvector)
Step 5      : Score targets and reporting

Run:
    cd rag_system && python 11_golden_dataset.py
"""

import os, sys, json, re, math, time
from pathlib import Path
from dataclasses import dataclass, asdict, field
from datetime import datetime
from collections import Counter
from dotenv import load_dotenv
load_dotenv()

# ENV_PATH = Path(__file__).parent / ".env"
OUT_PATH = Path(__file__).parent / "golden_dataset.json"

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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","")
DB_HOST = os.getenv("PGVECTOR_HOST","localhost")
DB_PORT = int(os.getenv("PGVECTOR_PORT","5432"))
DB_NAME = os.getenv("PGVECTOR_DB","ecommerce_rag")
DB_USER = os.getenv("PGVECTOR_USER","raguser")
DB_PASS = os.getenv("PGVECTOR_PASS","ragpass123")

# Hardcoded golden questions per section
GOLDEN_QUESTIONS = {
    "sec_001": [
        ("What is the monthly cost of Prime membership?",              ["sec_001"]),
        ("How long is the Prime free trial?",                          ["sec_001"]),
        ("Can Prime benefits be shared with family members?",          ["sec_001"]),
    ],
    "sec_004": [
        ("What is the order cutoff time for Prime same-day delivery?", ["sec_004"]),
        ("Is 2-day shipping free for all Prime members?",              ["sec_004"]),
        ("What happens if my package is lost in transit?",             ["sec_004"]),
    ],
    "sec_005": [
        ("How many days does a Prime member have to return electronics?",["sec_005"]),
        ("Are digital downloads refundable?",                           ["sec_005"]),
        ("What is the step-by-step return process?",                    ["sec_005"]),
    ],
    "sec_006": [
        ("What photos do I need to submit for a damage claim?",         ["sec_006"]),
        ("How quickly must I report a damaged item after delivery?",    ["sec_006"]),
        ("Will I get a replacement or refund for a damaged item?",      ["sec_006"]),
    ],
    "sec_008": [
        ("How does the Price Match Guarantee work for Prime members?",  ["sec_008"]),
        ("Can I stack multiple coupons on one order?",                  ["sec_008"]),
        ("Which retailers are eligible for price matching?",            ["sec_008"]),
    ],
    "sec_012": [
        ("How many Coins do I earn per dollar as a Prime member?",      ["sec_012"]),
        ("When do my ShopNow Coins expire?",                            ["sec_012"]),
        ("What is the minimum number of Coins I can redeem?",           ["sec_012"]),
    ],
}

INTENT_KEYWORDS = {
    "comparative"    :["prime","standard","vs","compare","difference","between"],
    "procedural"     :["how to","step","process","procedure","what do i do"],
    "edge_case"      :["what if","exception","lost","wrong","special","unusual"],
    "policy_lookup"  :["policy","rule","days","hours","fee","cost","price","refund","window"],
    "factual_simple" :["what is","how much","when","where"],
}

SCORE_TARGETS = {
    "p@5"  :(0.60,"Precision@5 >= 0.60"),
    "r@5"  :(0.70,"Recall@5 >= 0.70"),
    "mrr"  :(0.55,"MRR >= 0.55"),
    "ndcg" :(0.65,"NDCG@5 >= 0.65"),
    "ctx_p":(0.60,"Context Precision >= 0.60"),
    "ctx_r":(0.70,"Context Recall >= 0.70"),
}


@dataclass
class GoldenItem:
    item_id      : str
    question     : str
    ground_truth : str
    section_ids  : list
    category     : str
    difficulty   : str
    access_level : str
    created_at   : str = field(default_factory=lambda: datetime.now().isoformat())


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


def fetch_section_text(conn, section_id: str) -> tuple[str,str]:
    """Fetch the full text and access_level of a section from pgvector."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT section_title, text, access_level
            FROM document_chunks
            WHERE section_id = %s
            ORDER BY chunk_index LIMIT 1;
        """, (section_id,))
        row = cur.fetchone()
    if row:
        return row[0], row[1], row[2]
    return "", "", "public"


def call_llm(prompt, client) -> str:
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}],
            temperature=0.2, max_tokens=400)
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


# ── Step 2: Generate ground truth ─────────────────────────────────────────────
ANSWER_PROMPT = """You are generating ground truth answers for an e-commerce RAG evaluation dataset.
Answer the question ONLY using the provided policy text.
Be specific — include any exact numbers, timeframes, or conditions from the text.

Policy text:
{text}

Question: {question}

Answer:"""


def generate_ground_truth(question: str, context: str, client) -> str:
    ans = call_llm(ANSWER_PROMPT.format(text=context[:2000], question=question), client)
    if ans:
        return ans
    # Heuristic fallback: return most relevant sentence
    sentences = [s.strip() for s in context.split(".") if s.strip()]
    qwords = set(question.lower().split())
    best, best_n = "", 0
    for s in sentences:
        n = len(qwords & set(s.lower().split()))
        if n > best_n:
            best_n, best = n, s
    return best + "." if best else context[:200]


# ── Step 3: Categorise ────────────────────────────────────────────────────────
def categorise(question: str) -> tuple[str,str]:
    q = question.lower()
    if any(k in q for k in INTENT_KEYWORDS["comparative"]):
        return "comparative", "medium"
    if any(k in q for k in INTENT_KEYWORDS["procedural"]):
        return "procedural", "medium"
    if any(k in q for k in INTENT_KEYWORDS["edge_case"]):
        return "edge_case", "hard"
    if any(k in q for k in INTENT_KEYWORDS["policy_lookup"]):
        return "policy_lookup", "medium"
    if len(question.split()) <= 8:
        return "factual_simple", "easy"
    return "factual_complex", "hard"


# ── Step 4: Metrics ───────────────────────────────────────────────────────────
def precision_at_k(res, rel, k):
    return sum(1 for r in res[:k] if r["section_id"] in rel)/k

def recall_at_k(res, rel, k):
    return len({r["section_id"] for r in res[:k]} & set(rel))/max(len(rel),1)

def mrr(res, rel):
    for rank,r in enumerate(res,1):
        if r["section_id"] in rel: return 1/rank
    return 0.0

def ndcg_at_k(res, rel, k):
    dcg  = sum(1/math.log2(rk+1) for rk,r in enumerate(res[:k],1) if r["section_id"] in rel)
    idcg = sum(1/math.log2(rk+1) for rk in range(1,min(len(rel),k)+1))
    return dcg/idcg if idcg else 0.0

def ctx_precision(res, rel):
    return sum(1 for r in res if r["section_id"] in rel)/max(len(res),1)

def ctx_recall(res, ground_truth):
    gt = set(ground_truth.lower().split())
    ctx= set(" ".join(r["text"] for r in res).lower().split())
    return len(gt & ctx)/max(len(gt),1)


def run_evaluation(golden: list[GoldenItem], conn, client, k=5) -> dict:
    """Query pgvector for every golden item and compute all metrics."""
    by_cat: dict = {}
    all_m = {m:[] for m in ["p@5","r@5","mrr","ndcg","ctx_p","ctx_r"]}

    for item in golden:
        qvec = embed_query(item.question, client)
        res  = pgvector_search(conn, qvec, k)
        rel  = item.section_ids

        scores = {
            "p@5"  : precision_at_k(res,rel,5),
            "r@5"  : recall_at_k(res,rel,5),
            "mrr"  : mrr(res,rel),
            "ndcg" : ndcg_at_k(res,rel,5),
            "ctx_p": ctx_precision(res,rel),
            "ctx_r": ctx_recall(res,item.ground_truth),
        }
        for m,v in scores.items():
            all_m[m].append(v)
            by_cat.setdefault(item.category,{m:[] for m in all_m})[m].append(v)

    def avg(lst): return round(sum(lst)/max(len(lst),1),4)
    return {
        "overall"     : {m:avg(v) for m,v in all_m.items()},
        "by_category" : {cat:{m:avg(v) for m,v in mets.items()}
                         for cat,mets in by_cat.items()},
        "n_items"     : len(golden),
    }


def run():
    print("="*65)
    print("  MODULE 11 — Golden Dataset & Continuous Evaluation")
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

    # ── Step 1 & 2: Build golden items ────────────────────────────────────────
    print(f"\n  Step 1+2: Building golden dataset from pgvector sections ...")
    golden: list[GoldenItem] = []
    item_id = 0

    for sec_id, qa_pairs in GOLDEN_QUESTIONS.items():
        title, context, access = fetch_section_text(conn, sec_id)
        if not context:
            print(f"    ⚠  Section {sec_id} not found in pgvector — skipping")
            continue

        for question, rel_secs in qa_pairs:
            gt  = generate_ground_truth(question, context, client)
            cat, diff = categorise(question)
            golden.append(GoldenItem(
                item_id      = f"gold_{item_id:04d}",
                question     = question,
                ground_truth = gt,
                section_ids  = rel_secs,
                category     = cat,
                difficulty   = diff,
                access_level = access,
            ))
            item_id += 1

    print(f"    Generated {len(golden)} golden items across "
          f"{len(GOLDEN_QUESTIONS)} sections")

    # ── Step 3: Distribution ──────────────────────────────────────────────────
    by_cat  = Counter(g.category   for g in golden)
    by_diff = Counter(g.difficulty for g in golden)
    print(f"\n  Step 3: Query Categorisation")
    print(f"    By category  : {dict(by_cat)}")
    print(f"    By difficulty: {dict(by_diff)}")

    # ── Step 4: Run evaluation against pgvector ───────────────────────────────
    print(f"\n  Step 4: Running evaluation pipeline (pgvector HNSW) ...")
    eval_results = run_evaluation(golden, conn, client)

    print(f"\n    Overall Metrics (n={eval_results['n_items']})")
    print(f"    {'Metric':<16} {'Score':>8} {'Target':>8}  Status")
    print(f"    {'─'*44}")
    passed = 0
    for metric,(target,desc) in SCORE_TARGETS.items():
        actual = eval_results["overall"].get(metric,0)
        ok     = actual >= target
        if ok: passed += 1
        print(f"    {metric:<16} {actual:>8.4f} {target:>8.2f}  "
              f"{'PASS' if ok else 'FAIL'}")

    print(f"\n    By Category")
    print(f"    {'Category':<20} {'P@5':>6} {'MRR':>6} {'NDCG':>6} {'N':>4}")
    print(f"    {'─'*42}")
    for cat,mets in eval_results["by_category"].items():
        n = by_cat.get(cat,0)
        print(f"    {cat:<20} {mets.get('p@5',0):>6.4f} "
              f"{mets.get('mrr',0):>6.4f} {mets.get('ndcg',0):>6.4f} {n:>4}")

    # ── Step 5: Score guidance ────────────────────────────────────────────────
    print(f"\n  Step 5: Score Targets")
    print(f"  {'─'*55}")
    for metric,(target,desc) in SCORE_TARGETS.items():
        actual = eval_results["overall"].get(metric,0)
        status = "PASS" if actual>=target else "NEEDS WORK"
        print(f"  {status:<12} {metric:<8} {actual:.4f}  {desc}")

    print(f"\n  Overall: {passed}/{len(SCORE_TARGETS)} targets met")
    if passed == len(SCORE_TARGETS):
        print("  ✓  System is production-ready.")
    elif passed >= len(SCORE_TARGETS)*0.75:
        print("  △  Minor tuning needed before production.")
    else:
        print("  ✗  Significant improvement needed.")
        print("     Tip: ensure module 03 used real OpenAI embeddings,")
        print("     and module 04 loaded those into pgvector.")

    # ── Save ──────────────────────────────────────────────────────────────────
    output = {
        "created_at"      : datetime.now().isoformat(),
        "total_items"     : len(golden),
        "sections_covered": list(GOLDEN_QUESTIONS.keys()),
        "eval_results"    : eval_results,
        "score_targets"   : {m:t for m,(t,_) in SCORE_TARGETS.items()},
        "golden_items"    : [asdict(g) for g in golden],
    }
    OUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"\n  Saved → {OUT_PATH}")

    conn.close()
    print(f"\n  Module 11 complete.")


if __name__ == "__main__":
    run()