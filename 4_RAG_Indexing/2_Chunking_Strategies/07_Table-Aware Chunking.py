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
# STRATEGY 7: Table-Aware Chunking
# ─────────────────────────────────────────────────────────────────────────────
# Best for: Financial/structured documents — keeps tables intact as one chunk
# Logic:    Detect tabular lines (multiple spaces / tab patterns), group them;
#           everything else is treated as prose
# ─────────────────────────────────────────────────────────────────────────────
# 🧠 What this function does

# 👉 It reads text line by line and:

# Groups normal text → prose chunks
# Groups table-like lines → table chunks

# 📘 Example Input

# Company performance summary for FY 2025.

# Revenue increased significantly across all regions.

# Region     Revenue     Growth
# USA        100M        10%
# India      80M         15%

# Future outlook remains strong with expansion plans.

# ⚙️ Step 1: Split into lines
# lines = text.split("\n")

# 👉 Result:

# [
#  "Company performance summary for FY 2025.",
#  "",
#  "Revenue increased significantly across all regions.",
#  "",
#  "Region     Revenue     Growth",
#  "USA        100M        10%",
#  "India      80M         15%",
#  "",
#  "Future outlook remains strong with expansion plans."
# ]

# 🧠 Step 2: Buffers
# prose_buffer = []
# table_buffer = []

# 👉 Think of these as:

# 📄 prose_buffer → normal text
# 📊 table_buffer → table rows

# 🔍 Step 3: Detect table rows
# def is_table_row(line):
#     return bool(re.search(r'\s{3,}', line)) and len(line.strip()) > 10

# 👉 Rule:

# If line has 3+ spaces together, it’s likely a table

# Example:
# Region     Revenue     Growth   ✅ table
# USA        100M        10%      ✅ table
# Revenue increased significantly ❌ prose

# 🔄 Step 4: Process each line
# 🔹 Line 1 (Prose)
# Company performance summary for FY 2025.

# 👉 Goes to:

# prose_buffer = ["Company performance summary..."]
# 🔹 Line 2 (Prose continues)
# Revenue increased significantly...

# 👉 Added to prose_buffer

# 🔹 Line 3 (Table detected)
# Region     Revenue     Growth

# 👉 Action:

# flush_prose()
# 🔥 flush_prose()
# prose_text = " ".join(prose_buffer)

# 👉 Creates chunk:

# {
#   "chunk_id": "prose_0",
#   "type": "prose",
#   "text": "Company performance summary... Revenue increased..."
# }

# 👉 Then:

# prose_buffer.clear()
# 🔹 Now start table buffer
# table_buffer = ["Region     Revenue     Growth"]
# 🔹 Next lines (Table continues)
# USA        100M        10%
# India      80M         15%

# 👉 Added to:

# table_buffer
# 🔹 Next line (Back to prose)
# Future outlook remains strong...

# 👉 Action:

# flush_table()
# 🔥 flush_table()
# table_text = "\n".join(table_buffer)

# 👉 Creates:

# {
#   "chunk_id": "table_1",
#   "type": "table",
#   "rows": 3,
#   "text": "Region     Revenue     Growth\nUSA...\nIndia..."
# }

# 👉 Then:

# table_buffer.clear()
# 🔹 Continue prose
# prose_buffer = ["Future outlook remains strong..."]
# 🔹 Final flush

# At end:

# flush_prose()
# flush_table()
# 📦 Final Output
# [
#   {
#     "chunk_id": "prose_0",
#     "type": "prose",
#     "text": "Company performance summary... Revenue increased..."
#   },
#   {
#     "chunk_id": "table_1",
#     "type": "table",
#     "rows": 3,
#     "text": "Region     Revenue     Growth\nUSA...\nIndia..."
#   },
#   {
#     "chunk_id": "prose_2",
#     "type": "prose",
#     "text": "Future outlook remains strong..."
#   }
# ]

# 🎯 Why This is Powerful in RAG
# ✅ 1. Tables are preserved correctly

# ❌ Without this:

# Region Revenue Growth USA 100M 10%

# 👉 Loses structure

# ✅ 2. Better Retrieval

# User query:

# "Revenue in India"

# 👉 Table chunk contains:

# India      80M      15%

# ✅ 3. Enables Special Handling

# You can:

# Send tables to LLM differently
# Convert to structured JSON
# Apply table-specific embeddings

# ⚠️ Limitations
# ❌ Simple detection
# Only checks for spaces (\s{3,})
# May fail for:
# CSV
# Markdown tables
# OCR noise

# 🚀 Production Improvements
# 1. Better Table Detection
# Use:
# PDF parsers (pdfplumber, camelot)
# HTML parsing

# 2. Hybrid Approach
# Table-aware chunking
#    ↓
# Recursive chunking (for prose)
#    ↓
# LLM refinement (optional)

# 🧠 Intuition

# 👉 Think of it like:

# 📄 Paragraphs → grouped together
# 📊 Tables → kept intact

# Instead of mixing everything randomly

def table_aware_chunking(text: str) -> list[dict]:
    lines = text.split("\n")
    chunks = []
    prose_buffer = []
    table_buffer = []
 
    def flush_prose():
        if prose_buffer:
            prose_text = " ".join(" ".join(prose_buffer).split())
            if prose_text.strip():
                chunks.append({
                    "chunk_id" : f"prose_{len(chunks)}",
                    "strategy" : "table_aware",
                    "type"     : "prose",
                    "text"     : prose_text,
                })
            prose_buffer.clear()
 
    def flush_table():
        if table_buffer:
            table_text = "\n".join(table_buffer)
            if table_text.strip():
                chunks.append({
                    "chunk_id" : f"table_{len(chunks)}",
                    "strategy" : "table_aware",
                    "type"     : "table",
                    "rows"     : len(table_buffer),
                    "text"     : table_text,
                })
            table_buffer.clear()
 
    def is_table_row(line: str) -> bool:
        # Table rows have multiple large whitespace gaps (tabular layout)
        return bool(re.search(r'\s{3,}', line)) and len(line.strip()) > 10
 
    for line in lines:
        if is_table_row(line):
            flush_prose()
            table_buffer.append(line)
        else:
            flush_table()
            if line.strip():
                prose_buffer.append(line.strip())
 
    flush_prose()
    flush_table()
    return chunks
 
 
table_chunks = table_aware_chunking(raw_text)
print_chunks(table_chunks, "7. Table-Aware Chunking", max_show=6)