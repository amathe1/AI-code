import os
import time

from utils.config_loader import load_config
from utils.logger import setup_logger
from utils.docker_manager import start_docker_services

from modules.M1_DataExtraction_Processing import run_data_extraction
from modules.M2_Chunking import run_chunking
from modules.M3_Embeddings import run_embeddings
from modules.M4_PGVectorDB import run_pgvector_ingestion

from modules.M5_QueryProcessing import process_query
from modules.M6_AccessControls import validate_user
from modules.M9_RedisCache import get_cached_response, set_cached_response
from modules.M8_Evaluation import evaluate_single  # ✅ NEW

from services.embedding_service import generate_embedding
from services.pgvector_service import search_hnsw
from services.llm_service import generate_response

from utils.scoring import citation_score

config = load_config()
logger = setup_logger(config["paths"]["logs"])


# -------------------------------
# STANDARD RESPONSE TEMPLATE
# -------------------------------
def base_response(query):
    return {
        "query": query,
        "answer": "",
        "chunks": [],
        "source": "",
        "timing": {
            "embed_ms": 0.0,
            "search_ms": 0.0,
            "gen_ms": 0.0,
            "total_ms": 0.0
        },
        "lineage": [],
        "metrics": {},   # ✅ ALWAYS PRESENT
        "error": None
    }


# -------------------------------
# INDEXING PIPELINE
# -------------------------------
def run_indexing_pipeline():
    flag_file = config["indexing"]["index_flag_file"]

    if os.path.exists(flag_file):
        return

    logger.info("Running indexing pipeline...")

    run_data_extraction()
    run_chunking()
    run_embeddings()
    run_pgvector_ingestion()

    with open(flag_file, "w") as f:
        f.write("done")

    logger.info("Indexing completed")


# -------------------------------
# MAIN RAG PIPELINE
# -------------------------------
def run_rag_pipeline(query: str, username=None, password=None, top_k=5, ef=100):

    result = base_response(query)
    start_total = time.time()

    def log_step(name, start, detail="", output=""):
        result["lineage"].append({
            "step": name,
            "ms": round((time.time() - start) * 1000, 2),
            "detail": detail,
            "output": output
        })

    try:
        # =========================================
        # 🚀 1. CACHE CHECK (FAST PATH)
        # =========================================
        t = time.time()
        cached = get_cached_response(query)

        if cached:
            cached["source"] = "redis_cache"

            cache_time = round((time.time() - t) * 1000, 2)
            cached["timing"]["total_ms"] = cache_time

            cached.setdefault("lineage", []).append({
                "step": "Cache Hit",
                "ms": cache_time
            })

            return cached

        log_step("Cache Miss", t)

        # =========================================
        # 2. DOCKER INIT (only if enabled)
        # =========================================
        t = time.time()
        start_docker_services()
        log_step("Docker Init", t)

        # =========================================
        # 3. INDEXING
        # =========================================
        t = time.time()
        if config["indexing"]["run_on_startup"]:
            run_indexing_pipeline()
        log_step("Indexing Check", t)

        # =========================================
        # 4. QUERY PROCESSING
        # =========================================
        t = time.time()
        qp = process_query(query)
        log_step("Query Processing", t)

        if not qp["valid"]:
            result["answer"] = qp["message"]
            result["source"] = "validation"
            return result

        # =========================================
        # 5. ACCESS CONTROL
        # =========================================
        t = time.time()
        if not validate_user(username, password):
            result["answer"] = "❌ Unauthorized access"
            result["source"] = "auth"
            return result
        log_step("Access Control", t)

        # =========================================
        # 6. EMBEDDING
        # =========================================
        t = time.time()
        embedding = generate_embedding(qp["query"])
        result["timing"]["embed_ms"] = round((time.time() - t) * 1000, 2)
        log_step("Embedding", t)

        # =========================================
        # 7. HNSW SEARCH
        # =========================================
        t = time.time()
        docs = search_hnsw(embedding, ["public"], top_k=top_k, ef=ef)
        result["timing"]["search_ms"] = round((time.time() - t) * 1000, 2)
        log_step("HNSW Search", t, output=f"{len(docs)} docs")

        if not docs:
            result["answer"] = "No relevant information found."
            result["source"] = "search"
            return result

        # =========================================
        # 8. RERANK
        # =========================================
        t = time.time()
        docs = sorted(docs, key=lambda x: x["score"], reverse=True)[:top_k]
        log_step("Reranking", t)

        # =========================================
        # 9. CONTEXT BUILD
        # =========================================
        t = time.time()
        context = "\n\n".join([d["content"] for d in docs])
        log_step("Context Build", t)

        # =========================================
        # 10. LLM GENERATION
        # =========================================
        t = time.time()
        prompt = f"""
Answer ONLY using the context below.

Context:
{context}

Question:
{query}
"""
        answer = generate_response(prompt)
        result["timing"]["gen_ms"] = round((time.time() - t) * 1000, 2)
        log_step("LLM Generation", t)

        result["answer"] = answer
        result["chunks"] = docs
        result["source"] = "pgvector"

        # =========================================
        # 11. CITATION SCORING
        # =========================================
        for d in result["chunks"]:
            d["citation_score"] = citation_score(answer, d["content"])

        # =========================================
        # 12. ✅ EVALUATION METRICS
        # =========================================
        if config.get("evaluation", {}).get("enabled", False):
            try:
                metrics = evaluate_single(
                    query,
                    result["chunks"],
                    result["answer"]
                )
                result["metrics"] = metrics
            except Exception as e:
                logger.warning(f"Evaluation failed: {e}")
                result["metrics"] = {}

        # =========================================
        # 13. TOTAL TIME
        # =========================================
        result["timing"]["total_ms"] = round((time.time() - start_total) * 1000, 2)

        # =========================================
        # 14. CACHE STORE
        # =========================================
        set_cached_response(query, result)

        return result

    except Exception as e:
        logger.error(f"RAG pipeline failed: {e}")
        result["answer"] = "System error occurred"
        result["error"] = str(e)
        return result