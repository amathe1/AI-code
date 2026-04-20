"""
Module 02 — Semantic Chunking + Cost Tracking + Fallback
==========================================================
Strategy : GPT-4o-mini identifies natural semantic break points.
Fallback : RecursiveCharacterTextSplitter when API unavailable.
Output   : chunks.json  (with per-chunk and aggregate cost)

Run:
    cd rag_system && python 02_chunking.py
"""

import os, json, re, time
from pathlib import Path
from dataclasses import dataclass, asdict, field
from langchain_text_splitters import RecursiveCharacterTextSplitter

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
LLM_MODEL       = "gpt-4o-mini"
PRICE_IN_1M     = 0.150    # $0.150 per 1M input tokens
PRICE_OUT_1M    = 0.600    # $0.600 per 1M output tokens
PRICE_EMBED_1M  = 0.020    # embedding cost estimate

DATA_PATH = Path(__file__).parent / "extracted_data.json"
OUT_PATH  = Path(__file__).parent / "chunks.json"

CHUNK_PROMPT = """Split the text below into semantically coherent chunks.
Rules:
- Each chunk covers ONE complete topic or policy rule
- 80–400 tokens per chunk
- Never cut mid-sentence or mid-policy
- Preserve all numbers, percentages, timeframes

Return ONLY a JSON array of strings. No markdown, no explanation.

Text:
{text}"""


@dataclass
class Chunk:
    chunk_id: str; section_id: str; section_title: str; text: str
    token_count: int; char_count: int; strategy: str; chunk_index: int
    metadata: dict = field(default_factory=dict)


@dataclass
class Cost:
    llm_in_tokens: int = 0; llm_out_tokens: int = 0; llm_usd: float = 0.0
    embed_tokens: int = 0;  embed_usd: float = 0.0; total_usd: float = 0.0
    api_calls: int = 0;     fallback_sections: int = 0


def tok(text: str) -> int:
    try:
        import tiktoken
        return len(tiktoken.encoding_for_model("gpt-4o-mini").encode(text))
    except Exception:
        return int(len(text.split()) * 1.3)


def llm_chunk(section_id: str, text: str, cost: Cost) -> tuple[list[str], str]:
    if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_OPENAI_API_KEY":
        return _fallback(text, cost, section_id), "recursive_fallback"
    try:
        import openai
        client   = openai.OpenAI(api_key=OPENAI_API_KEY)
        prompt   = CHUNK_PROMPT.format(text=text[:5000])
        t0       = time.perf_counter()
        resp     = client.chat.completions.create(
            model=LLM_MODEL, messages=[{"role": "user", "content": prompt}],
            temperature=0, max_tokens=2000)
        lat = (time.perf_counter() - t0) * 1000
        it, ot   = resp.usage.prompt_tokens, resp.usage.completion_tokens
        cost.llm_in_tokens  += it; cost.llm_out_tokens += ot
        cost.llm_usd        += it/1e6*PRICE_IN_1M + ot/1e6*PRICE_OUT_1M
        cost.api_calls      += 1
        raw = re.sub(r"^```json\s*|\s*```$", "", resp.choices[0].message.content.strip(), flags=re.M)
        chunks = json.loads(raw)
        print(f"    [LLM  ] {section_id}: {len(chunks)} chunks ({it}+{ot} tok, {lat:.0f}ms)")
        return [c.strip() for c in chunks if c.strip()], "semantic_llm"
    except Exception as e:
        print(f"    [FALL ] {section_id}: {e}")
        cost.fallback_sections += 1
        return _fallback(text, cost, section_id), "recursive_fallback"


def _fallback(text: str, cost: Cost, sid: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1400, chunk_overlap=150, separators=["\n\n", "\n", ". ", " "])
    chunks = [c for c in splitter.split_text(text) if c.strip()]
    print(f"    [FALL ] {sid}: {len(chunks)} chunks via recursive fallback")
    return chunks


def run():
    print("=" * 60)
    print("  MODULE 02 — Semantic Chunking")
    print("=" * 60)

    data  = json.loads(DATA_PATH.read_text())
    cost  = Cost()
    all_chunks: list[Chunk] = []
    ctr   = 0

    for sec in data["sections"]:
        if len(sec["content"].strip()) < 60:
            continue
        raw, strategy = llm_chunk(sec["section_id"], sec["content"], cost)
        for idx, text in enumerate(raw):
            t = tok(text)
            all_chunks.append(Chunk(
                chunk_id=f"chunk_{ctr:04d}", section_id=sec["section_id"],
                section_title=sec["title"], text=text,
                token_count=t, char_count=len(text),
                strategy=strategy, chunk_index=idx,
                metadata={
                    "section_num" : sec["section_num"],
                    "page_start"  : sec["page_start"],
                    "source"      : "ecommerce_knowledge_base.pdf",
                    "has_tables"  : sec["table_count"] > 0,
                    "access_level": sec["access_level"],
                },
            ))
            ctr += 1

    cost.embed_tokens = sum(c.token_count for c in all_chunks)
    cost.embed_usd    = round(cost.embed_tokens / 1e6 * PRICE_EMBED_1M, 8)
    cost.total_usd    = round(cost.llm_usd + cost.embed_usd, 6)

    print(f"\n  Results")
    print(f"    Total chunks          : {len(all_chunks)}")
    print(f"    Avg tokens/chunk      : {sum(c.token_count for c in all_chunks)//max(len(all_chunks),1)}")
    print(f"    Fallback sections     : {cost.fallback_sections}")
    print(f"\n  Cost Breakdown")
    print(f"    LLM input tokens      : {cost.llm_in_tokens:,}")
    print(f"    LLM output tokens     : {cost.llm_out_tokens:,}")
    print(f"    LLM cost              : ${cost.llm_usd:.6f}")
    print(f"    Embed tokens (est.)   : {cost.embed_tokens:,}")
    print(f"    Embed cost (est.)     : ${cost.embed_usd:.6f}")
    print(f"    TOTAL                 : ${cost.total_usd:.6f}")

    from collections import Counter
    by_sec = Counter(c.section_id for c in all_chunks)
    print(f"\n  Chunks per section")
    for sid, cnt in sorted(by_sec.items()):
        title = next(c.section_title for c in all_chunks if c.section_id == sid)
        print(f"    {sid}: {cnt:>3} chunks  {title[:50]}")

    output = {
        "cost": asdict(cost), "stats": {
            "total_chunks": len(all_chunks),
            "avg_tokens"  : sum(c.token_count for c in all_chunks)//max(len(all_chunks),1),
            "max_tokens"  : max(c.token_count for c in all_chunks),
            "min_tokens"  : min(c.token_count for c in all_chunks),
        },
        "chunks": [asdict(c) for c in all_chunks],
    }
    OUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"\n  Saved → {OUT_PATH}")
    return output


if __name__ == "__main__":
    run()