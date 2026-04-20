import re
import json
import pdfplumber
import pypdf
import tiktoken
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
)
 
PDF_PATH = "D:\GenAI Content\\AI code\\4_RAG_Indexing\\1_Document_Processing\\Data\\financial_report_2024.pdf"
 
# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Extract raw text from PDF
# ─────────────────────────────────────────────────────────────────────────────
def extract_text_from_pdf(path: str) -> str:
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()
 
 
def print_chunks(chunks: list[dict], strategy: str, max_show: int = 3):
    print(f"\n{'='*65}")
    print(f"  Strategy : {strategy}")
    print(f"  Total    : {len(chunks)} chunks")
    print(f"  Showing  : first {min(max_show, len(chunks))} chunks")
    print(f"{'='*65}")
    for i, chunk in enumerate(chunks[:max_show], 1):
        text = chunk.get("text", "")
        meta = {k: v for k, v in chunk.items() if k != "text"}
        print(f"\n  ── Chunk {i} ──────────────────────────────────────────")
        print(f"  Metadata : {json.dumps(meta, indent=None)}")
        print(f"  Length   : {len(text)} chars")
        print(f"  Text     :\n  {text[:300].strip()}{'...' if len(text) > 300 else ''}")
    print()
 
 
# ─────────────────────────────────────────────────────────────────────────────
# STEP 0: Load the PDF
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  Loading: financial_report_2024.pdf")
print("="*65)
 
raw_text = extract_text_from_pdf(PDF_PATH)
print(f"  Extracted {len(raw_text)} characters, {len(raw_text.split())} words")
print(f"\n  Preview:\n  {raw_text[:300]}...")

# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY 6: Sliding Window Chunking
# ─────────────────────────────────────────────────────────────────────────────
# Best for: Dense documents where context bleeds across paragraphs
# Logic:    Move a fixed window with high overlap to preserve context
# ─────────────────────────────────────────────────────────────────────────────
# 🧠 What this function does

# 👉 This function creates chunks using a sliding window approach (word-based)

# Each chunk contains fixed number of words (window_size)
# Next chunk starts after step_size words
# This creates overlapping chunks
# ⚙️ Parameters
# window_size = 120   # words per chunk
# step_size   = 40    # how much we move forward

# 👉 Overlap:

# overlap = window_size - step_size = 120 - 40 = 80 words

# 👉 Overlap %:

# (1 - 40/120) * 100 = 66.7% ≈ 67%

# 🔄 Step-by-Step Logic
# Step 1: Split text into words
# words = text.split()
# Example Input:
# "AI improves productivity and enables automation across industries with better decision making and insights"

# 👉 Words list:

# [
#  "AI", "improves", "productivity", "and", "enables",
#  "automation", "across", "industries", "with", "better",
#  "decision", "making", "and", "insights"
# ]

# Step 2: Loop with step size
# for i in range(0, len(words), step_size):

# 👉 If:

# window_size = 5
# step_size = 2

# 👉 Iterations:

# i = 0, 2, 4, 6, ...
# 📦 Example Walkthrough

# Let’s use:

# window_size = 5
# step_size = 2
# 🔹 Chunk 1 (i = 0)
# window_words = words[0:5]

# 👉 Words:

# AI improves productivity and enables
# 🔹 Chunk 2 (i = 2)
# window_words = words[2:7]

# 👉 Words:

# productivity and enables automation across

# 👉 Overlap:

# "productivity and enables" appears in both chunks ✅
# 🔹 Chunk 3 (i = 4)
# words[4:9]

# 👉 Words:

# enables automation across industries with
# 🔹 Chunk 4 (i = 6)
# words[6:11]

# 👉 Words:

# across industries with better decision
# 🔹 Chunk 5 (i = 8)
# words[8:13]

# 👉 Words:

# with better decision making and
# 🔹 Chunk 6 (i = 10)
# words[10:15]

# 👉 Words:

# decision making and insights
# 🔹 Stop condition
# if len(window_words) < 20:
#     break

# 👉 In your real code:

# Small trailing chunks are skipped
# Prevents noisy / useless chunks

# 📊 Output Structure
# {
#   "chunk_id": "window_0",
#   "strategy": "sliding_window",
#   "window_size": 120,
#   "step_size": 40,
#   "word_start": 0,
#   "word_end": 120,
#   "overlap_pct": 66.7,
#   "text": "..."
# }
# 🎯 Why Sliding Window is Powerful
# ✅ 1. Strong Context Preservation

# Each chunk shares large overlap:

# Chunk 1: A B C D E
# Chunk 2:     C D E F G

# 👉 Context flows smoothly

# ✅ 2. Better Retrieval in RAG

# User query:

# "automation across industries"

# 👉 Multiple chunks contain it → higher recall

# ✅ 3. Reduces Boundary Issues

# ❌ Fixed chunking:

# "...automation across"
# "industries with better..."

# 👉 Meaning breaks

# ✅ Sliding window:

# Keeps phrases intact across chunks

# ⚠️ Trade-offs
# ❌ More chunks
# Higher storage cost
# More embeddings

# ❌ Duplicate content
# Same text repeated across chunks

# ⚖️ When to Use This

# 👍 Best for:
# Long documents
# QA systems
# Search-heavy RAG

# 👎 Avoid when:
# Cost is very sensitive
# Data is already well-structured

# 🧠 Intuition

# 👉 Think of it like a moving window over text:

# [ A B C D E ]
#     [ C D E F G ]
#         [ E F G H I ]

def sliding_window_chunking(text: str, window_size: int = 400, step_size: int = 100) -> list[dict]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), step_size):
        window_words = words[i : i + window_size]
        if len(window_words) < 20:  # skip tiny trailing chunks
            break
        chunk_text = " ".join(window_words)
        chunks.append({
            "chunk_id"   : f"window_{len(chunks)}",
            "strategy"   : "sliding_window",
            "window_size": window_size,
            "step_size"  : step_size,
            "word_start" : i,
            "word_end"   : i + len(window_words),
            "overlap_pct": round((1 - step_size / window_size) * 100, 1),
            "text"       : chunk_text,
        })
    return chunks
 
 
window_chunks = sliding_window_chunking(raw_text, window_size=120, step_size=40)
print_chunks(window_chunks, "6. Sliding Window Chunking (window=120w, step=40w, 67% overlap)")