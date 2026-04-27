import json
import os
from utils.config_loader import load_config
from utils.logger import setup_logger
from services.embedding_service import generate_embedding
from services.pgvector_service import search_similar

config = load_config()
logger = setup_logger(config["paths"]["logs"])


# -----------------------
# Keyword Search (BM25-lite)
# -----------------------
def keyword_search(query, documents, top_k=5):
    query_tokens = query.split()

    results = []

    for doc in documents:
        content = doc["content"].lower()
        content_tokens = content.split()

        score = sum(1 for token in query_tokens if token in content_tokens)

        results.append({
            "content": doc["content"],
            "metadata": doc["metadata"],
            "score": score
        })

    results = sorted(results, key=lambda x: x["score"], reverse=True)
    return results[:top_k]


# -----------------------
# Load chunked documents
# -----------------------
def load_documents():
    path = config["paths"]["chunks_json"]

    if not os.path.exists(path):
        raise FileNotFoundError("Chunks file not found. Run indexing first.")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# -----------------------
# Hybrid Search
# -----------------------
def hybrid_search(query: str):
    try:
        top_k = config["search"]["top_k"]

        # --- Vector Search ---
        query_embedding = generate_embedding(query)
        vector_results = search_similar(query_embedding, top_k=top_k)

        # --- Keyword Search ---
        documents = load_documents()
        keyword_results = keyword_search(query, documents, top_k=top_k)

        # --- Combine results ---
        combined = {}

        for item in vector_results:
            combined[item["content"]] = item

        for item in keyword_results:
            if item["content"] in combined:
                combined[item["content"]]["score"] += item["score"]
            else:
                combined[item["content"]] = item

        final_results = sorted(
            combined.values(),
            key=lambda x: x["score"],
            reverse=True
        )

        logger.info(f"Retrieved {len(final_results)} results")

        return final_results[:top_k]

    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        return []