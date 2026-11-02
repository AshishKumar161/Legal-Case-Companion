"""Evidentiary Bundle Service for Phase 11.

Coordinates bundle creation, deterministic exhibit ordering, Bates numbering,
cryptographic hash manifest generation, PDF compilation, private S3 storage,
and BSA Section 63 statutory certificate preparation.
"""

import hashlib
import io
import re
import uuid
from datetime import UTC, datetime
from typing import Any

import pypdf
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.authorization import (
    authorize_case_access,
    authorize_case_modification,
)
from app.core.exceptions import ConflictError, ResourceNotFoundError, ValidationError
from app.core.identifiers import generate_uuid7
from app.core.storage import get_storage_provider
from app.models.audit import AuditEvent
from app.models.bundle import (
    BSACertificateDraft,
    BundleStatus,
    EvidenceBundle,
    EvidenceBundleItem,
)
from app.models.case import Case, CaseTimelineEvent
from app.models.evidence import (
    CaseExhibit,
    Evidence,
    EvidenceAccessGrant,
    EvidenceAccessLevel,
    EvidenceStatus,
    EvidenceVersion,
)
from app.models.user import User, UserRole
from app.models.workflow import CaseHearing
from app.schemas.bundle import (
    BSACertificateCreateRequest,
    BundleCreateRequest,
    BundleItemCreate,
    BundleUpdateRequest,
)
from app.domain.cases.bundle_pdf_engine import BundlePdfEngine


def _natural_exhibit_sort_key(item: Any) -> tuple:
    """Sort key for deterministic exhibit ordering: Exhibit A, B... Z, AA, AB..."""
    ex_num = getattr(item, "exhibit_number", None) or ""
    if not ex_num:
        return (1, getattr(item, "order_index", 9999), "")

    # Strip common exhibit prefixes like "Exhibit ", "Ex. ", "Exhibit-"
    clean = re.sub(r"^(exhibit|ex\.?)\s*[-:]?\s*", "", ex_num, flags=re.IGNORECASE).strip()
    if clean.isalpha():
        letters = clean.upper()
        # Sort by length first so 'Z' precedes 'AA', then alphabetical
        return (0, len(letters), letters)
    elif clean.isdigit():
        return (0, 0, int(clean))
    return (0, 99, clean.upper())


class BundleService:
    """Production service for courtroom evidentiary bundle preparation and compilation."""

    def __init__(self, db: Session):
        self.db = db
        self.storage = get_storage_provider()

    def _log_audit(self, event_type: str, user_id: uuid.UUID, metadata: dict | None = None) -> None:
        bundle_id_val = None
        if metadata and metadata.get("bundle_id"):
            try:
                bundle_id_val = uuid.UUID(str(metadata["bundle_id"]))
            except Exception:
                bundle_id_val = None

        event = AuditEvent(
            id=generate_uuid7(),
            actor_user_id=user_id,
            event_type="BUNDLE_OPERATION",
            entity_type="EVIDENCE_BUNDLE",
            entity_id=bundle_id_val,
            action=event_type,
            timestamp=datetime.now(UTC),
            metadata_=metadata,
        )
        self.db.add(event)

    def _record_timeline(self, case_id: uuid.UUID, user_id: uuid.UUID, event_type: str, description: str, metadata: dict | None = None) -> None:
        timeline_ev = CaseTimelineEvent(
            id=generate_uuid7(),
            case_id=case_id,
            actor_user_id=user_id,
            event_type=event_type,
            description=description,
            event_metadata=metadata,
        )
        self.db.add(timeline_ev)

    def _authorize_evidence_access(self, user: User, case_id: uuid.UUID, evidence_id: uuid.UUID) -> Evidence:
        """Verifies evidence belongs to case and caller is authorized to view it."""
        evidence = (
            self.db.query(Evidence)
            .filter(
                Evidence.id == evidence_id,
                Evidence.case_id == case_id,
                Evidence.deleted_at.is_(None),
            )
            .first()
        )
        if not evidence:
            raise ResourceNotFoundError(f"Evidence '{evidence_id}' not found in case.")

        # Admin and Lawyer roles have case-wide access
        if user.role in (UserRole.ADMIN, UserRole.LAWYER):
            return evidence

        # Owner has access
        if evidence.created_by_user_id == user.id:
            return evidence

        # Otherwise check active access grants
        grant = (
            self.db.query(EvidenceAccessGrant)
            .filter(
                EvidenceAccessGrant.evidence_id == evidence_id,
                EvidenceAccessGrant.grantee_user_id == user.id,
                EvidenceAccessGrant.revoked_at.is_(None),
            )
            .first()
        )
        if not grant or (grant.expires_at and grant.expires_at < datetime.now(UTC)):
            raise ResourceNotFoundError(f"Access to evidence '{evidence_id}' denied or expired.")

        return evidence

    def create_bundle(
        self,
        user: User,
        case_id: uuid.UUID,
        req: BundleCreateRequest,
    ) -> EvidenceBundle:
        """Initializes a new draft evidentiary bundle."""
        authorize_case_modification(self.db, user, case_id)

        # Hearing check if provided
        hearing = None
        if req.hearing_id:
            hearing = (
                self.db.query(CaseHearing)
                .filter(
                    CaseHearing.id == req.hearing_id,
                    CaseHearing.case_id == case_id,
                    CaseHearing.deleted_at.is_(None),
                )
                .first()
            )
            if not hearing:
                raise ResourceNotFoundError("Court hearing not found in case.")

        bundle = EvidenceBundle(
            id=generate_uuid7(),
            case_id=case_id,
            hearing_id=req.hearing_id,
            title=req.title.strip(),
            description=req.description.strip() if req.description else None,
            status=BundleStatus.DRAFT,
            bates_prefix=req.bates_prefix.strip().upper(),
            bates_start=req.bates_start,
            created_by_user_id=user.id,
        )
        self.db.add(bundle)
        self.db.flush()

        if req.items:
            self._set_bundle_items(user, case_id, bundle, req.items)

        self._log_audit("BUNDLE_CREATED", user.id, {"case_id": str(case_id), "bundle_id": str(bundle.id), "title": bundle.title})
        self.db.commit()
        self.db.refresh(bundle)
        return bundle

    def _set_bundle_items(
        self,
        user: User,
        case_id: uuid.UUID,
        bundle: EvidenceBundle,
        item_creates: list[BundleItemCreate],
    ) -> None:
        """Resolves and sets items in a draft bundle with deterministic ordering."""
        # Remove existing items if any
        self.db.query(EvidenceBundleItem).filter(EvidenceBundleItem.bundle_id == bundle.id).delete()

        processed_items: list[dict[str, Any]] = []

        for idx, item_req in enumerate(item_creates):
            evidence = self._authorize_evidence_access(user, case_id, item_req.evidence_id)

            # Resolve version
            version_id = item_req.version_id or evidence.current_version_id
            if not version_id:
                raise ValidationError(f"Evidence '{evidence.title}' has no valid version uploaded.")

            version = (
                self.db.query(EvidenceVersion)
                .filter(
                    EvidenceVersion.id == version_id,
                    EvidenceVersion.evidence_id == evidence.id,
                )
                .first()
            )
            if not version:
                raise ResourceNotFoundError(f"Version '{version_id}' not found for evidence '{evidence.title}'.")

            # Resolve exhibit if linked
            exhibit_number = None
            if item_req.exhibit_id:
                exhibit = (
                    self.db.query(CaseExhibit)
                    .filter(
                        CaseExhibit.id == item_req.exhibit_id,
                        CaseExhibit.case_id == case_id,
                        CaseExhibit.deleted_at.is_(None),
                    )
                    .first()
                )
                if exhibit:
                    exhibit_number = exhibit.exhibit_number
            else:
                # Auto-find if evidence has a marked exhibit in this case
                exhibit = (
                    self.db.query(CaseExhibit)
                    .filter(
                        CaseExhibit.evidence_id == evidence.id,
                        CaseExhibit.case_id == case_id,
                        CaseExhibit.deleted_at.is_(None),
                    )
                    .first()
                )
                if exhibit:
                    exhibit_number = exhibit.exhibit_number

            processed_items.append({
                "evidence_id": evidence.id,
                "version_id": version.id,
                "exhibit_id": item_req.exhibit_id,
                "exhibit_number": exhibit_number,
                "custom_title": item_req.custom_title or evidence.title,
                "order_index": item_req.order_index if item_req.order_index is not None else idx,
                "sha256_hash": version.sha256,
                "file_size": version.size_bytes,
                "mime_type": version.content_type,
            })

        # Sort items deterministically: exhibit number first, then order_index
        processed_items.sort(key=lambda x: (0 if x["exhibit_number"] else 1, _natural_exhibit_sort_key(type("Item", (), x))))

        for sorted_idx, p_item in enumerate(processed_items):
            bundle_item = EvidenceBundleItem(
                id=generate_uuid7(),
                bundle_id=bundle.id,
                evidence_id=p_item["evidence_id"],
                version_id=p_item["version_id"],
                exhibit_id=p_item["exhibit_id"],
                order_index=sorted_idx,
                exhibit_number=p_item["exhibit_number"],
                custom_title=p_item["custom_title"],
                sha256_hash=p_item["sha256_hash"],
                file_size=p_item["file_size"],
                mime_type=p_item["mime_type"],
            )
            self.db.add(bundle_item)

        bundle.total_items = len(processed_items)

    def get_bundle(
        self,
        user: User,
        case_id: uuid.UUID,
        bundle_id: uuid.UUID,
    ) -> EvidenceBundle:
        """Retrieves a single evidentiary bundle with bounded authorization."""
        authorize_case_access(self.db, user, case_id)
        bundle = (
            self.db.query(EvidenceBundle)
            .filter(
                EvidenceBundle.id == bundle_id,
                EvidenceBundle.case_id == case_id,
                EvidenceBundle.deleted_at.is_(None),
            )
            .first()
        )
        if not bundle:
            raise ResourceNotFoundError("Evidentiary bundle not found.")
        return bundle

    def list_bundles(
        self,
        user: User,
        case_id: uuid.UUID,
        status: BundleStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[EvidenceBundle]:
        """Lists bundles for a case with bounded pagination."""
        authorize_case_access(self.db, user, case_id)
        bounded_limit = max(1, min(100, limit))

        query = self.db.query(EvidenceBundle).filter(
            EvidenceBundle.case_id == case_id,
            EvidenceBundle.deleted_at.is_(None),
        )
        if status:
            query = query.filter(EvidenceBundle.status == status)

        return (
            query.order_by(desc(EvidenceBundle.created_at), desc(EvidenceBundle.id))
            .offset(offset)
            .limit(bounded_limit)
            .all()
        )

    def update_bundle(
        self,
        user: User,
        case_id: uuid.UUID,
        bundle_id: uuid.UUID,
        req: BundleUpdateRequest,
    ) -> EvidenceBundle:
        """Updates a draft bundle. Finalized bundles are strictly immutable."""
        authorize_case_modification(self.db, user, case_id)
        bundle = self.get_bundle(user, case_id, bundle_id)

        if bundle.status == BundleStatus.FINALIZED:
            raise ConflictError("Cannot modify a finalized bundle. Create a new bundle version instead.")

        if req.title is not None:
            bundle.title = req.title.strip()
        if req.description is not None:
            bundle.description = req.description.strip() if req.description else None
        if req.hearing_id is not None:
            bundle.hearing_id = req.hearing_id
        if req.bates_prefix is not None:
            bundle.bates_prefix = req.bates_prefix.strip().upper()
        if req.bates_start is not None:
            bundle.bates_start = req.bates_start

        if req.items is not None:
            self._set_bundle_items(user, case_id, bundle, req.items)

        self.db.commit()
        self.db.refresh(bundle)
        return bundle

    def finalize_bundle(
        self,
        user: User,
        case_id: uuid.UUID,
        bundle_id: uuid.UUID,
    ) -> EvidenceBundle:
        """Compiles the full court bundle PDF with Bates numbering and finalizes it immutably."""
        authorize_case_modification(self.db, user, case_id)

        # Pessimistic row locking on bundle
        bundle = (
            self.db.query(EvidenceBundle)
            .filter(
                EvidenceBundle.id == bundle_id,
                EvidenceBundle.case_id == case_id,
                EvidenceBundle.deleted_at.is_(None),
            )
            .with_for_update()
            .first()
        )
        if not bundle:
            raise ResourceNotFoundError("Evidentiary bundle not found.")

        if bundle.status == BundleStatus.FINALIZED:
            raise ConflictError("Bundle is already finalized and immutable.")

        items = (
            self.db.query(EvidenceBundleItem)
            .filter(EvidenceBundleItem.bundle_id == bundle.id)
            .order_by(EvidenceBundleItem.order_index.asc())
            .all()
        )
        if not items:
            raise ValidationError("Cannot finalize an empty bundle. Add at least one evidence item.")

        bundle.status = BundleStatus.GENERATING
        self.db.commit()

        try:
            case = self.db.query(Case).filter(Case.id == case_id).first()
            hearing = None
            if bundle.hearing_id:
                hearing = self.db.query(CaseHearing).filter(CaseHearing.id == bundle.hearing_id).first()

            # Compile PDF
            writer = pypdf.PdfWriter()
            current_bates = bundle.bates_start
            now_dt = datetime.now(UTC)

            # 1. Estimate bates range and prepare manifest list
            item_manifest_entries: list[dict[str, Any]] = []

            # Pass 1: Read page counts and build manifest entries
            item_page_counts: list[tuple[EvidenceBundleItem, EvidenceVersion, bytes, int]] = []
            for item in items:
                version = self.db.query(EvidenceVersion).filter(EvidenceVersion.id == item.version_id).first()
                if not version:
                    raise ResourceNotFoundError(f"Version '{item.version_id}' missing during finalization.")

                file_bytes = self.storage.get_object_bytes(version.storage_key)
                if not file_bytes:
                    raise ResourceNotFoundError(f"File bytes missing for version '{version.id}'.")

                computed_hash = hashlib.sha256(file_bytes).hexdigest()
                if computed_hash != version.sha256:
                    raise ValidationError(f"Integrity check failed for '{version.original_filename}'. Expected {version.sha256}, got {computed_hash}.")

                item.sha256_hash = computed_hash
                item.file_size = len(file_bytes)

                count = 1
                if version.content_type == "application/pdf":
                    try:
                        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                        count = len(reader.pages)
                    except Exception:
                        count = 1

                item.bates_start_page = current_bates
                item.bates_end_page = current_bates + count - 1
                current_bates += count

                item_page_counts.append((item, version, file_bytes, count))
                item_manifest_entries.append({
                    "item_id": str(item.id),
                    "evidence_id": str(item.evidence_id),
                    "version_id": str(item.version_id),
                    "exhibit_number": item.exhibit_number,
                    "title": item.custom_title or version.original_filename,
                    "filename": version.original_filename,
                    "bates_start": f"{bundle.bates_prefix}{item.bates_start_page:06d}",
                    "bates_end": f"{bundle.bates_prefix}{item.bates_end_page:06d}",
                    "sha256": computed_hash,
                    "size_bytes": len(file_bytes),
                    "mime_type": version.content_type,
                })

            final_bates_range = f"{bundle.bates_prefix}{bundle.bates_start:06d} - {bundle.bates_prefix}{current_bates - 1:06d}"

            # Step 1: Add Cover Page
            cover_page = BundlePdfEngine.create_cover_page(
                bundle_title=bundle.title,
                case_title=case.title if case else "Legal Proceeding",
                case_id=str(case_id),
                court_name=hearing.court_name if hearing else None,
                hearing_info=f"{hearing.purpose} ({hearing.hearing_at.strftime('%d %b %Y')})" if hearing else None,
                bates_range=final_bates_range,
                total_items=len(items),
                finalized_at=now_dt,
            )
            writer.add_page(cover_page)

            # Step 2: Add Index Page
            index_page = BundlePdfEngine.create_index_page(
                bundle_title=bundle.title,
                items=item_manifest_entries,
            )
            writer.add_page(index_page)

            # Step 3: Add and Stamp Evidence Pages
            for item, version, file_bytes, _ in item_page_counts:
                bates_num = item.bates_start_page or bundle.bates_start

                if version.content_type == "application/pdf":
                    try:
                        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                        for page in reader.pages:
                            added_page = writer.add_page(page)
                            bates_lbl = f"{bundle.bates_prefix}{bates_num:06d}"
                            header_lbl = f"{bundle.title} | {item.exhibit_number or item.custom_title or version.original_filename}"
                            overlay = BundlePdfEngine.create_bates_stamp_overlay(
                                bates_label=bates_lbl,
                                bundle_header=header_lbl,
                                width=float(added_page.mediabox.width),
                                height=float(added_page.mediabox.height),
                            )
                            added_page.merge_page(overlay)
                            bates_num += 1
                    except Exception:
                        bates_lbl = f"{bundle.bates_prefix}{bates_num:06d}"
                        ph = BundlePdfEngine.create_placeholder_page(
                            exhibit_number=item.exhibit_number,
                            title=item.custom_title or version.original_filename,
                            original_filename=version.original_filename,
                            mime_type=version.content_type,
                            sha256_hash=item.sha256_hash,
                            bates_label=bates_lbl,
                        )
                        writer.add_page(ph)
                else:
                    bates_lbl = f"{bundle.bates_prefix}{bates_num:06d}"
                    ph = BundlePdfEngine.create_placeholder_page(
                        exhibit_number=item.exhibit_number,
                        title=item.custom_title or version.original_filename,
                        original_filename=version.original_filename,
                        mime_type=version.content_type,
                        sha256_hash=item.sha256_hash,
                        bates_label=bates_lbl,
                    )
                    writer.add_page(ph)

            # Step 4: Add Manifest Summary Page
            manifest_summary_page = BundlePdfEngine.create_manifest_summary_page(
                bundle_title=bundle.title,
                bundle_hash="COMPUTING_FINAL_DIGEST",
                items=item_manifest_entries,
            )
            writer.add_page(manifest_summary_page)

            # Write compiled stream
            compiled_buf = io.BytesIO()
            writer.write(compiled_buf)
            compiled_bytes = compiled_buf.getvalue()

            bundle_sha256 = hashlib.sha256(compiled_bytes).hexdigest()
            storage_key = f"bundles/{case_id}/{bundle.id}.pdf"

            # Upload to private storage
            self.storage.put_object_bytes(storage_key, compiled_bytes, mime_type="application/pdf")

            # Freeze authoritative manifest
            frozen_manifest = {
                "bundle_id": str(bundle.id),
                "case_id": str(case_id),
                "title": bundle.title,
                "sha256_hash": bundle_sha256,
                "file_size": len(compiled_bytes),
                "bates_prefix": bundle.bates_prefix,
                "bates_start": bundle.bates_start,
                "bates_end": current_bates - 1,
                "total_pages": len(writer.pages),
                "finalized_at": now_dt.isoformat(),
                "created_by_user_id": str(user.id),
                "items": item_manifest_entries,
            }

            bundle.status = BundleStatus.FINALIZED
            bundle.storage_key = storage_key
            bundle.file_size = len(compiled_bytes)
            bundle.sha256_hash = bundle_sha256
            bundle.bates_end = current_bates - 1
            bundle.total_pages = len(writer.pages)
            bundle.finalized_at = now_dt
            bundle.manifest_json = frozen_manifest

            # Timeline event & audit log
            self._record_timeline(
                case_id=case_id,
                user_id=user.id,
                event_type="BUNDLE_FINALIZED",
                description=f"Evidentiary Bundle '{bundle.title}' finalized with {len(items)} exhibits ({final_bates_range})",
                metadata={"bundle_id": str(bundle.id), "sha256": bundle_sha256, "total_pages": len(writer.pages)},
            )
            self._log_audit("BUNDLE_FINALIZED", user.id, {"case_id": str(case_id), "bundle_id": str(bundle.id), "sha256": bundle_sha256})

            self.db.commit()
            self.db.refresh(bundle)
            return bundle

        except Exception:
            bundle.status = BundleStatus.FAILED
            self.db.commit()
            raise

    def get_bundle_download_url(
        self,
        user: User,
        case_id: uuid.UUID,
        bundle_id: uuid.UUID,
        expires_in: int = 60,
    ) -> dict[str, Any]:
        """Generates a short-lived presigned URL for the finalized bundle PDF."""
        bundle = self.get_bundle(user, case_id, bundle_id)
        if bundle.status != BundleStatus.FINALIZED or not bundle.storage_key:
            raise ValidationError("Bundle is not in finalized state. Download unavailable.")

        download_name = f"{bundle.title.replace(' ', '_')}_{bundle.bates_prefix}.pdf"
        url = self.storage.generate_presigned_download_url(
            object_key=bundle.storage_key,
            expires_in=expires_in,
            response_content_disposition=f'attachment; filename="{download_name}"',
            response_content_type="application/pdf",
        )

        self._log_audit("BUNDLE_DOWNLOADED", user.id, {"case_id": str(case_id), "bundle_id": str(bundle.id)})
        return {
            "url": url,
            "expires_in": expires_in,
            "filename": download_name,
            "sha256": bundle.sha256_hash,
            "file_size": bundle.file_size,
        }

    def prepare_bsa_certificate(
        self,
        user: User,
        case_id: uuid.UUID,
        bundle_id: uuid.UUID,
        req: BSACertificateCreateRequest,
    ) -> BSACertificateDraft:
        """Prepares a Section 63(4) BSA 2023 draft certificate for a finalized bundle."""
        bundle = self.get_bundle(user, case_id, bundle_id)
        if bundle.status != BundleStatus.FINALIZED:
            raise ValidationError("BSA certificates can only be prepared for finalized bundles.")

        if not req.is_confirmed:
            raise ValidationError("Human statutory confirmation of custody and operational statements is mandatory under Section 63 BSA 2023.")

        cert_id = generate_uuid7()
        cert_data = {
            "record_identification": req.record_identification.strip(),
            "source_device_type": req.source_device_type.strip(),
            "source_device_details": req.source_device_details.strip() if req.source_device_details else "Secure Cloud Infrastructure",
            "lawful_control_statement": req.lawful_control_statement.strip(),
            "operational_condition_statement": req.operational_condition_statement.strip(),
            "declarant_name": req.declarant_name.strip(),
            "declarant_designation": req.declarant_designation.strip(),
            "declarant_organization": req.declarant_organization.strip() if req.declarant_organization else None,
            "place": req.place.strip(),
            "declaration_date": req.declaration_date,
            "hash_value": bundle.sha256_hash,
            "hash_algorithm": "SHA-256",
            "expert_examiner_name": req.expert_examiner_name.strip() if req.expert_examiner_name else None,
            "expert_examiner_designation": req.expert_examiner_designation.strip() if req.expert_examiner_designation else None,
            "expert_examination_details": req.expert_examination_details.strip() if req.expert_examination_details else None,
        }

        # Generate certificate PDF
        pdf_bytes = BundlePdfEngine.create_bsa_certificate_pdf(cert_data)
        storage_key = f"certificates/{case_id}/{cert_id}.pdf"
        self.storage.put_object_bytes(storage_key, pdf_bytes, mime_type="application/pdf")

        cert = BSACertificateDraft(
            id=cert_id,
            case_id=case_id,
            bundle_id=bundle.id,
            record_identification=cert_data["record_identification"],
            source_device_type=cert_data["source_device_type"],
            source_device_details=cert_data["source_device_details"],
            lawful_control_statement=cert_data["lawful_control_statement"],
            operational_condition_statement=cert_data["operational_condition_statement"],
            hash_value=cert_data["hash_value"],
            hash_algorithm=cert_data["hash_algorithm"],
            declarant_name=cert_data["declarant_name"],
            declarant_designation=cert_data["declarant_designation"],
            declarant_organization=cert_data["declarant_organization"],
            place=cert_data["place"],
            declaration_date=cert_data["declaration_date"],
            is_confirmed=True,
            status="PREPARED_DRAFT",
            storage_key=storage_key,
            created_by_user_id=user.id,
        )
        self.db.add(cert)

        self._record_timeline(
            case_id=case_id,
            user_id=user.id,
            event_type="CERTIFICATE_PREPARED",
            description=f"BSA Section 63(4) Certificate Draft prepared for bundle '{bundle.title}' (Declarant: {cert.declarant_name})",
            metadata={"certificate_id": str(cert.id), "bundle_id": str(bundle.id)},
        )
        self._log_audit("BUNDLE_CERTIFICATE_PREPARED", user.id, {"case_id": str(case_id), "bundle_id": str(bundle.id), "certificate_id": str(cert.id)})

        self.db.commit()
        self.db.refresh(cert)
        return cert

    def get_certificate_download_url(
        self,
        user: User,
        case_id: uuid.UUID,
        certificate_id: uuid.UUID,
        expires_in: int = 60,
    ) -> dict[str, Any]:
        """Generates a short-lived presigned URL for the prepared BSA certificate PDF."""
        authorize_case_access(self.db, user, case_id)
        cert = (
            self.db.query(BSACertificateDraft)
            .filter(
                BSACertificateDraft.id == certificate_id,
                BSACertificateDraft.case_id == case_id,
            )
            .first()
        )
        if not cert or not cert.storage_key:
            raise ResourceNotFoundError("Certificate draft not found.")

        download_name = f"BSA_Sec63_Certificate_{cert.id}.pdf"
        url = self.storage.generate_presigned_download_url(
            object_key=cert.storage_key,
            expires_in=expires_in,
            response_content_disposition=f'attachment; filename="{download_name}"',
            response_content_type="application/pdf",
        )
        return {"url": url, "expires_in": expires_in, "filename": download_name}
