"""PDF processing service (Q&A-optimized)"""

import io
import logging
from typing import List, Dict

from PyPDF2 import PdfReader

logger = logging.getLogger("uvicorn.error")


def _split_page_into_chunks(text: str, page_number: int) -> List[Dict[str, any]]:
    """
    Split a page into Q&A chunks.

    Assumptions for this Q&A PDF:
    - Each question starts on its own line with something like:  "Q1. ...",
      "Q2. ...", etc. (we just check line.startswith("Q")).
    - The answer lines immediately follow, including bullet points,
      until the next question line starting with "Q" or end of page.
    - Header/title lines that don't start with "Q" are ignored.
    """
    chunks: List[Dict[str, any]] = []

    # Keep raw lines; we'll trim per use
    raw_lines = text.splitlines()
    if not raw_lines:
        return chunks

    i = 0
    n = len(raw_lines)

    while i < n:
        line = raw_lines[i].strip()

        # Skip empty or non-question header lines
        if not line or not line.startswith("Q"):
            i += 1
            continue

        # Start of a Q&A block
        group: List[str] = [line]
        i += 1

        # Collect answer lines until the next question or EOF
        while i < n:
            candidate = raw_lines[i].strip()

            if candidate and candidate.startswith("Q"):
                # Next question starts here; stop current block
                break

            # We include empty lines and "A..." / bullet lines as part of the answer
            group.append(candidate)
            i += 1

        chunk_text = "\n".join(l for l in group if l is not None).strip()
        if chunk_text:
            chunks.append({"page_number": page_number, "text": chunk_text})

    return chunks


def extract_text_from_pdf(pdf_bytes: bytes) -> List[Dict[str, any]]:
    """
    Extract text from a Q&A-formatted PDF and return Q&A chunks.

    Each returned item has:
      - page_number (1-based)
      - text (one full Q&A pair as a single chunk)
    """
    logger.info(f"Starting PDF text extraction from {len(pdf_bytes)} bytes")
    pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(pdf_reader.pages)
    logger.info(f"PDF has {total_pages} total pages")

    pages_data: List[Dict[str, any]] = []

    for page_num, page in enumerate(pdf_reader.pages, start=1):
        raw_text = page.extract_text() or ""
        text = raw_text.strip()

        if not text:
            logger.warning(f"Page {page_num}/{total_pages} has no extractable text")
            continue

        page_chunks = _split_page_into_chunks(text, page_num)

        if not page_chunks:
            # Fallback: whole page as one chunk (shouldn't usually happen
            # for your Q&A PDF, but keeps things robust)
            pages_data.append({"page_number": page_num, "text": text})
            logger.info(
                f"Stored full page {page_num}/{total_pages} as one chunk "
                f"({len(text)} chars)"
            )
        else:
            pages_data.extend(page_chunks)
            logger.info(
                f"Page {page_num}/{total_pages}: split into "
                f"{len(page_chunks)} Q&A chunk(s)"
            )

    logger.info(
        f"Successfully extracted {len(pages_data)} Q&A chunks "
        f"from {total_pages} pages"
    )
    return pages_data
