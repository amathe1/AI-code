import redis
import json
from utils.config_loader import load_config

config = load_config()

def get_redis_client():
    try:
        return redis.Redis(
            host=config["redis"]["host"],
            port=config["redis"]["port"],
            db=config["redis"]["db"],
            decode_responses=True
        )
    except Exception:
        return None


def get_cache(key: str):
    client = get_redis_client()
    if not client:
        return None

    value = client.get(key)
    return json.loads(value) if value else None


def set_cache(key: str, value):
    client = get_redis_client()
    if not client:
        return

    client.setex(
        key,
        config["redis"]["ttl_seconds"],
        json.dumps(value)
    )