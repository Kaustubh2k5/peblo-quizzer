import pdfplumber
import re
import io
from typing import List, Tuple
from app.core.config import settings
from app.core.models import ContentChunk, SourceDocument


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract raw text from PDF bytes using pdfplumber."""
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text.strip())
    return "\n\n".join(text_parts)


def clean_text(text: str) -> str:
    """Remove noise while preserving educational content structure."""
    # Collapse excessive whitespace but keep paragraph breaks
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    # Remove page numbers (standalone digits on a line)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    # Remove header/footer-like repeated short lines
    lines = text.split("\n")
    cleaned = [l for l in lines if len(l.strip()) > 3 or l.strip() == ""]
    return "\n".join(cleaned).strip()


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
    """
    Split text into overlapping chunks at paragraph boundaries where possible.
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE_CHARS
    overlap = overlap or settings.CHUNK_OVERLAP_CHARS

    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            # Start new chunk with overlap from previous
            if len(para) > chunk_size:
                # Paragraph itself is too long — split by sentence
                sentences = re.split(r"(?<=[.!?])\s+", para)
                current = ""
                for sent in sentences:
                    if len(current) + len(sent) + 1 <= chunk_size:
                        current = (current + " " + sent).strip()
                    else:
                        if current:
                            chunks.append(current)
                        current = sent
            else:
                # Carry over tail of previous chunk for context
                tail = current[-overlap:] if current else ""
                current = (tail + "\n\n" + para).strip() if tail else para

    if current:
        chunks.append(current)

    return [c for c in chunks if len(c.strip()) > 50]


def guess_metadata(filename: str, text: str) -> Tuple[int, str, str]:
    """
    Infer grade, subject, and topic from filename and text.
    Returns (grade, subject, topic).
    """
    filename_lower = filename.lower()
    text_lower = text.lower()[:500]

    # Grade
    grade = None
    for g in range(1, 13):
        if f"grade{g}" in filename_lower or f"grade_{g}" in filename_lower or f"grade {g}" in text_lower:
            grade = g
            break

    # Subject
    subject = "General"
    subject_map = {
        "math": "Math", "science": "Science", "english": "English",
        "history": "History", "geography": "Geography", "biology": "Biology",
        "physics": "Physics", "chemistry": "Chemistry",
    }
    for key, val in subject_map.items():
        if key in filename_lower or key in text_lower:
            subject = val
            break

    # Topic — grab first meaningful heading or filename segment
    topic = None
    heading = re.search(r"(?m)^([A-Z][A-Za-z\s]{5,50})$", text)
    if heading:
        topic = heading.group(1).strip()
    else:
        parts = re.split(r"[_\-\s]+", filename.replace(".pdf", ""))
        topic = " ".join(p.capitalize() for p in parts[-2:]) if parts else "General"

    return grade, subject, topic


def build_chunks(
    source: SourceDocument,
    text: str,
    topic_override: str = None,
) -> List[ContentChunk]:
    """Full pipeline: clean → chunk → attach metadata."""
    cleaned = clean_text(text)
    raw_chunks = chunk_text(cleaned)

    chunks = []
    for i, chunk_text_content in enumerate(raw_chunks):
        chunk = ContentChunk(
            source_id=source.source_id,
            grade=source.grade,
            subject=source.subject,
            topic=topic_override or source.subject or "General",
            text=chunk_text_content,
            chunk_index=i,
        )
        chunks.append(chunk)

    return chunks
