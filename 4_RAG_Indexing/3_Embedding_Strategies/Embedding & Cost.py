"""
============================================================
Production RAG Embeddings — Strategy 8: Hierarchical Chunking
Input : financial_report_2024.pdf
Models: OpenAI text-embedding-3-small / text-embedding-3-large
        HuggingFace all-MiniLM-L6-v2
        BGE BAAI/bge-large-en-v1.5
============================================================
"""

import re
import json, os
import time
import pdfplumber
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.1        # Low temp for deterministic zero-shot
    
)

PDF_PATH   = "D:\GenAI Content\\AI code\\4_RAG_Indexing\\1_Document_Processing\\Data\\financial_report_2024.pdf"
       # ← replace with real key

# ─────────────────────────────────────────────────────────────────────────────
# MODEL REGISTRY  (accurate as of April 2026)
# ─────────────────────────────────────────────────────────────────────────────
EMBEDDING_MODELS = {
    # ── OpenAI ──────────────────────────────────────────────────────────────
    "openai/text-embedding-3-small": {
        "provider"       : "OpenAI",
        "dimensions"     : 1536,
        "max_tokens"     : 8191,
        "cost_per_1k_tok": 0.00002,        # $0.020 per 1M tokens
        "speed"          : "Fast (API)",
        "quality"        : "★★★★☆",
        "best_for"       : "Cost-efficient production RAG",
        "requires_api"   : True,
    },
    "openai/text-embedding-3-large": {
        "provider"       : "OpenAI",
        "dimensions"     : 3072,
        "max_tokens"     : 8191,
        "cost_per_1k_tok": 0.00013,        # $0.130 per 1M tokens
        "speed"          : "Medium (API)",
        "quality"        : "★★★★★",
        "best_for"       : "High-accuracy retrieval, legal/financial docs",
        "requires_api"   : True,
    },
    # ── HuggingFace ──────────────────────────────────────────────────────────
    "huggingface/all-MiniLM-L6-v2": {
        "provider"       : "HuggingFace",
        "dimensions"     : 384,
        "max_tokens"     : 512,
        "cost_per_1k_tok": 0.0,            # Free, runs locally
        "speed"          : "Very Fast (local CPU/GPU)",
        "quality"        : "★★★☆☆",
        "best_for"       : "Lightweight, free local embeddings",
        "requires_api"   : False,
    },
    "huggingface/all-mpnet-base-v2": {
        "provider"       : "HuggingFace",
        "dimensions"     : 768,
        "max_tokens"     : 514,
        "cost_per_1k_tok": 0.0,
        "speed"          : "Fast (local CPU/GPU)",
        "quality"        : "★★★★☆",
        "best_for"       : "Higher quality free local embeddings",
        "requires_api"   : False,
    },
    # ── BGE (Beijing Academy of AI) ──────────────────────────────────────────
    "bge/bge-small-en-v1.5": {
        "provider"       : "BGE (BAAI)",
        "dimensions"     : 384,
        "max_tokens"     : 512,
        "cost_per_1k_tok": 0.0,
        "speed"          : "Very Fast (local)",
        "quality"        : "★★★★☆",
        "best_for"       : "Best free small model; beats MiniLM on MTEB",
        "requires_api"   : False,
    },
    "bge/bge-large-en-v1.5": {
        "provider"       : "BGE (BAAI)",
        "dimensions"     : 1024,
        "max_tokens"     : 512,
        "cost_per_1k_tok": 0.0,
        "speed"          : "Medium (local GPU recommended)",
        "quality"        : "★★★★★",
        "best_for"       : "Best open-source model; near OpenAI quality",
        "requires_api"   : False,
    },
}

"""
Data classes module is a python built-in utility, helps create classes mainly used to store data

Example :

@dataclass
class Employee:
    name: Str
    age: int

Usage:
e = Employee("Arun", 36)
print(e)

Output:
Employee(name="Arun", age=36 )


Also, @dataclass is a decorator which automatically geenrate methods like 
__init__()
__repr__()
__eq__()

from dataclasses import dataclass, field, asdict

field:  Used to customize attributes:
=====

from dataclasses import dataclass, field

@dataclass
class Team:
    members: list = field(default_factory=list)

This safely creates a new list for each pbject.

asdict: converts a dataclass object into a dictionary
======

Example :
from dataclasses import asdict

e = Employee("Arun", 36)
print(asdict(e))

Output:
{'name': 'Arun', 'age': 36}


@dataclass automatically creates:
__init__()
__repr__()
__eq__()

So you don’t need to manually write constructors.


"""

# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Chunk:
    chunk_id  : str
    level     : str          # "parent" or "child"
    section   : str
    parent_id : Optional[str]
    text      : str
    word_count: int = 0

    # __post_init__() runs automatiaally after __init__() in a data class
    # Used if you want extra logic after object creation
    def __post_init__(self):
        self.word_count = len(self.text.split())

@dataclass
class EmbeddingResult:
    chunk_id   : str
    model      : str
    provider   : str
    dimensions : int
    vector     : list[float]
    token_count: int
    cost_usd   : float
    latency_ms : float


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
# STEP 2 — Hierarchical Chunking (Strategy 8)
# ─────────────────────────────────────────────────────────────────────────────
def semantic_section_chunking(text: str) -> list[dict]:
    pattern = re.compile(
        r"(?m)^(Executive Summary|Revenue Growth|Key Metrics|Revenue by Segment|FY 2025 Outlook)\s*$"
    )
    splits = pattern.split(text)
    chunks, section_name = [], "Preamble"
    for part in splits:
        part = part.strip()
        if not part:
            continue
        if pattern.match(part):
            section_name = part
        else:
            chunks.append({"section": section_name, "text": part})
    return chunks


def hierarchical_chunking(text: str, child_size: int = 200) -> list[Chunk]:
    parents  = semantic_section_chunking(text)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_size, chunk_overlap=40,
        separators=["\n\n", "\n", ". ", " "],
    )
    all_chunks = []
    for i, p in enumerate(parents):
        parent_id = f"parent_{i}"
        all_chunks.append(Chunk(
            chunk_id=parent_id, level="parent",
            section=p["section"], parent_id=None, text=p["text"]
        ))
        for j, child_text in enumerate(splitter.split_text(p["text"])):
            if child_text.strip():
                all_chunks.append(Chunk(
                    chunk_id=f"{parent_id}_child_{j}", level="child",
                    section=p["section"], parent_id=parent_id,
                    text=child_text.strip()
                ))
    return all_chunks


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Token counting (word-based approximation)
# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Split text into words & punctuation
# re.findall(r"\w+|[^\w\s]", text)

# 👉 This regex extracts:

# Words (\w+)
# Punctuation ([^\w\s])
# 📘 Example
# Input:
# "AI is powerful."
# Step 1: Token-like split
# ["AI", "is", "powerful", "."]

# 👉 Count = 4

# Step 2: Multiply by 1.3
# 4 * 1.3 = 5.2
# Step 3: Convert to int
# int(5.2) = 5 tokens (approx)
# 🎯 Why 1.3?

# 👉 Because:

# LLM tokens ≠ words
# On average:
# 1 word ≈ 1.3 tokens
def approx_token_count(text: str) -> int:
    """~1.3 tokens per word — standard GPT/BERT approximation."""
    return int(len(re.findall(r"\w+|[^\w\s]", text)) * 1.3)


# Step 1: Get cost per 1000 tokens

# Example:

# EMBEDDING_MODELS = {
#     "openai": {"cost_per_1k_tok": 0.0001}
# }
# Step 2: Convert tokens → cost

# Formula:

# cost = (token_count / 1000) * cost_per_1k
# 📘 Example
# Input:
# token_count = 500
# model_key = "openai"
# cost_per_1k = 0.0001
# Calculation:
# (500 / 1000) * 0.0001 = 0.00005
# Final Output:
# 0.00005

# 👉 Very small cost (as expected for embeddings)

def estimate_cost(token_count: int, model_key: str) -> float:
    cost_per_1k = EMBEDDING_MODELS[model_key]["cost_per_1k_tok"]
    return round((token_count / 1000) * cost_per_1k, 8)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Embedding providers
# ─────────────────────────────────────────────────────────────────────────────

# ── 4a. OpenAI ────────────────────────────────────────────────────────────────
# 🔹 Step 1: Initialize OpenAI Client
# import openai
# client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# 👉 Uses your API key to connect to OpenAI

# 🔹 Step 2: Prepare Metadata
# model_key = f"openai/{model}"
# dims = EMBEDDING_MODELS[model_key]["dimensions"]

# 👉 Example:

# model = "text-embedding-3-small"
# dims = 1536

# 🔹 Step 3: Extract Text from Chunks
# texts = [c.text for c in chunks]
# Example:
# chunks = [
#   {"chunk_id": "c1", "text": "AI improves productivity"},
#   {"chunk_id": "c2", "text": "Machine learning enables automation"}
# ]

# 👉 Result:

# texts = [
#   "AI improves productivity",
#   "Machine learning enables automation"
# ]
# 🔹 Step 4: Call OpenAI Embedding API
# response = client.embeddings.create(
#     model=model,
#     input=texts
# )

# 👉 OpenAI returns:

# response.data = [
#   {"embedding": [0.12, 0.45, ...]},
#   {"embedding": [0.98, 0.33, ...]}
# ]
# 🔹 Step 5: Measure Latency
# t0 = time.time()
# latency = (time.time() - t0) * 1000

# 👉 Measures how long API call took (in ms)

# 🔹 Step 6: Loop Through Results
# for chunk, emb_obj in zip(chunks, response.data):

# 👉 Matches:

# each chunk
# with its embedding

# 🔹 Step 7: Token Count
# tok = approx_token_count(chunk.text)

# 👉 Example:

# "AI improves productivity" → ~5 tokens

# 🔹 Step 8: Cost Calculation
# cost_usd = estimate_cost(tok, model_key)

# 👉 Example:

# 5 tokens → very small cost (~0.0000005)

# 🔹 Step 9: Create Result Object
# EmbeddingResult(
#     chunk_id   = chunk.chunk_id,
#     model      = model,
#     provider   = "OpenAI",
#     dimensions = dims,
#     vector     = emb_obj.embedding,
#     token_count= tok,
#     cost_usd   = cost,
#     latency_ms = latency / len(chunks),
# )
# 📦 Final Output Example
# [
#   {
#     "chunk_id": "c1",
#     "vector": [0.12, 0.45, ...],
#     "token_count": 5,
#     "cost_usd": 0.0000005,
#     "latency_ms": 20
#   },
#   {
#     "chunk_id": "c2",
#     "vector": [0.98, 0.33, ...],
#     "token_count": 6,
#     "cost_usd": 0.0000006,
#     "latency_ms": 20
#   }
# ]

def embed_openai(chunks: list[Chunk], model: str = "text-embedding-3-small") -> list[EmbeddingResult]:
    """
    Real OpenAI embedding call.
    Replace OPENAI_KEY with your actual key to get live vectors.
    Docs: https://platform.openai.com/docs/guides/embeddings
    """
    try:
        import openai
        client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        results = []
        model_key = f"openai/{model}"
        dims = EMBEDDING_MODELS[model_key]["dimensions"]

        # Batch all child chunks for efficiency (OpenAI supports up to 2048 inputs)
        texts = [c.text for c in chunks]
        t0 = time.time()
        response = client.embeddings.create(model=model, input=texts)
        latency = (time.time() - t0) * 1000

        for i, (chunk, emb_obj) in enumerate(zip(chunks, response.data)):
            tok = approx_token_count(chunk.text)
            results.append(EmbeddingResult(
                chunk_id   = chunk.chunk_id,
                model      = model,
                provider   = "OpenAI",
                dimensions = dims,
                vector     = emb_obj.embedding,
                token_count= tok,
                cost_usd   = estimate_cost(tok, model_key),
                latency_ms = latency / len(chunks),
            ))
        return results

    except Exception as e:
        print(f"  [OpenAI] API call failed: {e}")
        print(f"  [OpenAI] Falling back to simulated vectors for cost/demo display.\n")
        return _simulate_embeddings(chunks, f"openai/{model}", "OpenAI")


# ── 4b. HuggingFace (local) ───────────────────────────────────────────────────
def embed_huggingface(chunks: list[Chunk], model_name: str = "all-MiniLM-L6-v2") -> list[EmbeddingResult]:
    """
    Local HuggingFace embedding via sentence-transformers.
    No API key needed. Runs on CPU or GPU.
    Install: pip install sentence-transformers
    """
    try:
        from sentence_transformers import SentenceTransformer
        model_key = f"huggingface/{model_name}"
        dims = EMBEDDING_MODELS[model_key]["dimensions"]

        print(f"  [HuggingFace] Loading model '{model_name}'...")
        model = SentenceTransformer(model_name)

        texts = [c.text for c in chunks]
        t0 = time.time()
        vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        latency = (time.time() - t0) * 1000

        results = []
        for chunk, vec in zip(chunks, vectors):
            tok = approx_token_count(chunk.text)
            results.append(EmbeddingResult(
                chunk_id   = chunk.chunk_id,
                model      = model_name,
                provider   = "HuggingFace",
                dimensions = dims,
                vector     = vec.tolist(),
                token_count= tok,
                cost_usd   = 0.0,           # free local model
                latency_ms = latency / len(chunks),
            ))
        return results

    except Exception as e:
        print(f"  [HuggingFace] Model load failed: {e}")
        print(f"  [HuggingFace] Falling back to simulated vectors.\n")
        return _simulate_embeddings(chunks, f"huggingface/{model_name}", "HuggingFace")


# ── 4c. BGE (local, via sentence-transformers) ────────────────────────────────
def embed_bge(chunks: list[Chunk], model_name: str = "BAAI/bge-large-en-v1.5") -> list[EmbeddingResult]:
    """
    BGE models from BAAI — best open-source embeddings on MTEB benchmark.
    Runs locally via sentence-transformers.
    BGE requires a query prefix for retrieval:
      - Passages (stored): no prefix needed
      - Queries (at search time): prefix with "Represent this sentence: "
    Install: pip install sentence-transformers
    """
    try:
        from sentence_transformers import SentenceTransformer
        short_key = model_name.split("/")[-1].lower().replace("-", "-")
        model_key = f"bge/{short_key}"
        dims = EMBEDDING_MODELS.get(model_key, {}).get("dimensions", 1024)

        print(f"  [BGE] Loading model '{model_name}'...")
        model = SentenceTransformer(model_name)

        # BGE: passages don't need prefix; queries need "Represent this: "
        texts = [c.text for c in chunks]
        t0 = time.time()
        vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        latency = (time.time() - t0) * 1000

        results = []
        for chunk, vec in zip(chunks, vectors):
            tok = approx_token_count(chunk.text)
            results.append(EmbeddingResult(
                chunk_id   = chunk.chunk_id,
                model      = model_name,
                provider   = "BGE (BAAI)",
                dimensions = dims,
                vector     = vec.tolist(),
                token_count= tok,
                cost_usd   = 0.0,
                latency_ms = latency / len(chunks),
            ))
        return results

    except Exception as e:
        print(f"  [BGE] Model load failed: {e}")
        print(f"  [BGE] Falling back to simulated vectors.\n")
        return _simulate_embeddings(chunks, model_key if 'model_key' in dir() else "bge/bge-large-en-v1.5", "BGE (BAAI)")


# ── Fallback: Simulate vectors for display when models can't be loaded ─────────
# 🧠 What this function does

# 👉 This function simulates embeddings (fake vectors) instead of calling a real API.

# It is used when:

# ❌ OpenAI API is not available
# ✅ You want to test/demo your pipeline

# 🔄 High-Level Flow
# Chunks → Generate fake vectors → Add metadata → Return results

# 📘 Step-by-Step Explanation

# 🔹 Step 1: Get model info
# info = EMBEDDING_MODELS.get(model_key, {"dimensions": 384, "cost_per_1k_tok": 0.0})
# dims = info["dimensions"]

# 👉 Example:

# model_key = "openai/text-embedding-3-small"
# dims = 1536

# 👉 If model not found:

# Default → 384 dimensions

# 🔹 Step 2: Fix random seed
# np.random.seed(42)

# 👉 This ensures:

# Same input → same output every time

# ✔ Useful for:

# Testing
# Debugging

# 🔹 Step 3: Loop through chunks
# for chunk in chunks:
# Example input:
# chunks = [
#   {"chunk_id": "c1", "text": "AI improves productivity"},
#   {"chunk_id": "c2", "text": "Machine learning enables automation"}
# ]

# 🔹 Step 4: Approximate token count
# tok = approx_token_count(chunk.text)

# 👉 Example:

# "AI improves productivity" → ~5 tokens

# 🔹 Step 5: Create random vector
# vec = np.random.randn(dims)

# 👉 Example (dims = 4 for simplicity):

# [0.2, -1.1, 0.5, 0.9]

# 🔹 Step 6: Normalize vector
# vec = vec / np.linalg.norm(vec)

# 👉 Makes vector length = 1

# Why?

# ✔ Important for:

# Cosine similarity
# Vector search

# 🔹 Step 7: Convert to list
# vec.tolist()

# 👉 So it can be stored in:

# JSON
# Vector DB

# 🔹 Step 8: Estimate cost
# cost_usd = estimate_cost(tok, model_key)

# 👉 Even though vector is fake:

# Cost is calculated correctly

# 🔹 Step 9: Simulate latency
# latency_ms = round(np.random.uniform(2, 8), 2)

# 👉 Example:

# 5.43 ms

# 🔹 Step 10: Create result object
# EmbeddingResult(
#     chunk_id   = chunk.chunk_id,
#     model      = model_key.split("/")[-1],
#     provider   = provider,
#     dimensions = dims,
#     vector     = vec,
#     token_count= tok,
#     cost_usd   = cost,
#     latency_ms = latency
# )

# 📦 Final Output Example
# [
#   {
#     "chunk_id": "c1",
#     "vector": [0.12, -0.45, 0.33, ...],
#     "dimensions": 1536,
#     "token_count": 5,
#     "cost_usd": 0.0000005,
#     "latency_ms": 4.2
#   },
#   {
#     "chunk_id": "c2",
#     "vector": [0.88, 0.21, -0.67, ...],
#     "dimensions": 1536,
#     "token_count": 6,
#     "cost_usd": 0.0000006,
#     "latency_ms": 6.1
#   }
# ]

# 🎯 Why This is Useful
# ✅ 1. No API required
# Works offline
# No cost

# ✅ 2. Pipeline testing

# You can test:

# Chunking → Embedding → Vector DB → Retrieval

# without real embeddings

# ✅ 3. Deterministic output

# Because of:

# np.random.seed(42)

# 👉 Same input → same vectors
# 👉 Easy debugging

# ⚠️ Important Limitation

# ❌ These vectors have:

# NO semantic meaning
# NO real similarity

# 👉 So:

# Not useful for real search
# Only for testing
# 🧠 Simple Analogy

# 👉 Real embedding:

# Meaningful fingerprint of text 🧠

# 👉 Simulated embedding:

# Random fingerprint 🎲

def _simulate_embeddings(chunks: list[Chunk], model_key: str, provider: str) -> list[EmbeddingResult]:
    """Produces deterministic mock vectors — dimensions/costs are 100% accurate."""
    info = EMBEDDING_MODELS.get(model_key, {"dimensions": 384, "cost_per_1k_tok": 0.0})
    dims = info["dimensions"]
    np.random.seed(42)
    results = []
    for chunk in chunks:
        tok = approx_token_count(chunk.text)
        vec = np.random.randn(dims)
        vec = (vec / np.linalg.norm(vec)).tolist()   # unit-normalized
        results.append(EmbeddingResult(
            chunk_id   = chunk.chunk_id,
            model      = model_key.split("/")[-1],
            provider   = provider,
            dimensions = dims,
            vector     = vec,
            token_count= tok,
            cost_usd   = estimate_cost(tok, model_key),
            latency_ms = round(np.random.uniform(2, 8), 2),
        ))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Cost report printer
# ─────────────────────────────────────────────────────────────────────────────
def print_cost_report(results: list[EmbeddingResult], model_key: str):
    info       = EMBEDDING_MODELS[model_key]
    total_tok  = sum(r.token_count for r in results)
    total_cost = sum(r.cost_usd    for r in results)
    avg_lat    = sum(r.latency_ms  for r in results) / len(results)

    print(f"\n  ┌─ Cost & Performance Report ─────────────────────────────────┐")
    print(f"  │  Model      : {model_key}")
    print(f"  │  Provider   : {info['provider']}")
    print(f"  │  Dimensions : {info['dimensions']}")
    print(f"  │  Max Tokens : {info['max_tokens']}")
    print(f"  │  Quality    : {info['quality']}")
    print(f"  │  Speed      : {info['speed']}")
    print(f"  │  Best For   : {info['best_for']}")
    print(f"  ├─ This PDF ─────────────────────────────────────────────────────┤")
    print(f"  │  Chunks embedded  : {len(results)}")
    print(f"  │  Total tokens     : {total_tok:,}")
    print(f"  │  Cost (this file) : ${total_cost:.6f} USD")
    if info["cost_per_1k_tok"] > 0:
        cost_1m_docs = total_cost * 1_000_000
        cost_10k     = total_cost * 10_000
        print(f"  │  Cost @ 10K docs  : ${cost_10k:,.2f} USD")
        print(f"  │  Cost @ 1M  docs  : ${cost_1m_docs:,.2f} USD")
    else:
        print(f"  │  Cost @ any scale : $0.00 (runs locally — FREE)")
    print(f"  │  Avg latency/chunk: {avg_lat:.1f} ms")
    print(f"  └────────────────────────────────────────────────────────────────┘")


# 🧠 What this function does

# 👉 It prints a small preview of embedding vectors for debugging/inspection.

# Instead of printing full vectors (which are huge), it shows:

# First few child chunks
# First 6 values of each vector
# Metadata (tokens, cost, dimensions)

# 🔄 High-Level Flow
# Embedding Results → Filter child chunks → Take first N → Print summary

# 📘 Step-by-Step Explanation

# 🔹 Step 1: Print header
# print(f"\n  Sample vectors (first {n} child chunks):")

# 👉 Example:

# Sample vectors (first 2 child chunks):

# 🔹 Step 2: Filter only child chunks
# child_results = [r for r in results if "child" in r.chunk_id][:n]

# 👉 It:

# Picks only chunks with "child" in ID
# Takes first n results
# Example Input:
# results = [
#   {"chunk_id": "parent_0", "vector": [...]},
#   {"chunk_id": "parent_0_child_0", "vector": [...]},
#   {"chunk_id": "parent_0_child_1", "vector": [...]},
#   {"chunk_id": "parent_1_child_0", "vector": [...]}
# ]

# 👉 After filtering:

# [
#   "parent_0_child_0",
#   "parent_0_child_1"
# ]

# 🔹 Step 3: Loop through selected results
# for r in child_results:

# 🔹 Step 4: Take only first 6 vector values
# vec_preview = [round(v, 4) for v in r.vector[:6]]

# 👉 Example:

# Full vector:

# [0.123456, -0.987654, 0.456789, 0.111111, -0.222222, 0.333333, ...]

# 👉 Preview:

# [0.1235, -0.9877, 0.4568, 0.1111, -0.2222, 0.3333]

# 🔹 Step 5: Print chunk details
# print(f"    [{r.chunk_id}]")

# 👉 Example:

# [parent_0_child_0]

# 🔹 Step 6: Print metadata
# print(f"      dims={r.dimensions}  tokens={r.token_count}  cost=${r.cost_usd:.8f}")

# 👉 Example:

# dims=1536  tokens=120  cost=$0.00001200

# 🔹 Step 7: Print vector preview
# print(f"      vector[:6] = {vec_preview} ...")

# 👉 Example:

# vector[:6] = [0.1235, -0.9877, 0.4568, 0.1111, -0.2222, 0.3333] ...

# 📦 Final Output Example
# Sample vectors (first 2 child chunks):

#   [parent_0_child_0]
#     dims=1536  tokens=120  cost=$0.00001200
#     vector[:6] = [0.1235, -0.9877, 0.4568, 0.1111, -0.2222, 0.3333] ...

#   [parent_0_child_1]
#     dims=1536  tokens=110  cost=$0.00001100
#     vector[:6] = [0.5432, 0.1111, -0.2222, 0.9999, -0.8888, 0.7777] ...

# 🎯 Why This is Useful

# ✅ 1. Debugging
# Check if embeddings are generated correctly

# ✅ 2. Avoid huge output
# Full vector = 1000+ numbers ❌
# Preview = manageable ✅

# ✅ 3. Validate pipeline
# Check:
# token count
# cost
# dimensions

def print_vector_sample(results: list[EmbeddingResult], n: int = 2):
    print(f"\n  Sample vectors (first {n} child chunks):")
    child_results = [r for r in results if "child" in r.chunk_id][:n]
    for r in child_results:
        vec_preview = [round(v, 4) for v in r.vector[:6]]
        print(f"    [{r.chunk_id}]")
        print(f"      dims={r.dimensions}  tokens={r.token_count}  "
              f"cost=${r.cost_usd:.8f}")
        print(f"      vector[:6] = {vec_preview} ...")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*65)
    print("  RAG EMBEDDING PIPELINE")
    print("  Strategy: Hierarchical Chunking (Parent-Child)")
    print("="*65)

    # ── Load & Chunk ──────────────────────────────────────────────────────────
    print("\n[1] Extracting text from PDF...")
    raw_text = extract_text(PDF_PATH)
    print(f"    Extracted {len(raw_text)} chars / {len(raw_text.split())} words")

    print("\n[2] Applying Hierarchical Chunking...")
    chunks = hierarchical_chunking(raw_text, child_size=200)
    parents  = [c for c in chunks if c.level == "parent"]
    children = [c for c in chunks if c.level == "child"]
    print(f"    Parents : {len(parents)}")
    print(f"    Children: {len(children)}")
    print(f"    Total   : {len(chunks)}")

    # Show chunk tree
    print("\n    Chunk Tree:")
    for p in parents:
        kids = [c for c in children if c.parent_id == p.chunk_id]
        print(f"    ├─ [PARENT] {p.chunk_id} | {p.section} | {p.word_count} words")
        for k in kids:
            print(f"    │    └─ [child] {k.chunk_id} | {k.word_count} words | "
                  f"{k.text[:50].strip()}...")

    # Embed only child chunks (parents stored separately for context retrieval)
    embed_chunks = children

    # ── MODEL COMPARISON TABLE ────────────────────────────────────────────────
    total_words = sum(c.word_count for c in embed_chunks)
    total_tokens = sum(approx_token_count(c.text) for c in embed_chunks)

    print(f"\n[3] Pre-flight Cost Estimation ({len(embed_chunks)} child chunks | ~{total_tokens} tokens)")
    print(f"\n  {'Model':<38} {'Dims':>5}  {'Cost/1K tok':>12}  {'Est. Cost':>12}  {'Type'}")
    print(f"  {'-'*85}")
    for key, info in EMBEDDING_MODELS.items():
        cost = (total_tokens / 1000) * info["cost_per_1k_tok"]
        cost_str = f"${cost:.6f}" if cost > 0 else "FREE"
        type_str = "API (paid)" if info["requires_api"] else "Local (free)"
        print(f"  {key:<38} {info['dimensions']:>5}  "
              f"${info['cost_per_1k_tok']:.5f}/1K  {cost_str:>12}  {type_str}")

    # ── PROVIDER 1: OpenAI ────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"[4a] OPENAI — text-embedding-3-small")
    print(f"{'='*65}")
    results_oai_small = embed_openai(embed_chunks, model="text-embedding-3-small")
    print_cost_report(results_oai_small, "openai/text-embedding-3-small")
    print_vector_sample(results_oai_small)

    print(f"\n{'='*65}")
    print(f"[4b] OPENAI — text-embedding-3-large")
    print(f"{'='*65}")
    results_oai_large = embed_openai(embed_chunks, model="text-embedding-3-large")
    print_cost_report(results_oai_large, "openai/text-embedding-3-large")
    print_vector_sample(results_oai_large)

    # ── PROVIDER 2: HuggingFace ───────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"[5a] HUGGINGFACE — all-MiniLM-L6-v2")
    print(f"{'='*65}")
    results_hf_mini = embed_huggingface(embed_chunks, model_name="all-MiniLM-L6-v2")
    print_cost_report(results_hf_mini, "huggingface/all-MiniLM-L6-v2")
    print_vector_sample(results_hf_mini)

    print(f"\n{'='*65}")
    print(f"[5b] HUGGINGFACE — all-mpnet-base-v2")
    print(f"{'='*65}")
    results_hf_mpnet = embed_huggingface(embed_chunks, model_name="all-mpnet-base-v2")
    print_cost_report(results_hf_mpnet, "huggingface/all-mpnet-base-v2")
    print_vector_sample(results_hf_mpnet)

    # ── PROVIDER 3: BGE ───────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"[6a] BGE — BAAI/bge-small-en-v1.5")
    print(f"{'='*65}")
    results_bge_small = embed_bge(embed_chunks, model_name="BAAI/bge-small-en-v1.5")
    print_cost_report(results_bge_small, "bge/bge-small-en-v1.5")
    print_vector_sample(results_bge_small)

    print(f"\n{'='*65}")
    print(f"[6b] BGE — BAAI/bge-large-en-v1.5")
    print(f"{'='*65}")
    results_bge_large = embed_bge(embed_chunks, model_name="BAAI/bge-large-en-v1.5")
    print_cost_report(results_bge_large, "bge/bge-large-en-v1.5")
    print_vector_sample(results_bge_large)

    # ── FINAL COMPARISON SUMMARY ──────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  FINAL MODEL COMPARISON SUMMARY")
    print(f"  (for {len(embed_chunks)} child chunks from financial_report_2024.pdf)")
    print(f"{'='*65}")

    all_results = [
        ("OpenAI 3-small",    results_oai_small,  "openai/text-embedding-3-small"),
        ("OpenAI 3-large",    results_oai_large,  "openai/text-embedding-3-large"),
        ("HF MiniLM-L6",      results_hf_mini,    "huggingface/all-MiniLM-L6-v2"),
        ("HF mpnet-base",     results_hf_mpnet,   "huggingface/all-mpnet-base-v2"),
        ("BGE small-v1.5",    results_bge_small,  "bge/bge-small-en-v1.5"),
        ("BGE large-v1.5",    results_bge_large,  "bge/bge-large-en-v1.5"),
    ]

    print(f"\n  {'Model':<20} {'Dims':>5} {'Quality':<10} {'Cost (file)':>14} {'Cost (10K docs)':>16} {'Recommended For'}")
    print(f"  {'-'*90}")
    for label, results, mkey in all_results:
        info    = EMBEDDING_MODELS[mkey]
        cost    = sum(r.cost_usd for r in results)
        cost10k = cost * 10_000
        cost_str   = f"${cost:.6f}" if cost > 0 else "$0.000000"
        cost10k_str= f"${cost10k:,.2f}" if cost10k > 0 else "FREE"
        print(f"  {label:<20} {info['dimensions']:>5} {info['quality']:<10} "
              f"{cost_str:>14} {cost10k_str:>16}  {info['best_for'][:35]}")

    print(f"""
  ┌─ Recommendation Guide ──────────────────────────────────────────┐
  │                                                                  │
  │  🏆 Best Quality (paid)  : OpenAI text-embedding-3-large        │
  │     → 3072 dims, highest MTEB score, ideal for finance/legal    │
  │                                                                  │
  │  💰 Best Value (paid)    : OpenAI text-embedding-3-small        │
  │     → 6.5x cheaper than large, still excellent retrieval        │
  │                                                                  │
  │  🆓 Best Free (quality)  : BGE bge-large-en-v1.5               │
  │     → 1024 dims, beats HF models on all MTEB benchmarks        │
  │     → GPU recommended for production throughput                  │
  │                                                                  │
  │  ⚡ Best Free (speed)    : BGE bge-small-en-v1.5               │
  │     → 384 dims, CPU-friendly, near-large quality at 3x speed    │
  │                                                                  │
  │  📌 Production Pattern   : Hierarchical chunks (this script)    │
  │     → Store child vectors in Chroma/Pinecone/Weaviate           │
  │     → At query time: retrieve child → send parent to LLM        │
  └──────────────────────────────────────────────────────────────────┘
""")


if __name__ == "__main__":
    main()