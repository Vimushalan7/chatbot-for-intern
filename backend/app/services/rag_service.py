"""
rag_service.py
--------------
RAG (Retrieval-Augmented Generation) pipeline orchestrator.

Flow:
  Upload PDF → extract text → chunk → embed → store in ChromaDB
  Ask question → embed query → retrieve top-K chunks → send to LLM → return answer
"""

from typing import Optional

from app.services.vector_store import vector_store
from app.services.llm_service import llm
from app.services.pdf_service import process_pdf
from app.core.logger import logger


# ── Instant low-latency conversational responses ──────────────────────────────
CONVERSATIONAL_RESPONSES = {
    "hi": "Hello! I am PaperMind, your AI Research Paper Assistant. 🎓 Please upload a PDF paper on the left, and feel free to ask me anything about it!",
    "hi there": "Hello there! I am PaperMind, your AI Research Paper Assistant. 🎓 Please upload a PDF paper on the left, and feel free to ask me anything about it!",
    "hello": "Hello! I am PaperMind, your AI Research Paper Assistant. 🎓 Please upload a PDF paper on the left, and feel free to ask me anything about it!",
    "hello there": "Hello there! I am PaperMind, your AI Research Paper Assistant. 🎓 Please upload a PDF paper on the left, and feel free to ask me anything about it!",
    "hey": "Hey there! I am PaperMind, your AI Research Paper Assistant. 🎓 Please upload a PDF paper on the left, and feel free to ask me anything about it!",
    "hey there": "Hey there! I am PaperMind, your AI Research Paper Assistant. 🎓 Please upload a PDF paper on the left, and feel free to ask me anything about it!",
    "greetings": "Greetings! I am PaperMind, your AI Research Paper Assistant. 🎓 Please upload a PDF paper on the left, and feel free to ask me anything about it!",
    "yo": "Yo! I am PaperMind, your AI Research Paper Assistant. 🎓 Please upload a PDF paper on the left, and feel free to ask me anything about it!",
    "hola": "¡Hola! I am PaperMind, your AI Research Paper Assistant. 🎓 Please upload a PDF paper on the left, and feel free to ask me anything about it!",
    "howdy": "Howdy! I am PaperMind, your AI Research Paper Assistant. 🎓 Please upload a PDF paper on the left, and feel free to ask me anything about it!",
    "good morning": "Good morning! I am PaperMind, your AI Research Paper Assistant. 🎓 Please upload a PDF paper on the left, and feel free to ask me anything about it!",
    "good afternoon": "Good afternoon! I am PaperMind, your AI Research Paper Assistant. 🎓 Please upload a PDF paper on the left, and feel free to ask me anything about it!",
    "good evening": "Good evening! I am PaperMind, your AI Research Paper Assistant. 🎓 Please upload a PDF paper on the left, and feel free to ask me anything about it!",
    "who are you": "I am PaperMind, a local AI Research Paper Assistant designed to help you analyze, summarize, and understand complex academic research papers fully offline.",
    "what is your name": "My name is PaperMind, your AI Research Paper Assistant.",
    "whats your name": "My name is PaperMind, your AI Research Paper Assistant.",
    "what can you do": "I can help you analyze uploaded PDF research papers. Specifically, I can:\n* Summarize the entire paper in clear, student-friendly terms.\n* Explain specific sections like the Abstract, Methodology, Results, or Conclusion.\n* Answer direct questions about the paper using context-grounded RAG search.",
    "help": "To get started:\n1. Drag & drop or browse to upload a PDF paper in the sidebar.\n2. Once processed, you can click on the quick action buttons (like 'Summarize' or section chips).\n3. Or, simply type a specific question about the paper in this input bar!",
    "how are you": "I'm doing great, thank you! Ready to help you understand your research papers. Please upload a PDF on the left, and let me know what questions you have! 🎓",
}


class RAGService:
    """
    Orchestrates the full RAG pipeline:
      1. Document ingestion (PDF → chunks → embeddings → ChromaDB)
      2. Question answering (query → retrieval → LLM → answer)
      3. Summarisation
    """

    # ── Ingestion ──────────────────────────────────────────────────────────────

    def ingest_document(self, file_path: str, document_id: str) -> dict:
        """
        Process a PDF and store its embeddings.

        Returns a summary dict with stats and detected sections.
        """
        logger.info(f"Starting ingestion: {file_path}")

        # 1. Extract text and detect sections
        result = process_pdf(file_path, document_id)

        # 2. Embed and store chunks
        chunk_count = vector_store.add_document(
            document_id=document_id,
            chunks=result["chunks"],
            metadata={
                "filename": result["metadata"].get("title", ""),
                "page_count": result["metadata"].get("page_count", 0),
            },
        )

        # 3. Cache sections and full text in memory (keyed by document_id)
        self._doc_cache[document_id] = {
            "full_text": result["full_text"],
            "sections":  result["sections"],
            "metadata":  result["metadata"],
        }

        logger.info(
            f"Ingestion complete: {chunk_count} chunks stored for {document_id}"
        )

        return {
            "document_id":  document_id,
            "chunk_count":  chunk_count,
            "page_count":   result["metadata"].get("page_count", "N/A"),
            "sections_found": list(result["sections"].keys()),
        }

    def __init__(self):
        # In-memory cache: doc_id → {full_text, sections, metadata}
        # This avoids re-reading from disk on every summarise/section request
        self._doc_cache: dict[str, dict] = {}

    def _is_conversational(self, query: str) -> bool:
        """
        Check if a query is a general greeting or conversation rather than a specific paper question.
        Bypassing retrieval for these saves massive prefill latency.
        """
        greetings = {
            "hi", "hello", "hey", "greetings", "good morning", "good afternoon", 
            "good evening", "howdy", "whats up", "what's up", "yo", "hola",
            "who are you", "who are you?", "what is your name", "what's your name",
            "what can you do", "what can you do?", "help", "help me", "how are you"
        }
        # Strip punctuation and normalize
        clean = "".join(c for c in query.lower() if c.isalnum() or c.isspace()).strip()
        
        if clean in greetings:
            return True
            
        # Also check for simple starting words
        if clean.startswith(("hello ", "hi ", "hey ", "good morning ", "good afternoon ", "good evening ")):
            return True
            
        return False

    # ── Question Answering ─────────────────────────────────────────────────────

    def ask(
        self,
        question: str,
        document_id: Optional[str] = None,
        chat_history: Optional[list[dict]] = None,
    ) -> dict:
        """
        Answer a student question using RAG.

        Parameters
        ----------
        question    : natural-language question from the student
        document_id : if set, restrict retrieval to this document
        chat_history: list of previous {"role", "content"} turns

        Returns
        -------
        { "answer": str, "sources": [{ "text", "metadata" }] }
        """
        logger.info(f"RAG query: '{question[:80]}' | doc={document_id}")

        # Strip punctuation and normalize
        clean_query = "".join(c for c in question.lower() if c.isalnum() or c.isspace()).strip()

        # Check for static conversational responses first (for instantaneous low-latency replies)
        if clean_query in CONVERSATIONAL_RESPONSES:
            logger.info(f"Returning static response for conversational query: '{question}'")
            return {"answer": CONVERSATIONAL_RESPONSES[clean_query], "sources": []}

        # Check if we should bypass vector database retrieval
        is_conv = self._is_conversational(question)

        hits = []
        if not is_conv and document_id:
            # 1. Retrieve relevant chunks
            hits = vector_store.query(
                query_text=question,
                document_id=document_id,
            )
        else:
            logger.info("Bypassing vector retrieval for conversational query or missing document ID")

        # 2. Extract chunk texts
        context_chunks = [h["text"] for h in hits] if hits else []

        # 3. Generate answer with LLM (LLM handles empty context for greetings)
        answer = llm.answer_question(
            question=question,
            context_chunks=context_chunks,
            chat_history=chat_history,
        )

        # 4. Return answer + source references for transparency
        sources = [
            {
                "text":     h["text"][:300] + "…" if len(h["text"]) > 300 else h["text"],
                "metadata": h["metadata"],
                "score":    round(1 - h["distance"], 3),  # convert distance → similarity
            }
            for h in hits
        ]

        return {"answer": answer, "sources": sources}

    # ── Summarisation ─────────────────────────────────────────────────────────

    def summarize(self, document_id: str) -> str:
        """
        Generate a full summary for a previously ingested document.
        Uses cached text if available, otherwise raises.
        """
        cached = self._doc_cache.get(document_id)
        if not cached:
            raise ValueError(
                f"Document {document_id} not found in cache. "
                "Please re-upload the PDF."
            )
        return llm.summarize_document(cached["full_text"])

    def get_section(self, document_id: str, section_name: str) -> dict:
        """
        Return raw section text and an LLM explanation.
        """
        cached = self._doc_cache.get(document_id)
        if not cached:
            raise ValueError(f"Document {document_id} not found in cache.")

        sections = cached.get("sections", {})
        text     = sections.get(section_name.lower(), "")

        if not text:
            return {
                "section":     section_name,
                "text":        "",
                "explanation": f"The '{section_name}' section was not detected in this paper.",
            }

        explanation = llm.explain_section(section_name, text)

        return {
            "section":     section_name,
            "text":        text[:2000],   # raw excerpt (first 2k chars)
            "explanation": explanation,
        }

    def get_sections_overview(self, document_id: str) -> list[str]:
        """Return list of sections detected in the document."""
        cached = self._doc_cache.get(document_id)
        if not cached:
            return []
        return list(cached.get("sections", {}).keys())


# Module-level singleton
rag_service = RAGService()
