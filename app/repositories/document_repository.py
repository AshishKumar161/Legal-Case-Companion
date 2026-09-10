"""Persistence repository for Document entities."""

from uuid import UUID
from sqlalchemy.orm import Session

from app.models.document import Document


class DocumentRepository:
    """Encapsulates persistence operations for Document domain models."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, document_id: UUID) -> Document | None:
        """Retrieves a document by UUID, excluding soft-deleted records."""
        return (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.deleted_at.is_(None))
            .first()
        )

    def list_by_case(
        self,
        case_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        """Lists active documents for a given case."""
        return (
            self.db.query(Document)
            .filter(Document.case_id == case_id, Document.deleted_at.is_(None))
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_by_case(self, case_id: UUID) -> int:
        """Counts active documents for a given case."""
        return (
            self.db.query(Document.id)
            .filter(Document.case_id == case_id, Document.deleted_at.is_(None))
            .count()
        )
