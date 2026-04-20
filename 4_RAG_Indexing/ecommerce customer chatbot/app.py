"""
Module 05 — Streamlit RAG Dashboard
=====================================
Data source : pgvector (HNSW search) → Redis cache (repeated queries)

Run:
    cd rag_system && streamlit run 05_streamlit_dashboard.py
"""

import os, sys, json, time, hashlib
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# ── .env loader ───────────────────────────────────────────────────────────────
# ENV_PATH = Path(__file__).parent / ".env"

# def load_env(path):
#     if not path.exists(): return {}
#     loaded = {}
#     with open(path) as f:
#         for line in f:
#             line = line.strip()
#             if not line or line.startswith("#") or "=" not in line:
#                 continue
#             k, _, v = line.partition("=")
#             k = k.strip(); v = v.strip()
#             if " #" in v:
#                 v = v[:v.index(" #")].strip()
#             if len(v) >= 2 and v[0] in ('"', "'") and v[0] == v[-1]:
#                 v = v[1:-1]
#             if k and k not in os.environ:
#                 os.environ[k] = v
#                 loaded[k] = v
#     return loaded

# load_env(ENV_PATH)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_HOST    = os.getenv("PGVECTOR_HOST", "localhost")
DB_PORT    = int(os.getenv("PGVECTOR_PORT", "5432"))
DB_NAME    = os.getenv("PGVECTOR_DB",   "ecommerce_rag")
DB_USER    = os.getenv("PGVECTOR_USER", "raguser")
DB_PASS    = os.getenv("PGVECTOR_PASS", "ragpass123")
REDIS_HOST = os.getenv("REDIS_HOST",   "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CACHE_TTL  = 3600

import streamlit as st

st.set_page_config(
    page_title="ShopNow RAG",
    page_icon="🛒",
    layout="wide",
)

st.markdown("""
<style>
.hit-badge  {background:#16a34a;color:white;padding:4px 12px;
             border-radius:12px;font-size:13px;font-weight:700;}
.miss-badge {background:#2563eb;color:white;padding:4px 12px;
             border-radius:12px;font-size:13px;font-weight:700;}
.score-high {color:#16a34a;font-weight:700;}
.score-mid  {color:#d97706;font-weight:700;}
.score-low  {color:#dc2626;font-weight:700;}
.source-tag {background:#eff6ff;color:#1d4ed8;padding:2px 8px;
             border-radius:6px;font-size:12px;font-weight:600;margin-right:6px;}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# CONNECTIONS  (built once, cached for the session)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def init_pgvector():
    """Connect to pgvector and register the vector type."""
    errors = []
    if not OPENAI_API_KEY or OPENAI_API_KEY in ("sk-...your-key-here...", "YOUR_OPENAI_API_KEY", ""):
        errors.append("OPENAI_API_KEY is missing or is a placeholder in .env")
    try:
        import psycopg2
        from pgvector.psycopg2 import register_vector
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            dbname=DB_NAME, user=DB_USER, password=DB_PASS,
            connect_timeout=5,
        )
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM document_chunks;")
            count = cur.fetchone()[0]
        if count == 0:
            errors.append("document_chunks table is empty — run python 04_pgvector.py")
            return None, count, errors
        return conn, count, errors
    except ImportError:
        errors.append("psycopg2 or pgvector package not installed — run: pip install psycopg2-binary pgvector")
        return None, 0, errors
    except Exception as e:
        errors.append(f"pgvector connection failed: {e}")
        errors.append(f"  Make sure Docker container is running:")
        errors.append(f"  docker run -d --name pgvector_rag -e POSTGRES_DB=ecommerce_rag -e POSTGRES_USER=raguser -e POSTGRES_PASSWORD=ragpass123 -p 5432:5432 pgvector/pgvector:pg16")
        errors.append(f"  Then run: python 04_pgvector.py")
        return None, 0, errors


@st.cache_resource(show_spinner=False)
def init_redis():
    try:
        import redis
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT,
                        socket_timeout=1, decode_responses=True)
        r.ping()
        return r, None
    except Exception as e:
        return None, str(e)


@st.cache_resource(show_spinner=False)
def init_openai():
    if not OPENAI_API_KEY or OPENAI_API_KEY in ("sk-...your-key-here...", "YOUR_OPENAI_API_KEY", ""):
        return None, "OPENAI_API_KEY not set in .env"
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        # Quick test call
        client.models.list()
        return client, None
    except Exception as e:
        return None, str(e)


# ─────────────────────────────────────────────────────────────────────────────
# CACHE HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def make_cache_key(query: str, access: list, k: int) -> str:
    payload = f"{query.lower().strip()}|{','.join(sorted(access))}|{k}"
    return "rag:" + hashlib.sha256(payload.encode()).hexdigest()[:32]


def redis_get(r, key):
    if r is None: return None
    try:
        raw = r.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def redis_set(r, key, value):
    if r is None: return
    try:
        r.setex(key, CACHE_TTL, json.dumps(value))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# CORE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
def embed_query(text: str, client) -> list:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=[text],
    )
    return response.data[0].embedding


def pgvector_search(conn, qvec: list, access: list, k: int, ef: int = 100) -> list[dict]:
    vec = f"[{','.join(str(round(x, 8)) for x in qvec)}]"
    with conn.cursor() as cur:
        cur.execute(f"SET hnsw.ef_search = {ef};")
        cur.execute("""
            SELECT
                chunk_id,
                section_id,
                section_title,
                text,
                access_level,
                token_count,
                1 - (embedding <=> %s::vector) AS score
            FROM document_chunks
            WHERE access_level = ANY(%s)
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (vec, access, vec, k))
        rows = cur.fetchall()
    return [
        {
            "chunk_id"      : r[0],
            "section_id"    : r[1],
            "section_title" : r[2],
            "text"          : r[3],
            "access_level"  : r[4],
            "token_count"   : r[5],
            "score"         : round(float(r[6]), 4),
        }
        for r in rows
    ]


ANSWER_PROMPT = """You are a ShopNow e-commerce customer service assistant.
Answer the customer question using ONLY the context provided.
Be concise, specific, and include exact numbers, timeframes, and conditions.
If the answer is not in the context, say: "I don't have that information in the knowledge base."

Context:
{context}

Customer Question: {question}

Answer:"""


def generate_answer(question: str, chunks: list, client) -> tuple[str, float]:
    context = "\n\n".join(
        f"[Source: {c['section_title']}]\n{c['text']}"
        for c in chunks[:3]
    )
    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model       = "gpt-4o-mini",
        messages    = [{"role": "user",
                        "content": ANSWER_PROMPT.format(
                            context=context, question=question)}],
        temperature = 0.1,
        max_tokens  = 500,
    )
    gen_ms = (time.perf_counter() - t0) * 1000
    return resp.choices[0].message.content.strip(), round(gen_ms, 1)


def citation_score(answer: str, chunk_text: str) -> float:
    ans_w   = set(w for w in answer.lower().split() if len(w) > 3)
    chunk_w = set(w for w in chunk_text.lower().split() if len(w) > 3)
    if not ans_w: return 0.0
    return round(len(ans_w & chunk_w) / len(ans_w), 3)


def score_css(score: float) -> str:
    if score >= 0.60: return "score-high"
    if score >= 0.35: return "score-mid"
    return "score-low"


# ─────────────────────────────────────────────────────────────────────────────
# FULL RAG PIPELINE
# ─────────────────────────────────────────────────────────────────────────────
def run_rag_pipeline(query: str, access: list, k: int, ef: int,
                     conn, r_conn, client) -> dict:
    key      = make_cache_key(query, access, k)
    t_all    = time.perf_counter()
    lineage  = []   # list of step dicts — the full execution trace

    def step(name: str, icon: str, detail: str, start: float,
             status: str = "ok", output: str = "") -> float:
        """Record a lineage step and return current time."""
        now = time.perf_counter()
        lineage.append({
            "step"    : name,
            "icon"    : icon,
            "detail"  : detail,
            "ms"      : round((now - start) * 1000, 2),
            "status"  : status,   # ok | hit | miss | skip | error
            "output"  : output,
        })
        return now

    # ── Step 1: Parse & validate query ───────────────────────────────────────
    t0 = time.perf_counter()
    q_len = len(query.split())
    step("Parse & Validate Query", "📝",
         f"{q_len} words · access={access} · top_k={k} · ef={ef}",
         t0, "ok", f"Query accepted ({q_len} words)")

    # ── Step 2: Build cache key ───────────────────────────────────────────────
    t0 = time.perf_counter()
    step("Build Cache Key", "🔑",
         f"SHA256(query + access + k) → {key}",
         t0, "ok", key)

    # ── Step 3: Redis cache lookup ────────────────────────────────────────────
    t0     = time.perf_counter()
    cached = redis_get(r_conn, key)
    if r_conn is None:
        step("Redis Cache Lookup", "💾",
             "Redis not connected — skipping cache",
             t0, "skip", "no cache")
    elif cached:
        step("Redis Cache Lookup", "💾",
             f"HIT — key={key[:20]}... — returning cached result",
             t0, "hit", "CACHE HIT")
        cached["source"]   = "redis_cache"
        cached["redis_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        cached["total_ms"] = round((time.perf_counter() - t_all) * 1000, 2)
        cached["lineage"]  = lineage
        # Recompute pct_total for any steps loaded from Redis that lack it
        _total = cached["total_ms"] or 1
        _cum   = 0
        for _s in cached["lineage"]:
            _s.setdefault("ms", 0)
            _s.setdefault("cumulative_ms", round(_cum + _s["ms"], 2))
            _s.setdefault("pct_total", round(_s["ms"] / _total * 100, 1))
            _cum += _s["ms"]
        return cached
    else:
        step("Redis Cache Lookup", "💾",
             f"MISS — key={key[:20]}... — proceeding to pgvector",
             t0, "miss", "CACHE MISS")

    # ── Step 4: Embed query via OpenAI ────────────────────────────────────────
    t0   = time.perf_counter()
    qvec = embed_query(query, client)
    embed_ms = round((time.perf_counter() - t0) * 1000, 2)
    step("Embed Query (OpenAI)", "🔢",
         f"model=text-embedding-3-small · dim=1536 · ~{len(query.split())*4//3} tokens",
         t0, "ok", f"1536-dim vector in {embed_ms}ms")

    # ── Step 5: pgvector HNSW search ─────────────────────────────────────────
    t0     = time.perf_counter()
    chunks = pgvector_search(conn, qvec, access, k, ef)
    search_ms = round((time.perf_counter() - t0) * 1000, 2)

    if not chunks:
        step("pgvector HNSW Search", "🗄️",
             f"access={access} · k={k} · ef_search={ef}",
             t0, "error", "No results returned")
        return {
            "error"    : "No results from pgvector. Run python 04_pgvector.py first.",
            "source"   : "pgvector",
            "lineage"  : lineage,
            "total_ms" : round((time.perf_counter()-t_all)*1000, 2),
        }

    top_sections = list(dict.fromkeys(c["section_id"] for c in chunks))
    step("pgvector HNSW Search", "🗄️",
         f"access={access} · k={k} · ef_search={ef} · "
         f"top sections: {', '.join(top_sections[:3])}",
         t0, "ok",
         f"{len(chunks)} chunks · top score={chunks[0]['score']:.4f}")

    # ── Step 6: Access control double-check ──────────────────────────────────
    t0       = time.perf_counter()
    approved = [c for c in chunks if c.get("access_level") in access]
    blocked  = len(chunks) - len(approved)
    step("Access Control Check", "🔒",
         f"allowed={access} · {len(approved)} approved · {blocked} blocked",
         t0, "ok",
         f"{len(approved)}/{len(chunks)} chunks passed")
    chunks = approved if approved else chunks

    # ── Step 7: Build LLM context ─────────────────────────────────────────────
    t0      = time.perf_counter()
    ctx_len = sum(len(c["text"].split()) for c in chunks[:3])
    step("Build LLM Context", "📄",
         f"top-3 chunks · ~{ctx_len} words fed to LLM",
         t0, "ok",
         f"{min(3,len(chunks))} chunks · {ctx_len} words")

    # ── Step 8: Generate answer via GPT-4o-mini ───────────────────────────────
    t0 = time.perf_counter()
    try:
        answer, gen_ms = generate_answer(query, chunks, client)
        step("Generate Answer (GPT-4o-mini)", "🤖",
             f"model=gpt-4o-mini · temperature=0.1 · max_tokens=500",
             t0, "ok",
             f"Answer generated in {gen_ms}ms ({len(answer.split())} words)")
    except Exception as e:
        step("Generate Answer (GPT-4o-mini)", "🤖",
             f"model=gpt-4o-mini", t0, "error", str(e))
        return {
            "error"    : f"Answer generation failed: {e}",
            "source"   : "pgvector",
            "chunks"   : chunks,
            "lineage"  : lineage,
            "total_ms" : round((time.perf_counter()-t_all)*1000, 2),
        }

    # ── Step 9: Compute citation scores ──────────────────────────────────────
    t0 = time.perf_counter()
    for c in chunks:
        c["citation_score"] = citation_score(answer, c["text"])
    top_cit = max(c["citation_score"] for c in chunks)
    step("Compute Citation Scores", "📊",
         f"word-overlap(answer, each chunk) for {len(chunks)} chunks",
         t0, "ok",
         f"top citation={top_cit:.3f}")

    # ── Step 10: Store in Redis cache ─────────────────────────────────────────
    t0 = time.perf_counter()
    if r_conn:
        redis_set(r_conn, key, {
            "query": query, "answer": answer, "chunks": chunks,
            "access": access, "k": k, "ef": ef,
            "source": "pgvector",
            "redis_ms": 0, "embed_ms": embed_ms,
            "search_ms": search_ms, "gen_ms": gen_ms,
            "total_ms": 0,
        })
        step("Store in Redis Cache", "💾",
             f"key={key[:20]}... · TTL={CACHE_TTL}s ({CACHE_TTL//3600}h)",
             t0, "ok", f"Cached for {CACHE_TTL//3600}h")
    else:
        step("Store in Redis Cache", "💾",
             "Redis not connected — skipping", t0, "skip", "skipped")

    total_ms = round((time.perf_counter() - t_all) * 1000, 2)

    # Finalise lineage with cumulative timing
    cumulative = 0
    for s in lineage:
        cumulative += s["ms"]
        s["cumulative_ms"] = round(cumulative, 2)
        s["pct_total"] = round(s["ms"] / total_ms * 100, 1) if total_ms else 0

    result = {
        "query"     : query,
        "answer"    : answer,
        "chunks"    : chunks,
        "access"    : access,
        "k"         : k,
        "ef"        : ef,
        "source"    : "pgvector",
        "redis_ms"  : 0,
        "embed_ms"  : embed_ms,
        "search_ms" : search_ms,
        "gen_ms"    : gen_ms,
        "total_ms"  : total_ms,
        "lineage"   : lineage,
    }
    return result


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────
st.title("🛒 ShopNow Customer Service ChatBot")
st.caption("pgvector HNSW · Redis cache · GPT-4o-mini · text-embedding-3-small")

# Initialise connections
conn, chunk_count, pg_errors = init_pgvector()
r_conn, redis_error          = init_redis()
client, openai_error         = init_openai()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Search Settings")
    access_levels = st.multiselect(
        "Access Level",
        ["public", "internal", "confidential", "most_confidential"],
        default=["public"],
    )
    top_k = st.slider("Top-K Chunks", 1, 10, 5)
    ef    = st.slider("HNSW ef_search", 10, 400, 100,
                      help="Higher = better recall, slower")

    st.markdown("---")
    st.markdown("### 🔌 Service Status")

    # pgvector status
    if conn:
        st.success(f"✅ pgvector — {chunk_count} chunks")
    else:
        st.error("❌ pgvector not connected")
        for e in pg_errors:
            st.caption(e)

    # Redis status
    if r_conn:
        try:
            info  = r_conn.info("stats")
            hits  = info.get("keyspace_hits", 0)
            misses= info.get("keyspace_misses", 0)
            st.success(f"✅ Redis — hits:{hits} misses:{misses}")
        except Exception:
            st.success("✅ Redis connected")
    else:
        st.warning(f"⚠️ Redis not available ({redis_error})")
        st.caption("Queries will work without cache.")

    # OpenAI status
    if client:
        st.success(f"✅ OpenAI — sk-...{OPENAI_API_KEY[-6:]}")
    else:
        st.error(f"❌ OpenAI: {openai_error}")
        st.caption("Add OPENAI_API_KEY to .env file")

    st.markdown("---")
    st.markdown("### 💬 Sample Questions")
    samples = [
        "What is the return window for Prime members?",
        "How does Prime same-day delivery work?",
        "My item arrived damaged. What should I do?",
        "Can I cancel my order after placing it?",
        "How many Coins do I earn per dollar?",
        "What is the Price Match Guarantee?",
        "What payment methods are accepted?",
        "How do I report a fraud charge?",
    ]
    for q in samples:
        if st.button(q, key=f"s_{q[:15]}", use_container_width=True):
            st.session_state["prefill"] = q
            st.rerun()

    if r_conn:
        st.markdown("---")
        if st.button("🗑️ Clear Redis cache", use_container_width=True):
            try:
                r_conn.flushdb()
                st.success("Cache cleared")
            except Exception as e:
                st.error(str(e))


# ── Guard: stop if critical services are missing ──────────────────────────────
if conn is None or client is None:
    st.error("**Cannot run queries** — fix the issues shown in the sidebar first.")
    if pg_errors:
        with st.expander("pgvector error details"):
            for e in pg_errors:
                st.code(e)
    if openai_error:
        with st.expander("OpenAI error details"):
            st.code(openai_error)
    st.stop()


# ── Query input ───────────────────────────────────────────────────────────────
default_q = st.session_state.pop("prefill", "")
query = st.text_input(
    "Ask a customer service question:",
    value=default_q,
    placeholder="e.g. What is the return policy for Prime members?",
)

col_btn, col_clear = st.columns([1, 6])
do_search = col_btn.button("🔍 Search", type="primary")
if col_clear.button("Clear history"):
    st.session_state.pop("history", None)
    st.rerun()


# ── Run pipeline ──────────────────────────────────────────────────────────────
if do_search and query.strip():
    if not access_levels:
        st.warning("Select at least one access level in the sidebar.")
        st.stop()

    with st.spinner("Searching pgvector and generating answer..."):
        result = run_rag_pipeline(
            query.strip(), access_levels, top_k, ef,
            conn, r_conn, client,
        )

    if "history" not in st.session_state:
        st.session_state["history"] = []
    st.session_state["history"].insert(0, result)


# ── Render result ─────────────────────────────────────────────────────────────
history = st.session_state.get("history", [])
if not history:
    st.info("Enter a question above and click Search.")
    st.stop()

result = history[0]

# Error state
if "error" in result:
    st.error(f"**Error:** {result['error']}")
    if result.get("chunks"):
        st.warning("Chunks were retrieved but answer generation failed. "
                   "See chunks below.")
    else:
        st.stop()

# ── Cache badge ───────────────────────────────────────────────────────────────
source = result.get("source", "pgvector")
if source == "redis_cache":
    st.markdown('<span class="hit-badge">⚡ REDIS CACHE HIT</span>',
                unsafe_allow_html=True)
else:
    st.markdown('<span class="miss-badge">🔍 PGVECTOR HNSW</span>',
                unsafe_allow_html=True)
st.markdown("")

# ── Answer ────────────────────────────────────────────────────────────────────
st.markdown("### 🤖 Answer")
st.info(result.get("answer", "No answer generated."))

# ── Timing ────────────────────────────────────────────────────────────────────
st.markdown("### ⏱️ Latency Breakdown")
tc = st.columns(5)
def show_time(col, label, ms):
    col.metric(label, f"{ms:.1f} ms" if ms else "—")

show_time(tc[0], "Redis Lookup", result.get("redis_ms", 0))
show_time(tc[1], "Embed Query",  result.get("embed_ms", 0))
show_time(tc[2], "HNSW Search",  result.get("search_ms", 0))
show_time(tc[3], "LLM Generate", result.get("gen_ms", 0))
show_time(tc[4], "Total",        result.get("total_ms", 0))

if source == "redis_cache":
    st.success(f"⚡ Served from Redis cache — "
               f"{result.get('total_ms',0):.1f}ms total "
               f"(vs ~{result.get('gen_ms',0) + result.get('search_ms',0) + result.get('embed_ms',0):.0f}ms live)")


# ── Query Lineage ─────────────────────────────────────────────────────────────
lineage = result.get("lineage", [])
if lineage:
    st.markdown("### 🔍 Query Execution Lineage")

    STATUS_STYLE = {
        "ok"   : ("✅", "#16a34a", "#f0fdf4", "#bbf7d0"),
        "hit"  : ("⚡", "#7c3aed", "#faf5ff", "#e9d5ff"),
        "miss" : ("💨", "#2563eb", "#eff6ff", "#bfdbfe"),
        "skip" : ("⏭️", "#6b7280", "#f9fafb", "#e5e7eb"),
        "error": ("❌", "#dc2626", "#fef2f2", "#fecaca"),
    }

    total_ms = result.get("total_ms", 1) or 1

    for i, s in enumerate(lineage):
        stat        = s.get("status", "ok")
        icon_s, color, bg, border = STATUS_STYLE.get(stat, STATUS_STYLE["ok"])
        step_ms     = s.get("ms", 0)
        cum_ms      = s.get("cumulative_ms", 0)
        pct         = s.get("pct_total", 0)
        bar_width   = max(int(pct), 1)

        st.markdown(f"""
<div style="background:{bg};border-left:4px solid {border};
     border-radius:6px;padding:10px 14px;margin:4px 0;">
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
    <span style="font-size:18px">{icon_s}</span>
    <span style="font-weight:700;color:{color};min-width:220px">
      Step {i+1}: {s['step']}
    </span>
    <span style="background:{color};color:white;padding:2px 10px;
          border-radius:10px;font-size:12px;font-weight:700">
      {step_ms} ms
    </span>
    <span style="color:#6b7280;font-size:12px">
      cumulative: {cum_ms} ms &nbsp;|&nbsp; {pct}% of total
    </span>
  </div>
  <div style="margin:6px 0 4px 28px;color:#374151;font-size:13px">
    {s['detail']}
  </div>
  <div style="margin:4px 0 2px 28px;color:{color};font-size:12px;font-weight:600">
    → {s['output']}
  </div>
  <div style="background:#e5e7eb;border-radius:4px;height:6px;margin:6px 0 0 28px;">
    <div style="background:{color};width:{bar_width}%;height:6px;
         border-radius:4px;transition:width 0.3s;"></div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Cumulative timeline bar ───────────────────────────────────────────────
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    with st.expander("📈 Cumulative Timeline & Step Comparison"):
        # Bar chart data
        import pandas as pd
        df = pd.DataFrame([
            {"Step": f"S{i+1} {s['step'][:18]}", "ms": s.get("ms",0), "pct": s.get("pct_total",0)}
            for i, s in enumerate(lineage)
        ])
        st.bar_chart(df.set_index("Step")["ms"], height=200)

        # Table
        table_rows = []
        for i, s in enumerate(lineage):
            stat = s.get("status","ok")
            icon_s = STATUS_STYLE.get(stat, STATUS_STYLE["ok"])[0]
            table_rows.append({
                "Step"        : f"{i+1}. {s['step']}",
                "Status"      : f"{icon_s} {stat}",
                "Time (ms)"   : s["ms"],
                "Cumulative"  : s.get("cumulative_ms", 0),
                "% of Total"  : f"{s.get('pct_total', 0)}%",
                "Output"      : s["output"][:45],
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

        st.caption(f"Total pipeline: {total_ms} ms  |  "
                   f"Steps: {len(lineage)}  |  "
                   f"Source: {result.get('source','—')}")

# ── Source documents ──────────────────────────────────────────────────────────
st.markdown("### 📚 Source Documents")
chunks = result.get("chunks", [])

if not chunks:
    st.caption("No source chunks returned.")
else:
    for i, c in enumerate(chunks, 1):
        sim = c.get("score", 0.0)
        cs  = c.get("citation_score", 0.0)

        title = c.get("section_title", "Unknown section")
        label = (f"[{i}]  {title[:55]}  "
                 f"—  Similarity: {sim:.4f}  |  Citation: {cs:.3f}")

        with st.expander(label, expanded=(i == 1)):
            # Top metadata row
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.markdown(
                f'<span class="source-tag">📂 {c.get("section_id","")}</span>',
                unsafe_allow_html=True)
            m2.markdown(
                f'<span class="source-tag">🔒 {c.get("access_level","")}</span>',
                unsafe_allow_html=True)
            m3.markdown(
                f'<span class="source-tag">🔤 {c.get("token_count",0)} tok</span>',
                unsafe_allow_html=True)
            m4.markdown(
                f'<span class="{score_css(sim)}">Similarity {sim:.4f}</span>',
                unsafe_allow_html=True)
            m5.markdown(
                f'<span class="{score_css(cs)}">Citation {cs:.3f}</span>',
                unsafe_allow_html=True)

            st.markdown("**Retrieved text:**")
            st.markdown(c.get("text", ""))
            st.caption(
                f"Citation score {cs:.3f}: ~{int(cs*100)}% of answer words "
                f"found in this chunk. "
                f"Similarity {sim:.4f}: cosine distance from pgvector HNSW."
            )

# ── Query info ────────────────────────────────────────────────────────────────
with st.expander("🔎 Query details"):
    st.json({
        "query"        : result.get("query"),
        "source"       : result.get("source"),
        "access_levels": result.get("access"),
        "top_k"        : result.get("k"),
        "ef_search"    : result.get("ef"),
        "cache_key"    : make_cache_key(
                            result.get("query",""),
                            result.get("access",[]),
                            result.get("k",5)),
        "timing_ms"    : {
            "redis_lookup" : result.get("redis_ms"),
            "embed_query"  : result.get("embed_ms"),
            "hnsw_search"  : result.get("search_ms"),
            "llm_generate" : result.get("gen_ms"),
            "total"        : result.get("total_ms"),
        },
    })


# ── Query history ─────────────────────────────────────────────────────────────
if len(history) > 1:
    st.markdown("---")
    st.markdown("### 📜 Query History")
    for i, h in enumerate(history[1:], 2):
        src   = h.get("source", "pgvector")
        badge = "⚡" if src == "redis_cache" else "🔍"
        q_txt = h.get("query", "")[:65]
        ms    = h.get("total_ms", 0)
        with st.expander(f"{badge} [{i}]  {q_txt}  — {ms:.0f}ms  ({src})"):
            if "error" in h:
                st.error(h["error"])
            else:
                st.write(h.get("answer", ""))
                c_list = h.get("chunks", [])
                if c_list:
                    st.caption("Sources: " + " · ".join(
                        f"{c['section_title'][:30]} (sim={c['score']:.3f})"
                        for c in c_list[:3]
                    ))


# ── DB analytics ──────────────────────────────────────────────────────────────
with st.expander("📊 Database Analytics"):
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT access_level, COUNT(*), AVG(token_count)::int
                    FROM document_chunks
                    GROUP BY access_level ORDER BY access_level;
                """)
                rows = cur.fetchall()
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Total Chunks", chunk_count)
            col_b.metric("Access Levels", len(rows))
            avg_tok = sum(r[2] for r in rows) // max(len(rows), 1)
            col_c.metric("Avg Tokens/Chunk", avg_tok)
            access_data = {r[0]: r[1] for r in rows}
            st.bar_chart(access_data)
            st.caption("Chunk count by access level")
        except Exception as e:
            st.caption(f"Analytics error: {e}")