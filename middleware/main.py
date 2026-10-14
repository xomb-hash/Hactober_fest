"""
FastAPI application for HelixGuard verification-first genomic middleware.
Provides endpoints for sequence extraction, alignment gating, and system health.
"""

import os
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import httpx
from dotenv import load_dotenv

from middleware.schemas import (
    ExtractionRequest,
    ExtractionResponse,
    ExtractAndAlignRequest,
    ExtractAndAlignResponse,
    AlignmentRequest,
    AlignmentResponse,
    DocumentUploadResponse,
)
from middleware.validation import validate_reference_sequence
from middleware.extraction import extract_sequence
from middleware.document_parser import extract_text_from_file

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("helixguard.main")

ENGINE_URL = os.getenv("ENGINE_URL", "http://localhost:8080").rstrip("/")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("HelixGuard Middleware starting up. Engine URL: %s", ENGINE_URL)
    yield
    logger.info("HelixGuard Middleware shutting down.")


app = FastAPI(
    title="HelixGuard Middleware",
    description="Deterministic sequence extraction and verified alignment pipeline.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint probing engine connectivity."""
    engine_reachable = False
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{ENGINE_URL}/health")
            if resp.status_code == 200:
                engine_reachable = True
    except Exception:
        engine_reachable = False

    return {
        "status": "healthy",
        "service": "helixguard-middleware",
        "engine_url": ENGINE_URL,
        "engine_reachable": engine_reachable,
    }


@app.post("/upload-document", response_model=DocumentUploadResponse, tags=["Document Ingestion"])
async def upload_document_endpoint(file: UploadFile = File(...)) -> DocumentUploadResponse:
    """
    Parses and extracts raw text from uploaded files:
    - Plain text & Markdown (.txt, .md, .text, .markdown)
    - PDF documents (.pdf)
    - Word documents (.docx, .doc)
    - Genomic data (.fasta, .fa, .fna, .seq, .sam, .vcf)
    - Structured data (.csv, .tsv, .json)
    """
    logger.info("Document upload received: filename='%s', content_type='%s'", file.filename, file.content_type)
    try:
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )

        text, file_type, char_count = extract_text_from_file(file.filename or "unknown.txt", content)
        if not text:
            logger.warning("No readable text could be extracted from '%s'", file.filename)
            return DocumentUploadResponse(
                filename=file.filename or "unknown",
                file_type=file_type,
                text="",
                character_count=0,
                message=f"No text content could be extracted from {file.filename}."
            )

        logger.info(
            "Document parsed successfully: %s (%s, %d characters)",
            file.filename,
            file_type,
            char_count,
        )
        return DocumentUploadResponse(
            filename=file.filename or "unknown",
            file_type=file_type,
            text=text,
            character_count=char_count,
            message=f"Successfully extracted {char_count:,} characters from {file.filename} ({file_type.upper()})."
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to parse uploaded document: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to process document {file.filename}: {str(exc)}"
        )


@app.post("/extract", response_model=ExtractionResponse, tags=["Extraction"])
async def extract_endpoint(req: ExtractionRequest) -> ExtractionResponse:
    """
    Extracts and deterministically verifies sequence from document text.
    Never accepts model-generated sequence as truth.
    """
    logger.info("Extraction request received for field_type: '%s', alphabet: '%s'", req.field_type, req.sequence_alphabet)
    try:
        resp = extract_sequence(
            document_text=req.document_text,
            field_type=req.field_type,
            alphabet=req.sequence_alphabet,
            candidate_quote=req.candidate_quote,
            anchor_before=req.anchor_before,
            anchor_after=req.anchor_after,
            allow_iupac=req.allow_iupac,
        )
        return resp
    except Exception as exc:
        logger.exception("Unexpected error during sequence extraction.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failure: {str(exc)}"
        )


@app.post("/extract-and-align", response_model=ExtractAndAlignResponse, tags=["Pipeline"])
async def extract_and_align_endpoint(req: ExtractAndAlignRequest) -> ExtractAndAlignResponse:
    """
    Full verified pipeline:
    1. Deterministic extraction & source verification.
    2. Input validation for reference sequence.
    3. Critical Gating: Unverified extracted sequence NEVER reaches C++ alignment engine.
    4. Call C++ alignment engine only on verified sequences.
    """
    logger.info("Extract and align request received for field: '%s'", req.field_type)

    # 1. Validate reference sequence
    ref_valid, ref_err = validate_reference_sequence(
        req.reference_sequence,
        alphabet=req.sequence_alphabet,
        allow_iupac=req.allow_iupac
    )
    if not ref_valid:
        # Pre-extraction rejection due to invalid reference sequence
        empty_extraction = ExtractionResponse(
            sequence=None,
            validation_status="rejected",
            source_match=False,
            boundaries_verified=False,
            completeness_verified=False,
            error_code="INVALID_REFERENCE_SEQUENCE",
            message=f"Reference sequence validation failed: {ref_err}"
        )
        return ExtractAndAlignResponse(
            status="rejected",
            extraction=empty_extraction,
            alignment=None
        )

    # 2. Extract and verify query sequence from document
    extraction_resp = extract_sequence(
        document_text=req.document_text,
        field_type=req.field_type,
        alphabet=req.sequence_alphabet,
        candidate_quote=req.candidate_quote,
        anchor_before=req.anchor_before,
        anchor_after=req.anchor_after,
        allow_iupac=req.allow_iupac,
    )

    # 3. CRITICAL GATING: Never send unverified sequence to engine
    if (
        extraction_resp.validation_status != "verified"
        or not extraction_resp.source_match
        or not extraction_resp.sequence
    ):
        logger.warning(
            "Gating blocked alignment: sequence unverified (status=%s, error_code=%s).",
            extraction_resp.validation_status,
            extraction_resp.error_code
        )
        return ExtractAndAlignResponse(
            status=extraction_resp.validation_status,
            extraction=extraction_resp,
            alignment=None
        )

    # 4. Forward verified sequence to C++ Smith-Waterman engine
    align_req_payload = {
        "reference_sequence": req.reference_sequence.strip(),
        "query_sequence": extraction_resp.sequence,
    }
    if req.scoring:
        align_req_payload["scoring"] = req.scoring.model_dump()

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{ENGINE_URL}/align", json=align_req_payload)

            if resp.status_code == 200:
                align_data = resp.json()
                alignment_resp = AlignmentResponse.model_validate(align_data)
                return ExtractAndAlignResponse(
                    status="success",
                    extraction=extraction_resp,
                    alignment=alignment_resp
                )
            else:
                logger.error("C++ engine returned non-200 code: %d %s", resp.status_code, resp.text)
                return ExtractAndAlignResponse(
                    status="error",
                    extraction=extraction_resp,
                    alignment=None
                )
    except (httpx.ConnectError, httpx.TimeoutException) as net_err:
        logger.warning("C++ engine unavailable at %s: %s", ENGINE_URL, str(net_err))
        # Return structured response recording extraction success but alignment unavailable
        return ExtractAndAlignResponse(
            status="error",
            extraction=extraction_resp,
            alignment=None
        )
    except Exception as exc:
        logger.exception("Unexpected error calling alignment engine.")
        return ExtractAndAlignResponse(
            status="error",
            extraction=extraction_resp,
            alignment=None
        )
