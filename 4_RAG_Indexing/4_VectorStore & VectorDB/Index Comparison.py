"""
=============================================================
Production-Grade FAISS Index Comparison
Indexes : IndexFlatIP | HNSW | IVF-PQ
Metrics : Build time, Query latency, Recall@K,
          Memory usage, Index size, QPS, Throughput
Dataset : Simulated BGE bge-large-en-v1.5 embeddings
          (1024-dim unit-normalized float32 vectors)
          Sizes: 10K / 100K / 500K vectors
=============================================================
"""

import os, time, struct, tempfile, gc
import numpy as np
import faiss

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
DIM        = 1024          # BGE large-en-v1.5 dimension
SIZES      = [10_000, 100_000, 500_000]
TOP_K      = 10            # retrieve top-10 results
N_QUERIES  = 200           # query vectors for benchmarking
N_WARMUP   = 10            # warmup queries (excluded from timing)
SEED       = 42
np.random.seed(SEED)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def unit_vectors(n: int, d: int, seed: int = 0) -> np.ndarray:
    """Generate L2-normalized float32 vectors (cosine-ready)."""
    rng = np.random.default_rng(seed)
    v   = rng.standard_normal((n, d)).astype(np.float32)
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    return v / norms


def index_size_bytes(index: faiss.Index) -> int:
    """Serialize index to a temp buffer and return byte count."""
    with tempfile.NamedTemporaryFile(suffix=".faiss", delete=False) as f:
        fname = f.name
    faiss.write_index(index, fname)
    size = os.path.getsize(fname)
    os.remove(fname)
    return size


def recall_at_k(true_ids: np.ndarray, pred_ids: np.ndarray, k: int) -> float:
    """Recall@K: fraction of true top-k neighbors found in predicted top-k."""
    hits = 0
    for t_row, p_row in zip(true_ids, pred_ids):
        hits += len(set(t_row[:k]) & set(p_row[:k]))
    return hits / (len(true_ids) * k)


def measure_query_latency(index, queries, k, warmup=N_WARMUP):
    """Return per-query latency stats (ms) and QPS."""
    # warmup
    index.search(queries[:warmup], k)

    latencies = []
    for q in queries:
        t0 = time.perf_counter()
        index.search(q[np.newaxis, :], k)
        latencies.append((time.perf_counter() - t0) * 1000)

    lat  = np.array(latencies)
    qps  = 1000 / np.mean(lat)
    return {
        "p50_ms" : round(float(np.percentile(lat, 50)), 3),
        "p95_ms" : round(float(np.percentile(lat, 95)), 3),
        "p99_ms" : round(float(np.percentile(lat, 99)), 3),
        "mean_ms": round(float(np.mean(lat)), 3),
        "min_ms" : round(float(np.min(lat)), 3),
        "max_ms" : round(float(np.max(lat)), 3),
        "qps"    : round(qps, 1),
    }


def measure_batch_throughput(index, queries, k, batch_size=N_QUERIES):
    """Batch search throughput (vectors/sec)."""
    t0 = time.perf_counter()
    index.search(queries[:batch_size], k)
    elapsed = time.perf_counter() - t0
    return round(batch_size / elapsed, 0)


def fmt_bytes(b: int) -> str:
    if b < 1024:           return f"{b} B"
    if b < 1024**2:        return f"{b/1024:.1f} KB"
    if b < 1024**3:        return f"{b/1024**2:.1f} MB"
    return                        f"{b/1024**3:.2f} GB"


def print_header(title: str):
    print(f"\n{'═'*70}")
    print(f"  {title}")
    print(f"{'═'*70}")


def print_section(title: str):
    print(f"\n  {'─'*60}")
    print(f"  {title}")
    print(f"  {'─'*60}")


# ─────────────────────────────────────────────────────────────
# INDEX BUILDERS
# ─────────────────────────────────────────────────────────────

def build_flatip(vectors: np.ndarray) -> tuple[faiss.Index, float]:
    """
    IndexFlatIP — exact inner-product search.
    - No training required
    - 100% recall guaranteed
    - O(n) per query (linear scan)
    - Best for: < 100K vectors, ground-truth generation
    """
    index = faiss.IndexFlatIP(DIM)
    t0    = time.perf_counter()
    index.add(vectors)
    build_time = time.perf_counter() - t0
    return index, build_time


def build_hnsw(vectors: np.ndarray,
               M: int = 32,
               ef_construction: int = 200,
               ef_search: int = 128) -> tuple[faiss.Index, float]:
    """
    IndexHNSWFlat — Hierarchical Navigable Small World.
    - M         : graph edges per node (higher = better recall, more RAM)
    - ef_construction : build-time search width (higher = better graph quality)
    - ef_search : query-time search width (tune for recall/speed tradeoff)
    - ~95-99% recall · very fast · high RAM
    - Best for: 100K–10M vectors, production RAG
    Production tuning:
      - M=32, ef_construction=200 → good default balance
      - M=64, ef_construction=400 → higher recall, 2x RAM
      - ef_search=64  → faster, ~95% recall
      - ef_search=256 → slower, ~99% recall
    """
    index = faiss.IndexHNSWFlat(DIM, M, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = ef_construction
    index.hnsw.efSearch        = ef_search

    t0 = time.perf_counter()
    index.add(vectors)
    build_time = time.perf_counter() - t0
    return index, build_time


def build_ivfpq(vectors: np.ndarray,
                nlist: int = None,
                M_pq: int = 64,
                nbits: int = 8,
                nprobe: int = 32) -> tuple[faiss.Index, float]:
    """
    IndexIVFPQ — Inverted File + Product Quantization.
    - nlist : number of Voronoi cells (sqrt(n) is a good default)
    - M_pq  : number of sub-quantizers (higher = better quality, more RAM)
    - nbits : bits per sub-quantizer code (8 = 256 centroids per sub-space)
    - nprobe: cells visited at query time (higher = better recall, slower)
    - ~85-95% recall · lowest RAM · GPU-compatible
    - Best for: > 1M vectors, memory-constrained, GPU acceleration
    Production tuning:
      - nlist = sqrt(n_vectors)
      - M_pq = 64 for 1024-dim (DIM // 16)
      - nprobe = 32–128 depending on recall target
      - nbits = 8 (standard) or 4 (extreme compression)
    IMPORTANT: Requires training on representative sample before adding vectors
    """
    n = len(vectors)
    if nlist is None:
        nlist = max(64, int(np.sqrt(n)))

    quantizer = faiss.IndexFlatIP(DIM)
    index     = faiss.IndexIVFPQ(
        quantizer, DIM, nlist, M_pq, nbits,
        faiss.METRIC_INNER_PRODUCT
    )
    index.nprobe = nprobe

    # Training — needs representative sample (use all data if feasible)
    train_size = min(n, max(10 * nlist, 50_000))
    train_data = vectors[:train_size]

    t0 = time.perf_counter()
    print(f"      Training IVF-PQ on {train_size:,} vectors (nlist={nlist})...")
    index.train(train_data)
    index.add(vectors)
    build_time = time.perf_counter() - t0

    return index, build_time


# ─────────────────────────────────────────────────────────────
# BENCHMARK RUNNER
# ─────────────────────────────────────────────────────────────
def benchmark(n_vectors: int):
    print_header(f"Benchmark — {n_vectors:,} vectors · {DIM}-dim · {TOP_K} results")

    # ── Generate data ──────────────────────────────────────────
    print(f"\n  [1] Generating {n_vectors:,} unit-normalized float32 vectors...")
    corpus  = unit_vectors(n_vectors, DIM, seed=SEED)
    queries = unit_vectors(N_QUERIES, DIM, seed=SEED + 1)
    print(f"      Corpus  shape: {corpus.shape}  ({fmt_bytes(corpus.nbytes)})")
    print(f"      Queries shape: {queries.shape}")

    results = {}

    # ═══════════════════════════════════════════════════════════
    # INDEX 1: IndexFlatIP (ground truth)
    # ═══════════════════════════════════════════════════════════
    print_section("INDEX 1 — IndexFlatIP (Exact · Ground Truth)")
    flat_idx, flat_build = build_flatip(corpus)
    flat_scores, flat_ids = flat_idx.search(queries, TOP_K)
    flat_lat  = measure_query_latency(flat_idx, queries, TOP_K)
    flat_tput = measure_batch_throughput(flat_idx, queries, TOP_K)
    flat_size = index_size_bytes(flat_idx)

    print(f"      Build time    : {flat_build*1000:.1f} ms")
    print(f"      Index size    : {fmt_bytes(flat_size)}")
    print(f"      Recall@{TOP_K}    : 100.00% (exact — ground truth)")
    print(f"      Latency p50   : {flat_lat['p50_ms']} ms")
    print(f"      Latency p95   : {flat_lat['p95_ms']} ms")
    print(f"      Latency p99   : {flat_lat['p99_ms']} ms")
    print(f"      Mean latency  : {flat_lat['mean_ms']} ms")
    print(f"      QPS           : {flat_lat['qps']:,.0f}")
    print(f"      Batch tput    : {flat_tput:,.0f} vec/s")

    results["FlatIP"] = {
        "build_ms" : round(flat_build * 1000, 1),
        "size_bytes": flat_size,
        "recall"   : 1.0,
        **flat_lat,
        "throughput": flat_tput,
    }

    # ═══════════════════════════════════════════════════════════
    # INDEX 2: HNSW variants
    # ═══════════════════════════════════════════════════════════
    for M, ef_c, ef_s, label in [
        (16, 128, 64,  "HNSW-16 (fast, lower recall)"),
        (32, 200, 128, "HNSW-32 (balanced — production default)"),
        (64, 400, 256, "HNSW-64 (high recall, more RAM)"),
    ]:
        print_section(f"INDEX 2 — {label}")
        hnsw_idx, hnsw_build = build_hnsw(corpus, M=M,
                                           ef_construction=ef_c,
                                           ef_search=ef_s)
        hnsw_scores, hnsw_ids = hnsw_idx.search(queries, TOP_K)
        hnsw_recall = recall_at_k(flat_ids, hnsw_ids, TOP_K)
        hnsw_lat    = measure_query_latency(hnsw_idx, queries, TOP_K)
        hnsw_tput   = measure_batch_throughput(hnsw_idx, queries, TOP_K)
        hnsw_size   = index_size_bytes(hnsw_idx)

        print(f"      M={M}, ef_construction={ef_c}, ef_search={ef_s}")
        print(f"      Build time    : {hnsw_build*1000:.1f} ms")
        print(f"      Index size    : {fmt_bytes(hnsw_size)}")
        print(f"      Recall@{TOP_K}    : {hnsw_recall*100:.2f}%")
        print(f"      Latency p50   : {hnsw_lat['p50_ms']} ms")
        print(f"      Latency p95   : {hnsw_lat['p95_ms']} ms")
        print(f"      Latency p99   : {hnsw_lat['p99_ms']} ms")
        print(f"      Mean latency  : {hnsw_lat['mean_ms']} ms")
        print(f"      QPS           : {hnsw_lat['qps']:,.0f}")
        print(f"      Batch tput    : {hnsw_tput:,.0f} vec/s")

        results[f"HNSW-M{M}"] = {
            "build_ms"  : round(hnsw_build * 1000, 1),
            "size_bytes": hnsw_size,
            "recall"    : hnsw_recall,
            **hnsw_lat,
            "throughput": hnsw_tput,
        }
        del hnsw_idx; gc.collect()

    # ═══════════════════════════════════════════════════════════
    # INDEX 3: IVF-PQ variants
    # ═══════════════════════════════════════════════════════════
    for M_pq, nprobe, label in [
        (32,  16,  "IVF-PQ-32 (high compression, lower recall)"),
        (64,  32,  "IVF-PQ-64 (balanced — production default)"),
        (128, 64,  "IVF-PQ-128 (near-lossless, more RAM)"),
    ]:
        print_section(f"INDEX 3 — {label}")
        pq_idx, pq_build = build_ivfpq(corpus, M_pq=M_pq, nprobe=nprobe)
        pq_scores, pq_ids = pq_idx.search(queries, TOP_K)
        pq_recall  = recall_at_k(flat_ids, pq_ids, TOP_K)
        pq_lat     = measure_query_latency(pq_idx, queries, TOP_K)
        pq_tput    = measure_batch_throughput(pq_idx, queries, TOP_K)
        pq_size    = index_size_bytes(pq_idx)

        nlist = max(64, int(np.sqrt(n_vectors)))
        print(f"      nlist={nlist}, M_pq={M_pq}, nprobe={nprobe}, nbits=8")
        print(f"      Build time    : {pq_build*1000:.0f} ms")
        print(f"      Index size    : {fmt_bytes(pq_size)}")
        print(f"      Recall@{TOP_K}    : {pq_recall*100:.2f}%")
        print(f"      Latency p50   : {pq_lat['p50_ms']} ms")
        print(f"      Latency p95   : {pq_lat['p95_ms']} ms")
        print(f"      Latency p99   : {pq_lat['p99_ms']} ms")
        print(f"      Mean latency  : {pq_lat['mean_ms']} ms")
        print(f"      QPS           : {pq_lat['qps']:,.0f}")
        print(f"      Batch tput    : {pq_tput:,.0f} vec/s")

        results[f"IVFPQ-M{M_pq}"] = {
            "build_ms"  : round(pq_build * 1000, 1),
            "size_bytes": pq_size,
            "recall"    : pq_recall,
            **pq_lat,
            "throughput": pq_tput,
        }
        del pq_idx; gc.collect()

    # ═══════════════════════════════════════════════════════════
    # COMPARISON TABLE
    # ═══════════════════════════════════════════════════════════
    print_header(f"COMPARISON SUMMARY — {n_vectors:,} vectors")
    hdr = (f"  {'Index':<16} {'Build(ms)':>10} {'Size':>9} {'Recall':>8} "
           f"{'p50(ms)':>8} {'p95(ms)':>8} {'p99(ms)':>8} "
           f"{'QPS':>8} {'Tput(v/s)':>10}")
    print(hdr)
    print(f"  {'─'*95}")
    for name, r in results.items():
        print(
            f"  {name:<16} {r['build_ms']:>10,.0f} "
            f"{fmt_bytes(r['size_bytes']):>9} "
            f"{r['recall']*100:>7.2f}% "
            f"{r['p50_ms']:>8.3f} "
            f"{r['p95_ms']:>8.3f} "
            f"{r['p99_ms']:>8.3f} "
            f"{r['qps']:>8,.0f} "
            f"{r['throughput']:>10,.0f}"
        )

    return results


# ─────────────────────────────────────────────────────────────
# NPROBE SWEEP — show IVF-PQ recall/speed tradeoff
# ─────────────────────────────────────────────────────────────
def nprobe_sweep(n_vectors: int = 100_000):
    print_header(f"IVF-PQ nprobe Sweep — Recall vs Latency ({n_vectors:,} vecs)")
    corpus  = unit_vectors(n_vectors, DIM, seed=SEED)
    queries = unit_vectors(N_QUERIES, DIM, seed=SEED + 1)

    flat_idx = faiss.IndexFlatIP(DIM)
    flat_idx.add(corpus)
    _, flat_ids = flat_idx.search(queries, TOP_K)

    nlist = max(64, int(np.sqrt(n_vectors)))
    quantizer = faiss.IndexFlatIP(DIM)
    base_idx  = faiss.IndexIVFPQ(
        quantizer, DIM, nlist, 64, 8,
        faiss.METRIC_INNER_PRODUCT
    )
    print(f"  Training IVF-PQ (nlist={nlist})...")
    base_idx.train(corpus)
    base_idx.add(corpus)

    print(f"\n  {'nprobe':>8} {'Recall@10':>12} {'p50 ms':>10} {'p99 ms':>10} {'QPS':>10}")
    print(f"  {'─'*55}")
    for nprobe in [1, 4, 8, 16, 32, 64, 128, nlist]:
        base_idx.nprobe = nprobe
        _, pq_ids = base_idx.search(queries, TOP_K)
        rec = recall_at_k(flat_ids, pq_ids, TOP_K)
        lat = measure_query_latency(base_idx, queries, TOP_K)
        print(f"  {nprobe:>8} {rec*100:>11.2f}% {lat['p50_ms']:>10.3f} "
              f"{lat['p99_ms']:>10.3f} {lat['qps']:>10,.0f}")


# ─────────────────────────────────────────────────────────────
# HNSW efSearch SWEEP
# ─────────────────────────────────────────────────────────────
def ef_search_sweep(n_vectors: int = 100_000):
    print_header(f"HNSW efSearch Sweep — Recall vs Latency ({n_vectors:,} vecs)")
    corpus  = unit_vectors(n_vectors, DIM, seed=SEED)
    queries = unit_vectors(N_QUERIES, DIM, seed=SEED + 1)

    flat_idx = faiss.IndexFlatIP(DIM)
    flat_idx.add(corpus)
    _, flat_ids = flat_idx.search(queries, TOP_K)

    hnsw_idx = faiss.IndexHNSWFlat(DIM, 32, faiss.METRIC_INNER_PRODUCT)
    hnsw_idx.hnsw.efConstruction = 200
    hnsw_idx.add(corpus)

    print(f"\n  {'efSearch':>10} {'Recall@10':>12} {'p50 ms':>10} {'p99 ms':>10} {'QPS':>10}")
    print(f"  {'─'*57}")
    for ef in [16, 32, 64, 128, 256, 512]:
        hnsw_idx.hnsw.efSearch = ef
        _, h_ids = hnsw_idx.search(queries, TOP_K)
        rec = recall_at_k(flat_ids, h_ids, TOP_K)
        lat = measure_query_latency(hnsw_idx, queries, TOP_K)
        print(f"  {ef:>10} {rec*100:>11.2f}% {lat['p50_ms']:>10.3f} "
              f"{lat['p99_ms']:>10.3f} {lat['qps']:>10,.0f}")


# ─────────────────────────────────────────────────────────────
# PRODUCTION DECISION GUIDE
# ─────────────────────────────────────────────────────────────
def print_decision_guide():
    print_header("Production Decision Guide")
    guide = """
  ┌─ IndexFlatIP ──────────────────────────────────────────────────────────┐
  │  Use when: < 100K vectors, need 100% recall, generating ground truth   │
  │  Pros  : Exact results, zero config, no training, fast to build        │
  │  Cons  : Linear scan O(n) — latency grows with corpus size             │
  │  RAM   : n × d × 4 bytes  (1024-dim, 100K vecs = 400 MB)              │
  │  Code  : index = faiss.IndexFlatIP(dim); index.add(vecs)               │
  └────────────────────────────────────────────────────────────────────────┘

  ┌─ HNSW ─────────────────────────────────────────────────────────────────┐
  │  Use when: 100K–10M vectors, sub-5ms latency required, high recall     │
  │  Pros  : ~95-99% recall, very fast query, no training required         │
  │  Cons  : High RAM (graph edges), slow to build at large scale          │
  │  RAM   : ~1.1× FlatIP RAM + graph overhead (~M × n × 4 bytes)         │
  │  Tune  : M=32, ef_construction=200, ef_search=128 → good default      │
  │  Code  : index = faiss.IndexHNSWFlat(dim, M, METRIC_INNER_PRODUCT)    │
  └────────────────────────────────────────────────────────────────────────┘

  ┌─ IVF-PQ ───────────────────────────────────────────────────────────────┐
  │  Use when: > 1M vectors, memory-constrained, GPU acceleration needed   │
  │  Pros  : Lowest RAM (~32x compression), GPU-compatible, scalable       │
  │  Cons  : ~85-95% recall, requires training, nprobe tuning needed       │
  │  RAM   : n × M_pq bytes  (1024-dim M=64, 1M vecs = 64 MB!)            │
  │  Tune  : nlist=sqrt(n), nprobe=32, M_pq=DIM//16                       │
  │  Code  : quantizer = faiss.IndexFlatIP(dim)                            │
  │          index = faiss.IndexIVFPQ(quantizer, dim, nlist, M_pq, nbits) │
  │          index.train(sample); index.add(vecs)                          │
  └────────────────────────────────────────────────────────────────────────┘

  Quick pick:
    < 100K  vectors  →  IndexFlatIP  (exact, zero ops)
    100K–5M vectors  →  HNSW M=32    (fast, high recall, ~5ms)
    > 5M    vectors  →  IVF-PQ M=64  (compressed, GPU-ready, ~10ms)
    Memory critical  →  IVF-PQ       (32x smaller than FlatIP)
    Recall critical  →  FlatIP > HNSW > IVF-PQ
    Speed critical   →  IVF-PQ > HNSW > FlatIP (at scale)
    """
    print(guide)


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    all_results = {}

    for n in SIZES:
        r = benchmark(n)
        all_results[n] = r

    # ── Parameter sweeps on 100K ──────────────────────────────
    nprobe_sweep(100_000)
    ef_search_sweep(100_000)

    # ── Decision guide ────────────────────────────────────────
    print_decision_guide()

    # ── Cross-scale summary ───────────────────────────────────
    print_header("CROSS-SCALE SUMMARY — Mean Latency (ms) per Index Type")
    print(f"\n  {'Index':<16} {'10K vecs':>12} {'100K vecs':>12} {'500K vecs':>12}")
    print(f"  {'─'*55}")
    for key in ["FlatIP", "HNSW-M32", "IVFPQ-M64"]:
        row = f"  {key:<16}"
        for n in SIZES:
            v = all_results[n].get(key, {}).get("mean_ms", "N/A")
            row += f"  {str(v):>10}"
        print(row)

    print(f"\n  {'Index':<16} {'10K vecs':>12} {'100K vecs':>12} {'500K vecs':>12}")
    print(f"  {'─'*55}")
    print("  Recall@10 (vs FlatIP ground truth):")
    for key in ["FlatIP", "HNSW-M32", "IVFPQ-M64"]:
        row = f"  {key:<16}"
        for n in SIZES:
            v = all_results[n].get(key, {}).get("recall", None)
            row += f"  {v*100:>9.2f}%" if v is not None else "       N/A"
        print(row)

    print()