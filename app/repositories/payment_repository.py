"""Persistence repository for Payment entities."""

from uuid import UUID
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentStatus


class PaymentRepository:
    """Encapsulates persistence operations for Payment domain models."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, payment_id: UUID) -> Payment | None:
        """Retrieves a payment record by UUID."""
        return self.db.query(Payment).filter(Payment.id == payment_id).first()

    def get_by_consultation(self, consultation_id: UUID) -> Payment | None:
        """Retrieves the latest payment for a consultation."""
        return (
            self.db.query(Payment)
            .filter(Payment.consultation_id == consultation_id)
            .order_by(Payment.created_at.desc())
            .first()
        )

    def get_by_provider_payment_id(self, provider_payment_id: str) -> Payment | None:
        """Retrieves a payment by external provider payment intent ID."""
        return (
            self.db.query(Payment)
            .filter(Payment.provider_payment_id == provider_payment_id)
            .first()
        )

    def list_by_payer(
        self,
        payer_user_id: UUID,
        status: PaymentStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Payment]:
        """Lists payments made by a specific payer user."""
        query = self.db.query(Payment).filter(Payment.payer_user_id == payer_user_id)
        if status:
            query = query.filter(Payment.status == status)
        return query.order_by(Payment.created_at.desc()).offset(offset).limit(limit).all()
