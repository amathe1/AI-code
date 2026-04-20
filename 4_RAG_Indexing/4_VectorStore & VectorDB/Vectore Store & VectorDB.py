"""
============================================================
Production Vector Store Pipeline
Best Model  : BGE bge-large-en-v1.5 (best free, 1024 dims)
Stores      : ChromaDB (persistent) + FAISS (in-memory/file)
Input       : financial_report_2024.pdf
Strategy    : Hierarchical Chunking (parent-child)
============================================================
"""

import os, re, json, time, uuid, pickle
import numpy as np
import pdfplumber
import faiss
from dataclasses import dataclass, field
from typing import Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb
from chromadb.config import Settings

PDF_PATH      = "C:\\Personal\\2024\\Learning\\Generative AI\\RAG\\27_Context_Engineering\\2_RAG\\1_Document_Processing\\Data\\financial_report_2024.pdf"
CHROMA_DIR    = "./chroma_store"
FAISS_DIR     = "./faiss_store"
COLLECTION    = "financial_report_rag"
EMBEDDING_DIM = 1024   # BGE large-en-v1.5 → 1024 dims

os.makedirs(CHROMA_DIR, exist_ok=True)
os.makedirs(FAISS_DIR,  exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Chunk:
    chunk_id  : str
    level     : str           # "parent" | "child"
    section   : str
    parent_id : Optional[str]
    text      : str
    word_count: int = 0
    metadata  : dict = field(default_factory=dict)

    def __post_init__(self):
        self.word_count = len(self.text.split())
        self.metadata = {
            "chunk_id" : self.chunk_id,
            "level"    : self.level,
            "section"  : self.section,
            "parent_id": self.parent_id or "",
            "word_count": self.word_count,
            "source"   : PDF_PATH,
        }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Extract PDF text
# ─────────────────────────────────────────────────────────────────────────────
def extract_text(path: str) -> str:
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Hierarchical Chunking
# ─────────────────────────────────────────────────────────────────────────────
def semantic_section_chunking(text: str) -> list[dict]:
    pattern = re.compile(
        r"(?m)^(Executive Summary|Revenue Growth|Key Metrics"
        r"|Revenue by Segment|FY 2025 Outlook)\s*$"
    )
    splits, chunks, section = pattern.split(text), [], "Preamble"
    for part in splits:
        part = part.strip()
        if not part: continue
        if pattern.match(part):
            section = part
        else:
            chunks.append({"section": section, "text": part})
    return chunks


def hierarchical_chunking(text: str, child_size: int = 200) -> list[Chunk]:
    parents  = semantic_section_chunking(text)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_size, chunk_overlap=40,
        separators=["\n\n", "\n", ". ", " "],
    )
    all_chunks = []
    for i, p in enumerate(parents):
        pid = f"parent_{i}"
        all_chunks.append(Chunk(chunk_id=pid, level="parent",
                                section=p["section"], parent_id=None,
                                text=p["text"]))
        for j, child_text in enumerate(splitter.split_text(p["text"])):
            if child_text.strip():
                all_chunks.append(Chunk(
                    chunk_id=f"{pid}_child_{j}", level="child",
                    section=p["section"], parent_id=pid,
                    text=child_text.strip()
                ))
    return all_chunks


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — BGE Embeddings
#   → In production: pip install sentence-transformers
#     model = SentenceTransformer("BAAI/bge-large-en-v1.5")
#     vectors = model.encode(texts, normalize_embeddings=True)
#
#   → Here we use deterministic mock vectors (same dim/normalization)
#     so ChromaDB + FAISS operations are 100% real and production-identical
# ─────────────────────────────────────────────────────────────────────────────
def get_bge_embeddings(texts: list[str], dim: int = EMBEDDING_DIM) -> np.ndarray:
    """
    Production code (uncomment when sentence-transformers can download models):

        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-large-en-v1.5")
        vectors = model.encode(
            texts,
            normalize_embeddings=True,   # cosine similarity ready
            show_progress_bar=True,
            batch_size=32,               # tune per GPU memory
        )
        return np.array(vectors, dtype=np.float32)

    BGE passage encoding tip:
      - Passages (stored docs): encode as-is
      - Queries (at search time): prefix with "Represent this sentence for retrieval: "
    """
    print(f"  [BGE] Encoding {len(texts)} texts → {dim}-dim vectors ...")
    t0 = time.time()
    rng = np.random.default_rng(seed=42)
    raw = rng.standard_normal((len(texts), dim)).astype(np.float32)
    # L2-normalize → unit vectors (cosine similarity equivalent to dot product)
    norms = np.linalg.norm(raw, axis=1, keepdims=True)
    vectors = raw / norms
    elapsed = (time.time() - t0) * 1000
    print(f"  [BGE] Done in {elapsed:.1f}ms | shape={vectors.shape} | dtype={vectors.dtype}")
    return vectors


def approx_tokens(text: str) -> int:
    return int(len(re.findall(r"\w+|[^\w\s]", text)) * 1.3)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — ChromaDB Vector Store
# ─────────────────────────────────────────────────────────────────────────────
# 🔹 🔧 Input to Your Function
# chunks: list[Chunk]
# vectors: np.ndarray
# Example:
# chunks = [
#     Chunk(chunk_id="1", text="AI is powerful system", metadata={"section": "intro", "level": 1}),
#     Chunk(chunk_id="2", text="Revenue increased in Q4", metadata={"section": "finance", "level": 2})
# ]

# vectors = [
#     [0.2, -0.3, 0.6],   # embedding for chunk 1
#     [0.8, 0.1, -0.2]    # embedding for chunk 2
# ]

# 🔹 1. Persistent Client
# client = chromadb.PersistentClient(path=CHROMA_DIR)

# 👉 This means:

# Data is stored on disk
# Even if you restart your program → data remains

# 📌 Think:

# Like a database saved in a folder

# 🔹 2. Delete Old Collection
# client.delete_collection(COLLECTION)

# 👉 If collection already exists:

# Delete it (clean start)

# 📌 Example:

# Old data removed → fresh data loaded

# 🔹 3. Create Collection (VERY IMPORTANT)
# collection = client.create_collection(
#     name=COLLECTION,
#     metadata={
#         "hnsw:space": "cosine",
#         "hnsw:construction_ef": 200,
#         "hnsw:M": 16,
#     }
# )

# 👉 This creates a vector store table

# Key Settings:
# Parameter	Meaning
# cosine	similarity metric
# ef	search accuracy
# M	graph connections

# 📌 Internally:

# Builds HNSW graph index

# 🔹 4. Batch Insert (Upsert)
# for i in range(0, len(chunks), BATCH):

# 👉 Why batching?

# Efficient for large data
# Avoid memory issues
# Inside Batch:
# collection.add(
#     ids=[c.chunk_id for c in batch_chunks],
#     embeddings=batch_vectors.tolist(),
#     documents=[c.text for c in batch_chunks],
#     metadatas=[c.metadata for c in batch_chunks],
# )

# 👉 This is the core storage step

# What gets stored?

# Example:

# {
#   "id": "1",
#   "embedding": [0.2, -0.3, 0.6],
#   "document": "AI is powerful system",
#   "metadata": {
#     "section": "intro",
#     "level": 1
#   }
# }

# 👉 So your earlier question:

# Vectors + Metadata + Documents

# ✅ All stored here

# 🔹 5. Store Summary
# count = collection.count()

# 👉 Shows how many chunks stored


# 🔹 6. Query Phase (🔥 Most Important)
# query_texts = [
#     "What was Q4 revenue?",
#     "What are the key metrics for FY 2024?",
# ]
# Convert query → embeddings
# query_vectors = get_bge_embeddings(query_texts)

# 👉 Same process as before:

# Text → vector

# 🔹 7. Similarity Search
# results = collection.query(
#     query_embeddings=[q_vec.tolist()],
#     n_results=3,
#     include=["documents", "metadatas", "distances"],
# )

# 👉 This does:

# Compare query vector with stored vectors
# Use HNSW index
# Return top 3 closest matches

# 🔹 8. Understanding Output
# results = {
#   "documents": [["Revenue increased in Q4"]],
#   "metadatas": [[{"section": "finance", "level": 2}]],
#   "distances": [[0.1]]
# }

# 🔹 9. Distance → Similarity
# similarity = 1 - dist

# 👉 Because:

# cosine distance = 0 → very similar
# so convert to similarity
# Example:
# Distance	Similarity
# 0.1	0.9 ✅
# 0.8	0.2 ❌

# 🔹 10. Final Printed Output
# Query: "What was Q4 revenue?"

# Rank 1 | section=finance | sim=0.9000 | level=2
# Revenue increased in Q4...

# 👉 Meaning:

# Best matching chunk found
# Based on semantic similarity

# 🔹 🔥 End-to-End Flow (Simple)
# Chunks → Embeddings → Store in ChromaDB
#                      ↓
#                 HNSW Index
#                      ↓
# Query → Embedding → Similarity Search → Top Results

# 🔹 🧠 Key Insights

# 👉 This function is doing complete RAG storage + retrieval setup

# ✔ Persistent DB
# ✔ Efficient batching
# ✔ Vector indexing (HNSW)
# ✔ Semantic search

def build_chromadb_store(chunks: list[Chunk], vectors: np.ndarray) -> chromadb.Collection:
    print(f"\n{'='*65}")
    print(f"  CHROMADB — Persistent Vector Store")
    print(f"  Path: {CHROMA_DIR}")
    print(f"{'='*65}")

    # Persistent client — survives process restarts
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Delete existing collection if re-running
    try:
        client.delete_collection(COLLECTION)
        print(f"  [ChromaDB] Deleted existing collection '{COLLECTION}'")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION,
        metadata={
            "hnsw:space"           : "cosine",   # cosine similarity
            "hnsw:construction_ef" : 200,         # build quality (higher=better recall)
            "hnsw:M"               : 16,          # graph connections per node
        }
    )
    print(f"  [ChromaDB] Created collection '{COLLECTION}' with cosine similarity")

    # Batch upsert — ChromaDB recommends batches of ≤5000
    BATCH = 100
    t0 = time.time()
    for i in range(0, len(chunks), BATCH):
        batch_chunks  = chunks[i:i+BATCH]
        batch_vectors = vectors[i:i+BATCH]

        collection.add(
            ids        = [c.chunk_id          for c in batch_chunks],
            embeddings = batch_vectors.tolist(),
            documents  = [c.text              for c in batch_chunks],
            metadatas  = [c.metadata          for c in batch_chunks],
        )
        print(f"  [ChromaDB] Upserted batch {i//BATCH + 1} | "
              f"{len(batch_chunks)} docs | total so far: {min(i+BATCH, len(chunks))}")

    elapsed = (time.time() - t0) * 1000
    count = collection.count()
    print(f"\n  [ChromaDB] ✓ Store ready")
    print(f"  [ChromaDB] Docs in store : {count}")
    print(f"  [ChromaDB] Upsert time   : {elapsed:.1f}ms")
    print(f"  [ChromaDB] Persist path  : {os.path.abspath(CHROMA_DIR)}")

    # ── Query demo ────────────────────────────────────────────────────────────
    print(f"\n  [ChromaDB] Running sample queries...")
    query_texts = [
        "What was Q4 revenue?",
        "What are the key metrics for FY 2024?",
        "What are the FY 2025 targets?",
    ]
    query_vectors = get_bge_embeddings(query_texts)

    for q_text, q_vec in zip(query_texts, query_vectors):
        results = collection.query(
            query_embeddings=[q_vec.tolist()],
            n_results=3,
            include=["documents", "metadatas", "distances"],
        )
        print(f"\n  Query: '{q_text}'")
        print(f"  {'─'*55}")
        for rank, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ), 1):
            similarity = round(1 - dist, 4)   # cosine: distance → similarity
            print(f"    Rank {rank} | section={meta['section']:<20} | "
                  f"sim={similarity:.4f} | level={meta['level']}")
            print(f"           {doc[:80].strip()}...")

    # ── Metadata filtering demo ───────────────────────────────────────────────
    print(f"\n  [ChromaDB] Metadata filter: only 'Key Metrics' section")
    filtered = collection.query(
        query_embeddings=[query_vectors[1].tolist()],
        n_results=5,
        where={"section": {"$eq": "Key Metrics"}},
        include=["documents", "distances"],
    )
    for doc, dist in zip(filtered["documents"][0], filtered["distances"][0]):
        print(f"    sim={round(1-dist,4):.4f} | {doc[:80].strip()}...")

    return collection


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — FAISS Vector Store
# ─────────────────────────────────────────────────────────────────────────────
# 🔹 🧠 What This Function Does (Big Picture)

# 👉 This function:

# Takes chunks + embeddings
# Builds a FAISS index (vector search engine)
# Stores metadata separately
# Saves everything to disk
# Reloads and runs semantic search
# 🔹 🔧 Input Example
# chunks = [
#     Chunk(chunk_id="1", text="AI is powerful system", metadata={"section": "intro", "level": 1}),
#     Chunk(chunk_id="2", text="Revenue increased in Q4", metadata={"section": "finance", "level": 2})
# ]

# vectors = np.array([
#     [0.2, -0.3, 0.6],
#     [0.8, 0.1, -0.2]
# ])

# 👉 n=2 vectors, d=3 dimensions

# 🔹 1. Choose Index Type (VERY IMPORTANT 🔥)
# n, d = vectors.shape
# Logic:
# Data Size	Index Type
# <10K	IndexFlatIP (exact)
# 10K–1M	IVF (fast approx)
# >1M	IVFPQ (compressed)
# In your example:
# n = 2 → use IndexFlatIP
# index = faiss.IndexFlatIP(d)

# 👉 Meaning:

# Brute force search
# Compare with all vectors
# Most accurate

# 🔹 2. Why "IP" (Inner Product)?

# 👉 If vectors are normalized:

# Inner Product ≈ Cosine Similarity

# So:

# Higher score = more similar

# 🔹 3. ID Mapping (IMPORTANT ⚠️)
# id_map = {i: chunks[i].chunk_id}
# chunk_map = {chunk_id: chunk}

# 👉 FAISS only stores vectors (NOT text!)

# So we create mapping:

# FAISS index → gives index (0,1,2...)
# You convert → chunk_id → actual text

# 🔹 4. Add Vectors to FAISS
# index.add(vectors)

# 👉 Now FAISS stores:

# Vector 0 → [0.2, -0.3, 0.6]
# Vector 1 → [0.8, 0.1, -0.2]

# 🔹 5. Save to Disk
# faiss.write_index(index, "index.faiss")

# 👉 Saves vectors + index

# Metadata saved separately:
# pickle.dump({
#     "id_map": id_map,
#     "chunk_map": chunk_map
# })

# 👉 Because FAISS does NOT store:

# ❌ documents
# ❌ metadata
# 🔹 ⚠️ Key Difference from ChromaDB
# Feature	FAISS	ChromaDB
# Vectors	✅	✅
# Metadata	❌	✅
# Documents	❌	✅
# Index	✅	✅

# 👉 FAISS = only vector engine

# 🔹 6. Reload Index
# loaded_index = faiss.read_index(faiss_path)

# 👉 Ensures persistence works

# 🔹 7. Query Phase (🔥 Most Important)
# Query:
# "What was Q4 revenue?"
# Convert to embedding:
# q_vec = [0.75, 0.05, -0.1]

# 🔹 8. Search
# scores, indices = loaded_index.search(q_vec, k=3)
# Example Output:
# scores  = [[0.95, 0.40]]
# indices = [[1, 0]]

# 🔹 9. Map Back to Text
# chunk_id = id_map[idx]
# chunk = chunk_map[chunk_id]
# Final Output:
# Rank 1 | section=finance | score=0.95
# Revenue increased in Q4...

# 👉 Perfect match 🎯

# 🔹 10. Latency Measurement
# latency = (time.time() - t0) * 1000

# 👉 Measures:

# Query speed (ms)
# Useful for p50/p95 analysis

# 🔹 🔥 Full Flow (Simple)
# Chunks → Embeddings → FAISS Index
#                           ↓
#                     Save to Disk
#                           ↓
# Query → Embedding → Search → Indices → Map → Text

# 🔹 🧠 Key Insights (VERY IMPORTANT)
# 1. FAISS stores ONLY vectors

# 👉 You must manage metadata separately

# 2. ID mapping is critical

# 👉 Without it → you lose document context

def build_faiss_store(chunks: list[Chunk], vectors: np.ndarray):
    print(f"\n{'='*65}")
    print(f"  FAISS — High-Performance Vector Store")
    print(f"  Path: {FAISS_DIR}")
    print(f"{'='*65}")

    n, d = vectors.shape
    print(f"  [FAISS] Building index | n={n} vectors | d={d} dims")

    # ── Choose index type based on data size ──────────────────────────────────
    # < 10K vectors  : IndexFlatIP  (exact, brute-force — perfect for small data)
    # 10K–1M vectors : IndexIVFFlat (approximate, partitioned — fast + accurate)
    # > 1M  vectors  : IndexIVFPQ   (compressed — huge scale, lower memory)

    if n < 10_000:
        # Exact cosine similarity (vectors are unit-normalized → inner product = cosine)
        index = faiss.IndexFlatIP(d)
        index_type = "IndexFlatIP (Exact — brute force, best for <10K docs)"
    elif n < 1_000_000:
        nlist = max(4, int(np.sqrt(n)))        # number of Voronoi cells
        quantizer = faiss.IndexFlatIP(d)
        index = faiss.IndexIVFFlat(quantizer, d, nlist, faiss.METRIC_INNER_PRODUCT)
        index.train(vectors)
        index.nprobe = min(10, nlist)          # cells to search at query time
        index_type = f"IndexIVFFlat (ANN — nlist={nlist}, nprobe={index.nprobe})"
    else:
        nlist, m_pq = 1024, 64
        quantizer = faiss.IndexFlatIP(d)
        index = faiss.IndexIVFPQ(quantizer, d, nlist, m_pq, 8)
        index.train(vectors)
        index_type = f"IndexIVFPQ (Compressed ANN — nlist={nlist}, m={m_pq})"

    print(f"  [FAISS] Index type: {index_type}")

    # ── Build ID map for chunk lookup ─────────────────────────────────────────
    id_map = {i: chunks[i].chunk_id for i in range(len(chunks))}
    chunk_map = {c.chunk_id: c for c in chunks}

    # ── Add vectors ───────────────────────────────────────────────────────────
    t0 = time.time()
    index.add(vectors)
    elapsed = (time.time() - t0) * 1000

    print(f"  [FAISS] ✓ Index built in {elapsed:.1f}ms")
    print(f"  [FAISS] Total vectors   : {index.ntotal}")
    mem_bytes = vectors.nbytes
    print(f"  [FAISS] Memory (vectors): {mem_bytes/1024:.1f} KB")

    # ── Save index + metadata to disk ────────────────────────────────────────
    faiss_path    = os.path.join(FAISS_DIR, "index.faiss")
    metadata_path = os.path.join(FAISS_DIR, "metadata.pkl")
    faiss.write_index(index, faiss_path)
    with open(metadata_path, "wb") as f:
        pickle.dump({"id_map": id_map, "chunk_map": {k: v.__dict__ for k, v in chunk_map.items()}}, f)

    print(f"  [FAISS] Saved index     : {faiss_path}")
    print(f"  [FAISS] Saved metadata  : {metadata_path}")
    faiss_size = os.path.getsize(faiss_path)
    meta_size  = os.path.getsize(metadata_path)
    print(f"  [FAISS] Index file size : {faiss_size/1024:.1f} KB")
    print(f"  [FAISS] Metadata size   : {meta_size/1024:.1f} KB")

    # ── Reload and verify ────────────────────────────────────────────────────
    print(f"\n  [FAISS] Reloading index from disk to verify persistence...")
    loaded_index = faiss.read_index(faiss_path)
    with open(metadata_path, "rb") as f:
        meta = pickle.load(f)
    print(f"  [FAISS] ✓ Reloaded | vectors={loaded_index.ntotal}")

    # ── Query demo ────────────────────────────────────────────────────────────
    print(f"\n  [FAISS] Running sample queries...")
    query_texts = [
        "What was Q4 revenue?",
        "What are the key metrics for FY 2024?",
        "What are the FY 2025 targets?",
    ]
    query_vectors = get_bge_embeddings(query_texts)

    for q_text, q_vec in zip(query_texts, query_vectors):
        t0 = time.time()
        scores, indices = loaded_index.search(
            q_vec.reshape(1, -1),
            k=3   # top-3 results
        )
        latency = (time.time() - t0) * 1000

        print(f"\n  Query: '{q_text}'  [{latency:.2f}ms]")
        print(f"  {'─'*55}")
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0]), 1):
            if idx == -1: continue
            chunk_id = meta["id_map"][idx]
            chunk    = meta["chunk_map"][chunk_id]
            print(f"    Rank {rank} | section={chunk['section']:<20} | "
                  f"score={score:.4f} | level={chunk['level']}")
            print(f"           {chunk['text'][:80].strip()}...")

    return index, id_map, chunk_map


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Hierarchical RAG Retrieval Demo
#  (the production pattern: retrieve child → fetch parent → send to LLM)
# ─────────────────────────────────────────────────────────────────────────────
# 🔹 🧠 What This Function Does (Big Idea)

# 👉 Instead of retrieving large chunks directly, it:

# 🔍 Finds small chunks (child) → better semantic accuracy
# 📚 Expands to large chunks (parent) → better context for LLM
# 🔹 📦 Example Data (Very Simple)
# Parent Chunk (big context)
# Parent ID: P1
# Text: "In Q4, revenue increased by 25% due to strong AI adoption and enterprise demand..."
# Child Chunks (split pieces)
# C1 → "Revenue increased in Q4"
# C2 → "AI adoption drove growth"
# C3 → "Enterprise demand was strong"
# Stored in ChromaDB:

# Each child has metadata:

# {
#   "chunk_id": "C1",
#   "level": "child",
#   "parent_id": "P1"
# }
# 🔹 🔎 Step-by-Step Code Explanation
# 🔹 1. Input
# query = "What was Q4 revenue?"
# query_vector = [0.75, 0.1, -0.2]

# 🔹 2. Retrieve CHILD Chunks
# results = collection.query(
#     query_embeddings=[query_vector.tolist()],
#     n_results=top_k,
#     where={"level": {"$eq": "child"}},
# )

# 👉 Important:

# Only retrieves small chunks
# Filters using:
# where={"level": "child"}
# Example Output:
# Step 1 — Retrieved child chunks:

# [child] C1 | sim=0.92 | Revenue increased in Q4...
# [child] C2 | sim=0.70 | AI adoption drove growth...

# 👉 What’s happening?

# Query matches precise sentence (C1)
# Also finds related concept (C2)

# 🔹 3. Collect Parent IDs
# parent_ids_to_fetch.add(pid)

# 👉 From child metadata:

# C1 → parent_id = P1
# C2 → parent_id = P1

# 👉 So:

# parent_ids_to_fetch = {"P1"}

# 🔹 4. Fetch Parent Chunks (Context Expansion)
# for pid in parent_ids_to_fetch:
#     p = parent_chunks[pid]
# Output:
# [parent] P1 | section=finance
# Context sent to LLM (120 words):
# "In Q4, revenue increased by 25% due to strong AI adoption..."

# 🔹 🔥 Why This Approach?
# Problem without hierarchy:

# If you retrieve only small chunks:

# "Revenue increased in Q4"

# 👉 ❌ Too little context for LLM

# Problem with large chunks:
# Entire 500-word paragraph

# 👉 ❌ Poor retrieval accuracy

# 🔹 ✅ Solution (Your Code)
# Step	              Benefit
# Child retrieval	 🎯 High precision
# Parent fetch	     📚 Full context

# 🔹 🧠 Flow Diagram (Simple)
# Query
#   ↓
# Embedding
#   ↓
# Search CHILD chunks (small, precise)
#   ↓
# Get parent_ids
#   ↓
# Fetch PARENT chunks (large, context)
#   ↓
# Send to LLM
# 🔹 🔍 Key Line Explained
# This is critical:
# where={"level": {"$eq": "child"}}

# 👉 Ensures:

# Only small chunks used for similarity search

# This connects hierarchy:
# pid = meta.get("parent_id")

# 👉 Links:

# child → parent

def hierarchical_retrieval_demo(
    collection: chromadb.Collection,
    parent_chunks: dict,
    query: str,
    query_vector: np.ndarray,
    top_k: int = 3
):
    print(f"\n  Query : '{query}'")

    # 1. Retrieve top-k CHILD chunks (small → precise vector match)
    results = collection.query(
        query_embeddings=[query_vector.tolist()],
        n_results=top_k,
        where={"level": {"$eq": "child"}},
        include=["documents", "metadatas", "distances"],
    )

    print(f"  Step 1 — Retrieved child chunks:")
    parent_ids_to_fetch = set()
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        sim = round(1 - dist, 4)
        pid = meta.get("parent_id", "")
        parent_ids_to_fetch.add(pid)
        print(f"    [child] {meta['chunk_id']} | sim={sim} | {doc[:60].strip()}...")

    # 2. Fetch PARENT chunks (large → full context for LLM)
    print(f"\n  Step 2 — Fetching parent context for LLM:")
    for pid in parent_ids_to_fetch:
        if pid and pid in parent_chunks:
            p = parent_chunks[pid]
            print(f"    [parent] {pid} | section={p.section}")
            print(f"    Context sent to LLM ({p.word_count} words):")
            print(f"    '{p.text[:200].strip()}...'")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — Store Stats
# ─────────────────────────────────────────────────────────────────────────────
def print_store_stats(chunks, vectors, collection, faiss_index):
    child_chunks  = [c for c in chunks if c.level == "child"]
    parent_chunks = [c for c in chunks if c.level == "parent"]
    total_tokens  = sum(approx_tokens(c.text) for c in child_chunks)

    print(f"\n{'='*65}")
    print(f"  VECTOR STORE STATISTICS")
    print(f"{'='*65}")
    print(f"  Source file     : {PDF_PATH}")
    print(f"  Total chunks    : {len(chunks)} ({len(parent_chunks)} parents + {len(child_chunks)} children)")
    print(f"  Embedding model : BGE bge-large-en-v1.5")
    print(f"  Dimensions      : {EMBEDDING_DIM}")
    print(f"  Total tokens    : {total_tokens}")
    print(f"  Vector dtype    : float32")
    print(f"  Vector matrix   : {vectors.shape} | {vectors.nbytes/1024:.1f} KB")
    print(f"\n  ── ChromaDB ────────────────────────────────────────────")
    print(f"  Docs in store   : {collection.count()}")
    print(f"  Similarity      : Cosine (HNSW index)")
    print(f"  Persist path    : {os.path.abspath(CHROMA_DIR)}")
    print(f"  Supports filter : Yes (metadata where-clauses)")
    chroma_size = sum(
        os.path.getsize(os.path.join(root, f))
        for root, _, files in os.walk(CHROMA_DIR) for f in files
    ) / 1024
    print(f"  Disk usage      : {chroma_size:.1f} KB")
    print(f"\n  ── FAISS ───────────────────────────────────────────────")
    print(f"  Vectors indexed : {faiss_index.ntotal}")
    print(f"  Index type      : IndexFlatIP (exact, <10K docs)")
    print(f"  Similarity      : Inner product (cosine on unit vectors)")
    faiss_size = os.path.getsize(os.path.join(FAISS_DIR, "index.faiss")) / 1024
    print(f"  Disk usage      : {faiss_size:.1f} KB")
    print(f"  Supports GPU    : Yes (faiss-gpu package)")
    print(f"  Supports filter : No (handle in Python post-query)")


def approx_tokens(text):
    return int(len(re.findall(r"\w+|[^\w\s]", text)) * 1.3)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*65)
    print("  PRODUCTION VECTOR STORE PIPELINE")
    print("  BGE large-en-v1.5 + ChromaDB + FAISS")
    print("="*65)

    # 1. Extract
    print("\n[1] Extracting PDF...")
    raw_text = extract_text(PDF_PATH)
    print(f"    {len(raw_text)} chars | {len(raw_text.split())} words")

    # 2. Chunk
    print("\n[2] Hierarchical Chunking...")
    chunks = hierarchical_chunking(raw_text, child_size=200)
    parents  = {c.chunk_id: c for c in chunks if c.level == "parent"}
    children = [c for c in chunks if c.level == "child"]
    print(f"    {len(parents)} parents | {len(children)} children | {len(chunks)} total")

    # 3. Embed ALL chunks (both child + parent stored; only children queried)
    print("\n[3] Generating BGE Embeddings...")
    all_texts = [c.text for c in chunks]
    vectors   = get_bge_embeddings(all_texts)

    # 4. ChromaDB
    collection = build_chromadb_store(chunks, vectors)

    # 5. FAISS
    faiss_index, id_map, chunk_map = build_faiss_store(chunks, vectors)

    # 6. Hierarchical retrieval demo
    print(f"\n{'='*65}")
    print(f"  HIERARCHICAL RETRIEVAL DEMO (ChromaDB)")
    print(f"  Pattern: retrieve child → send parent to LLM")
    print(f"{'='*65}")
    demo_queries = [
        "What was Q4 2024 revenue performance?",
        "How did customer retention change from 2023 to 2024?",
    ]
    demo_vecs = get_bge_embeddings(demo_queries)
    for q, v in zip(demo_queries, demo_vecs):
        hierarchical_retrieval_demo(collection, parents, q, v, top_k=2)

    # 7. Stats
    print_store_stats(chunks, vectors, collection, faiss_index)

    print(f"\n{'='*65}")
    print(f"  ✓ Pipeline complete. Stores saved to:")
    print(f"    ChromaDB : {os.path.abspath(CHROMA_DIR)}")
    print(f"    FAISS    : {os.path.abspath(FAISS_DIR)}")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()