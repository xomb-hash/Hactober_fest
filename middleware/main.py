import os
import logging
import threading
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
    GenomeIdentificationRequest,
    GenomeIdentificationResponse,
    ExtractAndIdentifyRequest,
    ExtractAndIdentifyResponse,
)
from middleware.validation import validate_reference_sequence
from middleware.extraction import extract_sequence
from middleware.document_parser import extract_text_from_file
from middleware.database import get_genome_database

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("helixguard.main")

ENGINE_URL = os.getenv("ENGINE_URL", "http://localhost:8080").rstrip("/")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")


def _bg_load_genome_database():
    """Background loader for viral genome database."""
    try:
        logger.info("Background genome database worker started.")
        db = get_genome_database()
        if db.is_loaded:
            logger.info("Genome database ready: %d records, %d kmers", len(db.records), len(db.kmer_index))
    except Exception as exc:
        logger.warning("Background genome database initialization notice: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("HelixGuard Middleware starting up. Engine URL: %s", ENGINE_URL)
    # Launch database load in background so server starts immediately
    loader_thread = threading.Thread(target=_bg_load_genome_database, daemon=True)
    loader_thread.start()
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
    - Images (.png, .jpg, .jpeg, .webp, .tiff, .bmp) via Local RapidOCR ONNX model
    - PDF documents (.pdf) with scanned image OCR fallback
    - Word documents (.docx, .doc)
    - Plain text & Markdown (.txt, .md, .text, .markdown)
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
        engine_label = "Local RapidOCR" if file_type == "image_ocr" else file_type.upper()
        return DocumentUploadResponse(
            filename=file.filename or "unknown",
            file_type=file_type,
            text=text,
            character_count=char_count,
            message=f"Successfully extracted {char_count:,} characters from {file.filename} ({engine_label})."
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
    logger.info("Extraction request received for field_type: '%s', alphabet: '%s', use_ai: %s", req.field_type, req.sequence_alphabet, req.use_ai)
    try:
        resp = extract_sequence(
            document_text=req.document_text,
            field_type=req.field_type,
            alphabet=req.sequence_alphabet,
            candidate_quote=req.candidate_quote,
            anchor_before=req.anchor_before,
            anchor_after=req.anchor_after,
            allow_iupac=req.allow_iupac,
            use_ai=req.use_ai,
            use_token_mask=req.use_token_mask,
            selected_span=req.selected_span,
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
    logger.info("Extract and align request received for field: '%s', use_ai: %s", req.field_type, req.use_ai)

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
        use_ai=req.use_ai,
        use_token_mask=req.use_token_mask,
        selected_span=req.selected_span,
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


@app.get("/genome-database/status", tags=["Genomic Database"])
async def genome_database_status_endpoint():
    """Returns the operational status, record count, and index metrics of the reference database."""
    db = get_genome_database()
    return {
        "status": "ready" if db.is_loaded else "loading",
        "total_records": len(db.records),
        "total_unique_kmers": len(db.kmer_index),
        "source_path": db.source_path,
        "k": db.k,
        "step": db.step,
    }


@app.post("/identify-genome", response_model=GenomeIdentificationResponse, tags=["Genomic Database"])
async def identify_genome_endpoint(req: GenomeIdentificationRequest) -> GenomeIdentificationResponse:
    """
    Identifies which viral genome in the reference database is closest to the given query sequence.
    Performs k-mer prefiltering and C++ Smith-Waterman alignment on candidate windows.
    Detects low-complexity/poly-A inflation and abstains if top scores are ambiguous.
    """
    logger.info("Genomic identification requested for sequence (length=%d, top_k=%d)", len(req.query_sequence), req.top_k)
    db = get_genome_database()
    if not db.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reference genome database is currently initializing. Please retry in a few moments."
        )

    # Validate query sequence
    valid, err = validate_reference_sequence(req.query_sequence, alphabet=req.sequence_alphabet, allow_iupac=req.allow_iupac)
    if not valid:
        return GenomeIdentificationResponse(
            status="error",
            query_sequence=req.query_sequence,
            query_length=len(req.query_sequence),
            total_candidates_evaluated=0,
            top_candidates=[],
            closest_match=None,
            abstain=True,
            abstain_reason=f"INVALID_QUERY_SEQUENCE: {err}",
            search_time_ms=0.0
        )

    return db.identify_closest_genome(
        query_seq=req.query_sequence,
        top_k=req.top_k,
        score_margin_threshold=req.score_margin_threshold,
        engine_url=ENGINE_URL,
    )


@app.post("/extract-and-identify", response_model=ExtractAndIdentifyResponse, tags=["Pipeline"])
async def extract_and_identify_endpoint(req: ExtractAndIdentifyRequest) -> ExtractAndIdentifyResponse:
    """
    Full verified clinical identification pipeline:
    1. Deterministic extraction and boundary verification from document/image.
    2. Strict Gating: unverified extracted sequence NEVER queries the reference database.
    3. Spaced k-mer prefiltering across thousands of RefSeq viral genomes.
    4. C++ Smith-Waterman local alignment and candidate ranking.
    5. Abstain gating for close scores or low complexity.
    """
    logger.info("Extract and identify pipeline requested for field: '%s'", req.field_type)

    # 1. Extract and verify query sequence from document
    extraction_resp = extract_sequence(
        document_text=req.document_text,
        field_type=req.field_type,
        alphabet=req.sequence_alphabet,
        candidate_quote=req.candidate_quote,
        anchor_before=req.anchor_before,
        anchor_after=req.anchor_after,
        allow_iupac=req.allow_iupac,
        use_ai=req.use_ai,
        use_token_mask=req.use_token_mask,
        selected_span=req.selected_span,
    )

    # 2. Strict Safety Gating: Unverified sequence never reaches the database
    if (
        extraction_resp.validation_status != "verified"
        or not extraction_resp.source_match
        or not extraction_resp.sequence
    ):
        logger.warning(
            "Gating blocked identification: sequence unverified (status=%s, error_code=%s).",
            extraction_resp.validation_status,
            extraction_resp.error_code
        )
        return ExtractAndIdentifyResponse(
            status=extraction_resp.validation_status,
            extraction=extraction_resp,
            identification=None,
            closest_organism=None,
            closest_accession=None,
        )

    # 3. Search genome database
    db = get_genome_database()
    if not db.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Genome reference database is currently initializing. Please retry in a few moments."
        )

    ident_resp = db.identify_closest_genome(
        query_seq=extraction_resp.sequence,
        top_k=req.top_k,
        engine_url=ENGINE_URL,
    )

    closest_org = ident_resp.closest_match.organism if ident_resp.closest_match else None
    closest_acc = ident_resp.closest_match.accession if ident_resp.closest_match else None

    return ExtractAndIdentifyResponse(
        status=ident_resp.status,
        extraction=extraction_resp,
        identification=ident_resp,
        closest_organism=closest_org,
        closest_accession=closest_acc,
    )


@app.post("/export-redacted", tags=["Privacy & Audit"])
async def export_redacted_provenance_endpoint(req: ExtractionRequest):
    """
    Round 2 Privacy Export:
    Produces a zero-retention, privacy-safe audit record.
    Strips all raw sequences, candidate quotes, and excerpts,
    retaining only the salted HMAC, checklist verification flags, offsets, and metadata.
    """
    extraction_resp = extract_sequence(
        document_text=req.document_text,
        field_type=req.field_type,
        alphabet=req.sequence_alphabet,
        candidate_quote=req.candidate_quote,
        anchor_before=req.anchor_before,
        anchor_after=req.anchor_after,
        allow_iupac=req.allow_iupac,
        use_ai=req.use_ai,
        use_token_mask=req.use_token_mask,
        selected_span=req.selected_span,
    )
    if extraction_resp.provenance:
        return extraction_resp.provenance.to_redacted_dict()
    return {"status": "no_provenance_record"}


