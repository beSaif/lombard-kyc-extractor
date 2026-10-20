"""Turn a PDF into page texts. Text-layer PDFs only; scans would need an OCR step here (docTR, PaddleOCR)."""

from pathlib import Path

from pypdf import PdfReader


def read_pages(path: Path) -> list[str]:
    pages = [page.extract_text() or "" for page in PdfReader(str(path)).pages]
    if not any(p.strip() for p in pages):
        raise ValueError(f"{path.name}: no text layer; plug an OCR engine into read_pages")
    return pages
