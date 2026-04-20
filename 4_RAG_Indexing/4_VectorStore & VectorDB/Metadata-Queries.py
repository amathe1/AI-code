"""
Simple ChromaDB Metadata Queries
==================================
All ChromaDB where-clause operators with real examples.
"""

import numpy as np
import chromadb

# ── Setup ─────────────────────────────────────────────────────────────────────
# 🔹 🧠 What This Function Does

# 👉 Converts text → deterministic random vectors (embeddings)

# Same text → same vector
# Different text → different vector
# 🔹 📦 Code Breakdown
# def embed(texts):

# 👉 Input:

# texts = ["AI is powerful", "Revenue increased"]
# 🔹 Step 1: Create empty list
# vecs = []

# 👉 This will store embeddings

# 🔹 Step 2: Loop through each text
# for t in texts:
# 🔹 Step 3: Create deterministic random generator
# rng = np.random.default_rng(seed=abs(hash(t)) % (2**31))

# 👉 Important idea:

# hash(t) → converts text into a number
# seed = hash(t) → ensures same text → same random numbers
# Example:
# "AI is powerful" → seed = 12345
# "Revenue increased" → seed = 67890

# 👉 So vectors are:

# Random
# But repeatable ✅
# 🔹 Step 4: Generate random vector
# v = rng.standard_normal(DIM).astype(np.float32)

# 👉 Creates vector like:

# [0.12, -0.45, 0.78, ..., -0.21]   (DIM = 128)

# 👉 This simulates what real models (like embeddings) do

# 🔹 Step 5: Normalize vector
# v / np.linalg.norm(v)

# 👉 Converts vector to unit vector

# Why?

# Because:

# Cosine similarity works best with normalized vectors
# Magnitude becomes 1
# 🔹 Example:

# Before normalization:

# [3, 4]

# Norm:

# √(3² + 4²) = 5

# After normalization:

# [0.6, 0.8]
# 🔹 Step 6: Convert to list
# .tolist()

# 👉 Because:

# NumPy → Python list (for DB/storage)
# 🔹 Step 7: Append to result
# vecs.append(...)
# 🔹 Final Output
# return vecs
# 🔹 🧪 Full Example
# texts = ["AI is powerful", "AI is powerful"]
# Output:
# [
#  [0.12, -0.45, ..., 0.33],
#  [0.12, -0.45, ..., 0.33]   ✅ same vector
# ]
# Another example:
# texts = ["AI is powerful", "Finance report"]
# [
#  [0.12, -0.45, ..., 0.33],
#  [-0.88, 0.21, ..., -0.11]  ❌ different vector
# ]
DIM = 64

def embed(texts):
    vecs = []
    for t in texts:
        rng = np.random.default_rng(seed=abs(hash(t)) % (2**31))
        v   = rng.standard_normal(DIM).astype(np.float32)
        vecs.append((v / np.linalg.norm(v)).tolist())
    return vecs

DOCS = [
    {"id":"d1","text":"FY2024 revenue $12.6M, 23% growth.",         "meta":{"type":"report",  "dept":"finance",     "year":2024,"amount":12600000,"status":"approved"}},
    {"id":"d2","text":"API latency reduced 38%, 99.98% uptime.",     "meta":{"type":"report",  "dept":"engineering", "year":2024,"amount":0,       "status":"approved"}},
    {"id":"d3","text":"Acme SaaS contract $450K, 36 months.",        "meta":{"type":"contract","dept":"sales",       "year":2024,"amount":450000,  "status":"approved"}},
    {"id":"d4","text":"Invoices: AWS $16K, DigitalOcean $3.68.",     "meta":{"type":"invoice", "dept":"finance",     "year":2024,"amount":16004,   "status":"pending"}},
    {"id":"d5","text":"HR policy: salary $75K–$450K, 16wk leave.",   "meta":{"type":"report",  "dept":"hr",          "year":2024,"amount":0,       "status":"approved"}},
    {"id":"d6","text":"Q3 2023 sales pipeline $9.2M, 14 deals.",     "meta":{"type":"report",  "dept":"sales",       "year":2023,"amount":9200000, "status":"approved"}},
    {"id":"d7","text":"Marketing invoice rejected, overcharged 40%.", "meta":{"type":"invoice", "dept":"sales",       "year":2024,"amount":45000,   "status":"rejected"}},
    {"id":"d8","text":"GPU cluster contract $240K, 8x A100 GPUs.",   "meta":{"type":"contract","dept":"engineering", "year":2024,"amount":240000,  "status":"approved"}},
]

client     = chromadb.Client()
col        = client.create_collection("docs", metadata={"hnsw:space":"cosine"})
col.add(ids=[d["id"] for d in DOCS], embeddings=embed([d["text"] for d in DOCS]),
        documents=[d["text"] for d in DOCS], metadatas=[d["meta"] for d in DOCS])

Q = embed(["financial documents"])[0]   # single query vector reused throughout

def show(label, r):
    print(f"\n  {label}")
    if not r["ids"][0]:
        print("    (no results)")
        return
    for id_, doc, meta in zip(r["ids"][0], r["documents"][0], r["metadatas"][0]):
        print(f"    {id_} | {meta['type']:<8} {meta['dept']:<12} ${meta['amount']:>10,} | {doc[:50]}...")

print("=" * 60)
print("  ChromaDB Metadata Query Examples")
print("=" * 60)

# 1 ── Equality  $eq ──────────────────────────────────────────────────────────
show("1. $eq — type = 'invoice'",
     col.query(query_embeddings=[Q], n_results=5,
               where={"type": {"$eq": "invoice"}},
               include=["documents","metadatas"]))

# 2 ── Not equal  $ne ─────────────────────────────────────────────────────────
show("2. $ne — status != 'approved'",
     col.query(query_embeddings=[Q], n_results=5,
               where={"status": {"$ne": "approved"}},
               include=["documents","metadatas"]))

# 3 ── Greater than  $gt ──────────────────────────────────────────────────────
show("3. $gt — amount > 100,000",
     col.query(query_embeddings=[Q], n_results=5,
               where={"amount": {"$gt": 100000}},
               include=["documents","metadatas"]))

# 4 ── Less than  $lt ─────────────────────────────────────────────────────────
show("4. $lt — amount < 50,000",
     col.query(query_embeddings=[Q], n_results=5,
               where={"amount": {"$lt": 50000}},
               include=["documents","metadatas"]))

# 5 ── Range  $gte + $lte ─────────────────────────────────────────────────────
show("5. $gte + $lte — 10,000 <= amount <= 500,000",
     col.query(query_embeddings=[Q], n_results=5,
               where={"$and": [{"amount": {"$gte": 10000}},
                               {"amount": {"$lte": 500000}}]},
               include=["documents","metadatas"]))

# 6 ── AND ─────────────────────────────────────────────────────────────────────
show("6. $and — dept='finance' AND status='approved'",
     col.query(query_embeddings=[Q], n_results=5,
               where={"$and": [{"dept":   {"$eq": "finance"}},
                               {"status": {"$eq": "approved"}}]},
               include=["documents","metadatas"]))

# 7 ── OR ──────────────────────────────────────────────────────────────────────
show("7. $or — type='contract' OR type='invoice'",
     col.query(query_embeddings=[Q], n_results=5,
               where={"$or": [{"type": {"$eq": "contract"}},
                              {"type": {"$eq": "invoice"}}]},
               include=["documents","metadatas"]))

# 8 ── IN ──────────────────────────────────────────────────────────────────────
show("8. $in — dept in ['finance', 'hr']",
     col.query(query_embeddings=[Q], n_results=5,
               where={"dept": {"$in": ["finance", "hr"]}},
               include=["documents","metadatas"]))

# 9 ── NOT IN  $nin ───────────────────────────────────────────────────────────
show("9. $nin — dept not in ['sales', 'hr']",
     col.query(query_embeddings=[Q], n_results=5,
               where={"dept": {"$nin": ["sales", "hr"]}},
               include=["documents","metadatas"]))

# 10 ── Year filter ────────────────────────────────────────────────────────────
show("10. year = 2023 (older docs)",
     col.query(query_embeddings=[Q], n_results=5,
               where={"year": {"$eq": 2023}},
               include=["documents","metadatas"]))

# 11 ── get() by ID — no vector search ────────────────────────────────────────
print("\n  11. get() by ID — no vector search needed")
r = col.get(ids=["d1","d3"], include=["documents","metadatas"])
for id_, doc, meta in zip(r["ids"], r["documents"], r["metadatas"]):
    print(f"    {id_} | {meta['type']:<8} | {doc[:50]}...")

# 12 ── get() by metadata — no vector search ───────────────────────────────────
print("\n  12. get() by metadata filter — fetch all rejected")
r = col.get(where={"status": {"$eq": "rejected"}}, include=["documents","metadatas"])
for id_, doc, meta in zip(r["ids"], r["documents"], r["metadatas"]):
    print(f"    {id_} | {meta['status']:<8} | {doc[:50]}...")

print(f"""
Operators : $eq  $ne  $gt  $gte  $lt  $lte  $in  $nin  $and  $or
Search    : col.query(where={{...}})   — vector search + filter
Fetch     : col.get(where={{...}})    — metadata-only, no vector needed
""")