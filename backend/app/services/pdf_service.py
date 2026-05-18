"""
pdf_service.py
--------------
Handles PDF ingestion: text extraction, section detection, and chunking.

Strategy:
  1. pdfplumber  → primary extractor (better layout/table handling)
  2. PyMuPDF     → fallback for scanned/complex PDFs
  3. pypdf       → last-resort fallback
"""

import re
import uuid
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.logger import logger


# ── Section patterns for research paper structure ──────────────────────────────
SECTION_PATTERNS = {
    "abstract":    re.compile(r"\babstract\b", re.IGNORECASE),
    "introduction": re.compile(r"\bintroduction\b", re.IGNORECASE),
    "methodology": re.compile(r"\b(methodology|methods?|approach)\b", re.IGNORECASE),
    "results":     re.compile(r"\b(results?|experiments?|evaluation)\b", re.IGNORECASE),
    "discussion":  re.compile(r"\bdiscussion\b", re.IGNORECASE),
    "conclusion":  re.compile(r"\b(conclusion|summary|future\s+work)\b", re.IGNORECASE),
    "references":  re.compile(r"\b(references|bibliography)\b", re.IGNORECASE),
}


def extract_text_pdfplumber(file_path: str) -> str:
    """Extract text using pdfplumber (primary method)."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        logger.warning(f"pdfplumber extraction failed: {e}")
        return ""


def extract_text_pymupdf(file_path: str) -> str:
    """Extract text using PyMuPDF (fallback method)."""
    try:
        import fitz  # PyMuPDF
        text_parts = []
        doc = fitz.open(file_path)
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts)
    except Exception as e:
        logger.warning(f"PyMuPDF extraction failed: {e}")
        return ""


def extract_text_pypdf(file_path: str) -> str:
    """Extract text using pypdf (last-resort fallback)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        )
    except Exception as e:
        logger.warning(f"pypdf extraction failed: {e}")
        return ""


def extract_text(file_path: str) -> str:
    """
    Try extractors in priority order and return the best result.
    Best = most characters extracted.
    """
    results = {
        "pdfplumber": extract_text_pdfplumber(file_path),
        "pymupdf":    extract_text_pymupdf(file_path),
        "pypdf":      extract_text_pypdf(file_path),
    }
    # pick the extractor that returned the most text
    best_method, best_text = max(results.items(), key=lambda kv: len(kv[1]))
    logger.info(f"Best extractor: {best_method} ({len(best_text):,} chars)")
    return best_text


def detect_sections(text: str) -> dict[str, str]:
    """
    Walk through the text line-by-line and bucket content into named sections.
    Returns a dict: { section_name -> section_text }
    """
    sections: dict[str, list[str]] = {k: [] for k in SECTION_PATTERNS}
    sections["other"] = []

    current_section = "other"
    for line in text.split("\n"):
        stripped = line.strip()
        matched = False
        for section_name, pattern in SECTION_PATTERNS.items():
            # A short line (≤80 chars) that matches a section keyword is a heading
            if len(stripped) <= 80 and pattern.search(stripped):
                current_section = section_name
                matched = True
                break
        if not matched:
            sections[current_section].append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[str]:
    """
    Split text into overlapping chunks for embedding.
    Uses simple character-based splitting with sentence-boundary awareness.
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap    = overlap    or settings.CHUNK_OVERLAP

    # Prefer splitting at sentence endings
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks    = []
    current   = ""

    for sentence in sentences:
        if len(current) + len(sentence) <= chunk_size:
            current += " " + sentence
        else:
            if current.strip():
                chunks.append(current.strip())
            # start new chunk with overlap from the previous one
            current = current[-overlap:] + " " + sentence if overlap else sentence

    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if len(c) > 50]  # discard trivially short chunks


def process_pdf(file_path: str, document_id: Optional[str] = None) -> dict:
    """
    Full PDF processing pipeline.

    Returns
    -------
    {
        "document_id": str,
        "full_text": str,
        "sections": { section_name: text, ... },
        "chunks": [ str, ... ],
        "metadata": { "page_count": int, ... }
    }
    """
    document_id = document_id or str(uuid.uuid4())
    logger.info(f"Processing PDF: {file_path} (doc_id={document_id})")

    # 1. Extract raw text
    full_text = extract_text(file_path)
    if not full_text.strip():
        raise ValueError("Could not extract any text from the PDF. "
                         "The file may be scanned/image-only.")

    # 2. Detect sections
    sections = detect_sections(full_text)

    # 3. Chunk for RAG
    chunks = chunk_text(full_text)

    # 4. Basic metadata
    try:
        import fitz
        doc  = fitz.open(file_path)
        meta = {
            "page_count": len(doc),
            "title":      doc.metadata.get("title", ""),
            "author":     doc.metadata.get("author", ""),
            "subject":    doc.metadata.get("subject", ""),
        }
        doc.close()
    except Exception:
        meta = {"page_count": full_text.count("\f") + 1}

    logger.info(f"Extracted {len(chunks)} chunks, {len(sections)} sections")

    return {
        "document_id": document_id,
        "full_text":   full_text,
        "sections":    sections,
        "chunks":      chunks,
        "metadata":    meta,
    }
