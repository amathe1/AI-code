import re

def normalize_query(query: str) -> str:
    query = query.lower().strip()
    query = re.sub(r"\s+", " ", query)
    return query