#Windows: Install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki

# Here is a **line‑by‑line explanation** of the OCR‑based scanned PDF extraction code, presented as bullet points:

# - `from pdf2image import convert_from_path`
#   - Imports the `convert_from_path` function from the `pdf2image` library.
#   - This function converts each page of a PDF into a PIL Image object (used for OCR).

# - `import pytesseract`
#   - Imports the `pytesseract` library, a Python wrapper for Google’s Tesseract OCR engine.
#   - It extracts text from images by performing optical character recognition.

# - `from pathlib import Path`
#   - Imports the `Path` class from Python’s `pathlib` module.
#   - Provides object‑oriented, cross‑platform handling of file paths.

# - `# ✅ Set Tesseract path (IMPORTANT on Windows)`
#   - A comment indicating that Tesseract’s executable location must be specified manually on Windows (since it is not automatically in PATH).

# - `pytesseract.pytesseract.tesseract_cmd = r"C:\Users\anilk\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"`
#   - Sets the path to the Tesseract OCR executable.
#   - The `r` before the string denotes a raw string, which treats backslashes as literal characters (avoiding escape sequences).
#   - This line is necessary for `pytesseract` to locate the Tesseract engine on Windows.

# - `# ✅ Use raw string for Windows path`
#   - A comment indicating that the PDF path is also written as a raw string for safety.

# - `pdf_path = Path(r"C:\Personal\2024\Learning\Generative AI\RAG\27_Context_Engineering\2_RAG\1_Document_Processing\Data\fixed_scanned_image.pdf")`
#   - Creates a `Path` object from the given raw string path.
#   - The path points to a scanned PDF file named `fixed_scanned_image.pdf` (likely a PDF containing images of text rather than selectable text).

# - `def extract_text_from_scanned_pdf(pdf_path: Path):`
#   - Defines a function named `extract_text_from_scanned_pdf`.
#   - It takes one parameter `pdf_path`, expected to be a `Path` object (type hint, though the return type is not specified).
#   - The function will extract text from a scanned PDF using OCR.

# - `text = ""`
#   - Initializes an empty string that will accumulate the OCR‑extracted text from all pages.

# - `# ✅ Convert PDF → images (fix: pass str path)`
#   - A comment noting that `convert_from_path` expects a string path, not a `Path` object, so we must convert it.

# - `images = convert_from_path(`
#   - Calls `convert_from_path` to convert the PDF into a list of PIL Image objects (one per page).

# - `str(pdf_path),  # ⚠️ Important fix`
#   - Converts the `Path` object `pdf_path` to a string using `str()` because `convert_from_path` requires a string path.
#   - This is the first argument to the function.

# - `poppler_path=r"C:\Users\anilk\Downloads\Release-25.12.0-0\poppler-25.12.0\Library\bin"`
#   - Specifies the path to the Poppler utilities (required by `pdf2image` on Windows for PDF rendering).
#   - The `r` makes it a raw string to handle backslashes correctly.
#   - This tells `pdf2image` where to find `pdftoppm.exe` and other Poppler binaries.

# - `)`
#   - Closes the `convert_from_path` function call. The returned list of images is stored in `images`.

# - `for i, image in enumerate(images):`
#   - Loops over each image (page) in the `images` list.
#   - `enumerate` provides both the index `i` (starting from 0) and the `image` object.

# - `print(f"Processing page {i+1}...")`
#   - Prints a status message indicating which page is being processed (adds 1 to `i` because page numbers start at 1 for humans).

# - `# ✅ Improve OCR accuracy with config`
#   - A comment explaining that Tesseract configuration options are used to enhance recognition quality.

# - `page_text = pytesseract.image_to_string(`
#   - Calls `image_to_string` from `pytesseract` to perform OCR on the current `image`.

# - `image,`
#   - Passes the current PIL image as the first argument.

# - `config="--oem 3 --psm 6"`
#   - Provides Tesseract configuration flags:
#     - `--oem 3` → uses the default OCR Engine Mode (LSTM only, which is the best for most cases).
#     - `--psm 6` → sets Page Segmentation Mode to “Assume a single uniform block of text.” This is suitable for a typical document page.

# - `)`
#   - Closes the `image_to_string` call. The extracted text (as a string) is stored in `page_text`.

# - `text += page_text + "\n"`
#   - Appends the extracted text from the current page to the accumulator `text`.
#   - Adds a newline character `"\n"` after each page to separate content.

# - `return text`
#   - After processing all pages, returns the complete extracted text.

# - `if __name__ == "__main__":`
#   - Checks if the script is being run directly (not imported as a module).
#   - If true, the indented block will execute.

# - `result = extract_text_from_scanned_pdf(pdf_path)`
#   - Calls the function `extract_text_from_scanned_pdf` with `pdf_path`.
#   - The returned OCR text is stored in the variable `result`.

# - `print(result)`
#   - Prints the full extracted text from the scanned PDF to the console.

from pdf2image import convert_from_path
import pytesseract
from pathlib import Path

# ✅ Set Tesseract path (IMPORTANT on Windows)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Users\anilk\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ✅ Use raw string for Windows path
#pdf_path = Path(r"C:\Personal\2024\Learning\Generative AI\RAG\27_Context_Engineering\2_RAG\1_Document_Processing\Data\fixed_scanned_image.pdf")
pdf_path = Path(r"D:\GenAI Content\AI code\4_RAG_Indexing\1_Document_Processing\Data\fixed_scanned_image.pdf")


def extract_text_from_scanned_pdf(pdf_path: Path):
    text = ""

    # ✅ Convert PDF → images (fix: pass str path)
    images = convert_from_path(
        str(pdf_path),  # ⚠️ Important fix
        #poppler_path=r"C:\Users\anilk\Downloads\Release-25.12.0-0\poppler-25.12.0\Library\bin"
        poppler_path=r"D:\GenAI Content\Release-25.12.0-0\poppler-25.12.0\Library\bin"
    )

    for i, image in enumerate(images):
        print(f"Processing page {i+1}...")

        # ✅ Improve OCR accuracy with config
        page_text = pytesseract.image_to_string(
            image,
            config="--oem 3 --psm 6"
        )

        text += page_text + "\n"

    return text


if __name__ == "__main__":
    result = extract_text_from_scanned_pdf(pdf_path)
    print(result)