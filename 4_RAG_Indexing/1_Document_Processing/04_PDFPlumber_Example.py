from pathlib import Path
import pdfplumber

# Get the path to the PDF file
pdf_path = Path(__file__).parent / "Data" / "1706.03762v7.pdf"

def extract_pdfplumber(pdf_path: Path) -> str:
    text = ""
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            
            if page_text:  # Handle None cases
                text += page_text + "\n"
    
    return text

print(extract_pdfplumber(pdf_path))