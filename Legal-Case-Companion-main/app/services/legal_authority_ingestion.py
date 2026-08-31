import logging

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.identifiers import generate_uuid7
from app.models.legal_authority import LegalSource, LegalSourceVersion
from app.schemas.legal_authority import (
    LegalAuthorityIngestRequest,
    LegalAuthorityResponse,
)
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class LegalAuthorityIngestionService:
    """Service for controlled, validated, and idempotent ingestion of Indian legal authorities."""

    def __init__(self, db: Session, embedding_service: EmbeddingService | None = None):
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService()

    def ingest_legal_authority(
        self, req: LegalAuthorityIngestRequest
    ) -> LegalAuthorityResponse:
        """Idempotently ingests or updates a legal authority (Act or Reported Judgment)

        with its constituent provisions/sections, performing date validation and vector indexing.
        """
        # 1. Date and metadata validation
        if req.effective_from and req.effective_to and req.effective_from > req.effective_to:
            raise AppException(
                status_code=400,
                code="INVALID_TEMPORAL_RANGE",
                message=f"effective_from ({req.effective_from}) cannot be after effective_to ({req.effective_to})",
            )

        for prov in req.provisions:
            if prov.effective_from and prov.effective_to and prov.effective_from > prov.effective_to:
                raise AppException(
                    status_code=400,
                    code="INVALID_PROVISION_TEMPORAL_RANGE",
                    message=f"Provision {prov.canonical_provision_id} has invalid dates: {prov.effective_from} > {prov.effective_to}",
                )

        # 2. Find or create canonical LegalSource
        source = (
            self.db.query(LegalSource)
            .filter(LegalSource.canonical_identifier == req.canonical_identifier)
            .first()
        )

        if not source:
            source = LegalSource(
                id=generate_uuid7(),
                canonical_identifier=req.canonical_identifier,
                name=req.name,
                short_title=req.short_title,
                year=req.year,
                source_type=req.source_type,
                authority_level=req.authority_level,
                jurisdiction=req.jurisdiction,
                issuing_body=req.issuing_body,
                publication_date=req.publication_date,
                effective_from=req.effective_from,
                effective_to=req.effective_to,
                status=req.status,
                citation_standard=req.citation_standard,
                canonical_url=req.canonical_url,
                metadata_=req.metadata_,
                is_active=True,
            )
            self.db.add(source)
            self.db.flush()
        else:
            # Update mutable metadata on existing source
            source.name = req.name
            source.short_title = req.short_title
            source.year = req.year
            source.source_type = req.source_type
            source.authority_level = req.authority_level
            source.jurisdiction = req.jurisdiction
            source.issuing_body = req.issuing_body
            source.publication_date = req.publication_date
            source.effective_from = req.effective_from
            source.effective_to = req.effective_to
            source.status = req.status
            source.citation_standard = req.citation_standard
            source.canonical_url = req.canonical_url
            source.metadata_ = req.metadata_
            self.db.flush()

        # 3. Idempotent provision upsert and vector embedding generation
        provisions_to_embed: list[tuple[LegalSourceVersion, str]] = []

        for p_req in req.provisions:
            existing_prov = (
                self.db.query(LegalSourceVersion)
                .filter(
                    LegalSourceVersion.source_id == source.id,
                    LegalSourceVersion.canonical_provision_id == p_req.canonical_provision_id,
                )
                .first()
            )

            if not existing_prov:
                new_prov = LegalSourceVersion(
                    id=generate_uuid7(),
                    source_id=source.id,
                    canonical_provision_id=p_req.canonical_provision_id,
                    section_number=p_req.section_number,
                    version_label=p_req.version_label,
                    chapter_number=p_req.chapter_number,
                    title=p_req.title,
                    content=p_req.content,
                    effective_from=p_req.effective_from or req.effective_from,
                    effective_to=p_req.effective_to or req.effective_to,
                    is_current=p_req.is_current,
                    metadata_=p_req.metadata_,
                )
                self.db.add(new_prov)
                provisions_to_embed.append((new_prov, p_req.content))
            else:
                # Content updated -> queue for re-embedding
                content_changed = existing_prov.content != p_req.content
                existing_prov.section_number = p_req.section_number
                existing_prov.version_label = p_req.version_label
                existing_prov.chapter_number = p_req.chapter_number
                existing_prov.title = p_req.title
                existing_prov.content = p_req.content
                existing_prov.effective_from = p_req.effective_from or req.effective_from
                existing_prov.effective_to = p_req.effective_to or req.effective_to
                existing_prov.is_current = p_req.is_current
                existing_prov.metadata_ = p_req.metadata_

                if content_changed or existing_prov.embedding is None:
                    provisions_to_embed.append((existing_prov, p_req.content))

        self.db.flush()

        # 4. Generate embeddings in batch if any new or modified provisions exist
        if provisions_to_embed:
            texts = [item[1] for item in provisions_to_embed]
            try:
                embeddings = self.embedding_service.generate_embeddings(texts)
                for (prov_obj, _), vec in zip(provisions_to_embed, embeddings, strict=False):
                    prov_obj.embedding = vec
            except Exception as emb_err:  # noqa: BLE001
                logger.warning(
                    f"Vector embedding generation failed during legal authority ingestion ({req.canonical_identifier}): {emb_err}"
                )

        self.db.commit()
        self.db.refresh(source)
        return LegalAuthorityResponse.model_validate(source)
