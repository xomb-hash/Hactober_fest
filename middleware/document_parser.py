"""
Document Parser module for Project HelixGuard.
Extracts raw text content from arbitrary user-uploaded clinical and genomic documents:
- PDF (.pdf)
- Word Documents (.docx)
- Markdown (.md, .markdown)
- Plain Text (.txt, .text, .rst)
- Genomic Formats (.fasta, .fa, .fna, .seq, .sam, .vcf)
- Tabular / Structured Data (.csv, .tsv, .json)
"""

import io
import re
import logging
import zipfile
import xml.etree.ElementTree as ET
from typing import Tuple, Optional

logger = logging.getLogger("helixguard.document_parser")


def extract_plain_text(content: bytes) -> str:
    """Decodes plain text bytes trying utf-8, then latin-1 as fallback."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return content.decode("latin-1")
        except UnicodeDecodeError:
            return content.decode("ascii", errors="replace")


def extract_pdf_text(content: bytes) -> str:
    """Extracts text content from a PDF document using pypdf."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        extracted_pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                extracted_pages.append(text.strip())
        if extracted_pages:
            return "\n\n".join(extracted_pages)
    except Exception as exc:
        logger.warning("pypdf parsing failed (%s), falling back to stream scanner.", exc)

    # Fallback heuristic: scan printable ASCII/UTF-8 streams from PDF
    text_fragments = re.findall(rb"\(([^\)\\]{4,})\)", content)
    if text_fragments:
        decoded = [f.decode("latin-1", errors="ignore") for f in text_fragments]
        return "\n".join(decoded)

    return ""


def extract_docx_text(content: bytes) -> str:
    """Extracts text paragraphs from a .docx file via word/document.xml."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            if "word/document.xml" not in z.namelist():
                raise ValueError("Not a valid DOCX file (missing word/document.xml)")
            xml_data = z.read("word/document.xml")

        tree = ET.fromstring(xml_data)
        # Namespace for OpenXML WordprocessingML
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

        paragraphs = []
        for p in tree.iter(f"{{{ns['w']}}}p"):
            texts = [
                node.text
                for node in p.iter(f"{{{ns['w']}}}t")
                if node.text
            ]
            if texts:
                paragraphs.append("".join(texts))

        return "\n".join(paragraphs)
    except Exception as exc:
        logger.error("Failed to parse DOCX: %s", exc)
        raise ValueError(f"Could not extract text from DOCX file: {exc}")


def extract_text_from_file(filename: str, content: bytes) -> Tuple[str, str, int]:
    """
    Main dispatcher for document text extraction.
    Returns: (extracted_text, detected_file_type, character_count)
    """
    if not content:
        return "", "empty", 0

    lower_name = filename.lower()
    file_type = "text"
    extracted_text = ""

    if lower_name.endswith(".pdf"):
        file_type = "pdf"
        extracted_text = extract_pdf_text(content)
    elif lower_name.endswith(".docx"):
        file_type = "docx"
        extracted_text = extract_docx_text(content)
    elif lower_name.endswith(".doc"):
        file_type = "doc"
        # Word 97-2003 binary format: extract printable strings
        printable = re.findall(rb"[\x20-\x7E\r\n\t]{4,}", content)
        extracted_text = "\n".join([p.decode("latin-1", errors="ignore") for p in printable])
    elif lower_name.endswith((".md", ".markdown")):
        file_type = "markdown"
        extracted_text = extract_plain_text(content)
    elif lower_name.endswith((".fasta", ".fa", ".fna", ".seq")):
        file_type = "fasta"
        extracted_text = extract_plain_text(content)
    elif lower_name.endswith((".sam", ".vcf")):
        file_type = "genomic_annotation"
        extracted_text = extract_plain_text(content)
    elif lower_name.endswith((".csv", ".tsv")):
        file_type = "delimited"
        extracted_text = extract_plain_text(content)
    elif lower_name.endswith(".json"):
        file_type = "json"
        extracted_text = extract_plain_text(content)
    else:
        file_type = "text"
        extracted_text = extract_plain_text(content)

    # Normalize line breaks
    normalized_text = extracted_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    return normalized_text, file_type, len(normalized_text)
