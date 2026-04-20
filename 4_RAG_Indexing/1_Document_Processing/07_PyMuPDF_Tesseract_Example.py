# Here is a **line‑by‑line explanation** of the PyMuPDF + OpenCV + Tesseract OCR code, presented as bullet points:

# - `import fitz  # PyMuPDF`
#   - Imports the `fitz` module, which is the Python binding for PyMuPDF.
#   - PyMuPDF is used to open, render, and extract content from PDF files (including converting pages to images).

# - `import pytesseract`
#   - Imports the `pytesseract` library, a Python wrapper for Google’s Tesseract OCR engine.
#   - Used to extract text from images.

# - `import cv2`
#   - Imports OpenCV (`cv2`), a computer vision library.
#   - Used for image preprocessing (grayscale, noise removal, thresholding).

# - `import numpy as np`
#   - Imports NumPy, which provides support for large, multi‑dimensional arrays.
#   - Used to convert PIL images to NumPy arrays for OpenCV processing.

# - `from PIL import Image`
#   - Imports the `Image` class from the Pillow (PIL) library.
#   - Used to create PIL Image objects from raw pixel data.

# - `# Set Tesseract path (Windows)`
#   - A comment indicating that the Tesseract executable path must be set manually on Windows.

# - `pytesseract.pytesseract.tesseract_cmd = r"C:\Users\anilk\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"`
#   - Specifies the location of the Tesseract OCR executable on the system.
#   - The raw string (`r"..."`) prevents backslashes from being interpreted as escape characters.

# - `pdf_path = "C:\\Personal\\2024\\Learning\\Generative AI\\RAG\\27_Context_Engineering\\2_RAG\\1_Document_Processing\\Data\\CIA-RDP82-00038R001800200001-1.pdf"`
#   - Assigns a string containing the path to the input PDF file (double backslashes are used for escaping in regular strings).
#   - The file appears to be a declassified CIA document (based on naming pattern).

# - `def preprocess_image(pil_image):`
#   - Defines a function named `preprocess_image` that takes a PIL Image as input.
#   - The function applies image processing steps to improve OCR accuracy.

# - `img = np.array(pil_image)`
#   - Converts the input PIL image into a NumPy array so it can be processed with OpenCV.
#   - The array contains pixel values in (height, width, channels) format.

# - `# Convert to grayscale`
#   - A comment describing the next operation.

# - `gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)`
#   - Converts the image from BGR color space (default for OpenCV when reading from certain sources) to grayscale.
#   - Grayscale simplifies the image and is sufficient for text recognition.

# - `# Remove noise`
#   - A comment indicating noise reduction.

# - `gray = cv2.medianBlur(gray, 3)`
#   - Applies a median blur filter with a kernel size of 3×3.
#   - This reduces salt‑and‑pepper noise while preserving edges.

# - `# Threshold (important for old scans)`
#   - A comment explaining that thresholding is especially helpful for old, faded, or low‑contrast scanned documents.

# - `_, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)`
#   - Applies binary thresholding: pixels with intensity > 150 become white (255), others become black (0).
#   - `_` discards the first return value (the threshold value used).
#   - The resulting binary image (`thresh`) has high contrast, making it easier for Tesseract to recognise text.

# - `return thresh`
#   - Returns the preprocessed binary image (as a NumPy array).

# - `def extract_text(pdf_path):`
#   - Defines a function named `extract_text` that takes a PDF file path as input.
#   - It will render each PDF page to an image, preprocess it, and run OCR.

# - `doc = fitz.open(pdf_path)`
#   - Opens the PDF file using PyMuPDF and stores the document object in `doc`.

# - `full_text = ""`
#   - Initialises an empty string that will accumulate the final extracted text from all pages.

# - `for page_num, page in enumerate(doc):`
#   - Loops over each page in the PDF document.
#   - `enumerate` provides the page index (`page_num`) starting from 0, and the page object (`page`).

# - `print(f"Processing page {page_num + 1}/{len(doc)}")`
#   - Prints a progress message showing the current page number and total number of pages.

# - `# Convert page → image`
#   - A comment indicating the next lines convert the PDF page into an image.

# - `pix = page.get_pixmap(dpi=300)  # high DPI improves OCR`
#   - Renders the current page into a pixmap (a bitmap image) with a resolution of 300 DPI (dots per inch).
#   - Higher DPI produces a larger, clearer image, which improves OCR accuracy.

# - `img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)`
#   - Creates a PIL Image object from the raw pixel data in the pixmap.
#   - `"RGB"` specifies the colour mode, `[pix.width, pix.height]` gives the dimensions, and `pix.samples` provides the pixel bytes.

# - `# Preprocess`
#   - A comment indicating that the image preprocessing function will be called.

# - `processed = preprocess_image(img)`
#   - Calls the `preprocess_image` function on the PIL image, which returns a preprocessed NumPy array (binary image).

# - `# OCR`
#   - A comment indicating the next line performs optical character recognition.

# - `text = pytesseract.image_to_string(`
#   - Calls Tesseract’s `image_to_string` function to extract text from the processed image.

# - `processed,`
#   - The first argument: the preprocessed image (NumPy array). Tesseract can accept both PIL images and NumPy arrays.

# - `config="--oem 3 --psm 6"`
#   - Provides Tesseract configuration options:
#     - `--oem 3` → uses the LSTM OCR engine only (best for most documents).
#     - `--psm 6` → page segmentation mode: “Assume a single uniform block of text.”

# - `)`
#   - Closes the `image_to_string` call. The extracted text is stored in `text`.

# - `full_text += f"\n--- Page {page_num+1} ---\n{text}"`
#   - Appends the extracted text to `full_text`.
#   - Adds a header line (`--- Page X ---`) before each page’s content for readability, plus newlines.

# - `return full_text`
#   - After processing all pages, returns the complete extracted text as a single string.

# - `result = extract_text(pdf_path)`
#   - Calls the `extract_text` function with the previously defined `pdf_path` and stores the returned text in `result`.

# - `# Save output`
#   - A comment indicating that the following lines save the extracted text to a file.

# - `with open("output.txt", "w", encoding="utf-8") as f:`
#   - Opens (or creates) a file named `output.txt` in write mode (`"w"`) with UTF‑8 encoding.
#   - The `with` statement ensures the file is properly closed after writing.

# - `f.write(result)`
#   - Writes the entire extracted text (`result`) into the file.

# - `print("Extraction completed!")`
#   - Prints a completion message to the console, indicating that the OCR process and file saving are done.

import fitz  # PyMuPDF
import pytesseract
import cv2
import numpy as np
from PIL import Image

# Set Tesseract path (Windows)
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\anilk\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

pdf_path = "D:\GenAI Content\\AI code\\4_RAG_Indexing\\1_Document_Processing\\Data\\CIA-RDP82-00038R001800200001-1.pdf"

def preprocess_image(pil_image):
    img = np.array(pil_image)

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Remove noise
    gray = cv2.medianBlur(gray, 3)

    # Threshold (important for old scans)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    return thresh


def extract_text(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""

    for page_num, page in enumerate(doc):
        print(f"Processing page {page_num + 1}/{len(doc)}")

        # Convert page → image
        pix = page.get_pixmap(dpi=300)  # high DPI improves OCR
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Preprocess
        processed = preprocess_image(img)

        # OCR
        text = pytesseract.image_to_string(
            processed,
            config="--oem 3 --psm 6"
        )

        full_text += f"\n--- Page {page_num+1} ---\n{text}"

    return full_text


result = extract_text(pdf_path)

# Save output
with open("output.txt", "w", encoding="utf-8") as f:
    f.write(result)

print("Extraction completed!")