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
# 🧠 What this function does

# 👉 It splits a document based on section headers (like a real report)

# Instead of splitting by size, it:

# Detects meaningful sections
# Groups content under each section
# ⚙️ Step 1: Define Section Pattern
# section_pattern = re.compile(
#     r"(?m)^(Executive Summary|Revenue Growth|Key Metrics|Revenue by Segment|FY 2025 Outlook)\s*$"
# )
# 🔍 What this regex means:
# (?m) → multi-line mode (matches line by line)
# ^ → start of line
# $ → end of line
# Matches ONLY these exact headings:

# 👉 Sections:

# Executive Summary
# Revenue Growth
# Key Metrics
# Revenue by Segment
# FY 2025 Outlook

# 📘 Example Input Text
# Executive Summary
# The company had a strong year with increased revenue.

# Revenue Growth
# Revenue grew by 20% compared to last year.

# Key Metrics
# Customer base increased to 1 million users.

# FY 2025 Outlook
# The company expects continued growth.

# 🔄 Step 2: Split Text Using Sections
# splits = section_pattern.split(text)

# 👉 This produces a list like:

# [
#   "", 
#   "Executive Summary",
#   "The company had a strong year...",
#   "Revenue Growth",
#   "Revenue grew by 20%...",
#   "Key Metrics",
#   "Customer base increased...",
#   "FY 2025 Outlook",
#   "The company expects continued growth."
# ]

# 👉 Notice:

# Section names and content are separated
# 🔁 Step 3: Iterate Through Splits
# section_name = "Preamble"

# 👉 Default section if no header is found

# Loop Logic
# for part in splits:
# Case 1: If part is a section header
# if section_pattern.match(part):
#     section_name = part

# 👉 Update current section

# Case 2: If part is content
# chunks.append({...})

# 👉 Create a chunk with:

# Section name
# Text
# Word count
# 📦 Output Example
# [
#   {
#     "chunk_id": "section_0",
#     "strategy": "semantic_section",
#     "section": "Executive Summary",
#     "word_count": 10,
#     "text": "The company had a strong year with increased revenue."
#   },
#   {
#     "chunk_id": "section_1",
#     "section": "Revenue Growth",
#     "text": "Revenue grew by 20% compared to last year."
#   },
#   {
#     "chunk_id": "section_2",
#     "section": "Key Metrics",
#     "text": "Customer base increased to 1 million users."
#   },
#   {
#     "chunk_id": "section_3",
#     "section": "FY 2025 Outlook",
#     "text": "The company expects continued growth."
#   }
# ]

# 🎯 Why This is Powerful in RAG
# ✅ 1. Preserves Meaning

# Instead of random chunks:

# ❌ Bad:

# "...Revenue grew by 20% Key Metrics Customer base..."

# ✅ Good:

# Section: Revenue Growth
# → Clean, meaningful chunk
# ✅ 2. Improves Retrieval

# User query:

# "What is the revenue growth?"

# 👉 System can:

# Filter by section = "Revenue Growth"
# Retrieve exact chunk
# ✅ 3. Enables Metadata Filtering
# {
#   "section": "Key Metrics"
# }

# 👉 You can do:

# Section-based search
# Priority ranking
# ⚠️ Important Limitation

# This approach depends on:

# 👉 Known section headers

# If document has:

# "Financial Overview" instead of "Revenue Growth"

# ❌ It won’t match

# 🚀 Production Enhancements
# 1. Dynamic Section Detection

# Use:

# NLP models
# LLM prompts

# 2. Combine with Recursive Chunking
# Section Split
#    ↓
# If section too large → Recursive chunking
# 3. Add Metadata
# {
#   "section": "Revenue Growth",
#   "page": 12,
#   "source": "report.pdf"
# }

# 🔄 Final Flow
# Raw Document
#    ↓
# Detect Sections (Regex / NLP)
#    ↓
# Assign Section Labels
#    ↓
# Create Chunks per Section
#    ↓
# (Optional) Further Split Large Sections

# 💡 Intuition

# 👉 This is like converting a document into:

# Chapters → Sections → Content

# Instead of:

# Random text blocks

# def semantic_section_chunking(text: str) -> list[dict]:
#     # Known section headers in this financial report
#     section_pattern = re.compile(
#         r"(?m)^(Executive Summary|Revenue Growth|Key Metrics|Revenue by Segment|FY 2025 Outlook)\s*$"
#     )
#     splits = section_pattern.split(text)
 
#     chunks = []
#     section_name = "Preamble"
#     for part in splits:
#         part = part.strip()
#         if not part:
#             continue
#         if section_pattern.match(part):
#             section_name = part
#         else:
#             chunks.append({
#                 "chunk_id"   : f"section_{len(chunks)}",
#                 "strategy"   : "semantic_section",
#                 "section"    : section_name,
#                 "word_count" : len(part.split()),
#                 "text"       : part,
#             })
#     return chunks
 
 
# semantic_chunks = semantic_section_chunking(raw_text)
# print_chunks(semantic_chunks, "3. Semantic / Section-Aware Chunking", max_show=5)

from langchain_openai import ChatOpenAI
from langchain.messages import SystemMessage, HumanMessage
import json
from dotenv import load_dotenv
load_dotenv()

# Initialize LLM
llm = ChatOpenAI(
    model="gpt-4.1",
    temperature=0
)

def llm_semantic_chunking(text: str) -> list[dict]:
    prompt = f"""
You are an expert in document understanding.

Task:
Split the following document into meaningful semantic sections.

Instructions:
- Identify logical sections (like summary, metrics, outlook, etc.)
- Each chunk should be self-contained
- Do NOT split mid-sentence
- Keep chunks reasonably sized (200–400 words)
- Return output in STRICT JSON format

Output format:
[
  {{
    "section": "Section Name",
    "text": "Chunk content"
  }}
]

Document:
{text}
"""

    response = llm.invoke([
        SystemMessage(content="You are a document chunking expert."),
        HumanMessage(content=prompt)
    ])

    content = response.content

    # Parse JSON safely
    try:
        parsed_chunks = json.loads(content)
    except json.JSONDecodeError:
        print("⚠️ JSON parsing failed. Raw response:", content)
        return []

    # Add metadata (same as your original logic)
    chunks = []
    for i, chunk in enumerate(parsed_chunks):
        chunks.append({
            "chunk_id": f"llm_section_{i}",
            "strategy": "llm_semantic",
            "section": chunk.get("section", "Unknown"),
            "word_count": len(chunk.get("text", "").split()),
            "text": chunk.get("text", "").strip(),
        })

    return chunks
semantic_chunks = llm_semantic_chunking(raw_text)
print_chunks(semantic_chunks, "3. Semantic / Section-Aware Chunking", max_show=5)