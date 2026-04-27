import pdfplumber
import json
import os

from utils.config_loader import load_config
from utils.logger import setup_logger
from utils.retry import retry

config = load_config()
logger = setup_logger(config["paths"]["logs"])


@retry(max_attempts=3)
def extract_text_from_pdf(pdf_path: str):
    data = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            try:
                text = page.extract_text()
                if text:
                    data.append({
                        "page": i + 1,
                        "text": text
                    })
            except Exception as e:
                logger.warning(f"Page {i+1} extraction failed: {e}")

    return data


def run_data_extraction():
    pdf_path = config["paths"]["raw_pdf"]
    output_path = config["paths"]["data_json"]

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found at {pdf_path}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    logger.info("📥 Starting PDF extraction...")

    try:
        data = extract_text_from_pdf(pdf_path)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        logger.info(f"✅ Extraction complete: {len(data)} pages processed")

    except Exception as e:
        logger.error(f"❌ Extraction failed: {e}")
        raise