# Here is a **line‑by‑line explanation** of the `pdfplumber`‑based PDF extraction code, presented as bullet points:

# - `from pathlib import Path`
#   - Imports the `Path` class from Python’s `pathlib` module.
#   - Enables object‑oriented, cross‑platform handling of file paths.

# - `import pdfplumber`
#   - Imports the `pdfplumber` library, which is more powerful than `PyPDF2` for extracting text, tables, and metadata from PDFs (handles layouts better).

# - `# Get the path to the PDF file`
#   - A comment indicating the next line builds the file path to the target PDF.

# - `pdf_path = Path(__file__).parent / "Data" / "financial_report_2024.pdf"`
#   - `__file__` → special variable holding the path of the current Python script.
#   - `Path(__file__)` → converts that path into a `Path` object.
#   - `.parent` → moves one directory up from the script’s location.
#   - `/ "Data" / "financial_report_2024.pdf"` → appends the subdirectory `Data` and the filename `financial_report_2024.pdf` to the path.
#   - The resulting complete path is stored in `pdf_path`.

# - `def extract_pdfplumber(pdf_path: Path) -> str:`
#   - Defines a function named `extract_pdfplumber`.
#   - It takes one parameter, `pdf_path`, expected to be a `Path` object (type hint).
#   - `-> str` indicates the function will return a string (the extracted text).

# - `text = ""`
#   - Initializes an empty string that will accumulate the extracted text from all pages.

# - `with pdfplumber.open(pdf_path) as pdf:`
#   - Opens the PDF file located at `pdf_path` using `pdfplumber.open()`.
#   - The `with` statement ensures the PDF is automatically closed after the block ends.
#   - The opened PDF object is assigned to the variable `pdf`.

# - `for page in pdf.pages:`
#   - Loops over every page in the PDF. `pdf.pages` returns a list of `Page` objects, one per page.

# - `page_text = page.extract_text()`
#   - Calls the `extract_text()` method on the current page.
#   - This attempts to extract all text content from that page as a string.  
#   - If the page contains no text (e.g., a scanned image page), it returns `None`.

# - `if page_text:  # Handle None cases`
#   - Checks if `page_text` is not `None` (i.e., text was actually found).
#   - This prevents adding the string `"None"` to the result and avoids errors.

# - `text += page_text + "\n"`
#   - Appends the extracted page text to the accumulator `text`.
#   - Also adds a newline character `"\n"` after each page to separate content visually.

# - `return text`
#   - After processing all pages, returns the complete concatenated string containing the extracted text with newlines between pages.

# - `print(extract_pdfplumber(pdf_path))`
#   - Calls the function `extract_pdfplumber` with the previously defined `pdf_path`.
#   - The returned text is passed to `print()`, which outputs it to the console.

from pathlib import Path
import pdfplumber

# Get the path to the PDF file
pdf_path = Path(__file__).parent / "Data" / "financial_report_2024.pdf"

def extract_pdfplumber(pdf_path: Path) -> str:
    text = ""
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            
            if page_text:  # Handle None cases
                text += page_text + "\n"
    
    return text

print(extract_pdfplumber(pdf_path))