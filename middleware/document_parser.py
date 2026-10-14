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
from typing import Tuple, Optional, Any, List

logger = logging.getLogger("helixguard.document_parser")

_RAPID_OCR_ENGINE: Optional[Any] = None


def get_ocr_engine() -> Optional[Any]:
    """
    Lazy-load singleton instance of RapidOCR ONNX model.
    Loads once into memory and handles subsequent inferences in <50ms.
    """
    global _RAPID_OCR_ENGINE
    if _RAPID_OCR_ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _RAPID_OCR_ENGINE = RapidOCR()
            logger.info("RapidOCR ONNX local model initialized successfully.")
        except Exception as exc:
            logger.error("Failed to initialize RapidOCR ONNX model: %s", exc)
            _RAPID_OCR_ENGINE = False
    return _RAPID_OCR_ENGINE if _RAPID_OCR_ENGINE is not False else None


def extract_plain_text(content: bytes) -> str:
    """Decodes plain text bytes trying utf-8, then latin-1 as fallback."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return content.decode("latin-1")
        except UnicodeDecodeError:
            return content.decode("ascii", errors="replace")


def extract_image_text(content: bytes) -> str:
    """
    Extracts text from arbitrary image formats (.png, .jpg, .jpeg, .webp, .tiff, .bmp)
    using the local RapidOCR ONNX model.
    Preserves top-to-bottom, left-to-right reading order.
    """
    if not content:
        return ""

    try:
        from PIL import Image
        import numpy as np
    except ImportError as e:
        logger.error("Pillow / NumPy not installed: %s", e)
        raise RuntimeError(f"Image processing libraries missing: {e}")

    engine = get_ocr_engine()
    if engine is None:
        raise RuntimeError(
            "Local OCR model (rapidocr-onnxruntime) could not be loaded. Please ensure dependencies are installed."
        )

    try:
        # Load image via PIL to validate bytes and handle color mode conversions
        image = Image.open(io.BytesIO(content))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        # Convert to numpy array for RapidOCR
        img_array = np.array(image)

        # Run local OCR inference
        results, elapse = engine(img_array)
        if not results:
            logger.info("RapidOCR completed: no text detected in image.")
            return ""

        # Each result element: [box_points, text, confidence_score]
        # box_points is [[x0, y0], [x1, y1], [x2, y2], [x3, y3]]
        def get_sort_key(item: Any) -> Tuple[float, float]:
            box = item[0]
            top_y = min(p[1] for p in box)
            left_x = min(p[0] for p in box)
            return (top_y, left_x)

        sorted_results = sorted(results, key=get_sort_key)
        lines: List[str] = [
            str(item[1]).strip()
            for item in sorted_results
            if item and len(item) > 1 and str(item[1]).strip()
        ]

        extracted_text = "\n".join(lines)
        logger.info(
            "RapidOCR extracted %d lines from image (%d chars, elapse: %s)",
            len(lines),
            len(extracted_text),
            elapse,
        )
        return extracted_text

    except Exception as exc:
        logger.error("Failed during image OCR extraction: %s", exc)
        raise ValueError(f"Could not extract text from image: {exc}")


def extract_pdf_text(content: bytes) -> str:
    """
    Extracts text content from a PDF document using pypdf.
    If no text layer exists (scanned PDF), attempts local OCR on embedded page images.
    """
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

        # Fallback for scanned PDF: attempt OCR on embedded page images
        logger.info("PDF has no selectable text layer. Checking for scanned page images...")
        ocr_pages = []
        for i, page in enumerate(reader.pages):
            page_lines = []
            for img_file in getattr(page, "images", []):
                try:
                    img_text = extract_image_text(img_file.data)
                    if img_text.strip():
                        page_lines.append(img_text.strip())
                except Exception as img_err:
                    logger.warning("Failed OCR on PDF page %d image: %s", i, img_err)
            if page_lines:
                ocr_pages.append("\n".join(page_lines))

        if ocr_pages:
            return "\n\n".join(ocr_pages)

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
    Supports:
    - Images (.png, .jpg, .jpeg, .webp, .tiff, .tif, .bmp) via RapidOCR ONNX
    - PDF (.pdf) with scanned image fallback
    - Word (.docx, .doc)
    - Markdown (.md, .markdown)
    - Genomic data (.fasta, .fa, .fna, .seq, .sam, .vcf)
    - Delimited & Structured (.csv, .tsv, .json)
    - Plain text (.txt, etc.)

    Returns: (extracted_text, detected_file_type, character_count)
    """
    if not content:
        return "", "empty", 0

    lower_name = filename.lower()
    file_type = "text"
    extracted_text = ""

    # Image formats -> Local RapidOCR ONNX model
    image_extensions = (".png", ".jpg", ".jpeg", ".webp", ".tiff", ".tif", ".bmp")
    if lower_name.endswith(image_extensions):
        file_type = "image_ocr"
        extracted_text = extract_image_text(content)
    elif lower_name.endswith(".pdf"):
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

