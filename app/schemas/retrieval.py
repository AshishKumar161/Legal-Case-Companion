import uuid

from pydantic import BaseModel


class RetrievedChunk(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    case_id: uuid.UUID
    content: str
    score: float
    source_metadata: dict | None
