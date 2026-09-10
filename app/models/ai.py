import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.document import Document
    from app.models.user import User


class SQLiteCompatibleArray(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, item_type, *args, **kwargs):
        self.item_type = item_type
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_ARRAY(self.item_type))
        return dialect.type_descriptor(JSON)


class AIMessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class DocumentChunk(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        SQLiteCompatibleArray(Float), nullable=True
    )
    embedding_model: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="document_chunks")
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


class AIConversation(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ai_conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case")
    user: Mapped["User | None"] = relationship("User")
    messages: Mapped[list["AIMessage"]] = relationship(
        "AIMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AIMessage.created_at.asc()",
    )


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[AIMessageRole] = mapped_column(
        Enum(AIMessageRole, name="aimessagerole"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    authority_citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    claims: Mapped[list | None] = mapped_column(JSON, nullable=True)
    grounding_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    uncertainties: Mapped[list | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    conversation: Mapped["AIConversation"] = relationship(
        "AIConversation", back_populates="messages"
    )




class AIResponseAudit(Base):
    __tablename__ = "ai_response_audits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grounding_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    citation_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case")
    message: Mapped["AIMessage | None"] = relationship("AIMessage")
