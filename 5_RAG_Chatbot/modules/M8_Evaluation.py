# import json
# from utils.config_loader import load_config
# from utils.logger import setup_logger

# config = load_config()
# logger = setup_logger(config["paths"]["logs"])


# def calculate_precision(retrieved, relevant):
#     return len(set(retrieved) & set(relevant)) / len(retrieved) if retrieved else 0


# def calculate_recall(retrieved, relevant):
#     return len(set(retrieved) & set(relevant)) / len(relevant) if relevant else 0


# def calculate_mrr(retrieved, relevant):
#     for i, doc in enumerate(retrieved):
#         if doc in relevant:
#             return 1 / (i + 1)
#     return 0


# def evaluate(query, retrieved_docs):
#     try:
#         with open(config["paths"]["golden_dataset"], "r") as f:
#             golden = json.load(f)

#         if query not in golden:
#             return {}

#         relevant_docs = golden[query]
#         retrieved_contents = [doc["content"] for doc in retrieved_docs]

#         metrics = {
#             "precision": calculate_precision(retrieved_contents, relevant_docs),
#             "recall": calculate_recall(retrieved_contents, relevant_docs),
#             "mrr": calculate_mrr(retrieved_contents, relevant_docs),
#         }

#         logger.info(f"Evaluation metrics: {metrics}")
#         return metrics

#     except Exception as e:
#         logger.error(f"Evaluation failed: {e}")
#         return {}

def evaluate_single(query, retrieved_chunks, generated_answer):
    """
    Lightweight evaluation (no golden dataset)
    Used for testing via UI
    """

    try:
        answer = generated_answer.lower()
        chunks_text = " ".join(
            [c.get("content", "").lower() for c in retrieved_chunks]
        )

        # Simple keyword signals
        keywords = ["return", "policy", "refund", "embedding", "vector"]

        keyword_hits = sum(1 for k in keywords if k in chunks_text)

        precision = min(1.0, keyword_hits / len(keywords))
        recall = precision  # simplified

        answer_score = 1.0 if any(k in answer for k in keywords) else 0.0

        metrics = {
            "precision": precision,
            "recall": recall,
            "answer_score": answer_score,
            "context_relevance": context_relevance(query, retrieved_chunks),
            "answer_relevance": answer_relevance(query, generated_answer),
            "groundedness": groundedness(generated_answer, retrieved_chunks)
            }

        return metrics

    except Exception as e:
        return {}

def context_relevance(query, retrieved_chunks):
    q_words = set(query.lower().split())

    scores = []
    for c in retrieved_chunks:
        chunk_words = set(c.get("content", "").lower().split())
        overlap = len(q_words & chunk_words)
        scores.append(overlap / len(q_words) if q_words else 0)

    return round(sum(scores) / len(scores), 3) if scores else 0


def answer_relevance(query, answer):
    q_words = set(query.lower().split())
    a_words = set(answer.lower().split())

    overlap = len(q_words & a_words)

    return round(overlap / len(q_words), 3) if q_words else 0


def groundedness(answer, retrieved_chunks):
    answer_words = set(answer.lower().split())

    chunk_text = " ".join(
        [c.get("content", "").lower() for c in retrieved_chunks]
    )
    chunk_words = set(chunk_text.split())

    overlap = len(answer_words & chunk_words)

    return round(overlap / len(answer_words), 3) if answer_words else 0

