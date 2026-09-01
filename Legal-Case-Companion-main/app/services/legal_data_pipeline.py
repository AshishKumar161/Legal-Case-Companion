import datetime
import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppException, ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.legal_authority import (
    AuthorityLevel,
    LegalAuthorityType,
    LegalJurisdiction,
    LegalSource,
    LegalSourceStatus,
    LegalSourceVersion,
    RawLegalSource,
)
from app.services.embedding_service import EmbeddingService
from app.services.legal_source_providers.base import RawLegalSourcePayload
from app.services.legal_source_providers.curated_fixtures import (
    CuratedFixtureSourceProvider,
)

logger = logging.getLogger(__name__)


class LegalDataPipeline:
    """Production pipeline for controlled, provenance-preserving, and version-aware

    ingestion, normalization, validation, and vector indexing of Indian legal authorities.
    """

    def __init__(self, db: Session, embedding_service: EmbeddingService | None = None):
        self.db = db
        self.embedding_service = embedding_service or EmbeddingService()

    def ingest_raw_payload(self, payload: RawLegalSourcePayload) -> RawLegalSource:
        """Stores raw legal material into the raw ingestion layer with cryptographic checksum."""
        checksum = (
            payload.content_checksum
            or hashlib.sha256(payload.raw_content.encode("utf-8")).hexdigest()
        )

        raw_record = (
            self.db.query(RawLegalSource)
            .filter(
                RawLegalSource.source_system == payload.source_system,
                RawLegalSource.external_identifier == payload.external_identifier,
            )
            .first()
        )

        if not raw_record:
            raw_record = RawLegalSource(
                id=generate_uuid7(),
                source_system=payload.source_system,
                external_identifier=payload.external_identifier,
                source_type=payload.source_type,
                raw_content=payload.raw_content,
                raw_metadata=payload.raw_metadata,
                content_checksum=checksum,
                retrieval_url=payload.retrieval_url,
                retrieved_at=datetime.datetime.now(datetime.UTC),
                status="RAW_INGESTED",
            )
            self.db.add(raw_record)
            self.db.flush()
        else:
            # If content changed, update raw record and reset status to RAW_INGESTED
            if raw_record.content_checksum != checksum:
                raw_record.raw_content = payload.raw_content
                raw_record.raw_metadata = payload.raw_metadata
                raw_record.content_checksum = checksum
                raw_record.retrieval_url = payload.retrieval_url
                raw_record.retrieved_at = datetime.datetime.now(datetime.UTC)
                raw_record.status = "RAW_INGESTED"
                self.db.flush()

        return raw_record

    def process_raw_source(self, raw_source_id: UUID) -> LegalSource:
        """Normalizes, validates, creates canonical versions, and indexes a raw legal source."""
        raw_source = (
            self.db.query(RawLegalSource).filter(RawLegalSource.id == raw_source_id).first()
        )
        if not raw_source:
            raise ResourceNotFoundError(f"Raw legal source '{raw_source_id}' not found.")

        try:
            parsed_data: dict[str, Any] = json.loads(raw_source.raw_content)
        except Exception as e:
            raw_source.status = "FAILED"
            raw_source.last_error = f"JSON parse failure: {e}"
            self.db.commit()
            raise AppException(
                status_code=400,
                code="INVALID_RAW_CONTENT",
                message=f"Raw legal content could not be parsed: {e}",
            ) from e

        # 1. Validation of essential metadata
        canonical_id = parsed_data.get("canonical_identifier") or raw_source.external_identifier
        name = parsed_data.get("name")
        year = parsed_data.get("year")
        if not canonical_id or not name or not year:
            raw_source.status = "FAILED"
            raw_source.last_error = "Missing canonical_identifier, name, or year."
            self.db.commit()
            raise AppException(
                status_code=400,
                code="VALIDATION_FAILED",
                message="Legal source is missing required identity fields.",
            )

        # 2. Find or create canonical LegalSource
        source = (
            self.db.query(LegalSource)
            .filter(LegalSource.canonical_identifier == canonical_id)
            .first()
        )

        is_new_source = source is None
        if source is None:
            source = LegalSource(
                id=generate_uuid7(),
                canonical_identifier=canonical_id,
                name=name,
                short_title=parsed_data.get("short_title"),
                year=int(year),
                source_type=LegalAuthorityType(
                    parsed_data.get("source_type", raw_source.source_type.value)
                ),
                authority_level=int(
                    parsed_data.get("authority_level", AuthorityLevel.PRIMARY_STATUTE.value)
                ),
                jurisdiction=parsed_data.get(
                    "jurisdiction", LegalJurisdiction.INDIA_CENTRAL.value
                ),
                issuing_body=parsed_data.get("issuing_body"),
                publication_date=(
                    datetime.date.fromisoformat(parsed_data["publication_date"])
                    if parsed_data.get("publication_date")
                    else None
                ),
                effective_from=(
                    datetime.date.fromisoformat(parsed_data["effective_from"])
                    if parsed_data.get("effective_from")
                    else None
                ),
                effective_to=(
                    datetime.date.fromisoformat(parsed_data["effective_to"])
                    if parsed_data.get("effective_to")
                    else None
                ),
                status=LegalSourceStatus(
                    parsed_data.get("status", LegalSourceStatus.PUBLISHED.value)
                ),
                citation_standard=parsed_data.get("citation_standard"),
                canonical_url=parsed_data.get("canonical_url") or raw_source.retrieval_url,
                metadata_=parsed_data.get("metadata"),
                is_active=True,
            )
            self.db.add(source)
            self.db.flush()
        else:
            source.name = name
            source.short_title = parsed_data.get("short_title", source.short_title)
            source.year = int(year)
            source.authority_level = int(
                parsed_data.get("authority_level", source.authority_level)
            )
            source.jurisdiction = parsed_data.get("jurisdiction", source.jurisdiction)
            source.issuing_body = parsed_data.get("issuing_body", source.issuing_body)
            source.citation_standard = parsed_data.get(
                "citation_standard", source.citation_standard
            )
            source.canonical_url = (
                parsed_data.get("canonical_url") or raw_source.retrieval_url or source.canonical_url
            )
            self.db.flush()

        assert source is not None

        # 3. Process and version provisions / judgment holdings
        provisions_to_embed: list[tuple[LegalSourceVersion, str]] = []
        raw_provisions = parsed_data.get("provisions", [])

        for p_data in raw_provisions:
            c_prov_id = p_data["canonical_provision_id"]
            sec_num = p_data["section_number"]
            ver_label = p_data.get("version_label", "Current")
            title = p_data.get("title", "")
            content = p_data.get("content", "")
            eff_from = (
                datetime.date.fromisoformat(p_data["effective_from"])
                if p_data.get("effective_from")
                else source.effective_from
            )
            eff_to = (
                datetime.date.fromisoformat(p_data["effective_to"])
                if p_data.get("effective_to")
                else source.effective_to
            )
            is_current = bool(p_data.get("is_current", True))

            existing_version = (
                self.db.query(LegalSourceVersion)
                .filter(
                    LegalSourceVersion.source_id == source.id,
                    LegalSourceVersion.canonical_provision_id == c_prov_id,
                )
                .first()
            )

            if not existing_version:
                new_version = LegalSourceVersion(
                    id=generate_uuid7(),
                    source_id=source.id,
                    canonical_provision_id=c_prov_id,
                    section_number=sec_num,
                    version_label=ver_label,
                    chapter_number=p_data.get("chapter_number"),
                    title=title,
                    content=content,
                    effective_from=eff_from,
                    effective_to=eff_to,
                    is_current=is_current,
                    metadata_=p_data.get("metadata"),
                )
                self.db.add(new_version)
                provisions_to_embed.append((new_version, content))
            else:
                content_changed = existing_version.content != content
                existing_version.section_number = sec_num
                existing_version.version_label = ver_label
                existing_version.chapter_number = p_data.get(
                    "chapter_number", existing_version.chapter_number
                )
                existing_version.title = title
                existing_version.content = content
                existing_version.effective_from = eff_from
                existing_version.effective_to = eff_to
                existing_version.is_current = is_current
                existing_version.metadata_ = p_data.get("metadata", existing_version.metadata_)

                if content_changed or existing_version.embedding is None:
                    provisions_to_embed.append((existing_version, content))

        self.db.flush()

        # 4. Generate batch embeddings for new or modified provisions
        if provisions_to_embed:
            texts = [item[1] for item in provisions_to_embed]
            try:
                embeddings = self.embedding_service.generate_embeddings(texts)
                for (prov_obj, _), vec in zip(provisions_to_embed, embeddings, strict=False):
                    prov_obj.embedding = vec
            except Exception as emb_err:  # noqa: BLE001
                logger.warning(
                    f"Vector embedding generation failed during pipeline processing ({canonical_id}): {emb_err}"
                )

        # 5. Link raw source and record audit event
        raw_source.canonical_source_id = source.id
        raw_source.status = "INDEXED"
        raw_source.last_error = None

        audit = AuditEvent(
            id=generate_uuid7(),
            event_type="LEGAL_AUTHORITY_CHANGE",
            entity_type="legal_source",
            entity_id=source.id,
            action="LEGAL_SOURCE_INGESTED" if is_new_source else "LEGAL_SOURCE_UPDATED",
            timestamp=datetime.datetime.now(datetime.UTC),
            metadata_={
                "canonical_identifier": source.canonical_identifier,
                "name": source.name,
                "provisions_count": len(raw_provisions),
                "provisions_embedded": len(provisions_to_embed),
                "source_system": raw_source.source_system,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(source)
        return source

    def sync_curated_fixtures(self) -> dict[str, Any]:
        """Idempotently syncs all curated Indian legal statutes and landmark judicial precedents."""
        provider = CuratedFixtureSourceProvider()
        payloads = provider.fetch_all()
        synced_sources = []

        for payload in payloads:
            raw_rec = self.ingest_raw_payload(payload)
            source = self.process_raw_source(raw_rec.id)
            synced_sources.append(source.canonical_identifier)

        return {
            "total_fixtures": len(payloads),
            "synced_identifiers": synced_sources,
            "status": "SUCCESS",
        }

    def reindex_source(self, source_id: UUID) -> int:
        """Regenerates vector embeddings for all provisions/holdings of a legal source."""
        source = self.db.query(LegalSource).filter(LegalSource.id == source_id).first()
        if not source:
            raise ResourceNotFoundError(f"Legal source '{source_id}' not found.")

        versions = (
            self.db.query(LegalSourceVersion)
            .filter(LegalSourceVersion.source_id == source.id)
            .all()
        )

        if not versions:
            return 0

        texts = [v.content for v in versions]
        embeddings = self.embedding_service.generate_embeddings(texts)
        for version_obj, vec in zip(versions, embeddings, strict=False):
            version_obj.embedding = vec

        audit = AuditEvent(
            id=generate_uuid7(),
            event_type="LEGAL_AUTHORITY_REINDEX",
            entity_type="legal_source",
            entity_id=source.id,
            action="LEGAL_SOURCE_REINDEXED",
            timestamp=datetime.datetime.now(datetime.UTC),
            metadata_={
                "canonical_identifier": source.canonical_identifier,
                "provisions_reindexed": len(versions),
            },
        )
        self.db.add(audit)
        self.db.commit()
        return len(versions)
