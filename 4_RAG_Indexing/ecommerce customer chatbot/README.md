# ShopNow E-Commerce RAG System
## Production Pipeline — Execution Guide

---

## Prerequisites

```bash
# Python packages
pip install pdfplumber openai langchain-text-splitters tiktoken \
            chromadb rank-bm25 psycopg2-binary pgvector \
            redis streamlit numpy

# Docker (for pgvector + Redis)
# Install Docker Desktop or Docker Engine
```

---

## Quick Start — Run Everything

```bash
cd rag_system

# Option A: Full pipeline (requires Docker)
python 00_run_pipeline.py

# Option B: Skip Docker services
python 00_run_pipeline.py --skip-pgvector --skip-redis

# Option C: Start from a specific module
python 00_run_pipeline.py --from 6
```

---

## Module-by-Module Execution

### Step 0 — Start Docker services (optional but recommended)

```bash
# pgvector (PostgreSQL + vector extension)
docker run -d --name pgvector_rag \
  -e POSTGRES_DB=ecommerce_rag \
  -e POSTGRES_USER=raguser \
  -e POSTGRES_PASSWORD=ragpass123 \
  -p 5432:5432 pgvector/pgvector:pg16

# Redis (query cache)
docker run -d --name redis_rag \
  -p 6379:6379 \
  redis:7-alpine

# Verify both are running
docker ps | grep -E "pgvector_rag|redis_rag"
```

### Step 1 — Set OpenAI API key (optional — pipeline runs without it)

```bash
export OPENAI_API_KEY="sk-..."

# Without a key: mock embeddings are used.
# All code still runs but retrieval metrics will be random.
# Set the key for real semantic search quality.
```

### Step 2 — Run extraction

```bash
python 01_extraction.py
# Output: extracted_data.json
# Metrics: 14 pages, 15 sections, quality score 100/100
```

### Step 3 — Chunk documents

```bash
python 02_chunking.py
# Output: chunks.json
# With OpenAI key: GPT-4o-mini semantic chunking
# Without key:     RecursiveCharacterTextSplitter fallback
# Cost estimate:   ~$0.000095 for this PDF
```

### Step 4 — Generate embeddings

```bash
python 03_embeddings.py
# Output: embeddings.json (chunks + 1536-dim vectors)
# Model:  text-embedding-3-small ($0.020/1M tokens)
# Cost:   ~$0.000095 for this PDF
```

### Step 5 — Load into pgvector (requires Docker)

```bash
python 04_pgvector.py
# Creates table: document_chunks
# Creates index: HNSW (m=16, ef_construction=200)
# Benchmarks:    ef_search 10/50/100/200/400
```

### Step 6 — Launch Streamlit dashboard

```bash
streamlit run 05_streamlit_dashboard.py
# Opens browser at http://localhost:8501
# Features: query input, results display, analytics tab, chunk browser
```

### Step 7 — Query processing

```bash
python 06_query_processing.py
# Techniques: baseline | reformulation | expansion | intent_validation
# Metrics:    Precision@5, latency per technique
# Output:     recommendation printed to console
```

### Step 8 — Access control

```bash
python 07_access_control.py
# Hierarchy:  public → internal → confidential → most_confidential
# Roles:      anonymous | customer | agent | supervisor | admin
# Metrics:    docs_searched, latency, memory, cost per approach
```

### Step 9 — Hybrid search

```bash
python 08_hybrid_search.py
# Techniques: Semantic | BM25 | RRF (Reciprocal Rank Fusion)
# Metrics:    Precision@1/3/5, Recall@5, latency p50/p90/p95/p99
# Runs:       50 iterations per query for stable percentiles
```

### Step 10 — Evaluation metrics

```bash
python 09_evaluation.py
# Standard: Precision@K, Recall@K, MRR, NDCG@5
# RAGAS:    Faithfulness, Answer Relevancy, Context Precision, Context Recall
# Targets:  printed with PASS/FAIL status
```

### Step 11 — Redis cache (requires Docker)

```bash
python 10_redis_cache.py
# Shows: MISS (first call) vs HIT (repeated query)
# Speedup: 3000x+ faster on cache hit
# TTL:     3600s (1 hour)
```

### Step 12 — Golden dataset

```bash
python 11_golden_dataset.py
# Output: golden_dataset.json
# Items:  18 golden questions across 6 sections
# Runs:   full evaluation pipeline on all items
# Report: score targets with PASS/FAIL
```

---

## Environment Variables

| Variable          | Default     | Description                        |
|-------------------|-------------|-------------------------------------|
| OPENAI_API_KEY    | —           | Required for real embeddings/LLM    |
| PGVECTOR_HOST     | localhost   | PostgreSQL host                     |
| PGVECTOR_PORT     | 5432        | PostgreSQL port                     |
| PGVECTOR_DB       | ecommerce_rag | Database name                     |
| PGVECTOR_USER     | raguser     | Database user                       |
| PGVECTOR_PASS     | ragpass123  | Database password                   |
| REDIS_HOST        | localhost   | Redis host                          |
| REDIS_PORT        | 6379        | Redis port                          |

---

## Data Flow

```
ecommerce_knowledge_base.pdf
    │
    ▼ 01_extraction.py
extracted_data.json  (15 sections, metrics)
    │
    ▼ 02_chunking.py
chunks.json  (28 chunks, cost breakdown)
    │
    ▼ 03_embeddings.py
embeddings.json  (28 chunks + 1536-dim vectors)
    │
    ├──▶ 04_pgvector.py  ──▶ PostgreSQL + HNSW index
    ├──▶ 05_streamlit_dashboard.py  ──▶ http://localhost:8501
    ├──▶ 06_query_processing.py  ──▶ 4 query techniques compared
    ├──▶ 07_access_control.py  ──▶ 4-level access hierarchy
    ├──▶ 08_hybrid_search.py  ──▶ BM25 + Semantic + RRF
    ├──▶ 09_evaluation.py  ──▶ IR + RAGAS metrics
    ├──▶ 10_redis_cache.py  ──▶ Query cache (3000x speedup)
    └──▶ 11_golden_dataset.py  ──▶ golden_dataset.json
```

---

## Expected Scores With Real OpenAI Embeddings

| Metric           | Mock Embeddings | Real Embeddings (Expected) |
|------------------|-----------------|---------------------------|
| Precision@5      | 0.04–0.20       | 0.60–0.85                 |
| Recall@5         | 0.20–0.40       | 0.70–0.90                 |
| MRR              | 0.10–0.30       | 0.55–0.80                 |
| NDCG@5           | 0.20–0.35       | 0.65–0.85                 |
| Faithfulness     | 0.30–0.50       | 0.75–0.90                 |
| Context Recall   | 0.40–0.60       | 0.70–0.88                 |

---

## Troubleshooting

**Module 04 fails:** Ensure Docker container is running — `docker ps`

**Module 10 fails:** Ensure Redis container is running — `docker ps`

**Low evaluation scores:** Expected with mock embeddings. Set `OPENAI_API_KEY`.

**Chunking uses fallback:** Set `OPENAI_API_KEY` for GPT-4o-mini semantic chunking.

**Import error:** Run `pip install -r requirements.txt` or install packages listed above.
