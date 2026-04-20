"""
Module 03 — OpenAI Embeddings
================================
Model  : text-embedding-3-small (1536-dim)
Cost   : Tracked per token and in aggregate
Output : embeddings.json  (chunks + real OpenAI vectors)

Run:
    export OPENAI_API_KEY="sk-..."
    cd rag_system && python 03_embeddings.py
"""

import os, json, time, math, sys
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBED_MODEL    = "text-embedding-3-small"
EMBED_DIM      = 1536
PRICE_PER_1M   = 0.020   # $0.020 per 1M tokens
BATCH_SIZE     = 100      # max inputs per API call

DATA_PATH = Path(__file__).parent / "chunks.json"
OUT_PATH  = Path(__file__).parent / "embeddings.json"


# ── Token counter ─────────────────────────────────────────────────────────────
def count_tokens(text: str) -> int:
    try:
        import tiktoken
        return len(tiktoken.encoding_for_model("text-embedding-3-small").encode(text))
    except Exception:
        return int(len(text.split()) * 1.3)


# ── Embeddings ────────────────────────────────────────────────────────────────
def embed_openai(texts: list[str]) -> tuple[list[list[float]], int, float]:
    """
    Call OpenAI text-embedding-3-small.
    Returns (vectors, total_tokens, cost_usd).
    Raises if API key is missing or call fails — no silent fallback.
    """
    if not OPENAI_API_KEY:
        print("\n  [ERROR] OPENAI_API_KEY is not set.")
        print("  Export it first:")
        print('  export OPENAI_API_KEY="sk-..."')
        print("  Then re-run: python 03_embeddings.py")
        sys.exit(1)

    import openai
    client   = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    tokens   = response.usage.total_tokens
    cost     = round(tokens / 1_000_000 * PRICE_PER_1M, 8)
    vectors  = [e.embedding for e in response.data]
    return vectors, tokens, cost


def cosine_sim(a: list[float], b: list[float]) -> float:
    a_arr, b_arr = np.array(a), np.array(b)
    return float(np.dot(a_arr, b_arr) /
                 (np.linalg.norm(a_arr) * np.linalg.norm(b_arr) + 1e-9))


# ── Main ─────────────────────────────────────────────────────────────────────
def run():
    print("=" * 60)
    print("  MODULE 03 — OpenAI Embedding Generation")
    print("=" * 60)

    if not OPENAI_API_KEY:
        print("\n  [ERROR] OPENAI_API_KEY environment variable is not set.")
        print("  Set it with:")
        print('    export OPENAI_API_KEY="sk-..."')
        print("  Then re-run this module.")
        sys.exit(1)

    print(f"\n  API key  : sk-...{OPENAI_API_KEY[-6:]}")
    print(f"  Model    : {EMBED_MODEL}  ({EMBED_DIM} dims)")
    print(f"  Price    : ${PRICE_PER_1M}/1M tokens")

    data   = json.loads(DATA_PATH.read_text())
    chunks = data["chunks"]
    texts  = [c["text"] for c in chunks]
    batches = math.ceil(len(texts) / BATCH_SIZE)

    # Estimate cost before calling API
    est_tokens = sum(count_tokens(t) for t in texts)
    est_cost   = round(est_tokens / 1_000_000 * PRICE_PER_1M, 6)
    print(f"\n  Chunks   : {len(texts)}")
    print(f"  Est. tokens : {est_tokens:,}")
    print(f"  Est. cost   : ${est_cost:.6f}")

    print(f"\n  Embedding {len(texts)} chunks in {batches} batch(es)...")

    all_vecs   : list[list[float]] = []
    total_tok  = 0
    total_cost = 0.0
    t0         = time.perf_counter()

    for i in range(0, len(texts), BATCH_SIZE):
        batch    = texts[i : i + BATCH_SIZE]
        batch_n  = i // BATCH_SIZE + 1

        try:
            vecs, tok, cost = embed_openai(batch)
        except Exception as e:
            print(f"\n  [ERROR] OpenAI API call failed on batch {batch_n}: {e}")
            sys.exit(1)

        all_vecs.extend(vecs)
        total_tok  += tok
        total_cost += cost
        print(f"    Batch {batch_n}/{batches}: {len(batch)} chunks  "
              f"{tok:,} tokens  ${cost:.6f}")

    elapsed = (time.perf_counter() - t0) * 1000

    # Attach vectors to chunks
    for chunk, vec in zip(chunks, all_vecs):
        chunk["embedding"] = vec

    # Quality checks
    norms    = [np.linalg.norm(v) for v in all_vecs]
    avg_norm = float(np.mean(norms))

    # Spot-check: semantically similar chunks should score higher
    spot = []
    if len(all_vecs) >= 4:
        # Same section similarity (should be higher)
        same_sec_pairs = [(i, j) for i in range(len(chunks))
                          for j in range(i+1, len(chunks))
                          if chunks[i]["section_id"] == chunks[j]["section_id"]]
        diff_sec_pairs = [(i, j) for i in range(len(chunks))
                          for j in range(i+1, len(chunks))
                          if chunks[i]["section_id"] != chunks[j]["section_id"]]

        if same_sec_pairs:
            i, j = same_sec_pairs[0]
            sim = cosine_sim(all_vecs[i], all_vecs[j])
            spot.append((f"Same section  ({chunks[i]['section_id']})", round(sim, 4)))

        if diff_sec_pairs:
            i, j = diff_sec_pairs[0]
            sim = cosine_sim(all_vecs[i], all_vecs[j])
            spot.append((f"Diff sections ({chunks[i]['section_id']} vs "
                          f"{chunks[j]['section_id']})", round(sim, 4)))

    print(f"\n  Embedding Metrics")
    print(f"    Model                 : {EMBED_MODEL}")
    print(f"    Dimensions            : {EMBED_DIM}")
    print(f"    Total chunks          : {len(chunks)}")
    print(f"    Total tokens          : {total_tok:,}")
    print(f"    Actual cost           : ${total_cost:.6f}")
    print(f"    Elapsed               : {elapsed:.0f} ms")
    print(f"    Throughput            : {len(texts) / (elapsed/1000):.0f} chunks/s")
    print(f"    Avg vector norm       : {avg_norm:.4f}  (should be ~1.0)")

    if spot:
        print(f"\n  Spot-check cosine similarity:")
        for label, sim in spot:
            print(f"    {label}: {sim:.4f}")
        if len(spot) == 2:
            if spot[0][1] > spot[1][1]:
                print(f"    ✓ Same-section > diff-section — embeddings are semantic")
            else:
                print(f"    ⚠ Same-section <= diff-section — check chunking quality")

    output = {
        "model"         : EMBED_MODEL,
        "dim"           : EMBED_DIM,
        "total_cost_usd": round(total_cost, 8),
        "total_tokens"  : total_tok,
        "elapsed_ms"    : round(elapsed, 1),
        "embedding_type": "openai_real",
        "stats": {
            "total_chunks"   : len(chunks),
            "avg_vector_norm": round(avg_norm, 4),
            "price_per_1m"   : PRICE_PER_1M,
        },
        "chunks": chunks,
    }

    OUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"\n  Saved → {OUT_PATH}")
    print(f"  embedding_type = openai_real  (real vectors, not mock)")
    return output


if __name__ == "__main__":
    run()