import hashlib
import io
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pypdf
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.core.storage import get_storage_provider
from app.models.ai import DocumentChunk
from app.models.document import (
    Document,
    DocumentProcessingStatus,
    DocumentSecurityStatus,
)
from app.models.document_page import DocumentPage
from app.domain.auth.auth_service import AuthService
from app.domain.cases.case_service import CaseService
from app.domain.ai.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class ExtractedPageData:
    page_number: int
    text: str
    word_count: int
    character_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentProcessor:
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService(db)

    def _log_audit(self, event_type: str, user_id: uuid.UUID, metadata: dict):
        self.auth_service.log_audit_event(
            event_type, user_id, metadata, action="document_processing"
        )

    def process_document(
        self,
        document_id: uuid.UUID,
        raw_text: str | None = None,
        expected_version: int | None = None,
        generate_embeddings: bool = True,
    ) -> list[DocumentChunk]:
        """Processes a SAFE document: extracts text page-by-page, generates structured

        pages and bounded provenance-preserving chunks, and updates processing status.
        Protects against version overwrite, ensures idempotency, and logs audit events.
        """
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ResourceNotFoundError("Document not found")

        if document.deleted_at is not None:
            logger.warning(f"Skipping processing for soft-deleted document {document_id}")
            return []

        # Quarantine safety check: prevent untrusted or pending documents from being processed
        if document.security_status != DocumentSecurityStatus.SAFE:
            logger.warning(
                f"Aborting processing for document {document_id}: "
                f"security status is {document.security_status.value}, expected SAFE"
            )
            return []

        # Version safety check: verify against stale jobs
        if expected_version is not None and document.version != expected_version:
            logger.warning(
                f"Aborting stale processing job for document {document_id}: "
                f"job version {expected_version} != current version {document.version}"
            )
            return []

        job_version = document.version

        # Mark document as PROCESSING
        document.processing_status = DocumentProcessingStatus.PROCESSING
        document.processing_error = None
        self.db.commit()
        self.db.refresh(document)

        self._log_audit(
            "DOCUMENT_PROCESSING_STARTED",
            document.uploaded_by,
            {
                "document_id": str(document.id),
                "case_id": str(document.case_id),
                "version": job_version,
                "mime_type": document.mime_type,
            },
        )

        try:
            pages: list[ExtractedPageData] = []
            status = DocumentProcessingStatus.READY
            error_msg: str | None = None

            if raw_text is not None:
                # Raw text provided directly (e.g. tests or pre-extracted pipeline)
                cleaned_text = raw_text.strip()
                if not cleaned_text:
                    status = DocumentProcessingStatus.EMPTY_DOCUMENT
                    error_msg = "Document contains no extractable text"
                else:
                    pages = [
                        ExtractedPageData(
                            page_number=1,
                            text=cleaned_text,
                            word_count=len(cleaned_text.split()),
                            character_count=len(cleaned_text),
                        )
                    ]
            else:
                # Retrieve document bytes safely through storage abstraction
                storage_provider = get_storage_provider()
                file_bytes = (
                    storage_provider.get_object_bytes(document.storage_key)
                    if document.storage_key
                    else None
                )

                if file_bytes is None or len(file_bytes) == 0:
                    status = DocumentProcessingStatus.EMPTY_DOCUMENT
                    error_msg = "Document storage object is empty or missing"
                else:
                    status, pages, error_msg = self._extract_content(
                        file_bytes, document.filename, document.mime_type
                    )

            # Check if extraction produced a terminal non-ready status
            if status != DocumentProcessingStatus.READY:
                self._finalize_failure_status(
                    document_id, status, error_msg, job_version
                )
                return []

            if not pages or all(len(p.text.strip()) == 0 for p in pages):
                self._finalize_failure_status(
                    document_id,
                    DocumentProcessingStatus.EMPTY_DOCUMENT,
                    "Document contains no extractable text",
                    job_version,
                )
                return []

            # Generate deterministic bounded chunks with page provenance
            chunks = self._generate_provenance_chunks(document, pages, job_version)

            # Generate embeddings if requested
            if generate_embeddings and chunks:
                texts_to_embed = [chunk.content for chunk in chunks]
                try:
                    embedding_service = EmbeddingService()
                    embeddings = embedding_service.generate_embeddings(texts_to_embed)
                    for idx, chunk in enumerate(chunks):
                        if idx < len(embeddings):
                            chunk.embedding = embeddings[idx]
                            chunk.embedding_model = settings.EMBEDDING_MODEL
                            chunk.embedding_version = "1"
                except Exception as emb_ex:  # noqa: BLE001
                    logger.warning(
                        f"Embedding generation skipped for doc {document_id}: {emb_ex}"
                    )

            # Persist pages and chunks idempotently in an atomic transaction
            self._persist_pages_and_chunks(
                document_id, pages, chunks, job_version
            )

            # Refresh document state
            self.db.refresh(document)

            self._log_audit(
                "DOCUMENT_PROCESSING_COMPLETED",
                document.uploaded_by,
                {
                    "document_id": str(document.id),
                    "case_id": str(document.case_id),
                    "version": job_version,
                    "page_count": len(pages),
                    "chunk_count": len(chunks),
                },
            )

            case_service = CaseService(self.db)
            case_service.record_case_activity(
                document.case_id,
                document.uploaded_by,
                "DOCUMENT_PROCESSED",
                f"Document {document.filename} was successfully processed ({len(pages)} pages, {len(chunks)} chunks)",
                {
                    "document_id": str(document.id),
                    "page_count": len(pages),
                    "chunk_count": len(chunks),
                },
            )

            return chunks

        except Exception as ex:
            logger.exception(f"Unhandled exception during document processing for {document_id}")
            self._finalize_failure_status(
                document_id,
                DocumentProcessingStatus.FAILED,
                f"Processing error: {str(ex)[:300]}",
                job_version,
            )
            return []

    def _extract_text_from_bytes(
        self, file_bytes: bytes, filename: str, mime_type: str
    ) -> str:
        """Extracts text from binary document bytes for backward compatibility."""
        if not file_bytes:
            return ""
        status, pages, _ = self._extract_content(file_bytes, filename, mime_type)
        if status == DocumentProcessingStatus.READY and pages:
            return "\n\n".join(p.text for p in pages if p.text.strip())
        return ""

    def _extract_content(
        self, file_bytes: bytes, filename: str, mime_type: str
    ) -> tuple[DocumentProcessingStatus, list[ExtractedPageData], str | None]:
        """Extracts structured text page-by-page based on document MIME type."""
        # 1. Plain text extraction
        if mime_type == "text/plain":
            return self._extract_txt(file_bytes, filename)

        # 2. PDF extraction
        if mime_type == "application/pdf":
            return self._extract_pdf(file_bytes, filename)

        # 3. DOCX extraction
        if mime_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ):
            return self._extract_docx(file_bytes, filename)

        # 4. Images requiring OCR
        if mime_type in ("image/png", "image/jpeg", "image/jpg"):
            return (
                DocumentProcessingStatus.OCR_REQUIRED,
                [],
                "Image documents require OCR pipeline for text extraction",
            )

        # 5. Unsupported formats
        return (
            DocumentProcessingStatus.UNSUPPORTED_FORMAT,
            [],
            f"Format '{mime_type}' is not supported for text extraction",
        )

    def _extract_txt(
        self, file_bytes: bytes, filename: str
    ) -> tuple[DocumentProcessingStatus, list[ExtractedPageData], str | None]:
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = file_bytes.decode("latin-1")
            except Exception as e:  # noqa: BLE001
                return (
                    DocumentProcessingStatus.CORRUPTED_FILE,
                    [],
                    f"Unable to decode text file: {e}",
                )

        cleaned = text.strip()
        if not cleaned:
            return (
                DocumentProcessingStatus.EMPTY_DOCUMENT,
                [],
                "Text file is empty",
            )

        pages = [
            ExtractedPageData(
                page_number=1,
                text=cleaned,
                word_count=len(cleaned.split()),
                character_count=len(cleaned),
            )
        ]
        return DocumentProcessingStatus.READY, pages, None

    def _extract_pdf(
        self, file_bytes: bytes, filename: str
    ) -> tuple[DocumentProcessingStatus, list[ExtractedPageData], str | None]:
        try:
            stream = io.BytesIO(file_bytes)
            reader = pypdf.PdfReader(stream)

            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:  # noqa: BLE001
                    return (
                        DocumentProcessingStatus.FAILED,
                        [],
                        "Password-protected PDF cannot be processed",
                    )

            pages: list[ExtractedPageData] = []
            for idx, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text() or ""
                except Exception as page_err:  # noqa: BLE001
                    logger.warning(f"Error extracting page {idx + 1} of {filename}: {page_err}")
                    page_text = ""

                cleaned = page_text.strip()
                pages.append(
                    ExtractedPageData(
                        page_number=idx + 1,
                        text=cleaned,
                        word_count=len(cleaned.split()) if cleaned else 0,
                        character_count=len(cleaned),
                    )
                )

            total_chars = sum(p.character_count for p in pages)
            if total_chars == 0:
                # Attempt fallback stream string extraction for simple uncompressed PDFs
                raw_strings = re.findall(rb"\(([^)]+)\)", file_bytes)
                extracted_tokens: list[str] = []
                for s in raw_strings:
                    try:
                        decoded = s.decode("utf-8", errors="ignore").strip()
                        if len(decoded) > 2 and all(32 <= ord(c) < 127 for c in decoded):
                            extracted_tokens.append(decoded)
                    except Exception:  # noqa: BLE001, S112
                        continue

                if extracted_tokens:
                    fallback_text = " ".join(extracted_tokens)
                    pages = [
                        ExtractedPageData(
                            page_number=1,
                            text=fallback_text,
                            word_count=len(fallback_text.split()),
                            character_count=len(fallback_text),
                        )
                    ]
                else:
                    return (
                        DocumentProcessingStatus.EMPTY_DOCUMENT,
                        [],
                        "PDF contains no extractable text (may be scanned image requiring OCR)",
                    )

            return DocumentProcessingStatus.READY, pages, None

        except (pypdf.errors.PdfReadError, ValueError, IndexError) as pdf_err:
            logger.warning(f"Corrupted PDF stream in {filename}: {pdf_err}")
            return (
                DocumentProcessingStatus.CORRUPTED_FILE,
                [],
                f"PDF is corrupted or invalid: {pdf_err}",
            )
        except Exception as e:
            logger.exception(f"Unexpected error extracting PDF {filename}")
            return (
                DocumentProcessingStatus.CORRUPTED_FILE,
                [],
                f"Failed to parse PDF: {e}",
            )

    def _extract_docx(
        self, file_bytes: bytes, filename: str
    ) -> tuple[DocumentProcessingStatus, list[ExtractedPageData], str | None]:
        try:
            import docx

            doc_obj = docx.Document(io.BytesIO(file_bytes))
            blocks: list[str] = []

            for p in doc_obj.paragraphs:
                p_text = p.text.strip()
                if p_text:
                    blocks.append(p_text)

            for table in doc_obj.tables:
                for row in table.rows:
                    row_parts = [c.text.strip() for c in row.cells if c.text.strip()]
                    if row_parts:
                        blocks.append(" | ".join(row_parts))

            full_text = "\n\n".join(blocks).strip()
            if not full_text:
                return (
                    DocumentProcessingStatus.EMPTY_DOCUMENT,
                    [],
                    "DOCX document contains no extractable text",
                )

            pages = [
                ExtractedPageData(
                    page_number=1,
                    text=full_text,
                    word_count=len(full_text.split()),
                    character_count=len(full_text),
                )
            ]
            return DocumentProcessingStatus.READY, pages, None

        except Exception as e:  # noqa: BLE001
            logger.warning(f"DOCX extraction failed for {filename}: {e}")
            return (
                DocumentProcessingStatus.CORRUPTED_FILE,
                [],
                f"DOCX file is corrupted or unreadable: {e}",
            )

    def _generate_provenance_chunks(
        self,
        document: Document,
        pages: list[ExtractedPageData],
        job_version: int,
    ) -> list[DocumentChunk]:
        """Generates deterministic, bounded text chunks preserving page provenance."""
        chunks: list[DocumentChunk] = []
        chunk_idx = 0
        seen_hashes: set[str] = set()

        for page in pages:
            if not page.text.strip():
                continue

            # Split page text into paragraphs
            paragraphs = [
                p.strip() for p in page.text.split("\n\n") if len(p.strip()) > 0
            ]
            if not paragraphs:
                paragraphs = [
                    p.strip() for p in page.text.split("\n") if len(p.strip()) > 0
                ]
            if not paragraphs:
                paragraphs = [page.text.strip()]

            # Subdivide oversized paragraphs (> 1500 chars) by sentence
            refined: list[str] = []
            for p in paragraphs:
                if len(p) > 1500:
                    sentences = p.split(". ")
                    cur_sub = ""
                    for s in sentences:
                        if len(cur_sub) + len(s) + 2 > 1200:
                            if cur_sub:
                                refined.append(cur_sub.strip())
                            cur_sub = s
                        else:
                            cur_sub = f"{cur_sub}. {s}" if cur_sub else s
                    if cur_sub:
                        refined.append(cur_sub.strip())
                else:
                    refined.append(p)

            # Sliding window of 2 paragraphs with 1 paragraph overlap
            chunk_window_size = 2
            chunk_overlap = 1
            i = 0
            while i < len(refined):
                window = refined[i : i + chunk_window_size]
                chunk_text = "\n\n".join(window).strip()
                if chunk_text:
                    content_hash = hashlib.md5(chunk_text.encode("utf-8")).hexdigest()
                    if content_hash not in seen_hashes:
                        seen_hashes.add(content_hash)
                        chunk_obj = DocumentChunk(
                            id=generate_uuid7(),
                            case_id=document.case_id,
                            document_id=document.id,
                            content=chunk_text,
                            metadata_={
                                "chunk_index": chunk_idx,
                                "page_start": page.page_number,
                                "page_end": page.page_number,
                                "page_number": page.page_number,
                                "source_filename": document.filename,
                                "source_type": document.mime_type,
                                "document_version": job_version,
                                "document_id": str(document.id),
                                "case_id": str(document.case_id),
                                "character_count": len(chunk_text),
                                "word_count": len(chunk_text.split()),
                            },
                        )
                        chunks.append(chunk_obj)
                        chunk_idx += 1

                if i + chunk_window_size >= len(refined):
                    break
                i += max(1, chunk_window_size - chunk_overlap)

        return chunks

    def _persist_pages_and_chunks(
        self,
        document_id: uuid.UUID,
        pages: list[ExtractedPageData],
        chunks: list[DocumentChunk],
        job_version: int,
    ) -> None:
        """Atomically replaces existing pages and chunks for document_id and updates

        document processing metrics with version safety.
        """
        # Re-fetch document inside transaction
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ResourceNotFoundError("Document not found during persist")

        # Version safety check
        if doc.version != job_version:
            logger.warning(
                f"Aborting persistence: Document {document_id} version changed from "
                f"{job_version} to {doc.version}"
            )
            return

        # 1. Clean existing pages and chunks (Idempotency)
        self.db.query(DocumentPage).filter(
            DocumentPage.document_id == document_id
        ).delete()
        self.db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).delete()

        # 2. Insert new pages
        total_words = 0
        total_chars = 0
        for p in pages:
            total_words += p.word_count
            total_chars += p.character_count
            page_record = DocumentPage(
                id=generate_uuid7(),
                document_id=doc.id,
                case_id=doc.case_id,
                page_number=p.page_number,
                text=p.text,
                word_count=p.word_count,
                character_count=p.character_count,
                metadata_=p.metadata,
            )
            self.db.add(page_record)

        # 3. Insert new chunks
        for c in chunks:
            self.db.add(c)

        # 4. Update document metadata
        doc.processing_status = DocumentProcessingStatus.READY
        doc.processing_error = None
        doc.page_count = len(pages)
        doc.word_count = total_words
        doc.character_count = total_chars
        doc.processed_at = datetime.now(UTC)

        self.db.commit()

    def _finalize_failure_status(
        self,
        document_id: uuid.UUID,
        status: DocumentProcessingStatus,
        error_msg: str | None,
        job_version: int,
    ) -> None:
        """Safely updates document failure status without throwing exceptions."""
        try:
            self.db.rollback()
            doc = self.db.query(Document).filter(Document.id == document_id).first()
            if doc and doc.version == job_version:
                doc.processing_status = status
                doc.processing_error = error_msg[:500] if error_msg else None
                doc.processed_at = datetime.now(UTC)
                self.db.commit()

                self._log_audit(
                    "DOCUMENT_PROCESSING_FAILED",
                    doc.uploaded_by,
                    {
                        "document_id": str(doc.id),
                        "case_id": str(doc.case_id),
                        "version": job_version,
                        "status": status.value,
                        "error": error_msg,
                    },
                )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to record failure status for document {document_id}: {e}")
