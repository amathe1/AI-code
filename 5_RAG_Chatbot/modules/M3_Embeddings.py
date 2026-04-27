import json
import os

from utils.config_loader import load_config
from utils.logger import setup_logger
from utils.retry import retry

from services.embedding_service import generate_embedding

config = load_config()
logger = setup_logger(config["paths"]["logs"])


@retry(max_attempts=3)
def embed_text(text):
    return generate_embedding(text)


def run_embeddings():
    input_path = config["paths"]["chunks_json"]
    output_path = config["paths"]["embeddings_json"]

    if not os.path.exists(input_path):
        raise FileNotFoundError("Run chunking first")

    with open(input_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    embedded_data = []

    logger.info("🧠 Generating embeddings...")

    for i, item in enumerate(chunks):
        try:
            embedding = embed_text(item["content"])

            embedded_data.append({
                "content": item["content"],
                "embedding": embedding,
                "metadata": item["metadata"]
            })

            if i % 50 == 0:
                logger.info(f"Processed {i}/{len(chunks)} chunks")

        except Exception as e:
            logger.error(f"Embedding failed at index {i}: {e}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(embedded_data, f)

    logger.info(f"✅ Embeddings complete: {len(embedded_data)} vectors created")