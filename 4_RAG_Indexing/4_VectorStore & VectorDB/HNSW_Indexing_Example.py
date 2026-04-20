"""
Simple ChromaDB HNSW Indexing Example
======================================
HNSW = Hierarchical Navigable Small World
5 financial documents → embed → HNSW index → search → tune → compare

How HNSW works:
  Builds a multi-layer graph where each node (vector) connects to
  its M nearest neighbours. Search navigates from the top layer
  (coarse) down to the bottom layer (fine) — like a skip list for
  vector space. Approximate but very fast.

Key parameters:
  M               : edges per node. More = better recall, more RAM.
  construction_ef : beam width at build time. More = better graph, slower insert.
  search_ef       : beam width at query time. More = better recall, slower query.
                    search_ef >= M is the recommended minimum.
"""

import numpy as np
import chromadb

# ── 1. Documents ──────────────────────────────────────────────────────────────
DOCS = [
    {"id": "doc_0", "text": "FY2024 revenue was $12.6M, growing 23% year-over-year. Q4 alone hit $4.2M.",
     "meta": {"doc_type": "report",   "department": "finance",     "year": 2024}},
    {"id": "doc_1", "text": "Engineering achieved 99.98% uptime and reduced API latency by 38% in Q1 2024.",
     "meta": {"doc_type": "report",   "department": "engineering", "year": 2024}},
    {"id": "doc_2", "text": "Acme Corp SaaS contract: $450,000 over 36 months. 99.9% uptime SLA guaranteed.",
     "meta": {"doc_type": "contract", "department": "sales",       "year": 2024}},
    {"id": "doc_3", "text": "Invoice: DigitalOcean $3.68, AWS $16,000, Bio Gen X $6,600 — all paid Q1 2024.",
     "meta": {"doc_type": "invoice",  "department": "finance",     "year": 2024}},
    {"id": "doc_4", "text": "HR policy: salary bands $75K–$450K. Parental leave 16 weeks fully paid.",
     "meta": {"doc_type": "report",   "department": "hr",          "year": 2024}},
]

DIM = 128   # embedding dimension (use 1536 for OpenAI in production)

# ── 2. Embeddings (replace with real OpenAI / BGE in production) ──────────────
def embed(texts):
    vecs = []
    for t in texts:
        rng = np.random.default_rng(seed=abs(hash(t)) % (2**31))
        v   = rng.standard_normal(DIM).astype(np.float32)
        vecs.append((v / np.linalg.norm(v)).tolist())
    return vecs


# ── 3. Build ChromaDB HNSW collection ─────────────────────────────────────────
# ChromaDB always uses HNSW internally.
# These parameters control the recall / speed / RAM tradeoff.
client = chromadb.Client()   # in-memory; swap to PersistentClient for disk

collection = client.create_collection(
    name     = "hnsw_demo",
    metadata = {
        "hnsw:space"           : "cosine",  # similarity metric: cosine | l2 | ip
        "hnsw:M"               : 16,        # edges per node  (default 16)
        "hnsw:construction_ef" : 100,       # build beam width (default 100)
        "hnsw:search_ef"       : 100,       # query beam width (default 10 — raise this!)
    }
)

collection.add(
    ids        = [d["id"]   for d in DOCS],
    embeddings = embed([d["text"] for d in DOCS]),
    documents  = [d["text"] for d in DOCS],
    metadatas  = [d["meta"] for d in DOCS],
)

print(f"HNSW index built — {collection.count()} documents\n")


# ── 4. Basic vector search ────────────────────────────────────────────────────
QUERIES = [
    "What was the annual revenue growth?",
    "Tell me about API performance improvements.",
    "What are the contract payment terms?",
    "Which vendor invoices were paid?",
    "What is the parental leave policy?",
]

query_vecs = embed(QUERIES)
results    = collection.query(
    query_embeddings = query_vecs,
    n_results        = 2,
    include          = ["documents", "distances"],
)

print("=" * 55)
print("Basic HNSW Search")
print("=" * 55)
for q, docs, dists in zip(QUERIES, results["documents"], results["distances"]):
    print(f"\nQuery : {q}")
    for rank, (doc, dist) in enumerate(zip(docs, dists), 1):
        sim = round(1 - dist, 4)
        print(f"  [{rank}] score={sim:.4f} | {doc[:65]}...")


# ── 5. Metadata filter search ─────────────────────────────────────────────────
print("\n" + "=" * 55)
print("HNSW + Metadata Filter")
print("=" * 55)

# Search only within finance department
r = collection.query(
    query_embeddings = [embed(["revenue costs budget"])[0]],
    n_results        = 3,
    where            = {"department": {"$eq": "finance"}},
    include          = ["documents", "metadatas", "distances"],
)
print("\nQuery: 'revenue costs budget' | where: department='finance'")
for doc, meta, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0]):
    print(f"  score={round(1-dist,4):.4f} | {meta['doc_type']:<8} | {doc[:60]}...")

# Search only contracts and invoices (OR filter)
r2 = collection.query(
    query_embeddings = [embed(["payment agreement billing"])[0]],
    n_results        = 3,
    where            = {"$or": [
        {"doc_type": {"$eq": "contract"}},
        {"doc_type": {"$eq": "invoice"}},
    ]},
    include          = ["documents", "metadatas", "distances"],
)
print("\nQuery: 'payment agreement billing' | where: doc_type in [contract, invoice]")
for doc, meta, dist in zip(r2["documents"][0], r2["metadatas"][0], r2["distances"][0]):
    print(f"  score={round(1-dist,4):.4f} | {meta['doc_type']:<8} | {doc[:60]}...")


# ── 6. HNSW parameter comparison ──────────────────────────────────────────────
print("\n" + "=" * 55)
print("HNSW M Parameter Comparison")
print("(higher M = better recall, more RAM, slower insert)")
print("=" * 55)

import time

query_vec = embed(["financial performance revenue growth"])[0]

for M in [4, 16, 32, 64]:
    col = client.create_collection(
        name     = f"hnsw_M{M}",
        metadata = {
            "hnsw:space"           : "cosine",
            "hnsw:M"               : M,
            "hnsw:construction_ef" : 100,
            "hnsw:search_ef"       : 100,
        }
    )
    t0 = time.perf_counter()
    col.add(
        ids        = [d["id"]   for d in DOCS],
        embeddings = embed([d["text"] for d in DOCS]),
        documents  = [d["text"] for d in DOCS],
        metadatas  = [d["meta"] for d in DOCS],
    )
    insert_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    res = col.query(query_embeddings=[query_vec], n_results=1,
                    include=["documents", "distances"])
    query_ms = (time.perf_counter() - t0) * 1000

    top_doc  = res["documents"][0][0][:45]
    top_sim  = round(1 - res["distances"][0][0], 4)
    # Approximate RAM: M * N * 4 bytes for the graph edges
    graph_kb = round(M * len(DOCS) * 4 / 1024, 2)

    print(f"  M={M:<3}  insert={insert_ms:5.1f}ms  "
          f"query={query_ms:4.1f}ms  "
          f"graph~{graph_kb}KB  "
          f"top_score={top_sim:.4f}  [{top_doc}...]")


# ── 7. search_ef comparison ───────────────────────────────────────────────────
print("\n" + "=" * 55)
print("search_ef Comparison")
print("(higher ef = better recall, slower query — tune at runtime)")
print("=" * 55)

# Note: ChromaDB sets search_ef at collection creation time, not per-query.
# To change it, create a new collection or set it before querying.
for ef in [10, 50, 100, 200, 400]:
    col_ef = client.create_collection(
        name     = f"hnsw_ef{ef}",
        metadata = {
            "hnsw:space"           : "cosine",
            "hnsw:M"               : 16,
            "hnsw:construction_ef" : 100,
            "hnsw:search_ef"       : ef,
        }
    )
    col_ef.add(
        ids        = [d["id"]   for d in DOCS],
        embeddings = embed([d["text"] for d in DOCS]),
        documents  = [d["text"] for d in DOCS],
        metadatas  = [d["meta"] for d in DOCS],
    )
    t0 = time.perf_counter()
    res = col_ef.query(query_embeddings=[query_vec], n_results=1,
                       include=["distances"])
    q_ms = (time.perf_counter() - t0) * 1000
    sim  = round(1 - res["distances"][0][0], 4)
    print(f"  search_ef={ef:<4}  query={q_ms:4.1f}ms  top_score={sim:.4f}")


# ── 8. CRUD operations ────────────────────────────────────────────────────────
# print("\n" + "=" * 55)
# print("CRUD Operations")
# print("=" * 55)

# # get by ID
# fetched = collection.get(ids=["doc_0"], include=["documents", "metadatas"])
# print(f"\nget(doc_0)  : {fetched['documents'][0][:55]}...")

# # update
# collection.update(
#     ids        = ["doc_0"],
#     documents  = ["FY2024 revenue $12.6M, 23% growth. FY2025 target: $16M+."],
#     embeddings = embed(["FY2024 revenue $12.6M, 23% growth. FY2025 target: $16M+."]),
#     metadatas  = [{"doc_type": "report", "department": "finance", "year": 2025}],
# )
# updated = collection.get(ids=["doc_0"], include=["documents"])
# print(f"update()    : {updated['documents'][0][:55]}...")

# # delete
# collection.delete(ids=["doc_4"])
# print(f"delete(doc_4): count now = {collection.count()}")

# # upsert (insert or update)
# collection.upsert(
#     ids        = ["doc_new"],
#     embeddings = embed(["New document about APAC expansion plans 2025."]),
#     documents  = ["New document about APAC expansion plans 2025."],
#     metadatas  = [{"doc_type": "report", "department": "sales", "year": 2025}],
# )
# print(f"upsert(doc_new): count now = {collection.count()}")


# ── 9. Cheat-sheet ────────────────────────────────────────────────────────────
# print("""
# ChromaDB HNSW Cheat-Sheet
# --------------------------
# Parameter          Default  Effect
# hnsw:space         cosine   cosine | l2 | ip
# hnsw:M             16       Edges per node. Higher = better recall, more RAM.
# hnsw:construction_ef 100    Build beam width. Higher = better graph, slower insert.
# hnsw:search_ef     10       Query beam width. Higher = better recall, slower query.
#                             Always set this >= M. Default 10 is too low!

# Recommended settings:
#   Dev/prototype  : M=16, construction_ef=100, search_ef=100
#   High recall    : M=32, construction_ef=200, search_ef=200
#   Near-flat      : M=64, construction_ef=400, search_ef=400

# Persist to disk:
#   client = chromadb.PersistentClient(path="./chroma_store")

# vs FAISS HNSW (faiss.IndexHNSWFlat):
#   ChromaDB  → metadata filtering, persistence, REST API, simple CRUD
#   FAISS     → lower latency, more parameter control, GPU-ready
# """)