"""
vector_store.py
---------------
ChromaDB vector store wrapper.

Responsibilities:
  • Create / open a persistent ChromaDB collection
  • Embed chunks using Ollama's nomic-embed-text (or any model)
  • Add, query, and delete documents
"""

import uuid
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.core.logger import logger


class VectorStore:
    """Thin wrapper around ChromaDB for research paper embeddings."""

    def __init__(self):
        # Persistent client stores data on disk between restarts
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},   # cosine distance for semantic search
        )
        logger.info(
            f"ChromaDB ready — collection '{settings.CHROMA_COLLECTION_NAME}' "
            f"at '{settings.CHROMA_PERSIST_DIR}'"
        )

    # ── Embedding ──────────────────────────────────────────────────────────────

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings via Ollama REST API.
        Falls back to a lightweight sentence-transformers model if Ollama is unavailable.
        """
        import requests, json

        try:
            embeddings = []
            for text in texts:
                resp = requests.post(
                    f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                    json={"model": settings.OLLAMA_EMBED_MODEL, "prompt": text},
                    timeout=60,
                )
                resp.raise_for_status()
                embeddings.append(resp.json()["embedding"])
            return embeddings
        except Exception as e:
            logger.warning(f"Ollama embedding failed ({e}). Using sentence-transformers fallback.")
            return self._embed_fallback(texts)

    def _embed_fallback(self, texts: list[str]) -> list[list[float]]:
        """Fallback: sentence-transformers all-MiniLM-L6-v2."""
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        return model.encode(texts, show_progress_bar=False).tolist()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def add_document(
        self,
        document_id: str,
        chunks: list[str],
        metadata: Optional[dict] = None,
    ) -> int:
        """
        Embed and store all chunks for a document.
        Each chunk gets a unique ID of the form: <document_id>_chunk_<n>
        Returns the number of chunks stored.
        """
        if not chunks:
            logger.warning(f"No chunks to add for document {document_id}")
            return 0

        logger.info(f"Embedding {len(chunks)} chunks for document {document_id} …")
        embeddings = self._embed(chunks)

        ids       = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
        meta_list = [
            {
                "document_id": document_id,
                "chunk_index": i,
                **(metadata or {}),
            }
            for i in range(len(chunks))
        ]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=meta_list,
        )

        logger.info(f"Stored {len(chunks)} chunks for document {document_id}")
        return len(chunks)

    def query(
        self,
        query_text: str,
        document_id: Optional[str] = None,
        top_k: int = None,
    ) -> list[dict]:
        """
        Semantic search over stored chunks.

        Parameters
        ----------
        query_text  : the user's natural-language question
        document_id : if set, restrict search to this document only
        top_k       : number of results to return

        Returns
        -------
        List of { "text": str, "metadata": dict, "distance": float }
        """
        top_k = top_k or settings.TOP_K_RESULTS
        query_embedding = self._embed([query_text])[0]

        where_filter = {"document_id": document_id} if document_id else None

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
        )

        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({"text": doc, "metadata": meta, "distance": dist})

        return hits

    def delete_document(self, document_id: str) -> bool:
        """Remove all chunks belonging to a document."""
        try:
            self.collection.delete(where={"document_id": document_id})
            logger.info(f"Deleted all chunks for document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Delete failed for {document_id}: {e}")
            return False

    def list_documents(self) -> list[str]:
        """Return distinct document IDs currently stored."""
        results = self.collection.get(include=["metadatas"])
        seen    = set()
        ids     = []
        for meta in results.get("metadatas", []):
            doc_id = meta.get("document_id")
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                ids.append(doc_id)
        return ids


# Module-level singleton — import this everywhere
vector_store = VectorStore()
