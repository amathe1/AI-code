"""
Module 06 — Query Processing
==============================
Data source : pgvector (PostgreSQL + HNSW index)  ← correct production flow
Techniques  : Baseline | Reformulation | Expansion | Intent Validation
Metrics     : Precision@5, Latency per technique, Final recommendation

Flow:
    User Query
        → OpenAI embed query          (text-embedding-3-small)
        → pgvector HNSW search        (cosine distance, ef_search=100)
        → return ranked chunks

Prerequisites:
    1. docker run -d --name pgvector_rag \
         -e POSTGRES_DB=ecommerce_rag \
         -e POSTGRES_USER=raguser \
         -e POSTGRES_PASSWORD=ragpass123 \
         -p 5432:5432 pgvector/pgvector:pg16

    2. python 03_embeddings.py   (real OpenAI vectors)
    3. python 04_pgvector.py     (loads vectors into pgvector)

Run:
    cd rag_system && python 06_query_processing.py
"""

import os, json, re, time, sys
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# ── Load .env ─────────────────────────────────────────────────────────────────
# ENV_PATH = Path(__file__).parent / ".env"

# def load_env(path: Path) -> dict:
#     if not path.exists():
#         return {}
#     loaded = {}
#     with open(path) as f:
#         for line in f:
#             line = line.strip()
#             if not line or line.startswith("#") or "=" not in line:
#                 continue
#             key, _, val = line.partition("=")
#             key = key.strip(); val = val.strip()
#             if " #" in val:
#                 val = val[:val.index(" #")].strip()
#             if len(val) >= 2 and val[0] in ('"', "'") and val[0] == val[-1]:
#                 val = val[1:-1]
#             if key and key not in os.environ:
#                 os.environ[key] = val
#                 loaded[key] = val
#     return loaded

# _loaded = load_env(ENV_PATH)

# ── Config ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBED_MODEL    = "text-embedding-3-small"
EMBED_DIM      = 1536

DB_HOST = os.getenv("PGVECTOR_HOST", "localhost")
DB_PORT = int(os.getenv("PGVECTOR_PORT", "5432"))
DB_NAME = os.getenv("PGVECTOR_DB",   "ecommerce_rag")
DB_USER = os.getenv("PGVECTOR_USER", "raguser")
DB_PASS = os.getenv("PGVECTOR_PASS", "ragpass123")

# Ground-truth for evaluation (section IDs from module 01)
TEST_QUERIES = [
    {
        "query"             : "What is the return window for Prime members?",
        "relevant_sections" : ["sec_005"],
        "topic"             : "returns",
    },
    {
        "query"             : "How does Prime same-day delivery work and what is the cutoff time?",
        "relevant_sections" : ["sec_004"],
        "topic"             : "shipping",
    },
    {
        "query"             : "My item arrived damaged. What photos do I need and how do I report it?",
        "relevant_sections" : ["sec_006"],
        "topic"             : "damage_claims",
    },
    {
        "query"             : "Can I cancel my order and within what time window?",
        "relevant_sections" : ["sec_003"],
        "topic"             : "ordering",
    },
    {
        "query"             : "How many ShopNow Coins do I earn per dollar as a Prime member?",
        "relevant_sections" : ["sec_012"],
        "topic"             : "loyalty",
    },
]

# Intent → section mapping
INTENT_MAP = {
    "returns_refunds"    : ["sec_005"],
    "shipping_delivery"  : ["sec_004"],
    "ordering_checkout"  : ["sec_003"],
    "membership_prime"   : ["sec_001"],
    "payment_billing"    : ["sec_009"],
    "damage_claims"      : ["sec_006"],
    "inventory"          : ["sec_007"],
    "account_management" : ["sec_010"],
    "loyalty_rewards"    : ["sec_012"],
    "pricing_promotions" : ["sec_008"],
    "general_inquiry"    : [],
}

INTENT_KEYWORDS = {
    "returns_refunds"    : ["return","refund","send back","money back","exchange"],
    "shipping_delivery"  : ["ship","deliver","tracking","arrival","same-day","cutoff","2-day"],
    "ordering_checkout"  : ["order","cancel","checkout","purchase","30 min","place order"],
    "membership_prime"   : ["prime","membership","subscription","trial","upgrade"],
    "payment_billing"    : ["pay","bill","charge","invoice","credit card","dispute"],
    "damage_claims"      : ["damage","broken","defective","wrong item","doa","photo","report"],
    "inventory"          : ["stock","available","backorder","pre-order","out of stock"],
    "account_management" : ["account","password","login","email","close account"],
    "loyalty_rewards"    : ["coin","loyalty","point","reward","cashback","earn","coins"],
    "pricing_promotions" : ["price","discount","coupon","promo","price match","deal"],
}

REFORMULATE_PROMPT = """You are a query rewriting assistant for an e-commerce customer service system.
Rewrite the following customer query to be more specific and suitable for semantic vector search.
- Expand abbreviations and vague terms
- Add relevant domain terms (policy, ShopNow, ecommerce)
- Keep it as a single natural-language sentence
Return ONLY the rewritten query string, nothing else.

Original query: {query}"""

EXPAND_PROMPT = """Generate exactly 3 alternative phrasings of this e-commerce customer query.
Each phrasing should capture the same intent using different words.
Return ONLY a valid JSON array of 3 strings. No explanation, no markdown fences.

Query: {query}"""

INTENT_PROMPT = """Classify the following e-commerce customer service query into exactly one of:
returns_refunds, shipping_delivery, ordering_checkout, membership_prime,
payment_billing, damage_claims, inventory, account_management,
loyalty_rewards, pricing_promotions, general_inquiry

Return ONLY the intent name, nothing else.

Query: {query}"""


# ─────────────────────────────────────────────────────────────────────────────
# PGVECTOR CONNECTION
# ─────────────────────────────────────────────────────────────────────────────
def get_db_connection():
    """
    Open a psycopg2 connection with the pgvector type registered.
    Exits with a helpful message if connection fails.
    """
    try:
        import psycopg2
        from pgvector.psycopg2 import register_vector
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            dbname=DB_NAME, user=DB_USER, password=DB_PASS,
            connect_timeout=5,
        )
        register_vector(conn)
        return conn
    except ImportError as e:
        print(f"\n  [ERROR] Missing package: {e}")
        print(f"  Fix:  pip install psycopg2-binary pgvector")
        sys.exit(1)
    except Exception as e:
        print(f"\n  [ERROR] Cannot connect to pgvector at {DB_HOST}:{DB_PORT}")
        print(f"  Detail: {e}")
        print(f"\n  Make sure the Docker container is running:")
        print(f"    docker ps | grep pgvector_rag")
        print(f"  If not running:")
        print(f"    docker run -d --name pgvector_rag \\")
        print(f"      -e POSTGRES_DB=ecommerce_rag \\")
        print(f"      -e POSTGRES_USER=raguser \\")
        print(f"      -e POSTGRES_PASSWORD=ragpass123 \\")
        print(f"      -p 5432:5432 pgvector/pgvector:pg16")
        print(f"\n  Then reload data:  python 04_pgvector.py")
        sys.exit(1)


def verify_db_has_data(conn) -> int:
    """Check how many rows are in document_chunks. Exit if empty."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM document_chunks;")
        count = cur.fetchone()[0]
    if count == 0:
        print(f"\n  [ERROR] document_chunks table is empty.")
        print(f"  Run module 04 to load data:  python 04_pgvector.py")
        sys.exit(1)
    return count


# ─────────────────────────────────────────────────────────────────────────────
# PGVECTOR SEARCH  (replaces the old in-memory cosine loop)
# ─────────────────────────────────────────────────────────────────────────────
def pgvector_search(conn,
                    query_vec    : list[float],
                    access_levels: list[str],
                    top_k        : int = 5,
                    ef_search    : int = 100) -> list[dict]:
    """
    Search document_chunks using the HNSW index.
    Uses cosine distance operator <=> (1 - cosine_similarity).
    """
    vec_str = f"[{','.join(str(round(x, 8)) for x in query_vec)}]"

    with conn.cursor() as cur:
        cur.execute(f"SET hnsw.ef_search = {ef_search};")
        cur.execute("""
            SELECT
                chunk_id,
                section_id,
                section_title,
                text,
                access_level,
                token_count,
                1 - (embedding <=> %s::vector) AS score
            FROM document_chunks
            WHERE access_level = ANY(%s)
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (vec_str, access_levels, vec_str, top_k))
        rows = cur.fetchall()

    return [
        {
            "chunk_id"     : r[0],
            "section_id"   : r[1],
            "section_title": r[2],
            "text"         : r[3],
            "access_level" : r[4],
            "token_count"  : r[5],
            "score"        : round(float(r[6]), 4),
        }
        for r in rows
    ]


def pgvector_search_by_sections(conn,
                                 query_vec   : list[float],
                                 section_ids : list[str],
                                 top_k       : int = 5,
                                 ef_search   : int = 100) -> list[dict]:
    """
    Intent-filtered search — restrict to specific section IDs.
    Used by the intent_validation technique.
    """
    vec_str = f"[{','.join(str(round(x, 8)) for x in query_vec)}]"

    with conn.cursor() as cur:
        cur.execute(f"SET hnsw.ef_search = {ef_search};")
        cur.execute("""
            SELECT
                chunk_id,
                section_id,
                section_title,
                text,
                access_level,
                token_count,
                1 - (embedding <=> %s::vector) AS score
            FROM document_chunks
            WHERE section_id = ANY(%s)
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (vec_str, section_ids, vec_str, top_k))
        rows = cur.fetchall()

    return [
        {
            "chunk_id"     : r[0],
            "section_id"   : r[1],
            "section_title": r[2],
            "text"         : r[3],
            "access_level" : r[4],
            "token_count"  : r[5],
            "score"        : round(float(r[6]), 4),
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# OPENAI HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def embed_query(text: str, client) -> list[float]:
    response = client.embeddings.create(model=EMBED_MODEL, input=[text])
    return response.data[0].embedding


def call_llm(prompt: str, client) -> tuple[str, float]:
    t0       = time.perf_counter()
    response = client.chat.completions.create(
        model       = "gpt-4o-mini",
        messages    = [{"role": "user", "content": prompt}],
        temperature = 0,
        max_tokens  = 400,
    )
    lat = (time.perf_counter() - t0) * 1000
    return response.choices[0].message.content.strip(), round(lat, 2)


def detect_intent_keywords(query: str) -> str:
    q = query.lower()
    best, best_n = "general_inquiry", 0
    for intent, kws in INTENT_KEYWORDS.items():
        n = sum(1 for kw in kws if kw in q)
        if n > best_n:
            best_n, best = n, intent
    return best


# ─────────────────────────────────────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────────────────────────────────────
def precision_at_k(results: list[dict], relevant: list[str], k: int) -> float:
    hits = sum(1 for r in results[:k] if r.get("section_id") in relevant)
    return round(hits / k, 4)


# ─────────────────────────────────────────────────────────────────────────────
# 4 QUERY TECHNIQUES  (all use pgvector for retrieval)
# ─────────────────────────────────────────────────────────────────────────────
def run_baseline(query: str, conn, relevant: list[str], client) -> dict:
    """
    Technique 1 — Baseline
    Embed the raw query as-is → pgvector HNSW search.
    """
    t0  = time.perf_counter()
    qv  = embed_query(query, client)
    res = pgvector_search(conn, qv, ["public", "internal", "confidential"])
    lat = (time.perf_counter() - t0) * 1000
    return {
        "technique"    : "baseline",
        "query_used"   : query,
        "precision@5"  : precision_at_k(res, relevant, 5),
        "latency_ms"   : round(lat, 2),
        "top_sections" : [r["section_id"] for r in res[:3]],
        "top_scores"   : [r["score"]      for r in res[:3]],
        "results"      : res,
    }


def run_reformulation(query: str, conn, relevant: list[str], client) -> dict:
    """
    Technique 2 — Query Reformulation
    LLM rewrites the query to be more specific → embed → pgvector search.
    """
    t0               = time.perf_counter()
    reformed, llm_ms = call_llm(REFORMULATE_PROMPT.format(query=query), client)
    qv               = embed_query(reformed, client)
    res              = pgvector_search(conn, qv, ["public", "internal", "confidential"])
    lat              = (time.perf_counter() - t0) * 1000
    return {
        "technique"    : "reformulation",
        "query_used"   : reformed,
        "original"     : query,
        "llm_ms"       : llm_ms,
        "precision@5"  : precision_at_k(res, relevant, 5),
        "latency_ms"   : round(lat, 2),
        "top_sections" : [r["section_id"] for r in res[:3]],
        "top_scores"   : [r["score"]      for r in res[:3]],
        "results"      : res,
    }


def run_expansion(query: str, conn, relevant: list[str], client) -> dict:
    """
    Technique 3 — Query Expansion
    LLM generates 3 variants → embed all → pgvector search each →
    merge results (best score per chunk wins) → return top-5.
    """
    t0          = time.perf_counter()
    raw, llm_ms = call_llm(EXPAND_PROMPT.format(query=query), client)

    variants: list[str] = []
    try:
        raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.M)
        variants = json.loads(raw)
        if not isinstance(variants, list):
            variants = []
    except Exception:
        pass

    if not variants:
        variants = [
            query + " policy details",
            "ShopNow " + query,
            "how does " + query + " work",
        ]

    # Embed base query once for deduplication scoring
    base_qv = embed_query(query, client)

    # Search with each variant and merge by best score
    best_per_chunk: dict[str, dict] = {}
    for q in [query] + variants[:3]:
        qv = embed_query(q, client)
        for r in pgvector_search(conn, qv, ["public","internal","confidential"], top_k=10):
            cid = r["chunk_id"]
            if cid not in best_per_chunk or r["score"] > best_per_chunk[cid]["score"]:
                best_per_chunk[cid] = r

    merged = sorted(best_per_chunk.values(),
                    key=lambda x: x["score"], reverse=True)[:5]
    lat    = (time.perf_counter() - t0) * 1000
    return {
        "technique"    : "expansion",
        "query_used"   : query,
        "variants"     : variants,
        "queries_run"  : len(variants) + 1,
        "llm_ms"       : llm_ms,
        "precision@5"  : precision_at_k(merged, relevant, 5),
        "latency_ms"   : round(lat, 2),
        "top_sections" : [r["section_id"] for r in merged[:3]],
        "top_scores"   : [r["score"]      for r in merged[:3]],
        "results"      : merged,
    }


def run_intent_validation(query: str, conn, relevant: list[str], client) -> dict:
    """
    Technique 4 — Intent Validation
    LLM classifies query intent → filter pgvector search to target sections.
    This is the most precise technique — searches only the relevant section.
    """
    t0               = time.perf_counter()
    intent_raw, llm_ms = call_llm(INTENT_PROMPT.format(query=query), client)

    intent = intent_raw.strip().lower()
    if intent not in INTENT_MAP:
        intent = detect_intent_keywords(query)   # keyword fallback

    target_secs = INTENT_MAP.get(intent, [])

    qv = embed_query(query, client)

    if target_secs:
        # Search ONLY within the detected intent's sections
        res = pgvector_search_by_sections(conn, qv, target_secs, top_k=5)
        # If filtered search returns nothing, fall back to full search
        if not res:
            res = pgvector_search(conn, qv, ["public","internal","confidential"])
    else:
        # general_inquiry — search everything
        res = pgvector_search(conn, qv, ["public","internal","confidential"])

    lat = (time.perf_counter() - t0) * 1000
    return {
        "technique"         : "intent_validation",
        "query_used"        : query,
        "intent"            : intent,
        "target_sections"   : target_secs,
        "llm_ms"            : llm_ms,
        "precision@5"       : precision_at_k(res, relevant, 5),
        "latency_ms"        : round(lat, 2),
        "top_sections"      : [r["section_id"] for r in res[:3]],
        "top_scores"        : [r["score"]      for r in res[:3]],
        "results"           : res,
    }


# ─────────────────────────────────────────────────────────────────────────────
# RECOMMENDATION
# ─────────────────────────────────────────────────────────────────────────────
def recommend(techniques: list[dict]) -> str:
    max_lat = max(t["latency_ms"] for t in techniques) or 1.0
    scored  = [
        (t["precision@5"] * 0.7 + (1.0 - t["latency_ms"] / max_lat) * 0.3,
         t["technique"])
        for t in techniques
    ]
    return max(scored, key=lambda x: x[0])[1]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def run():
    print("=" * 65)
    print("  MODULE 06 — Query Processing")
    print("  Data source: pgvector HNSW index (PostgreSQL)")
    print("=" * 65)

    # ── Validate API key ──────────────────────────────────────────────────────
    # if not OPENAI_API_KEY or OPENAI_API_KEY in ("sk-...your-key-here...",):
    #     print(f"\n  [ERROR] OPENAI_API_KEY not set in .env")
    #     print(f"  Add it to {ENV_PATH}:  OPENAI_API_KEY=sk-...")
    #     sys.exit(1)

    # print(f"\n  API key   : sk-...{OPENAI_API_KEY[-8:]}")
    # print(f"  DB        : {DB_HOST}:{DB_PORT}/{DB_NAME}")

    # ── Connect to pgvector ───────────────────────────────────────────────────
    print(f"\n  Connecting to pgvector ...")
    conn  = get_db_connection()
    count = verify_db_has_data(conn)
    print(f"  ✓  Connected — {count} chunks in document_chunks")

    # ── OpenAI client ─────────────────────────────────────────────────────────
    import openai
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    # ── Run all 4 techniques on every test query ──────────────────────────────
    agg = {t: {"p5": [], "lat": []}
           for t in ["baseline","reformulation","expansion","intent_validation"]}
    all_recs = []

    for tq in TEST_QUERIES:
        q, rel = tq["query"], tq["relevant_sections"]

        print(f"\n  {'═'*63}")
        print(f"  Query   : '{q}'")
        print(f"  Topic   : {tq['topic']}")
        print(f"  Relevant: {rel}")
        print(f"  {'─'*63}")

        t1 = run_baseline(q,           conn, rel, client)
        t2 = run_reformulation(q,      conn, rel, client)
        t3 = run_expansion(q,          conn, rel, client)
        t4 = run_intent_validation(q,  conn, rel, client)

        techniques = [t1, t2, t3, t4]
        rec        = recommend(techniques)
        all_recs.append(rec)

        print(f"\n  {'Technique':<22} {'P@5':>6} {'Latency':>10}  Top sections        Scores")
        print(f"  {'─'*75}")
        for t in techniques:
            mark   = " ← rec" if t["technique"] == rec else ""
            secs   = ", ".join(t.get("top_sections", []))
            scores = ", ".join(str(s) for s in t.get("top_scores", []))
            extra  = ""
            if t["technique"] == "reformulation":
                extra = f"\n{'':24}  rewritten: \"{t['query_used'][:55]}\""
            elif t["technique"] == "intent_validation":
                extra = f"\n{'':24}  intent={t['intent']}  filter→{t.get('target_sections',[])}"
            elif t["technique"] == "expansion":
                extra = f"\n{'':24}  {t.get('queries_run',1)} queries merged"
            print(f"  {t['technique']:<22} {t['precision@5']:>6.4f}"
                  f" {t['latency_ms']:>8.1f}ms  [{secs}]  [{scores}]{mark}{extra}")
            agg[t["technique"]]["p5"].append(t["precision@5"])
            agg[t["technique"]]["lat"].append(t["latency_ms"])

    conn.close()

    # ── Aggregate summary ─────────────────────────────────────────────────────
    def avg(lst): return round(sum(lst) / max(len(lst), 1), 4)

    print(f"\n\n  {'═'*65}")
    print(f"  Aggregate Results — {len(TEST_QUERIES)} queries — pgvector HNSW")
    print(f"  {'═'*65}")
    print(f"  {'Technique':<22} {'Avg P@5':>8} {'Avg Lat':>10}  Wins  Bar")
    print(f"  {'─'*60}")
    for tech, vals in agg.items():
        wins = all_recs.count(tech)
        bar  = "█" * int(avg(vals["p5"]) * 20)
        print(f"  {tech:<22} {avg(vals['p5']):>8.4f}"
              f" {avg(vals['lat']):>8.1f}ms  {wins:>4}  {bar}")

    best_p5  = max(agg.items(), key=lambda x: avg(x[1]["p5"]))[0]
    best_lat = min(agg.items(), key=lambda x: avg(x[1]["lat"]))[0]

    print(f"\n  Best Precision@5 : {best_p5}")
    print(f"  Fastest          : {best_lat}")
    print(f"""
  Production recommendation:
    ┌─ intent_validation  → primary path (highest precision, low latency)
    │   Narrows pgvector search to the correct section before querying.
    │
    ├─ expansion          → fallback when intent = general_inquiry
    │   Runs 4 queries, merges results — best recall at higher latency.
    │
    └─ baseline           → fastest option when latency is critical
        Single embed + single pgvector query, no LLM overhead.
""")


if __name__ == "__main__":
    run()


# """
# M6_QueryProcessing - Intelligent Query Processing with Semantic Caching
# =======================================================================
# Architecture:
#   User Query → Intent Normalizer → Redis Semantic Cache Check
#                                         ↓ HIT              ↓ MISS
#                                    Return cached     PgVector similarity
#                                      response           search + LLM
#                                                             ↓
#                                                     Store in Redis cache
#                                                     (with intent fingerprint)

# Key Intelligence:
#   - Canonicalizes intent so "how to cancel order" == "can I cancel my order?"
#   - Uses embedding similarity for fuzzy cache matching (threshold: 0.92)
#   - Stores both exact query hash AND semantic embedding fingerprint
#   - TTL-aware: fresh data for prices, longer cache for policies
# """

# import hashlib
# import json
# import time
# import re
# import logging
# from dataclasses import dataclass, field, asdict
# from typing import Optional, Any
# from enum import Enum

# import redis
# import numpy as np
# from openai import OpenAI  # or use anthropic / sentence-transformers

# logger = logging.getLogger(__name__)


# # ─────────────────────────────────────────────
# # 1. INTENT TAXONOMY
# # ─────────────────────────────────────────────

# class QueryIntent(str, Enum):
#     """Canonical intent labels. These are the normalised 'buckets'."""
#     ORDER_CANCEL        = "order_cancel"
#     ORDER_STATUS        = "order_status"
#     ORDER_RETURN        = "order_return"
#     ORDER_REFUND        = "order_refund"
#     PRODUCT_INFO        = "product_info"
#     PRODUCT_AVAILABILITY= "product_availability"
#     SHIPPING_INFO       = "shipping_info"
#     PAYMENT_METHODS     = "payment_methods"
#     ACCOUNT_HELP        = "account_help"
#     COMPLAINT           = "complaint"
#     GENERAL             = "general"


# # TTL (seconds) per intent — volatile data gets shorter TTL
# INTENT_TTL: dict[QueryIntent, int] = {
#     QueryIntent.ORDER_CANCEL:        3600 * 6,   # 6h  – policy stable
#     QueryIntent.ORDER_STATUS:        60,          # 1m  – live data
#     QueryIntent.ORDER_RETURN:        3600 * 6,
#     QueryIntent.ORDER_REFUND:        3600 * 6,
#     QueryIntent.PRODUCT_INFO:        3600 * 2,
#     QueryIntent.PRODUCT_AVAILABILITY:120,         # 2m  – stock changes fast
#     QueryIntent.SHIPPING_INFO:       3600 * 12,
#     QueryIntent.PAYMENT_METHODS:     3600 * 24,
#     QueryIntent.ACCOUNT_HELP:        3600 * 4,
#     QueryIntent.COMPLAINT:           300,
#     QueryIntent.GENERAL:             1800,
# }


# # ─────────────────────────────────────────────
# # 2. INTENT PATTERN MATCHER  (fast, no LLM)
# # ─────────────────────────────────────────────

# # Each pattern is a list of regex fragments – ANY match → that intent
# INTENT_PATTERNS: list[tuple[QueryIntent, list[str]]] = [
#     (QueryIntent.ORDER_CANCEL, [
#         r"cancel\w*\s+(?:my\s+)?order",
#         r"(?:how\s+(?:do|can|to)\s+(?:i\s+)?)?cancel",
#         r"stop\s+(?:my\s+)?order",
#         r"(?:undo|abort|revoke|nullify|withdraw)\s+(?:my\s+)?(?:order|purchase)",
#         r"don.t\s+want\s+(?:the\s+)?order",
#         r"want\s+to\s+(?:back\s+out|pull\s+out)",
#         r"order\s+(?:cancellation|cancelled|cancel)",
#         r"i\s+(?:want|need)\s+to\s+abort",
#     ]),
#     (QueryIntent.ORDER_STATUS, [
#         r"(?:where|when)\s+is\s+my\s+(?:order|package|parcel|shipment)",
#         r"track(?:ing)?\s+(?:my\s+)?(?:order|package)",
#         r"order\s+status",
#         r"has\s+(?:my\s+)?order\s+(?:shipped|arrived|dispatched)",
#         r"delivery\s+status",
#         r"estimated\s+(?:delivery|arrival)",
#     ]),
#     (QueryIntent.ORDER_RETURN, [
#         r"return\s+(?:my\s+)?(?:order|item|product|purchase)",
#         r"how\s+(?:do|can|to)\s+(?:i\s+)?return",
#         r"send\s+(?:it\s+)?back",
#         r"return\s+policy",
#         r"want\s+to\s+return",
#     ]),
#     (QueryIntent.ORDER_REFUND, [
#         r"refund",
#         r"money\s+back",
#         r"get\s+(?:my\s+)?(?:cash|money)\s+(?:back|returned)",
#         r"reimburs",
#         r"chargeback",
#     ]),
#     (QueryIntent.PRODUCT_AVAILABILITY, [
#         r"in\s+stock",
#         r"available\b",
#         r"out\s+of\s+stock",
#         r"when\s+(?:will|is)\s+.+\s+(?:available|back)",
#         r"do\s+you\s+(?:have|carry|sell)",
#     ]),
#     (QueryIntent.SHIPPING_INFO, [
#         r"shipping\s+(?:cost|fee|charge|time|option)",
#         r"how\s+(?:long|much)\s+(?:does|for)\s+(?:shipping|delivery)",
#         r"free\s+shipping",
#         r"express\s+(?:delivery|shipping)",
#         r"international\s+shipping",
#     ]),
#     (QueryIntent.PAYMENT_METHODS, [
#         r"payment\s+(?:method|option|mode)",
#         r"(?:can\s+i\s+pay|accept)\s+(?:with\s+)?(?:card|upi|cod|emi|wallet)",
#         r"emi\s+(?:option|available|plan)",
#         r"cash\s+on\s+delivery",
#     ]),
#     (QueryIntent.ACCOUNT_HELP, [
#         r"(?:forgot|reset|change)\s+(?:my\s+)?password",
#         r"(?:login|sign.in)\s+(?:issue|problem|help)",
#         r"account\s+(?:locked|suspended|help|issue)",
#         r"update\s+(?:my\s+)?(?:email|phone|address)",
#     ]),
#     (QueryIntent.COMPLAINT, [
#         r"(?:wrong|damaged|broken|defective|missing)\s+(?:item|product|order)",
#         r"never\s+(?:arrived|received|delivered)",
#         r"complaint",
#         r"escalat",
#         r"very\s+(?:bad|poor|terrible)\s+(?:service|experience)",
#     ]),
# ]


# def detect_intent_pattern(query: str) -> Optional[QueryIntent]:
#     """
#     Fast regex-based intent detection (no API call).
#     Returns None if ambiguous – caller should use LLM fallback.
#     """
#     q = query.lower().strip()
#     matches: list[QueryIntent] = []
#     for intent, patterns in INTENT_PATTERNS:
#         for pat in patterns:
#             if re.search(pat, q):
#                 matches.append(intent)
#                 break
#     if len(matches) == 1:
#         return matches[0]
#     # Multiple matches → ambiguous (e.g., "cancel and refund")
#     # Return the first match as best-guess; LLM will confirm
#     return matches[0] if matches else None


# # ─────────────────────────────────────────────
# # 3. QUERY NORMALIZER
# # ─────────────────────────────────────────────

# # Words that don't change semantic intent – strip them for cache key
# _FILLER = re.compile(
#     r"\b(please|kindly|could|would|can|may|i|my|the|a|an|"
#     r"tell|me|want|need|like|help|just|quick|quickly|exactly|"
#     r"is it possible|possible|hi|hello|hey|dear|sir|madam|"
#     r"how do i|how to|how can i|what is|what's|"
#     r"steps to|steps for|ways to|guide|guide me|"
#     r"to|for|of|in|on|at|this|that|these|those|it|"
#     r"get|do|did|does|done|have|has|had)\b",
#     re.IGNORECASE,
# )
# _PUNCT   = re.compile(r"[^\w\s]")
# _SPACES  = re.compile(r"\s+")

# SYNONYMS: dict[str, str] = {
#     # cancel synonyms (longest phrases first to avoid partial replacement)
#     "pull out":    "cancel",
#     "back out":    "cancel",
#     "don't want":  "cancel",
#     "not want":    "cancel",
#     "send back":   "return",
#     "ship back":   "return",
#     "money back":  "refund",
#     "get refund":  "refund",
#     "where is":    "status",
#     # single-word synonyms
#     "abort":       "cancel",
#     "revoke":      "cancel",
#     "undo":        "cancel",
#     "withdraw":    "cancel",
#     "stop":        "cancel",
#     "nullify":     "cancel",
#     "tracking":    "status",
#     "locate":      "status",
#     "delivery":    "shipping",
#     "dispatch":    "shipping",
# }


# def normalize_query(query: str) -> str:
#     """
#     Produces a canonical string from a raw query.
#     'How can I cancel my order please?' → 'cancel order'
#     'I want to stop my order!'         → 'cancel order'
#     """
#     q = query.lower().strip()
#     q = _PUNCT.sub(" ", q)

#     # Apply synonym map (longest match first)
#     for synonym, canonical in sorted(SYNONYMS.items(), key=lambda x: -len(x[0])):
#         q = q.replace(synonym, canonical)

#     q = _FILLER.sub(" ", q)
#     q = _SPACES.sub(" ", q).strip()
#     return q


# def build_exact_cache_key(normalized: str, intent: Optional[QueryIntent]) -> str:
#     """
#     Deterministic Redis key for exact/near-exact matches.
#     Format: eq:<intent>:<md5(normalized)>
#     """
#     h = hashlib.md5(normalized.encode()).hexdigest()[:12]
#     prefix = intent.value if intent else "general"
#     return f"eq:{prefix}:{h}"


# # ─────────────────────────────────────────────
# # 4. EMBEDDING CLIENT (swap in any provider)
# # ─────────────────────────────────────────────

# class EmbeddingClient:
#     """Thin wrapper – swap for sentence-transformers, Cohere, etc."""

#     def __init__(self, api_key: str = ""):
#         # Using OpenAI here; replace with your provider
#         self._client = OpenAI(api_key=api_key) if api_key else None

#     def embed(self, text: str) -> list[float]:
#         if self._client:
#             resp = self._client.embeddings.create(
#                 model="text-embedding-3-small",
#                 input=text,
#             )
#             return resp.data[0].embedding
#         # Fallback: random vector for local dev/testing
#         rng = np.random.default_rng(abs(hash(text)) % (2**31))
#         return rng.random(1536).tolist()

#     @staticmethod
#     def cosine_similarity(a: list[float], b: list[float]) -> float:
#         va, vb = np.array(a), np.array(b)
#         denom = np.linalg.norm(va) * np.linalg.norm(vb)
#         return float(np.dot(va, vb) / denom) if denom else 0.0


# # ─────────────────────────────────────────────
# # 5. REDIS SEMANTIC CACHE
# # ─────────────────────────────────────────────

# SEMANTIC_SIMILARITY_THRESHOLD = 0.92   # tune this
# MAX_SEMANTIC_CANDIDATES       = 50     # scan at most N keys per intent bucket


# @dataclass
# class CachedEntry:
#     query_raw:       str
#     query_normalized:str
#     intent:          str
#     response:        str
#     embedding:       list[float]
#     hit_count:       int = 0
#     created_at:      float = field(default_factory=time.time)
#     last_accessed:   float = field(default_factory=time.time)


# class SemanticCache:
#     """
#     Two-level cache:
#       L1 – exact match:   Redis GET  on deterministic key (O(1))
#       L2 – semantic match: Redis SCAN + cosine similarity  (O(n), bounded)
#     """

#     def __init__(self, redis_client: redis.Redis, embedder: EmbeddingClient):
#         self.r         = redis_client
#         self.embedder  = embedder

#     # ── Public API ──────────────────────────────

#     def get(
#         self,
#         query: str,
#         intent: Optional[QueryIntent],
#     ) -> tuple[Optional[CachedEntry], str]:
#         """
#         Returns (entry, cache_level) where cache_level ∈ {'L1','L2','MISS'}
#         """
#         norm = normalize_query(query)

#         # L1 – exact/near-exact
#         exact_key = build_exact_cache_key(norm, intent)
#         raw = self.r.get(exact_key)
#         if raw:
#             entry = CachedEntry(**json.loads(raw))
#             self._bump_hit(exact_key, entry)
#             logger.info(f"[Cache L1 HIT] key={exact_key}")
#             return entry, "L1"

#         # L2 – semantic similarity
#         query_emb = self.embedder.embed(norm)
#         entry = self._semantic_search(query_emb, intent)
#         if entry:
#             logger.info(f"[Cache L2 HIT] intent={intent}")
#             # Promote: write L1 alias so next identical query is O(1)
#             self._write(exact_key, entry, intent)
#             return entry, "L2"

#         return None, "MISS"

#     def set(
#         self,
#         query: str,
#         intent: Optional[QueryIntent],
#         response: str,
#     ) -> None:
#         norm      = normalize_query(query)
#         emb       = self.embedder.embed(norm)
#         exact_key = build_exact_cache_key(norm, intent)
#         ttl       = INTENT_TTL.get(intent, 1800) if intent else 1800

#         entry = CachedEntry(
#             query_raw        = query,
#             query_normalized = norm,
#             intent           = intent.value if intent else "general",
#             response         = response,
#             embedding        = emb,
#         )
#         self.r.set(exact_key, json.dumps(asdict(entry)), ex=ttl)

#         # Also store in semantic index bucket for L2 lookups
#         bucket_key = self._bucket_key(intent)
#         self.r.lpush(bucket_key, exact_key)
#         self.r.ltrim(bucket_key, 0, 999)   # keep last 1000 per intent
#         logger.info(f"[Cache SET] key={exact_key} ttl={ttl}s")

#     def invalidate_intent(self, intent: QueryIntent) -> int:
#         """Flush all cached entries for a given intent (e.g., after policy change)."""
#         bucket_key  = self._bucket_key(intent)
#         keys        = self.r.lrange(bucket_key, 0, -1)
#         deleted     = 0
#         for k in keys:
#             deleted += self.r.delete(k)
#         self.r.delete(bucket_key)
#         logger.info(f"[Cache INVALIDATE] intent={intent.value} deleted={deleted}")
#         return deleted

#     # ── Internals ───────────────────────────────

#     def _semantic_search(
#         self,
#         query_emb: list[float],
#         intent: Optional[QueryIntent],
#     ) -> Optional[CachedEntry]:
#         bucket_key = self._bucket_key(intent)
#         candidate_keys = self.r.lrange(bucket_key, 0, MAX_SEMANTIC_CANDIDATES - 1)

#         best_score = 0.0
#         best_entry = None

#         for k in candidate_keys:
#             raw = self.r.get(k)
#             if not raw:
#                 continue
#             entry = CachedEntry(**json.loads(raw))
#             score = self.embedder.cosine_similarity(query_emb, entry.embedding)
#             if score > best_score:
#                 best_score = score
#                 best_entry = entry

#         if best_score >= SEMANTIC_SIMILARITY_THRESHOLD:
#             logger.info(f"[Semantic] best_score={best_score:.4f} ≥ threshold")
#             return best_entry

#         logger.debug(f"[Semantic] best_score={best_score:.4f} < threshold → MISS")
#         return None

#     def _write(self, key: str, entry: CachedEntry, intent: Optional[QueryIntent]) -> None:
#         ttl = INTENT_TTL.get(intent, 1800) if intent else 1800
#         self.r.set(key, json.dumps(asdict(entry)), ex=ttl)

#     def _bump_hit(self, key: str, entry: CachedEntry) -> None:
#         entry.hit_count   += 1
#         entry.last_accessed = time.time()
#         ttl = self.r.ttl(key)
#         self.r.set(key, json.dumps(asdict(entry)), ex=max(ttl, 60))

#     @staticmethod
#     def _bucket_key(intent: Optional[QueryIntent]) -> str:
#         label = intent.value if intent else "general"
#         return f"sem_bucket:{label}"


# # ─────────────────────────────────────────────
# # 6. PGVECTOR RETRIEVER  (your existing RAG layer)
# # ─────────────────────────────────────────────

# class PgVectorRetriever:
#     """Placeholder – wire up your existing pgvector logic here."""

#     def __init__(self, dsn: str, embedder: EmbeddingClient):
#         self.dsn      = dsn
#         self.embedder = embedder

#     def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
#         """Returns list of {content, metadata, score} dicts."""
#         logger.info(f"[PgVector] Querying for: {query!r}")
#         # ── YOUR EXISTING PGVECTOR CODE GOES HERE ──
#         # Example stub:
#         return [
#             {
#                 "content":  "To cancel an order, go to My Orders → Select Order → Cancel. "
#                             "Cancellation is free if the order hasn't shipped.",
#                 "metadata": {"source": "faq", "topic": "cancellation"},
#                 "score":    0.97,
#             }
#         ]


# # ─────────────────────────────────────────────
# # 7. RESPONSE GENERATOR  (LLM synthesis)
# # ─────────────────────────────────────────────

# class ResponseGenerator:
#     """Synthesizes a final answer from retrieved chunks."""

#     def __init__(self, openai_client: OpenAI):
#         self._client = openai_client

#     def generate(
#         self,
#         query:    str,
#         intent:   Optional[QueryIntent],
#         chunks:   list[dict],
#     ) -> str:
#         context = "\n\n".join(c["content"] for c in chunks)
#         system  = (
#             "You are a helpful ecommerce support assistant. "
#             "Answer ONLY using the provided context. Be concise and friendly."
#         )
#         user_msg = (
#             f"Context:\n{context}\n\n"
#             f"Customer question: {query}\n"
#             f"Detected intent: {intent.value if intent else 'unknown'}"
#         )
#         # Replace with your LLM call
#         # resp = self._client.chat.completions.create(
#         #     model="gpt-4o-mini",
#         #     messages=[{"role":"system","content":system},
#         #               {"role":"user","content":user_msg}],
#         #     temperature=0.3,
#         # )
#         # return resp.choices[0].message.content
#         return f"[LLM Response for intent={intent}] Based on our policy: {chunks[0]['content'] if chunks else 'No info found.'}"


# # ─────────────────────────────────────────────
# # 8. M6 QUERY PROCESSOR  (the orchestrator)
# # ─────────────────────────────────────────────

# @dataclass
# class ProcessingResult:
#     query:          str
#     intent:         Optional[str]
#     normalized:     str
#     response:       str
#     cache_level:    str          # "L1" | "L2" | "MISS"
#     latency_ms:     float
#     from_cache:     bool


# class M6QueryProcessor:
#     """
#     Main entry point.  Call .process(query) for every user message.

#     Pipeline:
#       1. Pattern-match intent (fast, no LLM)
#       2. Normalize query
#       3. L1 cache check (exact key lookup)
#       4. L2 cache check (semantic embedding similarity)
#       5. PgVector retrieval   ← only on cache MISS
#       6. LLM synthesis        ← only on cache MISS
#       7. Store result in Redis
#     """

#     def __init__(
#         self,
#         redis_client:  redis.Redis,
#         pg_retriever:  PgVectorRetriever,
#         response_gen:  ResponseGenerator,
#         embedder:      EmbeddingClient,
#     ):
#         self.cache     = SemanticCache(redis_client, embedder)
#         self.retriever = pg_retriever
#         self.gen       = response_gen

#     def process(self, query: str) -> ProcessingResult:
#         t0     = time.perf_counter()
#         norm   = normalize_query(query)
#         intent = detect_intent_pattern(query)

#         # ── Cache lookup ──────────────────────────
#         entry, cache_level = self.cache.get(query, intent)

#         if entry:
#             latency = (time.perf_counter() - t0) * 1000
#             logger.info(
#                 f"[M6] {cache_level} HIT | intent={intent} | "
#                 f"norm='{norm}' | latency={latency:.1f}ms"
#             )
#             return ProcessingResult(
#                 query        = query,
#                 intent       = entry.intent,
#                 normalized   = norm,
#                 response     = entry.response,
#                 cache_level  = cache_level,
#                 latency_ms   = latency,
#                 from_cache   = True,
#             )

#         # ── Cache MISS: full RAG pipeline ────────
#         logger.info(f"[M6] MISS | intent={intent} | norm='{norm}' | hitting PgVector")

#         chunks   = self.retriever.retrieve(query)
#         response = self.gen.generate(query, intent, chunks)

#         self.cache.set(query, intent, response)

#         latency = (time.perf_counter() - t0) * 1000
#         logger.info(f"[M6] MISS resolved | latency={latency:.1f}ms")

#         return ProcessingResult(
#             query        = query,
#             intent       = intent.value if intent else "general",
#             normalized   = norm,
#             response     = response,
#             cache_level  = "MISS",
#             latency_ms   = latency,
#             from_cache   = False,
#         )

#     def invalidate(self, intent: QueryIntent) -> int:
#         """Call when policy/product data changes."""
#         return self.cache.invalidate_intent(intent)