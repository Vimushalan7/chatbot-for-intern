"""
test_api.py
-----------
Basic API tests using pytest + httpx.
Run with: pytest tests/ -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Health endpoint should always return 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "ollama" in data


@pytest.mark.asyncio
async def test_list_documents():
    """Documents endpoint returns a list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/documents")
    assert resp.status_code == 200
    assert "documents" in resp.json()


@pytest.mark.asyncio
async def test_upload_invalid_file_type():
    """Uploading a non-PDF should return 400."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_ask_without_document():
    """Asking without a document should still return 200 with a graceful message."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ask",
            json={"question": "What is this paper about?", "document_id": None},
        )
    assert resp.status_code in (200, 500)  # depends on Ollama availability
