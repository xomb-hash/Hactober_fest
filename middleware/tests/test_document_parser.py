"""
Tests for Document Parser and /upload-document endpoint.
Verifies parsing of TXT, MD, FASTA, DOCX, and PDF formats.
"""

import io
import zipfile
import xml.etree.ElementTree as ET
import unittest
from fastapi.testclient import TestClient

from middleware.main import app
from middleware.document_parser import (
    extract_plain_text,
    extract_docx_text,
    extract_pdf_text,
    extract_text_from_file,
)

client = TestClient(app)


def create_minimal_docx_bytes(paragraphs: list[str]) -> bytes:
    """Helper to generate a minimal valid DOCX byte stream."""
    buf = io.BytesIO()
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    root = ET.Element(f"{{{ns}}}document")
    body = ET.SubElement(root, f"{{{ns}}}body")

    for p_text in paragraphs:
        p = ET.SubElement(body, f"{{{ns}}}p")
        r = ET.SubElement(p, f"{{{ns}}}r")
        t = ET.SubElement(r, f"{{{ns}}}t")
        t.text = p_text

    xml_bytes = ET.tostring(root, encoding="utf-8")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", xml_bytes)
    return buf.getvalue()


class TestDocumentParser(unittest.TestCase):
    def test_plain_text_and_markdown_extraction(self):
        sample_md = "# Gene Report\n\nObserved sequence: ATCGATCG\n"
        text, ftype, length = extract_text_from_file("report.md", sample_md.encode("utf-8"))
        self.assertEqual(ftype, "markdown")
        self.assertIn("Observed sequence: ATCGATCG", text)
        self.assertEqual(length, len(text))

    def test_fasta_extraction(self):
        sample_fasta = ">sample_read_01\nATCGATCGATCG\n"
        text, ftype, length = extract_text_from_file("sample.fasta", sample_fasta.encode("utf-8"))
        self.assertEqual(ftype, "fasta")
        self.assertIn(">sample_read_01", text)
        self.assertIn("ATCGATCGATCG", text)

    def test_docx_extraction(self):
        docx_bytes = create_minimal_docx_bytes([
            "CLINICAL GENOMICS REPORT",
            "Observed sequence: GCTAGCTA",
            "Reference sequence: GCTAGCTA"
        ])
        text, ftype, length = extract_text_from_file("patient.docx", docx_bytes)
        self.assertEqual(ftype, "docx")
        self.assertIn("CLINICAL GENOMICS REPORT", text)
        self.assertIn("Observed sequence: GCTAGCTA", text)
        self.assertTrue(length > 0)

    def test_empty_content(self):
        text, ftype, length = extract_text_from_file("empty.txt", b"")
        self.assertEqual(ftype, "empty")
        self.assertEqual(length, 0)
        self.assertEqual(text, "")


    def test_image_ocr_png_extraction(self):
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (600, 100), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 30), "Observed sequence: ATCGTTCGACTG", fill=(0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        text, ftype, length = extract_text_from_file("scan.png", buf.getvalue())
        self.assertEqual(ftype, "image_ocr")
        self.assertTrue(length > 0)
        self.assertIn("ATCG", text)

    def test_image_ocr_jpeg_extraction(self):
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (500, 100), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 30), "Reference sequence: ATCGATCG", fill=(0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")

        text, ftype, length = extract_text_from_file("report.jpg", buf.getvalue())
        self.assertEqual(ftype, "image_ocr")
        self.assertTrue(length > 0)
        self.assertIn("ATCGATCG", text)


class TestUploadDocumentEndpoint(unittest.TestCase):
    def test_upload_markdown_file(self):
        content = b"# Lab Note\nObserved sequence: ATCGTTCG\n"
        resp = client.post(
            "/upload-document",
            files={"file": ("lab_note.md", content, "text/markdown")}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["filename"], "lab_note.md")
        self.assertEqual(data["file_type"], "markdown")
        self.assertIn("Observed sequence: ATCGTTCG", data["text"])

    def test_upload_docx_file(self):
        docx_bytes = create_minimal_docx_bytes(["Tumor sample sequence: ATCGATCG"])
        resp = client.post(
            "/upload-document",
            files={"file": ("tumor_panel.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["filename"], "tumor_panel.docx")
        self.assertEqual(data["file_type"], "docx")
        self.assertIn("Tumor sample sequence: ATCGATCG", data["text"])

    def test_upload_image_file_with_local_ocr(self):
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (600, 100), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 30), "Observed sequence: ATCGTTCGACTG", fill=(0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        resp = client.post(
            "/upload-document",
            files={"file": ("gel_report.png", buf.getvalue(), "image/png")}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["filename"], "gel_report.png")
        self.assertEqual(data["file_type"], "image_ocr")
        self.assertIn("ATCG", data["text"])
        self.assertIn("RapidOCR", data["message"])

    def test_upload_empty_file_fails(self):
        resp = client.post(
            "/upload-document",
            files={"file": ("empty.txt", b"", "text/plain")}
        )
        self.assertEqual(resp.status_code, 400)

