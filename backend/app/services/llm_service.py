"""
llm_service.py
--------------
Ollama LLM integration layer.

All prompts are centralised here so the RAG service can stay clean.
Supports:
  • Chat / Q&A with retrieved context
  • Document summarisation
  • Section-specific summaries
"""

import json
import requests
from typing import Generator, Optional

from app.core.config import settings
from app.core.logger import logger


# ── Prompt templates ──────────────────────────────────────────────────────────

QA_SYSTEM_PROMPT = """You are PaperMind, a highly accurate research assistant that helps students understand academic papers.

CRITICAL RULES FOR HIGH TRUTHFULNESS & LOW LATENCY:
1. STRICT FACTUAL GROUNDING: Answer the student's question ONLY using the provided research paper context chunks. Do NOT speculate, extrapolate, or use external knowledge.
2. NO HALLUCINATION: If the context does not explicitly contain the answer, say "I cannot find this in the paper." Do not attempt to guess or give general knowledge.
3. CONCISENESS (LOW LATENCY): Keep your answers direct, crisp, and extremely brief (typically 2-4 sentences). Avoid wordy explanations, introductory filler, or repetitive summaries. Less output tokens = faster response time.
4. If the student greets you or asks who you are, respond politely and explain that you can help them understand research papers they upload.
"""

SUMMARIZE_SYSTEM_PROMPT = """You are an expert at summarising research papers for students.

Create a clear, structured summary that includes:
- Main objective of the paper
- Key methodology used
- Important findings and results
- Practical implications

Use simple language. Avoid jargon. Format with bullet points where helpful.
"""

SECTION_SYSTEM_PROMPT = """You are a teaching assistant helping students understand a specific section of a research paper.
Explain the content clearly, highlight the key points, and provide context for why this section matters.
"""


class OllamaLLM:
    """Wrapper for Ollama's REST API with streaming support."""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model    = settings.OLLAMA_MODEL

    def _is_available(self) -> bool:
        """Check if LLM is available (either local Ollama or cloud Groq)."""
        import os
        if os.environ.get("GROQ_API_KEY"):
            return True
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def _generate(self, prompt: str, system: str = "", stream: bool = False) -> str:
        """
        Call LLM. If GROQ_API_KEY is present in environment variables, uses Groq Cloud API.
        Otherwise, falls back to local Ollama REST API.
        """
        import os
        groq_key = os.environ.get("GROQ_API_KEY")
        if groq_key:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json"
            }
            # Use llama-3.2-3b-preview as default, or any configured model (e.g., llama-3.3-70b-specdec)
            groq_model = os.environ.get("GROQ_MODEL", "llama-3.2-3b-preview")
            payload = {
                "model": groq_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.0,
            }
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=60)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.error(f"Groq API call failed: {e}.")
                raise RuntimeError(
                    f"Groq API call failed: {e}. "
                    "Please verify that your GROQ_API_KEY is correct and active in your Render settings."
                )

        # Fallback to local Ollama
        payload = {
            "model":  self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": 0.0,    # 0.0 = highest truthfulness (deterministic selection)
                "top_p":       0.9,
                "num_ctx":     4096,   # context window
            },
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Cannot connect to Ollama. "
                "Make sure Ollama is running: `ollama serve`"
            )
        except requests.exceptions.Timeout:
            raise RuntimeError("Ollama request timed out. Try a smaller model.")
        except Exception as e:
            raise RuntimeError(f"Ollama error: {e}")

    # ── Public methods ─────────────────────────────────────────────────────────

    def answer_question(
        self,
        question: str,
        context_chunks: list[str],
        chat_history: Optional[list[dict]] = None,
    ) -> str:
        """
        Answer a student's question using retrieved context chunks.

        Parameters
        ----------
        question      : the student's question
        context_chunks: relevant text chunks from the vector store
        chat_history  : previous turns [ {"role": "user"|"assistant", "content": str} ]
        """
        # Build context block
        context = "\n\n---\n\n".join(
            f"[Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(context_chunks)
        )

        # Build chat history string
        history_str = ""
        if chat_history:
            for turn in chat_history[-6:]:  # keep last 6 turns for context window
                role = "Student" if turn["role"] == "user" else "Assistant"
                history_str += f"{role}: {turn['content']}\n"

        prompt = f"""Context from the research paper:
{context}

{f'Previous conversation:{chr(10)}{history_str}' if history_str else ''}
Student question: {question}

Answer:"""

        logger.info(f"Answering question: {question[:80]}…")
        return self._generate(prompt, system=QA_SYSTEM_PROMPT)

    def summarize_document(self, full_text: str, max_chars: int = 8000) -> str:
        """
        Summarise an entire research paper.
        Truncates input to avoid exceeding the context window.
        """
        # Use a representative sample if the paper is very long
        truncated = full_text[:max_chars]
        if len(full_text) > max_chars:
            # Also grab the conclusion section if available
            truncated += "\n\n[...paper continues...]\n\n"
            truncated += full_text[-2000:]

        prompt = f"""Please summarise this research paper:

{truncated}

Provide a comprehensive but student-friendly summary."""

        logger.info("Generating document summary …")
        return self._generate(prompt, system=SUMMARIZE_SYSTEM_PROMPT)

    def explain_section(self, section_name: str, section_text: str) -> str:
        """
        Provide an accessible explanation of a specific paper section.
        """
        prompt = f"""Explain the '{section_name}' section of this research paper to a student:

{section_text[:4000]}

Make it easy to understand and highlight the most important points."""

        logger.info(f"Explaining section: {section_name}")
        return self._generate(prompt, system=SECTION_SYSTEM_PROMPT)

    def health_check(self) -> dict:
        """Return Ollama server or Cloud status and available models."""
        import os
        if os.environ.get("GROQ_API_KEY"):
            return {
                "status": "online",
                "models": ["llama-3.2-3b-preview"],
                "active_model": os.environ.get("GROQ_MODEL", "llama-3.2-3b-preview")
            }

        if not self._is_available():
            return {"status": "offline", "models": []}
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            models = [m["name"] for m in resp.json().get("models", [])]
            return {"status": "online", "models": models, "active_model": self.model}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# Module-level singleton
llm = OllamaLLM()
