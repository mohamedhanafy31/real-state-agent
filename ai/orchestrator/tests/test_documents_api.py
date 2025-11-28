"""Unit tests for document CRUD proxy endpoints."""
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import documents
from app.services.rag_client import RAGServiceError


class _FakeRAGClient:
    """Simple in-memory fake used to track proxy interactions."""

    def __init__(self):
        self.calls = []

    async def list_documents(self):
        self.calls.append(("list", {}))
        return {"documents": [], "total": 0}

    async def upload_document(self, **payload):
        self.calls.append(("upload", payload))
        return {"status": "success", "filename": payload["filename"]}

    async def delete_document(self, **payload):
        self.calls.append(("delete", payload))
        return {"status": "success", "filename": payload["filename"]}

    async def clear_documents(self, **payload):
        self.calls.append(("clear", payload))
        return {"status": "success", "files_deleted": 0}


_test_app = FastAPI()
_test_app.include_router(documents.router)


class DocumentsRouterTests(unittest.TestCase):
    """Ensure CRUD endpoints proxy to the RAG client."""

    def setUp(self):
        self.client = TestClient(_test_app)
        self.fake_client = _FakeRAGClient()
        self.original_client = documents.rag_client
        documents.rag_client = self.fake_client

    def tearDown(self):
        documents.rag_client = self.original_client

    def test_list_documents_proxies_response(self):
        response = self.client.get("/documents")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"documents": [], "total": 0})
        self.assertEqual(self.fake_client.calls[0][0], "list")

    def test_create_document_uploads_file(self):
        files = {"file": ("hello.txt", b"hello", "text/plain")}
        response = self.client.post("/documents", files=files, params={"rebuild_index": "false"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["filename"], "hello.txt")
        call_type, payload = self.fake_client.calls[-1]
        self.assertEqual(call_type, "upload")
        self.assertEqual(payload["filename"], "hello.txt")
        self.assertEqual(payload["content"], b"hello")
        self.assertFalse(payload["rebuild_index"])

    def test_update_document_blocks_invalid_name(self):
        files = {"file": ("hello.txt", b"hello", "text/plain")}
        response = self.client.put("/documents/..secret", files=files)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid filename", response.text)

    def test_delete_document_proxies_flags(self):
        response = self.client.delete("/documents/sample.pdf", params={"remove_from_index": "false"})

        self.assertEqual(response.status_code, 200)
        call_type, payload = self.fake_client.calls[-1]
        self.assertEqual(call_type, "delete")
        self.assertEqual(payload["filename"], "sample.pdf")
        self.assertFalse(payload["remove_from_index"])

    def test_clear_documents_handles_rag_errors(self):
        async def _raise_error(**_payload):
            raise RAGServiceError("boom", status_code=503)

        documents.rag_client.clear_documents = _raise_error  # type: ignore[assignment]

        response = self.client.delete("/documents")

        self.assertEqual(response.status_code, 503)
        self.assertIn("boom", response.text)


if __name__ == "__main__":
    unittest.main()


