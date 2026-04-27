from services.redis_service import get_cache, set_cache
from utils.helpers import normalize_query

def get_cached_response(query: str):
    return get_cache(normalize_query(query))

def set_cached_response(query: str, response: dict):
    set_cache(normalize_query(query), response)