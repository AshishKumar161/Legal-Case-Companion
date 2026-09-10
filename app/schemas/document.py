from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentCategory


class DocumentCreate(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    mime_type: str = Field(..., max_length=100)
    file_size: int
    document_type: DocumentCategory = DocumentCategory.MISCELLANEOUS
    description: str | None = Field(None, max_length=1000)
    checksum: str | None = Field(None, max_length=64)
    is_confidential: bool = False


class DocumentUpdate(BaseModel):
    filename: str | None = Field(None, min_length=1, max_length=255)
    document_type: DocumentCategory | None = None
    description: str | None = Field(None, max_length=1000)
    is_confidential: bool | None = None


class DocumentResponse(BaseModel):
    id: UUID
    case_id: UUID
    uploaded_by: UUID
    filename: str
    storage_key: str
    mime_type: str
    file_size: int
    security_status: str
    processing_status: str = "PENDING"
    processing_error: str | None = None
    page_count: int | None = None
    word_count: int | None = None
    character_count: int | None = None
    processed_at: datetime | None = None
    document_type: str
    description: str | None = None
    checksum: str | None = None
    version: int = 1
    is_confidential: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadDocumentResponse(BaseModel):
    document: DocumentResponse
    upload_url: str


class DownloadDocumentResponse(BaseModel):
    download_url: str


class DocumentSummaryStats(BaseModel):
    total: int = 0
    safe: int = 0
    pending: int = 0
    quarantined: int = 0
    rejected: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)


class DocumentProcessingStatusResponse(BaseModel):
    document_id: UUID
    case_id: UUID
    security_status: str
    processing_status: str
    processing_error: str | None = None
    page_count: int | None = None
    word_count: int | None = None
    character_count: int | None = None
    chunk_count: int = 0
    version: int = 1
    processed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentPageResponse(BaseModel):
    id: UUID
    document_id: UUID
    case_id: UUID
    page_number: int
    text: str
    word_count: int
    character_count: int
    metadata_: dict | None = Field(None, serialization_alias="metadata")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DocumentChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    case_id: UUID
    content: str
    metadata_: dict | None = Field(None, serialization_alias="metadata")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

