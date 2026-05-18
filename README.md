# 🧠 PaperMind — AI Research Paper Assistant

> Help students understand complex research papers through AI-powered Q&A, summarization, and section explanations.

[![CI](https://github.com/your-org/papermind/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/papermind/actions)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector%20Store-orange)](https://trychroma.com)
[![Ollama](https://img.shields.io/badge/Ollama-LLM-black)](https://ollama.ai)

---

## ✨ Features

| Feature | Details |
|---|---|
| 📤 **PDF Upload** | Drag & drop or click to upload research papers (up to 50 MB) |
| 🔍 **Text Extraction** | Multi-library fallback: pdfplumber → PyMuPDF → pypdf |
| 📋 **Summarization** | Student-friendly full-paper summary |
| 💬 **RAG Chatbot** | Accurate answers grounded in the paper's content |
| 📖 **Section Explorer** | Abstract · Introduction · Methodology · Results · Conclusion |
| 🧠 **Chat Memory** | Multi-turn conversation with session history |
| 🌐 **Modern UI** | Dark-theme, glassmorphism, animated interactions |
| ⚡ **Fast & Local** | Runs fully offline with Ollama — no API keys needed |

---

## 🏗️ Architecture

```
PaperMind
├── backend/                    # FastAPI Python backend
│   ├── main.py                 # Application entry point
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py       # All API endpoints
│   │   │   └── schemas.py      # Pydantic request/response models
│   │   ├── core/
│   │   │   ├── config.py       # Environment-driven settings
│   │   │   └── logger.py       # Centralised logging
│   │   └── services/
│   │       ├── pdf_service.py  # PDF extraction & chunking
│   │       ├── vector_store.py # ChromaDB wrapper
│   │       ├── llm_service.py  # Ollama LLM integration
│   │       └── rag_service.py  # RAG pipeline orchestrator
│   ├── tests/                  # pytest test suite
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                   # Vanilla HTML/CSS/JS UI
│   ├── index.html
│   ├── style.css
│   └── app.js
├── .github/
│   └── workflows/ci.yml        # GitHub Actions CI/CD
├── docker-compose.yml
└── README.md
```

### RAG Pipeline Flow

```
Upload PDF
    │
    ▼
PDF Text Extraction (pdfplumber / PyMuPDF / pypdf)
    │
    ▼
Section Detection (Abstract, Methodology, Results, Conclusion…)
    │
    ▼
Text Chunking (1000 chars, 200 overlap)
    │
    ▼
Embedding Generation (Ollama nomic-embed-text / sentence-transformers)
    │
    ▼
ChromaDB Storage (persistent, cosine similarity)

────────────────────────────────────────────────────────

Student Question
    │
    ▼
Query Embedding
    │
    ▼
ChromaDB Semantic Search (Top-5 chunks)
    │
    ▼
Ollama LLM (llama3.2) with retrieved context + chat history
    │
    ▼
Answer + Source References
```

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.11+** — [Download](https://python.org)
2. **Ollama** — [Download](https://ollama.ai) | Must be running locally

### 1. Install Ollama & Pull Models

```bash
# Install Ollama (Windows: download installer from https://ollama.ai)

# Pull the LLM model (choose one)
ollama pull llama3.2          # Recommended — fast & capable
ollama pull mistral           # Alternative
ollama pull phi3              # Lightweight option

# Pull the embedding model
ollama pull nomic-embed-text  # Required for semantic search

# Start Ollama server (runs automatically on install, or manually)
ollama serve
```

### 2. Set Up Backend

```bash
# Clone / navigate to project
cd "ChatBot for intern\backend"

# Create virtual environment
python -m venv venv
venv\Scripts\activate         # Windows
# source venv/bin/activate    # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env if needed (e.g., change OLLAMA_MODEL)

# Start the API server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be live at: http://localhost:8000
Swagger docs at: http://localhost:8000/docs

### 3. Open the Frontend

Simply open `frontend/index.html` in your browser, or serve it:

```bash
# Using Python's built-in server
cd frontend
python -m http.server 3000
# Open http://localhost:3000
```

---

## 🐳 Docker

```bash
# Build and run with Docker Compose
docker-compose up --build

# The backend will be at http://localhost:8000
# Note: Ollama must be running on the host machine
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload & process a PDF |
| `POST` | `/api/ask` | Ask a question (RAG) |
| `POST` | `/api/summarize` | Get full paper summary |
| `POST` | `/api/section` | Get section explanation |
| `GET`  | `/api/documents` | List all documents |
| `DELETE` | `/api/documents/{id}` | Delete a document |
| `GET`  | `/api/health` | System health check |
| `GET`  | `/api/documents/{id}/sections` | List detected sections |

**Full interactive docs:** http://localhost:8000/docs

### Example: Upload PDF

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@my_paper.pdf"
```

### Example: Ask a Question

```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the main contribution of this paper?",
    "document_id": "your-document-id-here"
  }'
```

---

## 🧪 Running Tests

```bash
cd backend
pytest tests/ -v
```

---

## ⚙️ Configuration

Edit `backend/.env` to customize:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.2` | LLM model to use |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks |
| `TOP_K_RESULTS` | `5` | Chunks retrieved per query |
| `MAX_FILE_SIZE_MB` | `50` | Upload size limit |

---

## 🗺️ Future Roadmap

- [ ] Mobile app integration (Kavidaran & team)
- [ ] Multi-document comparison and cross-referencing
- [ ] Voice interaction (speech-to-text + TTS)
- [ ] Citation generation (BibTeX, APA, MLA)
- [ ] Research recommendation system
- [ ] User authentication & paper library
- [ ] Export chat transcripts as PDF

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "feat: add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
Built with ❤️ for students who want to understand research without the headache.
</div>
