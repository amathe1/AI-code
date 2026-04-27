import json
import os

from utils.config_loader import load_config
from utils.logger import setup_logger

config = load_config()
logger = setup_logger(config["paths"]["logs"])


def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []

    step = chunk_size - overlap

    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    return chunks


def run_chunking():
    input_path = config["paths"]["data_json"]
    output_path = config["paths"]["chunks_json"]

    if not os.path.exists(input_path):
        raise FileNotFoundError("Run data extraction first")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_chunks = []

    for item in data:
        chunks = chunk_text(item["text"])

        for chunk in chunks:
            all_chunks.append({
                "content": chunk,
                "metadata": {
                    "page": item["page"]
                }
            })

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2)

    logger.info(f"✅ Chunking complete: {len(all_chunks)} chunks created")