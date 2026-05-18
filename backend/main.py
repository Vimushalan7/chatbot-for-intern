"""
main.py
-------
FastAPI application entry point.

Configures:
  • CORS (allows frontend at localhost:3000 or any origin in dev)
  • Static file serving for the frontend build
  • API routes
  • Startup / shutdown lifecycle hooks
  • Global exception handler for clean error messages
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import traceback

from app.api.routes import router
from app.core.config import settings
from app.core.logger import logger


# ── Application factory ────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "AI-powered assistant that helps students understand research papers "
            "using RAG (Retrieval-Augmented Generation) and Ollama LLMs."
        ),
        docs_url="/docs",        # Swagger UI
        redoc_url="/redoc",      # ReDoc
    )

    # ── CORS ───────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handler ───────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred. Please try again."},
        )

    # ── API routes ─────────────────────────────────────────────────────────────
    app.include_router(router)

    # ── Serve frontend static files ────────────────────────────────────────────
    # Path: backend/ -> parent -> project root -> frontend/
    plain_frontend = Path(__file__).parent.parent / "frontend"
    if plain_frontend.exists():
        # Serve index.html at root
        @app.get("/", include_in_schema=False)
        async def serve_index():
            return FileResponse(str(plain_frontend / "index.html"))

        # Mount the rest of the files (CSS, JS) so they are accessible at root path
        app.mount("/", StaticFiles(directory=str(plain_frontend)), name="frontend")
        
        logger.info(f"Frontend served from: {plain_frontend}")

    # ── Lifecycle hooks ────────────────────────────────────────────────────────
    @app.on_event("startup")
    async def startup_event():
        logger.info(f"[START] {settings.APP_NAME} v{settings.APP_VERSION} started")
        logger.info(f"   Ollama: {settings.OLLAMA_BASE_URL} (model: {settings.OLLAMA_MODEL})")
        logger.info(f"   Vector DB: {settings.CHROMA_PERSIST_DIR}")
        logger.info(f"   API Docs: http://localhost:8000/docs")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Shutting down Research Paper AI Assistant …")

    return app


# ── Entrypoint ────────────────────────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,          # hot-reload in development
        log_level="info",
    )
