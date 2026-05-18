"""
schemas.py
----------
Pydantic request/response models for all API endpoints.
Using these models ensures automatic validation and OpenAPI documentation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


# ── Chat / Q&A ────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """A single message in the conversation history."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class AskRequest(BaseModel):
    """Request body for the /ask endpoint."""
    question: str = Field(..., min_length=1, description="Student's question")
    document_id: Optional[str] = Field(None, description="Restrict to a specific uploaded PDF")
    chat_history: Optional[List[ChatMessage]] = Field(
        default=[], description="Previous conversation turns for context"
    )


class SourceChunk(BaseModel):
    """A retrieved context chunk (shown as a source reference)."""
    text: str
    metadata: dict
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score (0-1)")


class AskResponse(BaseModel):
    """Response from the /ask endpoint."""
    answer: str
    sources: List[SourceChunk]
    document_id: Optional[str] = None


# ── Summarise ─────────────────────────────────────────────────────────────────

class SummarizeRequest(BaseModel):
    """Request body for the /summarize endpoint."""
    document_id: str = Field(..., description="ID of the uploaded document to summarise")


class SummarizeResponse(BaseModel):
    """Response from the /summarize endpoint."""
    document_id: str
    summary: str


# ── Sections ─────────────────────────────────────────────────────────────────

class SectionRequest(BaseModel):
    """Request body for the /section endpoint."""
    document_id: str
    section_name: str = Field(
        ...,
        description="One of: abstract, introduction, methodology, results, discussion, conclusion, references"
    )


class SectionResponse(BaseModel):
    document_id: str
    section: str
    text: str
    explanation: str


# ── Upload ────────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Response after a successful PDF upload and processing."""
    document_id: str
    filename: str
    chunk_count: int
    page_count: int | str
    sections_found: List[str]
    message: str


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    ollama: dict
    vector_store_count: int
