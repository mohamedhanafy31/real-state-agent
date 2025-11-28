"""
Document management endpoints that proxy CRUD operations to the RAG service.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, status

from app.logging_config import get_logger
from app.services.rag_client import RAGClient, RAGServiceError

router = APIRouter(prefix="/documents", tags=["documents"])

logger = get_logger(__name__)
rag_client = RAGClient()


def _validate_filename(filename: str) -> None:
    """Ensure filenames do not contain traversal segments."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )


def _handle_rag_error(error: RAGServiceError) -> HTTPException:
    """Convert service errors into HTTP exceptions."""
    status_code = error.status_code or status.HTTP_502_BAD_GATEWAY
    return HTTPException(status_code=status_code, detail=str(error))


async def _read_upload(file: UploadFile) -> bytes:
    """Read upload contents and guard against empty payloads."""
    content = await file.read()
    if content is None or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    return content


@router.get("", summary="List documents")
async def list_documents():
    """Return the documents tracked by the RAG service."""
    try:
        return await rag_client.list_documents()
    except RAGServiceError as error:
        logger.error("Failed to list documents via RAG: %s", error)
        raise _handle_rag_error(error)


@router.post("", summary="Upload a new document")
async def create_document(
    file: UploadFile = File(...),
    rebuild_index: bool = Query(
        True,
        description="Trigger RAG ingestion after upload.",
    ),
):
    """Upload a document to the RAG data store."""
    content = await _read_upload(file)
    try:
        return await rag_client.upload_document(
            filename=file.filename,
            content=content,
            content_type=file.content_type,
            rebuild_index=rebuild_index,
        )
    except RAGServiceError as error:
        logger.error("Failed to upload document %s: %s", file.filename, error)
        raise _handle_rag_error(error)


@router.put("/{filename}", summary="Replace an existing document")
async def update_document(
    filename: str,
    file: UploadFile = File(...),
    rebuild_index: bool = Query(
        True,
        description="Trigger RAG ingestion after replacing the file.",
    ),
):
    """Overwrite a document by name in the RAG data store."""
    _validate_filename(filename)
    content = await _read_upload(file)
    try:
        return await rag_client.upload_document(
            filename=filename,
            content=content,
            content_type=file.content_type,
            rebuild_index=rebuild_index,
        )
    except RAGServiceError as error:
        logger.error("Failed to update document %s: %s", filename, error)
        raise _handle_rag_error(error)


@router.delete(
    "/{filename}",
    summary="Delete a document",
    status_code=status.HTTP_200_OK,
)
async def delete_document(
    filename: str,
    remove_from_index: bool = Query(
        True,
        description="Remove document chunks from the FAISS index.",
    ),
):
    """Delete a single document."""
    _validate_filename(filename)
    try:
        return await rag_client.delete_document(
            filename=filename,
            remove_from_index=remove_from_index,
        )
    except RAGServiceError as error:
        logger.error("Failed to delete document %s: %s", filename, error)
        raise _handle_rag_error(error)


@router.delete(
    "",
    summary="Clear all documents",
    status_code=status.HTTP_200_OK,
)
async def clear_documents(
    clear_index: bool = Query(
        True,
        description="Also remove FAISS index artifacts.",
    ),
):
    """Delete every document (and optionally the FAISS index)."""
    try:
        return await rag_client.clear_documents(clear_index=clear_index)
    except RAGServiceError as error:
        logger.error("Failed to clear documents: %s", error)
        raise _handle_rag_error(error)


