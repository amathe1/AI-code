from pathlib import Path
import PyPDF2

# Get the path to the PDF file
pdf_path = Path(__file__).parent / "Data" / "1706.03762v7.pdf"

def extract_pypdf2(pdf_path: Path) -> str:
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text

print(extract_pypdf2(pdf_path))