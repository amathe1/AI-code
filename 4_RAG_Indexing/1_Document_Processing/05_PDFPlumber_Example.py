# Here is a **line‑by‑line explanation** of the provided `pdfplumber` extraction code, presented as bullet points:

# - `from pathlib import Path`
#   - Imports the `Path` class from Python’s `pathlib` module.
#   - Allows cross‑platform, object‑oriented handling of file system paths.

# - `import pdfplumber`
#   - Imports the `pdfplumber` library, which is designed for extracting text, tables, and metadata from PDFs (better at preserving layout than `PyPDF2`).

# - `# Get the path to the PDF file`
#   - A comment indicating that the following line constructs the path to the target PDF.

# - `pdf_path = Path(__file__).parent / "Data" / "1810.04805v2.pdf"`
#   - `__file__` → a special variable that holds the path of the current Python script.
#   - `Path(__file__)` → converts that path into a `Path` object.
#   - `.parent` → moves one directory up from the script’s location.
#   - `/ "Data" / "1810.04805v2.pdf"` → appends the subdirectory `Data` and the filename `1810.04805v2.pdf` (likely an academic paper from arXiv).
#   - The resulting complete path is stored in `pdf_path`.

# - `def extract_pdfplumber(pdf_path: Path) -> str:`
#   - Defines a function named `extract_pdfplumber`.
#   - Takes one parameter `pdf_path`, expected to be a `Path` object (type hint).
#   - `-> str` indicates the function returns a string (the extracted text).

# - `with pdfplumber.open(pdf_path) as pdf:`
#   - Opens the PDF file located at `pdf_path` using `pdfplumber.open()`.
#   - The `with` statement guarantees the file is properly closed after the block finishes.
#   - The opened PDF object is assigned to the variable `pdf`.

# - `text = ""`
#   - Initializes an empty string that will accumulate the extracted text from all pages.

# - `for page in pdf.pages:`
#   - Loops over each page in the PDF. `pdf.pages` returns an iterable of `Page` objects.

# - `text += page.extract_text(use_text_flow=True)`
#   - Calls `extract_text()` on the current page with the argument `use_text_flow=True`.
#   - `use_text_flow=True` instructs pdfplumber to attempt to reconstruct the natural reading order of the text (following text flow instead of strict top‑to‑bottom bounding box order). This is especially useful for multi‑column documents or complex layouts.
#   - The extracted text string from the page is appended (`+=`) to the `text` accumulator.

# - `return text`
#   - After processing all pages, returns the complete concatenated string.

# - `print("pdfplumber extracted text:")`
#   - Prints a header line to the console, indicating that the following output comes from pdfplumber.

# - `print(extract_pdfplumber(pdf_path)[:500])`
#   - Calls the function `extract_pdfplumber` with `pdf_path`.
#   - Takes the returned string and slices it to get only the first 500 characters (`[:500]`). This prevents flooding the console if the PDF is large.
#   - The sliced text is then printed.

# - `print("-" * 100)`
#   - Prints a line of 100 hyphen characters (`-`).
#   - Acts as a visual separator after the extracted text output.

from pathlib import Path
import pdfplumber

# Get the path to the PDF file
pdf_path = Path(__file__).parent / "Data" / "1810.04805v2.pdf"

def extract_pdfplumber(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text(use_text_flow=True)
        return text
        
print("pdfplumber extracted text:")
print(extract_pdfplumber(pdf_path)[:2000])
print("-" * 100)

# use_text_flow=True