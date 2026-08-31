import uuid

from sqlalchemy import JSON, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.identifiers import generate_uuid7
from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class AIEvaluation(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ai_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=generate_uuid7)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    grounding_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    citation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String, nullable=True)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
