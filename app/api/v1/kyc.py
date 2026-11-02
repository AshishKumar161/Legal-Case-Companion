import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.auth import limiter
from app.core.exceptions import AuthorizationError, ResourceNotFoundError, ValidationError
from app.core.storage import get_storage_provider, validate_storage_object_key
from app.domain.auth.auth_service import AuthService
from app.models.user import AccountStatus, ClientProfile, LawyerProfile, User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kyc", tags=["kyc"])


class KYCDocumentDownloadResponse(BaseModel):
    download_url: str
    filename: str | None = None
    expires_in_seconds: int = 300

ALLOWED_DOC_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


class KYCStatusResponse(BaseModel):
    role: str
    kyc_status: str
    is_kyc_completed: bool
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    id_type: str | None = None
    id_number: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    kyc_document_filename: str | None = None
    kyc_submitted_at: datetime | None = None
    kyc_verified_at: datetime | None = None
    kyc_rejection_reason: str | None = None
    enrollment_number: str | None = None
    state_bar_council: str | None = None
    practice_areas: list[str] | None = None
    court_jurisdictions: list[str] | None = None


class ClientKYCSubmitRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    phone: str = Field(..., min_length=10, max_length=20)
    date_of_birth: str | None = None
    gender: str | None = None
    id_type: str = Field(..., description="AADHAAR, PAN, PASSPORT, VOTER_ID, DRIVING_LICENSE")
    id_number: str = Field(..., min_length=4, max_length=100)
    address: str = Field(..., min_length=3, max_length=500)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    pincode: str = Field(..., min_length=6, max_length=10)
    kyc_document_storage_key: str | None = None
    kyc_document_filename: str | None = None
    dpdp_consent: bool = Field(True, description="Consent under Digital Personal Data Protection Act")


class KYCDocumentUploadResponse(BaseModel):
    storage_key: str
    filename: str
    sha256_hash: str
    content_type: str
    file_size_bytes: int


@router.get("/status", response_model=KYCStatusResponse)
@limiter.limit("60/minute")
def get_kyc_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves authoritative KYC / profile verification dossier for the active user."""
    if current_user.role == UserRole.ADMIN:
        return KYCStatusResponse(
            role="ADMIN",
            kyc_status="VERIFIED",
            is_kyc_completed=True,
            full_name=current_user.full_name,
            email=current_user.email,
        )

    if current_user.role == UserRole.LAWYER:
        lawyer_prof = (
            db.query(LawyerProfile).filter(LawyerProfile.user_id == current_user.id).first()
        )
        if not lawyer_prof:
            raise ResourceNotFoundError("Lawyer profile not found")

        return KYCStatusResponse(
            role="LAWYER",
            kyc_status=lawyer_prof.verification_status,
            is_kyc_completed=lawyer_prof.is_kyc_completed,
            full_name=lawyer_prof.full_name,
            email=current_user.email,
            phone=lawyer_prof.phone or current_user.phone,
            city=lawyer_prof.location,
            enrollment_number=lawyer_prof.enrollment_number,
            state_bar_council=lawyer_prof.state_bar_council,
            practice_areas=lawyer_prof.practice_areas if isinstance(lawyer_prof.practice_areas, list) else None,
            court_jurisdictions=lawyer_prof.court_jurisdictions if isinstance(lawyer_prof.court_jurisdictions, list) else None,
        )

    # User is CLIENT
    client_prof = (
        db.query(ClientProfile).filter(ClientProfile.user_id == current_user.id).first()
    )
    if not client_prof:
        # Create blank client profile if missing
        client_prof = ClientProfile(
            user_id=current_user.id,
            full_name=current_user.email.split("@")[0].capitalize(),
            kyc_status="PENDING",
        )
        db.add(client_prof)
        db.commit()
        db.refresh(client_prof)

    return KYCStatusResponse(
        role="CLIENT",
        kyc_status=client_prof.kyc_status or "PENDING",
        is_kyc_completed=client_prof.is_kyc_completed,
        full_name=client_prof.full_name,
        email=current_user.email,
        phone=client_prof.phone or current_user.phone,
        date_of_birth=client_prof.date_of_birth,
        gender=client_prof.gender,
        id_type=client_prof.id_type,
        id_number=client_prof.id_number,
        address=client_prof.address,
        city=client_prof.city or client_prof.location,
        state=client_prof.state,
        pincode=client_prof.pincode,
        kyc_document_filename=client_prof.kyc_document_filename,
        kyc_submitted_at=client_prof.kyc_submitted_at,
        kyc_verified_at=client_prof.kyc_verified_at,
        kyc_rejection_reason=client_prof.kyc_rejection_reason,
    )


@router.post("/client/document", response_model=KYCDocumentUploadResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def upload_client_kyc_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads and cryptographically hashes client identity proof document (PDF, PNG, JPG)."""
    if current_user.role != UserRole.CLIENT:
        raise AuthorizationError("Only clients can upload client KYC documents.")

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_DOC_TYPES:
        raise ValidationError("Unsupported file format. Please upload PDF, JPEG, PNG, or WebP.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise ValidationError("Uploaded file is empty.")
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValidationError("File exceeds maximum allowed size of 5MB.")

    # Compute SHA-256 integrity hash
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    sanitized_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", file.filename or "id_proof.pdf")
    ext = ALLOWED_DOC_TYPES.get(content_type, ".pdf")
    if not sanitized_filename.endswith(ext):
        sanitized_filename += ext

    storage_key = f"kyc/{current_user.id}/{uuid.uuid4().hex[:12]}_{sanitized_filename}"
    validated_key = validate_storage_object_key(storage_key)

    storage = get_storage_provider()
    storage.put_object_bytes(validated_key, file_bytes, content_type)

    logger.info(f"Client KYC document uploaded: user={current_user.id}, key={validated_key}, hash={sha256_hash}")

    return KYCDocumentUploadResponse(
        storage_key=validated_key,
        filename=sanitized_filename,
        sha256_hash=sha256_hash,
        content_type=content_type,
        file_size_bytes=len(file_bytes),
    )


@router.post("/client/submit", response_model=KYCStatusResponse)
@limiter.limit("15/minute")
def submit_client_kyc(
    request: Request,
    payload: ClientKYCSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submits client profile details and identity verification declaration."""
    if current_user.role != UserRole.CLIENT:
        raise AuthorizationError("Only clients can submit client KYC.")

    if not payload.dpdp_consent:
        raise ValidationError("DPDP Act statutory consent is required to complete KYC.")

    # Clean and validate phone (accept 10 digits with optional +91 or leading 0)
    cleaned_phone = re.sub(r"[\s\-\(\)]", "", payload.phone)
    if cleaned_phone.startswith("+91"):
        cleaned_phone = cleaned_phone[3:]
    elif cleaned_phone.startswith("91") and len(cleaned_phone) == 12:
        cleaned_phone = cleaned_phone[2:]
    elif cleaned_phone.startswith("0") and len(cleaned_phone) == 11:
        cleaned_phone = cleaned_phone[1:]

    if not re.match(r"^[6-9]\d{9}$", cleaned_phone):
        raise ValidationError("Please provide a valid 10-digit Indian mobile number.")

    # Clean and validate PIN code (6 digits)
    cleaned_pincode = payload.pincode.strip()
    if not re.match(r"^\d{6}$", cleaned_pincode):
        raise ValidationError("Please provide a valid 6-digit Indian PIN code.")

    # Validate ID Number
    cleaned_id = payload.id_number.strip().upper()
    if len(cleaned_id) < 4:
        raise ValidationError("Please provide a valid Identity Document number.")

    client_prof = (
        db.query(ClientProfile).filter(ClientProfile.user_id == current_user.id).first()
    )
    if not client_prof:
        client_prof = ClientProfile(user_id=current_user.id)
        db.add(client_prof)

    now = datetime.now(UTC)

    # Populate profile attributes
    client_prof.full_name = payload.full_name.strip()
    client_prof.phone = cleaned_phone
    current_user.phone = cleaned_phone
    client_prof.date_of_birth = payload.date_of_birth
    client_prof.gender = payload.gender
    client_prof.id_type = payload.id_type.upper()
    client_prof.id_number = cleaned_id
    client_prof.address = payload.address.strip()
    client_prof.city = payload.city.strip()
    client_prof.state = payload.state.strip()
    client_prof.location = f"{payload.city.strip()}, {payload.state.strip()}"
    client_prof.pincode = cleaned_pincode

    if payload.kyc_document_storage_key:
        clean_key = validate_storage_object_key(payload.kyc_document_storage_key)
        expected_prefix = f"kyc/{current_user.id}/"
        if not clean_key.startswith(expected_prefix):
            raise AuthorizationError("Access denied: KYC document does not belong to the authenticated user.")
        client_prof.kyc_document_storage_key = clean_key
    if payload.kyc_document_filename:
        client_prof.kyc_document_filename = payload.kyc_document_filename.strip()

    # Mark as VERIFIED so client instantly has full platform functionality
    client_prof.kyc_status = "VERIFIED"
    client_prof.kyc_submitted_at = now
    client_prof.kyc_verified_at = now
    client_prof.kyc_rejection_reason = None
    current_user.account_status = AccountStatus.ACTIVE

    db.commit()
    db.refresh(client_prof)

    logger.info(f"Client KYC completed successfully: user_id={current_user.id}, name={client_prof.full_name}")

    return KYCStatusResponse(
        role="CLIENT",
        kyc_status=client_prof.kyc_status,
        is_kyc_completed=True,
        full_name=client_prof.full_name,
        email=current_user.email,
        phone=client_prof.phone,
        date_of_birth=client_prof.date_of_birth,
        gender=client_prof.gender,
        id_type=client_prof.id_type,
        id_number=client_prof.id_number,
        address=client_prof.address,
        city=client_prof.city,
        state=client_prof.state,
        pincode=client_prof.pincode,
        kyc_document_filename=client_prof.kyc_document_filename,
        kyc_submitted_at=client_prof.kyc_submitted_at,
        kyc_verified_at=client_prof.kyc_verified_at,
    )


@router.get("/client/document/download", response_model=KYCDocumentDownloadResponse)
@limiter.limit("20/minute")
def download_client_kyc_document(
    request: Request,
    user_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates a secure, authorized, signed URL to view or download a client KYC document.
    Access strictly restricted to the owning client or platform administrators.
    """
    target_user_id = user_id or current_user.id
    if target_user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise AuthorizationError("Access denied: you are not authorized to view this KYC document.")

    client_prof = db.query(ClientProfile).filter(ClientProfile.user_id == target_user_id).first()
    if not client_prof or not client_prof.kyc_document_storage_key:
        raise ResourceNotFoundError("KYC document not found for user.")

    storage = get_storage_provider()
    expires_in = 300
    if hasattr(storage, "generate_presigned_download_url"):
        download_url = storage.generate_presigned_download_url(
            client_prof.kyc_document_storage_key, expires_in=expires_in
        )
    else:
        download_url = f"/api/v1/storage/{client_prof.kyc_document_storage_key}"

    auth_svc = AuthService(db)
    auth_svc.log_audit_event(
        event_type="KYC_DOCUMENT_DOWNLOADED",
        user_id=current_user.id,
        metadata={
            "target_user_id": str(target_user_id),
            "filename": client_prof.kyc_document_filename,
            "storage_key": client_prof.kyc_document_storage_key,
        },
        action="user_mutation",
    )
    db.commit()

    return KYCDocumentDownloadResponse(
        download_url=download_url,
        filename=client_prof.kyc_document_filename,
        expires_in_seconds=expires_in,
    )

