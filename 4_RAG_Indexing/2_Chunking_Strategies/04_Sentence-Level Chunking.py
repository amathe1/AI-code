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
# STRATEGY 4: Sentence-Level Chunking
# ─────────────────────────────────────────────────────────────────────────────
# Best for: Q&A, fact retrieval — fine-grained precision
# Logic:    Split on sentence boundaries, group N sentences per chunk
# ─────────────────────────────────────────────────────────────────────────────
# 🧠 What this function does

# 👉 It splits text into chunks of sentences instead of characters or tokens.

# Each chunk contains N sentences
# Consecutive chunks overlap by some sentences
# ⚙️ Parameters
# sentences_per_chunk = 3
# overlap = 1

# 👉 Meaning:

# Each chunk has 3 sentences
# Next chunk shares 1 sentence with previous chunk
# 🔄 Step-by-Step Logic
# Step 1: Split text into sentences
# raw_sentences = re.split(r'(?<=[.!?])\s+', text)

# 👉 This splits text at:

# .
# !
# ?
# Example Input:
# Insurance provides protection. It reduces financial risk. Policies vary by type. Claims depend on conditions. Premium must be paid regularly.

# Step 2: Clean sentences
# sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 20]

# 👉 Removes:

# Extra spaces
# Very short sentences (less than 20 characters)
# After cleaning:
# [
#  "Insurance provides protection.",
#  "It reduces financial risk.",
#  "Policies vary by type.",
#  "Claims depend on conditions.",
#  "Premium must be paid regularly."
# ]

# Step 3: Define step size
# step = sentences_per_chunk - overlap

# 👉 Here:

# step = 3 - 1 = 2

# 👉 So we move 2 sentences forward each time

# Step 4: Create chunks
# for i in range(0, len(sentences), step):

# 👉 Iteration:

# i = 0
# i = 2
# i = 4
# ...
# 📦 Example Walkthrough
# 🔹 Chunk 1 (i = 0)
# group = sentences[0:3]

# 👉 Sentences:

# Insurance provides protection.
# It reduces financial risk.
# Policies vary by type.

# Chunk 1:
# Insurance provides protection. It reduces financial risk. Policies vary by type.
# 🔹 Chunk 2 (i = 2)
# group = sentences[2:5]

# 👉 Sentences:
# 3. Policies vary by type.
# 4. Claims depend on conditions.
# 5. Premium must be paid regularly.

# Chunk 2:
# Policies vary by type. Claims depend on conditions. Premium must be paid regularly.

# 👉 Notice overlap:

# Sentence 3 appears in both chunks ✅
# 🔹 Chunk 3 (i = 4)
# group = sentences[4:7]

# 👉 Only one sentence left:

# Chunk 3:
# Premium must be paid regularly.
# 📊 Final Output
# [
#   {
#     "chunk_id": "sentence_0",
#     "sentence_start": 0,
#     "sentence_end": 3,
#     "text": "Insurance provides protection..."
#   },
#   {
#     "chunk_id": "sentence_1",
#     "sentence_start": 2,
#     "sentence_end": 5,
#     "text": "Policies vary by type..."
#   },
#   {
#     "chunk_id": "sentence_2",
#     "sentence_start": 4,
#     "sentence_end": 5,
#     "text": "Premium must be paid regularly."
#   }
# ]
# 🎯 Why This Works Well
# ✅ Keeps meaning intact
# Doesn’t break sentences
# ✅ Better than fixed chunking

# ❌ Bad (fixed):

# "...risk. Policies vary by t"

# ✅ Good (sentence):

# "Policies vary by type."
# ✅ Overlap preserves context

# Without overlap ❌:

# Context may break

# With overlap ✅:

# Smooth transition between chunks
# ⚠️ Important Considerations
# 1. Sentence splitter is basic
# May fail for:
# abbreviations (e.g., "Dr.", "U.S.")

# 👉 Production:

# Use NLP libraries like spaCy
# 2. Chunk size control
# Based on sentences, not tokens
# May vary in length
# ⚖️ When to Use This
# 👍 Best for:
# Clean text (PDF, articles)
# QA systems
# Narrative content
# 👎 Not ideal for:
# Tables
# Code
# Highly structured docs
# 🚀 Final Intuition

# 👉 Think of it like:

# Fixed chunking → cut by size 📏
# Sentence chunking → cut by meaning 🧠

def sentence_chunking(text: str, sentences_per_chunk: int = 3, overlap: int = 1) -> list[dict]:
    # Basic sentence splitter (works well for clean PDF text)
    raw_sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 20]
 
    chunks = []
    step = sentences_per_chunk - overlap
    for i in range(0, len(sentences), step):
        group = sentences[i : i + sentences_per_chunk]
        if not group:
            continue
        chunk_text = " ".join(group)
        chunks.append({
            "chunk_id"         : f"sentence_{len(chunks)}",
            "strategy"         : "sentence_level",
            "sentences_per_chunk": sentences_per_chunk,
            "sentence_start"   : i,
            "sentence_end"     : i + len(group),
            "text"             : chunk_text,
        })
    return chunks
 
 
sentence_chunks = sentence_chunking(raw_text, sentences_per_chunk=3, overlap=1)
print_chunks(sentence_chunks, "4. Sentence-Level Chunking (3 sentences, overlap=1)")