import re
from utils.config_loader import load_config
from utils.logger import setup_logger

config = load_config()
logger = setup_logger(config["paths"]["logs"])

INVALID_PATTERNS = [
    r"\b(weather|temperature|news|stock|cricket|sports)\b",
]

def normalize_query(query: str) -> str:
    query = query.lower().strip()
    query = re.sub(r"\s+", " ", query)
    return query

def is_valid_query(query: str) -> bool:
    for pattern in INVALID_PATTERNS:
        if re.search(pattern, query):
            return False
    return True

def process_query(query: str):
    try:
        normalized_query = normalize_query(query)

        if not is_valid_query(normalized_query):
            logger.warning(f"Invalid query detected: {query}")
            return {
                "valid": False,
                "query": normalized_query,
                "message": "❌ Query not related to the document."
            }

        return {
            "valid": True,
            "query": normalized_query
        }

    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        return {
            "valid": False,
            "query": query,
            "message": "Error processing query."
        }