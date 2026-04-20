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
# STRATEGY 1: Fixed-Size Chunking
# ─────────────────────────────────────────────────────────────────────────────
# Best for: Quick prototyping, uniform retrieval
# Risk:     Cuts mid-sentence; loses context at boundaries
# ─────────────────────────────────────────────────────────────────────────────
# 🧠 What this function does

# This function performs fixed-size chunking with overlap.

# 👉 Meaning:

# It splits a long text into equal-sized chunks
# Each chunk overlaps with the previous one to preserve context
# ⚙️ Key Parameters
# chunk_size = 300   # number of characters per chunk
# overlap   = 50     # overlapping characters between chunks

# 👉 So:

# Each chunk = 300 characters
# Next chunk starts 50 characters before the previous chunk ends
# 🔄 Step-by-Step Logic
# 1. Initialization
# start = 0
# chunk_index = 0
# start → where chunk begins
# chunk_index → chunk numbering
# 2. Loop through text
# while start < len(text):

# 👉 Keep creating chunks until the full text is processed

# 3. Define chunk boundaries
# end = start + chunk_size
# chunk_text = text[start:end]

# 👉 Extract substring from:

# start → end
# 4. Store chunk with metadata

# Each chunk is stored like this:

# {
#     "chunk_id": "fixed_0",
#     "strategy": "fixed_size",
#     "chunk_size": 300,
#     "overlap": 50,
#     "start_char": 0,
#     "end_char": 300,
#     "text": "actual chunk text..."
# }

# 👉 Important:

# You’re not just storing text
# You’re storing traceability metadata (very important in production RAG)
# 5. Move to next chunk (WITH overlap)
# start += chunk_size - overlap

# 👉 This is the most important line

# If:

# chunk_size = 300
# overlap = 50

# Then:

# start += 250

# 👉 So next chunk starts 250 characters ahead, not 300

# 📊 Example Walkthrough

# Let’s take a simple text:

# ABCDEFGHIJKLMNOPQRSTUVWXYZ (26 chars for simplicity)

# Now assume:

# chunk_size = 10
# overlap = 3
# 🔹 Chunk 1
# start = 0
# end = 10
# ABCDEFGHIJ
# 🔹 Move start
# start += 10 - 3 = 7
# 🔹 Chunk 2
# start = 7
# end = 17
# HIJKLMNOPQ

# 👉 Notice overlap:

# Chunk 1 ends at J
# Chunk 2 starts at H
# → Overlap = HIJ (3 chars)
# 🔹 Chunk 3
# start = 14
# end = 24
# OPQRSTUVWX
# 🔹 Chunk 4
# start = 21
# end = 31 (overflow handled automatically)
# VWXYZ
# 📦 Final Output Structure
# [
#   {"chunk_id": "fixed_0", "start_char": 0,  "end_char": 10},
#   {"chunk_id": "fixed_1", "start_char": 7,  "end_char": 17},
#   {"chunk_id": "fixed_2", "start_char": 14, "end_char": 24},
#   {"chunk_id": "fixed_3", "start_char": 21, "end_char": 31},
# ]

def fixed_size_chunking(text: str, chunk_size: int = 300, overlap: int = 50) -> list[dict]:
    chunks = []
    start = 0
    chunk_index = 0
    while start < len(text):
        end = start + chunk_size
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({
                "chunk_id"    : f"fixed_{chunk_index}",
                "strategy"    : "fixed_size",
                "chunk_size"  : chunk_size,
                "overlap"     : overlap,
                "start_char"  : start,
                "end_char"    : end,
                "text"        : chunk_text,
            })
            chunk_index += 1
        start += chunk_size - overlap  # slide forward with overlap
    return chunks
 
 
fixed_chunks = fixed_size_chunking(raw_text, chunk_size=300, overlap=50)
print_chunks(fixed_chunks, "1. Fixed-Size Chunking (size=300, overlap=50)")