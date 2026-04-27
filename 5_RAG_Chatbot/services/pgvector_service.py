import json
import psycopg2
from utils.config_loader import load_config

config = load_config()

def get_connection():
    return psycopg2.connect(
        host=config["pgvector"]["host"],
        port=config["pgvector"]["port"],
        dbname=config["pgvector"]["db"],
        user=config["pgvector"]["user"],
        password=config["pgvector"]["password"]
    )


def create_table():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE EXTENSION IF NOT EXISTS vector;

        CREATE TABLE IF NOT EXISTS document_embeddings (
            id SERIAL PRIMARY KEY,
            content TEXT,
            embedding vector(1536),
            metadata JSONB
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


def insert_embedding(content, embedding, metadata):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
    "INSERT INTO document_embeddings (content, embedding, metadata) VALUES (%s, %s, %s)",
    (content, embedding, json.dumps(metadata))
    )

    conn.commit()
    cur.close()
    conn.close()


def search_similar(query_embedding, top_k=5):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT content, metadata,
        1 - (embedding <=> %s::vector) AS similarity
        FROM document_embeddings
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """,
        (query_embedding, query_embedding, top_k)
    )

    results = cur.fetchall()

    cur.close()
    conn.close()

    return [
        {
            "content": r[0],
            "metadata": r[1],
            "score": float(r[2])
        }
        for r in results
    ]

def search_hnsw(query_embedding, access_levels, top_k=5, ef=100):
    conn = get_connection()
    cur = conn.cursor()

    vec = "[" + ",".join(map(str, query_embedding)) + "]"

    cur.execute(f"SET hnsw.ef_search = {ef};")

    cur.execute("""
        SELECT content, metadata,
        1 - (embedding <=> %s::vector) AS score
        FROM document_embeddings
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """, (vec, vec, top_k))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [
        {
            "content": r[0],
            "metadata": r[1],
            "score": float(r[2])
        }
        for r in rows
    ]