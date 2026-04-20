"""
Simple FAISS IVF-PQ Example
============================
5 financial documents → chunk → embed → IVF-PQ index → search
"""

import numpy as np
import faiss

# ── 1. Documents ──────────────────────────────────────────────────────────────
DOCS = [
    {"id": 0, "text": "FY2024 revenue was $12.6M, growing 23% year-over-year. Q4 alone hit $4.2M."},
    {"id": 1, "text": "Engineering achieved 99.98% uptime and reduced API latency by 38% in Q1 2024."},
    {"id": 2, "text": "Acme Corp SaaS contract: $450,000 over 36 months. 99.9% uptime SLA guaranteed."},
    {"id": 3, "text": "Invoice: DigitalOcean $3.68, AWS $16,000, Bio Gen X $6,600 — all paid Q1 2024."},
    {"id": 4, "text": "HR policy: salary bands $75K–$450K. Parental leave 16 weeks fully paid."},
]

DIM      = 128   # embedding dimension (use 1536 for OpenAI in production)
N        = len(DOCS)
NLIST    = 2     # Voronoi cells  — rule: sqrt(N), minimum 2
M_PQ     = 16    # sub-quantizers — DIM must be divisible by M_PQ
NBITS    = 8     # bits per code  — 2^8 = 256 centroids per sub-quantizer
NPROBE   = 2     # cells to search at query time (= NLIST → exhaustive)

# ── 2. Fake embeddings (replace with real OpenAI / BGE in production) ─────────
def embed(texts):
    vecs = []
    for t in texts:
        rng = np.random.default_rng(seed=abs(hash(t)) % (2**31))
        v   = rng.standard_normal(DIM).astype(np.float32)
        vecs.append(v / np.linalg.norm(v))   # L2-normalise → cosine similarity
    return np.array(vecs)

doc_vecs = embed([d["text"] for d in DOCS])

# IVF-PQ training needs at least 2^nbits samples per sub-quantizer (=256).
# Our 5 docs are too few, so we pad with noise for training only.
# In production with 10K+ real vectors this padding is never needed.
MIN_TRAIN = 2 ** NBITS   # = 256
if N < MIN_TRAIN:
    rng   = np.random.default_rng(99)
    noise = rng.standard_normal((MIN_TRAIN - N, DIM)).astype(np.float32)
    noise /= np.linalg.norm(noise, axis=1, keepdims=True)
    train_data = np.vstack([doc_vecs, noise])
else:
    train_data = doc_vecs

# ── 3. Build IVF-PQ index ────────────────────────────────────────────────────
#   IndexFlatIP  → quantizer that assigns vectors to Voronoi cells
#   IndexIVFPQ   → compressed approximate search on top
quantizer = faiss.IndexFlatIP(DIM)
index     = faiss.IndexIVFPQ(
    quantizer,
    DIM,
    NLIST,       # number of Voronoi cells
    M_PQ,        # sub-quantizers (controls recall vs RAM)
    NBITS,       # bits per code  (8 = standard)
    faiss.METRIC_INNER_PRODUCT,
)
index.nprobe = NPROBE

# Step 1: Train — learns cluster centroids + PQ codebook
index.train(train_data)

# Step 2: Add — compresses and stores our 5 real documents
index.add(doc_vecs)

print(f"Index built — {index.ntotal} vectors stored")
print(f"Compression: {DIM * 4}B per vector (float32) → {M_PQ}B per vector (IVF-PQ)")
print(f"Ratio      : {DIM * 4 // M_PQ}x smaller\n")

# ── 4. Search ─────────────────────────────────────────────────────────────────
QUERIES = [
    "What was the annual revenue growth?",
    "Tell me about API performance improvements.",
    "What are the contract payment terms?",
    "Which vendor invoices were paid?",
    "What is the parental leave policy?",
]

query_vecs = embed(QUERIES)

print("=" * 55)
print("Search Results")
print("=" * 55)

scores, indices = index.search(query_vecs, k=2)   # top-2 results

for q, score_row, idx_row in zip(QUERIES, scores, indices):
    print(f"\nQuery : {q}")
    for rank, (score, idx) in enumerate(zip(score_row, idx_row), 1):
        if idx == -1:
            continue
        print(f"  [{rank}] score={score:.4f} | {DOCS[idx]['text'][:65]}...")

# ── 5. Save and reload ────────────────────────────────────────────────────────
faiss.write_index(index, "C:\\Personal\\2024\\Learning\\Generative AI\\RAG\\27_Context_Engineering\\2_RAG\\4_VectorStore & VectorDB\\ivfpq.faiss")
loaded = faiss.read_index("C:\\Personal\\2024\\Learning\\Generative AI\\RAG\\27_Context_Engineering\\2_RAG\\4_VectorStore & VectorDB\\ivfpq.faiss")
loaded.nprobe = NPROBE
print(f"\nSaved & reloaded — vectors: {loaded.ntotal}")

# ── 6. Key parameters cheat-sheet ─────────────────────────────────────────────
print("""
IVF-PQ Parameter Guide
-----------------------
nlist  : Voronoi cells. Rule: sqrt(N). More = better quality, slower train.
M_pq   : Sub-quantizers. Rule: DIM // 16. DIM must be divisible by M_pq.
nbits  : Bits per code. 8 = standard (256 centroids). 4 = aggressive compress.
nprobe : Cells searched per query. Higher = better recall, higher latency.
         nprobe == nlist means exhaustive (same recall as FlatIP).

Memory  : N * M_pq bytes   vs   N * DIM * 4 bytes (float32)
Example : 1M vecs, DIM=1536, M_pq=96 → 96MB vs 6,144MB (64x smaller)

When to use IVF-PQ:
  > 500K vectors, GPU available, or RAM is constrained.
  For < 100K vectors use IndexFlatIP — it is simpler and exact.
""")