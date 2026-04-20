# Here is a **line‑by‑line explanation** presented as bullet points:

# - `from pathlib import Path`
#   - Imports the `Path` class from Python’s `pathlib` module.
#   - Allows you to work with file paths in an object‑oriented, cross‑platform way.

# - `import PyPDF2`
#   - Imports the `PyPDF2` library, which is used to read and manipulate PDF files (e.g., extracting text, merging pages).

# - `# Get the path to the PDF file`
#   - A comment indicating the next line builds the file path to the target PDF.

# - `pdf_path = Path(__file__).parent / "Data" / "financial_report_2024.pdf"`
#   - `__file__` → special variable holding the path of the current Python script.
#   - `Path(__file__)` → converts that path into a `Path` object.
#   - `.parent` → moves one directory up from the script’s location.
#   - `/ "Data" / "financial_report_2024.pdf"` → appends the subdirectory `Data` and the filename `financial_report_2024.pdf` to the path.
#   - The resulting complete path is stored in `pdf_path`.

# - `def extract_pypdf2(pdf_path: Path) -> str:`
#   - Defines a function named `extract_pypdf2`.
#   - It takes one parameter, `pdf_path`, which is expected to be a `Path` object (type hint).
#   - The `-> str` indicates the function will return a string (the extracted text).

# - `with open(pdf_path, "rb") as f:`
#   - Opens the file at `pdf_path` in **binary read mode** (`"rb"`).
#   - The `with` statement ensures the file is automatically closed when the block finishes.
#   - The opened file object is assigned to variable `f`.

# - `reader = PyPDF2.PdfReader(f)`
#   - Creates a `PdfReader` object from the opened PDF file (`f`).
#   - This reader provides access to the PDF’s pages, metadata, etc.

# - `text = ""`
#   - Initializes an empty string that will later hold all extracted text from the PDF.

# - `for page in reader.pages:`
#   - Loops over every page in the PDF. `reader.pages` returns an iterable of `PageObject` instances, one per page.

# - `text += page.extract_text()`
#   - On each page, calls the `extract_text()` method to get the page’s text content.
#   - Appends (`+=`) that text to the `text` variable.

# - `return text`
#   - After the loop finishes (all pages processed), returns the accumulated string containing the full extracted text.

# - `print(extract_pypdf2(pdf_path))`
#   - Calls the function `extract_pypdf2` with the previously defined `pdf_path`.
#   - The returned text is passed to `print()`, which outputs it to the console.
from pathlib import Path
import PyPDF2

# Get the path to the PDF file
pdf_path = Path(__file__).parent / "Data" / "financial_report_2024.pdf"

def extract_pypdf2(pdf_path: Path) -> str:
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text

print(extract_pypdf2(pdf_path))