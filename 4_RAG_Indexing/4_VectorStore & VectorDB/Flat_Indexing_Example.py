"""
Simple ChromaDB Flat Indexing Example
======================================
5 financial documents → embed → ChromaDB collection → search
"""

import numpy as np
import chromadb

# ── 1. Documents ──────────────────────────────────────────────────────────────
DOCS = [
    {"id": "doc_0", "text": "FY2024 revenue was $12.6M, growing 23% year-over-year. Q4 alone hit $4.2M."},
    {"id": "doc_1", "text": "Engineering achieved 99.98% uptime and reduced API latency by 38% in Q1 2024."},
    {"id": "doc_2", "text": "Acme Corp SaaS contract: $450,000 over 36 months. 99.9% uptime SLA guaranteed."},
    {"id": "doc_3", "text": "Invoice: DigitalOcean $3.68, AWS $16,000, Bio Gen X $6,600 — all paid Q1 2024."},
    {"id": "doc_4", "text": "HR policy: salary bands $75K–$450K. Parental leave 16 weeks fully paid."},
]

DIM = 128   # embedding dimension (use 1536 for OpenAI in production)

# ── 2. Fake embeddings (replace with real OpenAI / BGE in production) ─────────
def embed(texts):
    vecs = []
    for t in texts:
        rng = np.random.default_rng(seed=abs(hash(t)) % (2**31))
        v   = rng.standard_normal(DIM).astype(np.float32)
        vecs.append((v / np.linalg.norm(v)).tolist())
    return vecs

# ── 3. Build ChromaDB flat index ──────────────────────────────────────────────
# ChromaDB uses HNSW internally, but setting high ef values makes it
# behave like a near-flat (exhaustive) index — maximum recall.
client = chromadb.Client()   # in-memory; use PersistentClient for disk storage

collection = client.create_collection(
    name="financial_docs",
    metadata={
        "hnsw:space"           : "cosine",   # similarity metric
        "hnsw:construction_ef" : 400,        # high = near-flat graph quality
        "hnsw:M"               : 64,         # high connectivity = better recall
        "hnsw:search_ef"       : 400,        # high = near-exhaustive search
    }
)

# Step 1: Add documents with embeddings and metadata
collection.add(
    ids        = [d["id"]   for d in DOCS],
    embeddings = embed([d["text"] for d in DOCS]),
    documents  = [d["text"] for d in DOCS],
    metadatas  = [{"source": "finance", "year": 2024} for _ in DOCS],
)

print(f"Collection built — {collection.count()} documents indexed\n")

# ── 4. Search ─────────────────────────────────────────────────────────────────
QUERIES = [
    "What was the annual revenue growth?",
    "Tell me about API performance improvements.",
    "What are the contract payment terms?",
    "Which vendor invoices were paid?",
    "What is the parental leave policy?",
]

print("=" * 55)
print("Search Results")
print("=" * 55)

query_vecs = embed(QUERIES)
results    = collection.query(
    query_embeddings = query_vecs,
    n_results        = 2,
    include          = ["documents", "distances"],
)

for q, docs, dists in zip(QUERIES, results["documents"], results["distances"]):
    print(f"\nQuery : {q}")
    for rank, (doc, dist) in enumerate(zip(docs, dists), 1):
        similarity = round(1 - dist, 4)   # cosine distance → similarity
        print(f"  [{rank}] score={similarity:.4f} | {doc[:65]}...")

# ── 5. Metadata filter search ─────────────────────────────────────────────────
# print("\n" + "=" * 55)
# print("Metadata Filter Search")
# print("=" * 55)

# filtered = collection.query(
#     query_embeddings = [embed(["revenue financial performance"])[0]],
#     n_results        = 3,
#     where            = {"year": {"$eq": 2024}},   # filter by metadata
#     include          = ["documents", "distances"],
# )

# print("\nQuery: 'revenue financial performance' | filter: year=2024")
# for doc, dist in zip(filtered["documents"][0], filtered["distances"][0]):
#     print(f"  score={round(1-dist, 4):.4f} | {doc[:65]}...")

# # ── 6. Fetch by ID (no vector search) ─────────────────────────────────────────
# print("\n" + "=" * 55)
# print("Direct ID Fetch (no vector search)")
# print("=" * 55)

# fetched = collection.get(ids=["doc_0", "doc_2"], include=["documents"])
# for doc_id, doc in zip(fetched["ids"], fetched["documents"]):
#     print(f"  {doc_id}: {doc[:65]}...")

# # ── 7. Update a document ──────────────────────────────────────────────────────
# collection.update(
#     ids        = ["doc_0"],
#     documents  = ["FY2024 revenue $12.6M, 23% growth. FY2025 target: $16M+."],
#     embeddings = embed(["FY2024 revenue $12.6M, 23% growth. FY2025 target: $16M+."]),
# )
# print(f"\nUpdated doc_0. Collection count: {collection.count()}")

# # ── 8. Delete a document ──────────────────────────────────────────────────────
# collection.delete(ids=["doc_4"])
# print(f"Deleted doc_4.  Collection count: {collection.count()}")

# # ── 9. Persist to disk (swap Client → PersistentClient) ──────────────────────
# print("""
# To persist to disk, replace:
#   client = chromadb.Client()
# With:
#   client = chromadb.PersistentClient(path="./chroma_store")
# Data survives process restarts automatically.
# """)

# # ── 10. Cheat-sheet ───────────────────────────────────────────────────────────
# print("""
# ChromaDB Flat Index Cheat-Sheet
# ---------------------------------
# hnsw:space           cosine | l2 | ip
# hnsw:construction_ef Build quality. Higher = better recall, slower insert.
# hnsw:M               Graph edges per node. Higher = better recall, more RAM.
# hnsw:search_ef       Query quality. Higher = better recall, slower query.

# Key methods:
#   collection.add()    — insert documents + embeddings + metadata
#   collection.query()  — vector search (+ optional metadata where-filter)
#   collection.get()    — fetch by ID (no vector search)
#   collection.update() — update document text + embedding
#   collection.delete() — remove by ID or metadata filter
#   collection.count()  — number of documents in collection

# vs FAISS IVF-PQ:
#   ChromaDB  → built-in metadata filtering, persistence, simple API
#   FAISS     → lower-level, faster at huge scale, GPU support, IVF-PQ compression
# """)