import streamlit as st
from rag_pipeline import run_rag_pipeline

st.set_page_config(page_title="RAG Dashboard", layout="wide")

st.title("🛒 RAG Observability Dashboard")

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown("### ⚙️ Search Settings")

    access = st.multiselect(
        "Access Level",
        ["public", "internal", "confidential"],
        default=["public"]
    )

    top_k = st.slider("Top-K", 1, 10, 5)
    ef = st.slider("HNSW ef_search", 10, 400, 100)

# ---------------- INPUT ----------------
query = st.text_input("Ask a question")

if st.button("Search") and query:
    result = run_rag_pipeline(query)

    # ---------------- CACHE BADGE ----------------
    if result.get("source") == "redis_cache":
        st.success("⚡ REDIS CACHE HIT")
    else:
        st.info("🔍 PGVECTOR HNSW")

    # ---------------- ANSWER ----------------
    st.markdown("### 🤖 Answer")
    st.write(result["answer"])

    # ---------------- LATENCY ----------------
    st.markdown("### ⏱️ Latency")

    t = result.get("timing", {})
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Embed", f"{t.get('embed_ms', 0):.1f} ms")
    c2.metric("Search", f"{t.get('search_ms', 0):.1f} ms")
    c3.metric("LLM", f"{t.get('gen_ms', 0):.1f} ms")
    c4.metric("Total", f"{t.get('total_ms', 0):.1f} ms")
    
     # ---------------- Evaluation Metrics ----------------
    st.markdown("### 📊 Evaluation Metrics")

    metrics = result.get("metrics", {})

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric("Precision", round(metrics.get("precision", 0), 3))
    c2.metric("Recall", round(metrics.get("recall", 0), 3))
    c3.metric("Answer", round(metrics.get("answer_score", 0), 3))
    c4.metric("Context Rel", round(metrics.get("context_relevance", 0), 3))
    c5.metric("Answer Rel", round(metrics.get("answer_relevance", 0), 3))
    c6.metric("Grounded", round(metrics.get("groundedness", 0), 3))

    # ---------------- LINEAGE ----------------
    st.markdown("### 🔍 Execution Lineage")

    for step in result.get("lineage", []):
        st.write(step)

    # ---------------- CHUNKS ----------------
    st.markdown("### 📚 Source Documents")

    for i, c in enumerate(result["chunks"], 1):
        with st.expander(
            f"[{i}] Score: {c['score']:.3f} | Citation: {c.get('citation_score',0):.3f}"
        ):
            st.write(c["content"])