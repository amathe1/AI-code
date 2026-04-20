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
# STRATEGY 3: Semantic / Section-Aware Chunking
# ─────────────────────────────────────────────────────────────────────────────
# Best for: Documents with clear headings (reports, contracts, manuals)
# Logic:    Detect section headers via regex → split on them
# ─────────────────────────────────────────────────────────────────────────────
def semantic_section_chunking(text: str) -> list[dict]:
    # Known section headers in this financial report
    section_pattern = re.compile(
        r"(?m)^(Executive Summary|Revenue Growth|Key Metrics|Revenue by Segment|FY 2025 Outlook)\s*$"
    )
    splits = section_pattern.split(text)
 
    chunks = []
    section_name = "Preamble"
    for part in splits:
        part = part.strip()
        if not part:
            continue
        if section_pattern.match(part):
            section_name = part
        else:
            chunks.append({
                "chunk_id"   : f"section_{len(chunks)}",
                "strategy"   : "semantic_section",
                "section"    : section_name,
                "word_count" : len(part.split()),
                "text"       : part,
            })
    return chunks
 
 
# semantic_chunks = semantic_section_chunking(raw_text)
# print_chunks(semantic_chunks, "3. Semantic / Section-Aware Chunking", max_show=5)

# ─────────────────────────────────────────────────────────────────────────────
# STRATEGY 8: Hierarchical / Parent-Child Chunking
# ─────────────────────────────────────────────────────────────────────────────
# Best for: Production RAG — retrieve small child chunks, send large parent
#           to LLM for context. Reduces noise while preserving coherence.
# Logic:    Section = parent chunk → sentences within = child chunks
# ─────────────────────────────────────────────────────────────────────────────
# 🧠 What this function does

# 👉 It creates two levels of chunks:

# 1. Parent chunks
# Large, meaningful sections (from semantic chunking)

# 2. Child chunks
# Smaller pieces of each parent (for better retrieval)

# 📘 Example Input
# Executive Summary
# The company had a strong year with significant growth in revenue and customer base.

# Revenue Growth
# Revenue increased by 20% driven by product expansion and global demand.

# ⚙️ Step 1: Create Parent Chunks
# parents = semantic_section_chunking(text)

# 👉 Output:

# [
#   {
#     "chunk_id": "section_0",
#     "section": "Executive Summary",
#     "text": "The company had a strong year..."
#   },
#   {
#     "chunk_id": "section_1",
#     "section": "Revenue Growth",
#     "text": "Revenue increased by 20%..."
#   }
# ]

# 🔄 Step 2: Convert Parent IDs
# parent_id = parent["chunk_id"].replace("section_", "parent_")

# 👉 Example:

# section_0 → parent_0

# 🧱 Step 3: Store Parent Chunk
# all_chunks.append({
#     "chunk_id": parent_id,
#     "level": "parent",
#     ...
# })

# 👉 Example:

# {
#   "chunk_id": "parent_0",
#   "level": "parent",
#   "section": "Executive Summary",
#   "text": "The company had a strong year..."
# }

# ✂️ Step 4: Split Parent into Child Chunks
# splitter = RecursiveCharacterTextSplitter(
#     chunk_size=150,
#     chunk_overlap=30
# )

# 👉 Each parent is split into:

# Smaller chunks (~150 chars)
# With overlap
# 🔹 Example Parent Text
# "The company had a strong year with significant growth in revenue and customer base."
# 🔹 Child Chunks
# [
#   "The company had a strong year with significant growth...",
#   "significant growth in revenue and customer base..."
# ]

# 🔗 Step 5: Link Children to Parent
# {
#   "chunk_id": "parent_0_child_0",
#   "level": "child",
#   "parent_id": "parent_0",
#   "section": "Executive Summary",
#   "text": "The company had a strong year..."
# }

# 👉 Key idea:

# Each child knows its parent
# 📦 Final Output Structure
# [
#   # Parent
#   {
#     "chunk_id": "parent_0",
#     "level": "parent",
#     "section": "Executive Summary"
#   },

#   # Children
#   {
#     "chunk_id": "parent_0_child_0",
#     "level": "child",
#     "parent_id": "parent_0"
#   },
#   {
#     "chunk_id": "parent_0_child_1",
#     "level": "child",
#     "parent_id": "parent_0"
#   }
# ]
# 🔍 Final Print Logic (What your print shows)
# =================================================
# Strategy : Hierarchical / Parent-Child Chunking
# Parents  : 2 | Children: 4 | Total: 6
# =================================================

# PARENT [parent_0] — Section: Executive Summary
# Parent text: The company had a strong year...
# Children (2):
#   └─ [parent_0_child_0] The company had a strong year...
#   └─ [parent_0_child_1] significant growth in revenue...

# 🎯 Why This is Powerful in RAG

# ✅ 1. Best of Both Worlds
# Level	Purpose
# Parent	Full context
# Child	Precise retrieval

# ✅ 2. Retrieval Strategy

# 👉 Query:

# "What is revenue growth?"

# Step 1:
# Search over child chunks (fast & precise)

# Step 2:
# Retrieve parent chunk for full context

# ✅ 3. Reduces Hallucination

# Instead of giving small chunk:

# "growth in revenue..."

# 👉 You give full parent:

# "Revenue increased by 20% driven by product expansion..."
# ⚠️ Without Hierarchical Chunking

# ❌ Only small chunks:

# Loss of context
# Fragmented answers

# ❌ Only large chunks:

# Poor retrieval accuracy

# 🚀 Production Architecture

# Document
#    ↓
# Section Chunking (Parents)
#    ↓
# Recursive Chunking (Children)
#    ↓
# Store Children in Vector DB
#    ↓
# Query → Retrieve Children
#    ↓
# Fetch Parent Context
#    ↓
# Send to LLM

# 🧠 Intuition

# 👉 Think of it like a book:

# 📘 Chapter = Parent
# 📄 Paragraph = Child

# You:

# Search paragraph
# Read full chapter

def hierarchical_chunking(text: str, child_size: int = 150) -> list[dict]:
    # Reuse semantic sections as parents
    parents = semantic_section_chunking(text)
 
    all_chunks = []
    for parent in parents:
        parent_id = parent["chunk_id"].replace("section_", "parent_")
 
        # Store parent
        all_chunks.append({
            "chunk_id"  : parent_id,
            "strategy"  : "hierarchical",
            "level"     : "parent",
            "section"   : parent["section"],
            "text"      : parent["text"],
        })
 
        # Split parent into smaller child chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_size,
            chunk_overlap=30,
            separators=["\n", ". ", " "],
        )
        children = splitter.split_text(parent["text"])
        for j, child_text in enumerate(children):
            if child_text.strip():
                all_chunks.append({
                    "chunk_id"   : f"{parent_id}_child_{j}",
                    "strategy"   : "hierarchical",
                    "level"      : "child",
                    "parent_id"  : parent_id,
                    "section"    : parent["section"],
                    "text"       : child_text.strip(),
                })
    return all_chunks
 
 
hierarchical_chunks = hierarchical_chunking(raw_text, child_size=150)
parents  = [c for c in hierarchical_chunks if c["level"] == "parent"]
children = [c for c in hierarchical_chunks if c["level"] == "child"]
 
print(f"\n{'='*65}")
print(f"  Strategy : 8. Hierarchical / Parent-Child Chunking")
print(f"  Parents  : {len(parents)} | Children: {len(children)} | Total: {len(hierarchical_chunks)}")
print(f"{'='*65}")
for p in parents:
    kids = [c for c in children if c["parent_id"] == p["chunk_id"]]
    print(f"\n  PARENT [{p['chunk_id']}] — Section: {p['section']}")
    print(f"  Parent text ({len(p['text'])} chars): {p['text'][:120]}...")
    print(f"  Children ({len(kids)}):")
    for k in kids[:2]:
        print(f"    └─ [{k['chunk_id']}] {k['text'][:100]}...")


# When to use which in production:

# Prototyping → Strategy 2 (Recursive Character) — safe default
# Financial/structured docs → Strategy 3 (Semantic) + 7 (Table-Aware) combined
# Q&A systems → Strategy 4 (Sentence) for precision retrieval
# Token-limited APIs → Strategy 5 (Token-Based) to stay within context window
# Best overall production → Strategy 8 (Hierarchical) — retrieve small child chunks, send parent to LLM for full context


# Note: In production, replace the approx_tokenize in Strategy 5 with tiktoken.get_encoding("cl100k_base").encode() for exact GPT-4/Claude token counts.