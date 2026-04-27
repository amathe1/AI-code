import json
import os

from utils.config_loader import load_config
from utils.logger import setup_logger

from services.pgvector_service import create_table, insert_embedding

config = load_config()
logger = setup_logger(config["paths"]["logs"])


def run_pgvector_ingestion():
    input_path = config["paths"]["embeddings_json"]

    if not os.path.exists(input_path):
        raise FileNotFoundError("Run embeddings first")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info("🗄️ Setting up PGVector table...")
    create_table()

    logger.info("📦 Inserting embeddings into DB...")

    for i, item in enumerate(data):
        try:
            insert_embedding(
                content=item["content"],
                embedding=item["embedding"],
                metadata=item["metadata"]
            )

            if i % 50 == 0:
                logger.info(f"Inserted {i}/{len(data)} rows")

        except Exception as e:
            logger.error(f"Insert failed at index {i}: {e}")

    logger.info("✅ PGVector ingestion completed")