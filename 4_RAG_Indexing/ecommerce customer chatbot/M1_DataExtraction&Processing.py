"""
Module 01 — Data Extraction & Processing
==========================================
Input  : ecommerce_knowledge_base.pdf
Output : extracted_data.json

Run:
    cd rag_system && python 01_extraction.py
"""

import json, re, time, hashlib
from pathlib import Path
from dataclasses import dataclass, asdict
import pdfplumber

PDF_PATH = Path(__file__).parent / "ecommerce_knowledge_base.pdf"
OUT_PATH = Path(__file__).parent / "extracted_data.json"

SECTION_RE = re.compile(r"^(Section\s+\d+[.:][^\n]+)", re.MULTILINE)
SUBSEC_RE  = re.compile(r"^(\d+\.\d+\s+[^\n]+)", re.MULTILINE)
JUNK_RE    = re.compile(r"(ShopNow\s+E-Commerce|Version \d+\.\d+)", re.I)


@dataclass
class RawPage:
    page_num: int; text: str; tables: list
    word_count: int; char_count: int; has_content: bool


@dataclass
class Section:
    section_id: str; section_num: str; title: str; content: str
    page_start: int; char_count: int; word_count: int
    table_count: int; subsections: list; content_hash: str; access_level: str


@dataclass
class Metrics:
    total_pages: int; total_chars: int; total_words: int
    total_sections: int; total_tables: int; empty_pages: int
    extraction_time_ms: float; avg_words_per_section: float
    coverage_pct: float; quality_score: float


def classify_access(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["fraud", "legal", "billing", "compliance"]): return "confidential"
    if any(k in t for k in ["escalation", "agent", "verification", "security"]): return "internal"
    return "public"


def clean(text: str) -> str:
    text = JUNK_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def quality_score(pages: list[RawPage]) -> float:
    if not pages: return 0.0
    s = 0.0
    avg_w = sum(p.word_count for p in pages) / len(pages)
    s += 30 if avg_w >= 100 else (20 if avg_w >= 50 else 10)
    ep = sum(1 for p in pages if not p.has_content) / len(pages)
    s += 30 if ep < 0.05 else (15 if ep < 0.15 else 0)
    s += 20 if any(p.tables for p in pages) else 0
    s += 20 if any(SECTION_RE.search(p.text) for p in pages) else 0
    return round(s, 1)


def extract_pages(pdf_path: Path) -> list[RawPage]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for pg in pdf.pages:
            text = pg.extract_text() or ""
            tables = pg.extract_tables() or []
            pages.append(RawPage(
                page_num=pg.page_number, text=text, tables=tables,
                word_count=len(text.split()), char_count=len(text),
                has_content=len(text.strip()) > 30,
            ))
    return pages


def build_sections(pages: list[RawPage]) -> list[Section]:
    full = "\n\n".join(p.text for p in pages)
    parts = SECTION_RE.split(full)
    secs, idx = [], 0
    i = 0
    while i < len(parts):
        part = parts[i].strip()
        if not part: i += 1; continue
        if SECTION_RE.match(part):
            title = part; content = parts[i+1].strip() if i+1 < len(parts) else ""; i += 2
        else:
            title, content = "Preamble", part; i += 1
        m = re.match(r"Section\s+(\d+)", title)
        body = clean(content)
        pg_start = next((p.page_num for p in pages if title[:15] in p.text), 1)
        tables = sum(1 for p in pages if p.page_num == pg_start and p.tables)
        secs.append(Section(
            section_id=f"sec_{idx:03d}", section_num=m.group(1) if m else "0",
            title=title, content=body, page_start=pg_start,
            char_count=len(body), word_count=len(body.split()),
            table_count=tables, subsections=SUBSEC_RE.findall(content),
            content_hash=hashlib.md5(body.encode()).hexdigest(),
            access_level=classify_access(title),
        ))
        idx += 1
    return secs


def run():
    print("=" * 60)
    print("  MODULE 01 — Data Extraction & Processing")
    print("=" * 60)
    t0 = time.perf_counter()
    pages = extract_pages(PDF_PATH)
    secs  = build_sections(pages)
    ms    = (time.perf_counter() - t0) * 1000
    m = Metrics(
        total_pages=len(pages), total_chars=sum(p.char_count for p in pages),
        total_words=sum(p.word_count for p in pages), total_sections=len(secs),
        total_tables=sum(len(p.tables) for p in pages),
        empty_pages=sum(1 for p in pages if not p.has_content),
        extraction_time_ms=round(ms, 2),
        avg_words_per_section=round(sum(s.word_count for s in secs)/max(len(secs),1), 1),
        coverage_pct=round(sum(1 for p in pages if p.has_content)/max(len(pages),1)*100, 1),
        quality_score=quality_score(pages),
    )
    print(f"\n  Extraction Metrics")
    for k, v in asdict(m).items():
        print(f"    {k:<28}: {v}")
    print(f"\n  Sections [{m.total_sections}]")
    for s in secs:
        print(f"    [{s.section_id}][{s.access_level:<13}] {s.title[:50]:<50} {s.word_count:>5}w")
    output = {"source": PDF_PATH.name, "metrics": asdict(m),
              "sections": [asdict(s) for s in secs],
              "pages": [{"page_num": p.page_num, "word_count": p.word_count,
                         "has_content": p.has_content} for p in pages]}
    OUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"\n  Saved → {OUT_PATH}")
    return output


if __name__ == "__main__":
    run()