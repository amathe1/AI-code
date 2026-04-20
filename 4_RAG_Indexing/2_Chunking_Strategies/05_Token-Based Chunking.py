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
# STRATEGY 5: Token-Based Chunking
# ─────────────────────────────────────────────────────────────────────────────
# Best for: LLM APIs with token limits (OpenAI, Claude, etc.)
# Logic:    Count tokens via tiktoken; never exceed model context window
# ─────────────────────────────────────────────────────────────────────────────
def token_based_chunking(text: str, max_tokens: int = 150, overlap_tokens: int = 20) -> list[dict]:
    # Initialize tokenizer (same used by GPT-4 / GPT-4.1 family)
    encoding = tiktoken.get_encoding("cl100k_base")

    # Convert text → token IDs
    tokens = encoding.encode(text)

    chunks = []
    start = 0

    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))

        # Slice tokens
        token_slice = tokens[start:end]

        # Convert tokens back → text
        chunk_text = encoding.decode(token_slice).strip()

        if chunk_text:
            chunks.append({
                "chunk_id"     : f"token_{len(chunks)}",
                "strategy"     : "token_based",
                "max_tokens"   : max_tokens,
                "actual_tokens": len(token_slice),
                "token_start"  : start,
                "token_end"    : end,
                "text"         : chunk_text,
            })

        # Move forward with overlap
        start += max_tokens - overlap_tokens

    return chunks

token_chunks = token_based_chunking(raw_text, max_tokens=150, overlap_tokens=20) 
print_chunks(token_chunks, "5. Token-Based Chunking (max=150 tokens, overlap=20)")