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
 
 #
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
# STRATEGY 2: Recursive Character Text Splitting (LangChain)
# ─────────────────────────────────────────────────────────────────────────────
# Best for: General-purpose RAG — respects paragraphs → sentences → words
# Splits on: \n\n → \n → " " → "" (in order)
# ─────────────────────────────────────────────────────────────────────────────
# 🧠 What this code does

# This function performs recursive character-based chunking using a smart splitting strategy.

# 👉 Instead of blindly cutting text, it:

# Tries to split using natural boundaries (paragraphs, sentences, words)
# Falls back step-by-step if needed
# ⚙️ Key Components
# RecursiveCharacterTextSplitter(
#     chunk_size=400,
#     chunk_overlap=80,
#     separators=["\n\n", "\n", ". ", " ", ""],
# )
# 🔑 Parameters Explained:
# 1. chunk_size = 400
# Max size of each chunk (in characters)
# 2. chunk_overlap = 80
# Overlap between chunks (for context continuity)
# 3. separators

# This is the core logic 👇

# ["\n\n", "\n", ". ", " ", ""]

# 👉 Priority order:

# Level	 Separator	   Meaning
# 1	      \n\n	      Paragraph
# 2	      \n	      Line
# 3	        .	      Sentence
# 4	      " "	      Word
# 5	       ""	    Character-level fallback

# 🔄 How Recursive Splitting Works

# 👉 Algorithm:

# Try splitting by paragraph (\n\n)
# If chunk is still too big → split by line (\n)
# Still big → split by sentence (. )
# Still big → split by words
# Final fallback → split by characters

# 📘 Example Input

# Paragraph 1:
# Insurance policies provide financial protection. They cover risks like accidents and hospitalization.

# Paragraph 2:
# Premium is the amount paid regularly. Claims are processed based on policy terms.

# 🔍 Step-by-Step Execution
# Step 1: Try splitting by paragraph (\n\n)

# We get:

# Chunk Candidate 1:
# Insurance policies provide financial protection. They cover risks like accidents and hospitalization.

# Chunk Candidate 2:
# Premium is the amount paid regularly. Claims are processed based on policy terms.

# 👉 If each is < 400 chars → keep as is

# ✅ Done at paragraph level

# ❗ What if a paragraph is too large?

# Let’s say:

# Paragraph = 1000 characters
# Step 2: Split by sentence (. )

# Example:

# Sentence 1
# Sentence 2
# Sentence 3
# ...

# Now group sentences until:

# length ≤ 400
# Step 3: If still too large → split by words

# Step 4: Final fallback → character-level split

# 👉 This ensures:

# No chunk exceeds size
# But tries to preserve meaning first

# 🔁 Overlap Handling

# After chunks are formed:

# Each chunk overlaps by 80 characters
# Example:
# Chunk 1:
# "...financial protection. They cover risks like accidents"

# Chunk 2:
# "...cover risks like accidents and hospitalization. Premium is..."

# 👉 Overlap ensures:

# No context loss
# Better retrieval quality
# 🧾 Output Format

# Each chunk looks like:

# {
#     "chunk_id": "recursive_0",
#     "strategy": "recursive_character",
#     "chunk_size": 400,
#     "overlap": 80,
#     "text": "Insurance policies provide financial protection..."
# }
# 🔁 Full Flow Summary
# Raw Text
#    ↓
# Try Paragraph Split
#    ↓ (if too big)
# Try Sentence Split
#    ↓ (if too big)
# Try Word Split
#    ↓ (if too big)
# Character Split
#    ↓
# Apply Overlap
#    ↓
# Final Chunks

# ⚖️ Fixed vs Recursive (Important Insight)

# Feature	     Fixed Chunking	  Recursive Chunking
# Splitting	       Blind	        Smart
# Context	    Often broken	  Preserved
# Quality	     Medium	          High
# Production use	Rare	    Very common

def recursive_character_chunking(text: str, chunk_size: int = 400, overlap: int = 80) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    raw_chunks = splitter.split_text(text)
    return [
        {
            "chunk_id"  : f"recursive_{i}",
            "strategy"  : "recursive_character",
            "chunk_size": chunk_size,
            "overlap"   : overlap,
            "text"      : chunk.strip(),
        }
        for i, chunk in enumerate(raw_chunks) if chunk.strip()
    ]
 
 
recursive_chunks = recursive_character_chunking(raw_text, chunk_size=400, overlap=80)
print_chunks(recursive_chunks, "2. Recursive Character Text Splitting (size=400, overlap=80)")