"""PDF processing service"""

import io
import logging
from typing import List, Dict
from PyPDF2 import PdfReader

logger = logging.getLogger("uvicorn.error")


def extract_text_from_pdf(pdf_bytes: bytes) -> List[Dict[str, any]]:
    """Extract text from each page of a PDF"""
    logger.info(f"Starting PDF text extraction from {len(pdf_bytes)} bytes")
    pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(pdf_reader.pages)
    logger.info(f"PDF has {total_pages} total pages")

    pages_data = []

    for page_num, page in enumerate(pdf_reader.pages):
        text = page.extract_text()
        if text.strip():  # Only include pages with text
            pages_data.append({"page_number": page_num + 1, "text": text.strip()})
            logger.info(
                f"Extracted text from page {page_num + 1}/{total_pages} ({len(text.strip())} chars)"
            )
        else:
            logger.warning(f"Page {page_num + 1}/{total_pages} has no extractable text")

    logger.info(
        f"Successfully extracted text from {len(pages_data)}/{total_pages} pages"
    )
    return pages_data
