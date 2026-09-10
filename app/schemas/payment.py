from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.payment import PaymentStatus


class PaymentResponse(BaseModel):
    id: UUID
    consultation_id: UUID
    payer_user_id: UUID
    amount: float
    currency: str
    status: PaymentStatus
    provider: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentIntentResponse(BaseModel):
    payment_id: UUID
    client_secret: str
    amount: float
    currency: str


# In a real Stripe integration, Stripe SDK parses the webhook, but we define a minimal mocked schema for our implementation
class StripeWebhookPayload(BaseModel):
    id: str
    type: str
    data: dict
