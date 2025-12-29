"""
extract_text.py

Extracts text content from PDF files using pdfplumber.
Handles common PDF issues like multi-column layouts and encoding problems.
"""

import pdfplumber
from pathlib import Path
from typing import Optional


def extract_text_from_pdf(pdf_path: str | Path) -> Optional[str]:
    """
    Extract all text from a PDF file.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Extracted text as a single string, or None if extraction fails.
        Pages are separated by double newlines.
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        print(f"[WARN] PDF file not found: {pdf_path}")
        return None

    try:
        all_text = []

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Extract text from the page
                # Using default settings which work well for most CVs
                page_text = page.extract_text()

                if page_text:
                    # Clean up common artifacts
                    page_text = _clean_page_text(page_text)
                    all_text.append(page_text)

        if not all_text:
            print(f"[WARN] No text extracted from: {pdf_path.name}")
            return None

        # Join pages with double newline to preserve page boundaries
        return "\n\n".join(all_text)

    except Exception as e:
        print(f"[ERROR] Failed to extract text from {pdf_path.name}: {e}")
        return None


def _clean_page_text(text: str) -> str:
    """
    Clean up common artifacts in extracted PDF text.

    Args:
        text: Raw text from a PDF page

    Returns:
        Cleaned text
    """
    # Replace multiple spaces with single space (common in PDFs)
    import re
    text = re.sub(r' {2,}', ' ', text)

    # Normalize various dash characters to standard hyphen
    text = text.replace('', '-')  # en-dash
    text = text.replace('', '-')  # em-dash
    text = text.replace('', '-')  # minus sign

    # Remove form feed and other control characters (except newlines/tabs)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Remove excessive blank lines (more than 2 consecutive)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def extract_text_with_metadata(pdf_path: str | Path) -> dict:
    """
    Extract text and basic metadata from a PDF file.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dictionary with 'text', 'num_pages', 'filename', and 'success' keys
    """
    pdf_path = Path(pdf_path)

    result = {
        'filename': pdf_path.name,
        'text': None,
        'num_pages': 0,
        'success': False
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            result['num_pages'] = len(pdf.pages)

            all_text = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    all_text.append(_clean_page_text(page_text))

            if all_text:
                result['text'] = "\n\n".join(all_text)
                result['success'] = True

    except Exception as e:
        print(f"[ERROR] Failed to process {pdf_path.name}: {e}")

    return result
