"""
routes.py
---------
FastAPI route definitions for the Research Paper AI Assistant.

Endpoints:
  POST /api/upload          → Upload and process a PDF
  POST /api/ask             → Ask a question about uploaded papers
  POST /api/summarize       → Get a full paper summary
  POST /api/section         → Get an explanation of a specific section
  GET  /api/documents       → List all uploaded documents
  DELETE /api/documents/{id} → Remove a document
  GET  /api/health          → System health check
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException

from app.api.schemas import (
    AskRequest, AskResponse, SourceChunk,
    SummarizeRequest, SummarizeResponse,
    SectionRequest, SectionResponse,
    UploadResponse, HealthResponse,
)
from app.services.rag_service import rag_service
from app.services.vector_store import vector_store
from app.services.llm_service import llm
from app.core.config import settings
from app.core.logger import logger

router = APIRouter(prefix="/api", tags=["Research Assistant"])


# ── Upload PDF ────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, summary="Upload & process a research PDF")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF research paper.
    The backend will:
      1. Save the file to the uploads directory
      2. Extract text with multi-library fallback
      3. Detect standard paper sections (Abstract, Methodology, etc.)
      4. Chunk and embed the text
      5. Store embeddings in ChromaDB
    Returns a document_id to use in subsequent requests.
    """
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Validate file size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_mb:.1f} MB). Maximum is {settings.MAX_FILE_SIZE_MB} MB."
        )

    # Generate unique document ID and save file
    document_id = str(uuid.uuid4())
    save_path = Path(settings.UPLOAD_DIR) / f"{document_id}.pdf"

    with open(save_path, "wb") as f:
        f.write(content)

    logger.info(f"Saved PDF '{file.filename}' → {save_path} ({size_mb:.2f} MB)")

    try:
        # Run full RAG ingestion pipeline
        result = rag_service.ingest_document(
            file_path=str(save_path),
            document_id=document_id,
        )
        return UploadResponse(
            document_id=result["document_id"],
            filename=file.filename,
            chunk_count=result["chunk_count"],
            page_count=result["page_count"],
            sections_found=result["sections_found"],
            message="PDF processed successfully! You can now ask questions about this paper.",
        )
    except ValueError as e:
        # Clean up saved file on processing failure
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        save_path.unlink(missing_ok=True)
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


# ── Ask a Question ────────────────────────────────────────────────────────────

@router.post("/ask", response_model=AskResponse, summary="Ask a question about the paper")
async def ask_question(request: AskRequest):
    """
    Ask any question about the uploaded research paper.
    Uses RAG to retrieve relevant context, then generates an answer with Ollama.
    Optionally pass chat_history for multi-turn conversations.
    """
    try:
        result = rag_service.ask(
            question=request.question,
            document_id=request.document_id,
            chat_history=[m.dict() for m in (request.chat_history or [])],
        )
        return AskResponse(
            answer=result["answer"],
            sources=[SourceChunk(**s) for s in result["sources"]],
            document_id=request.document_id,
        )
    except Exception as e:
        logger.error(f"Ask failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Summarise Document ────────────────────────────────────────────────────────

@router.post("/summarize", response_model=SummarizeResponse, summary="Get a paper summary")
async def summarize_document(request: SummarizeRequest):
    """
    Generate a concise, student-friendly summary of the full research paper.
    The paper must have been uploaded first.
    """
    try:
        summary = rag_service.summarize(request.document_id)
        return SummarizeResponse(document_id=request.document_id, summary=summary)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Summarize failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Get Section ───────────────────────────────────────────────────────────────

@router.post("/section", response_model=SectionResponse, summary="Explain a specific section")
async def get_section(request: SectionRequest):
    """
    Get the raw text and an AI explanation of a specific paper section.
    Supported sections: abstract, introduction, methodology, results, discussion, conclusion
    """
    try:
        result = rag_service.get_section(request.document_id, request.section_name)
        return SectionResponse(
            document_id=request.document_id,
            **result,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Section fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── List Documents ────────────────────────────────────────────────────────────

@router.get("/documents", summary="List all uploaded documents")
async def list_documents():
    """Return a list of all document IDs currently stored in the vector store."""
    doc_ids = vector_store.list_documents()
    return {"documents": doc_ids, "count": len(doc_ids)}


# ── Delete Document ───────────────────────────────────────────────────────────

@router.delete("/documents/{document_id}", summary="Remove a document")
async def delete_document(document_id: str):
    """
    Delete all embeddings for a document from ChromaDB.
    Also removes the cached PDF file if it exists.
    """
    success = vector_store.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Remove PDF file
    pdf_path = Path(settings.UPLOAD_DIR) / f"{document_id}.pdf"
    pdf_path.unlink(missing_ok=True)

    return {"message": f"Document {document_id} deleted successfully."}


# ── Health Check ─────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, summary="System health check")
async def health_check():
    """
    Check if all system components are healthy:
    - Ollama LLM server
    - ChromaDB vector store
    """
    ollama_status = llm.health_check()
    stored_docs = len(vector_store.list_documents())
    overall_status = "healthy" if ollama_status["status"] == "online" else "degraded"

    return HealthResponse(
        status=overall_status,
        ollama=ollama_status,
        vector_store_count=stored_docs,
    )


# ── Sections Overview ─────────────────────────────────────────────────────────

@router.get("/documents/{document_id}/sections", summary="Get detected sections")
async def get_sections(document_id: str):
    """List all sections detected in the uploaded paper."""
    sections = rag_service.get_sections_overview(document_id)
    if not sections:
        raise HTTPException(
            status_code=404,
            detail="Document not found or has no detected sections."
        )
    return {"document_id": document_id, "sections": sections}
