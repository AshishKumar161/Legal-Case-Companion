import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.core.identifiers import generate_uuid7
from app.models.audit import AuditEvent
from app.models.notification import (
    Notification,
    NotificationType,
    UserNotificationPreference,
)
from app.models.user import User
from app.schemas.notification import NotificationPreferenceUpdate
from app.services.email_service import get_email_provider

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.email_provider = get_email_provider()

    def get_preferences(
        self, user: User | None = None, user_id: uuid.UUID | None = None
    ) -> UserNotificationPreference:
        target_uid = user.id if user else user_id
        if not target_uid:
            raise ValueError("User or user_id must be provided")

        pref = (
            self.db.query(UserNotificationPreference)
            .filter(UserNotificationPreference.user_id == target_uid)
            .first()
        )
        if not pref:
            pref = UserNotificationPreference(
                id=generate_uuid7(),
                user_id=target_uid,
                email_enabled=True,
                case_updates=True,
                task_updates=True,
                consultation_updates=True,
            )
            self.db.add(pref)
            self.db.commit()
            self.db.refresh(pref)
        return pref

    def update_preferences(
        self, user: User, req: NotificationPreferenceUpdate
    ) -> UserNotificationPreference:
        pref = self.get_preferences(user=user)
        dump = req.model_dump(exclude_unset=True)
        updated_fields = []
        for k, v in dump.items():
            if v is not None:
                setattr(pref, k, v)
                updated_fields.append(k)

        if updated_fields:
            self.db.commit()
            self.db.refresh(pref)

            # Audit preference update
            audit = AuditEvent(
                id=generate_uuid7(),
                actor_user_id=user.id,
                event_type="NOTIFICATION_PREFERENCES_UPDATED",
                entity_type="user_notification_preferences",
                entity_id=user.id,
                action="update_preferences",
                timestamp=datetime.now(UTC),
                metadata_={"updated_fields": updated_fields},
            )
            self.db.add(audit)
            self.db.commit()

        return pref

    def create_notification(
        self,
        user_id: uuid.UUID,
        type: NotificationType,
        title: str,
        message: str,
        case_id: uuid.UUID | None = None,
        consultation_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
        deadline_id: uuid.UUID | None = None,
        hearing_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
        event_id: str | None = None,
        metadata: dict | None = None,
        send_email: bool = True,
    ) -> Notification | None:
        # Check user preferences
        pref = self.get_preferences(user_id=user_id)

        case_types = {
            NotificationType.CASE_CREATED,
            NotificationType.CASE_STATUS_CHANGED,
            NotificationType.PARTICIPANT_ADDED,
            NotificationType.LAWYER_ASSIGNED,
            NotificationType.DOCUMENT_READY,
            NotificationType.DOCUMENT_PROCESSING_FAILED,
            NotificationType.AI_REVIEW_REQUIRED,
        }
        task_types = {
            NotificationType.TASK_ASSIGNED,
            NotificationType.TASK_DUE_SOON,
            NotificationType.TASK_OVERDUE,
            NotificationType.TASK_COMPLETED,
            NotificationType.DEADLINE_APPROACHING,
            NotificationType.DEADLINE_OVERDUE,
            NotificationType.HEARING_REMINDER,
        }
        consultation_types = {
            NotificationType.CONSULTATION_REQUESTED,
            NotificationType.CONSULTATION_ACCEPTED,
            NotificationType.CONSULTATION_REJECTED,
            NotificationType.CONSULTATION_SCHEDULED,
            NotificationType.CONSULTATION_CANCELLED,
            NotificationType.CONSULTATION_COMPLETED,
            NotificationType.PAYMENT_CREATED,
            NotificationType.PAYMENT_SUCCEEDED,
            NotificationType.PAYMENT_FAILED,
            NotificationType.PAYMENT_REFUNDED,
        }

        # Check in-app category opt-outs
        if type in case_types and not pref.case_updates:
            return None
        if type in task_types and not pref.task_updates:
            return None
        if type in consultation_types and not pref.consultation_updates:
            return None

        # Deterministic event deduplication
        if event_id:
            existing = (
                self.db.query(Notification)
                .filter(
                    Notification.user_id == user_id,
                    Notification.event_id == event_id,
                    Notification.type == type,
                    Notification.deleted_at.is_(None),
                )
                .first()
            )
            if existing:
                return existing

        notification = Notification(
            id=generate_uuid7(),
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            case_id=case_id,
            consultation_id=consultation_id,
            task_id=task_id,
            deadline_id=deadline_id,
            hearing_id=hearing_id,
            document_id=document_id,
            event_id=event_id,
            metadata_=metadata,
            is_read=False,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)

        # Delivery boundary: attempt email notification safely if opted in
        if send_email and pref.email_enabled:
            try:
                user = self.db.query(User).filter(User.id == user_id).first()
                if user and user.email:
                    self.email_provider.send_email(
                        to_email=user.email,
                        subject=f"[LCC] {title}",
                        html_body=f"<p>{message}</p>",
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"Failed to dispatch email notification to user {user_id}: {e}"
                )

        return notification

    def list_notifications(
        self,
        user: User,
        is_read: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        limit = min(max(limit, 1), 100)
        query = self.db.query(Notification).filter(
            Notification.user_id == user.id, Notification.deleted_at.is_(None)
        )

        if is_read is not None:
            query = query.filter(Notification.is_read == is_read)

        total = query.count()
        items = (
            query.order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def get_unread_count(self, user: User) -> int:
        return (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user.id,
                Notification.is_read.is_(False),
                Notification.deleted_at.is_(None),
            )
            .count()
        )

    def _get_user_notification(
        self, user: User, notification_id: uuid.UUID
    ) -> Notification:
        notification = (
            self.db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.deleted_at.is_(None),
            )
            .first()
        )
        if not notification or notification.user_id != user.id:
            raise ResourceNotFoundError("Notification not found")  # IDOR protection
        return notification

    def mark_as_read(self, user: User, notification_id: uuid.UUID) -> Notification:
        notification = self._get_user_notification(user, notification_id)
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(notification)
        return notification

    def mark_as_unread(self, user: User, notification_id: uuid.UUID) -> Notification:
        notification = self._get_user_notification(user, notification_id)
        if notification.is_read:
            notification.is_read = False
            notification.read_at = None
            self.db.commit()
            self.db.refresh(notification)
        return notification

    def mark_all_as_read(self, user: User) -> int:
        now = datetime.now(UTC)
        updated = (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user.id,
                Notification.is_read.is_(False),
                Notification.deleted_at.is_(None),
            )
            .update({"is_read": True, "read_at": now}, synchronize_session=False)
        )
        self.db.commit()
        return updated

    def bulk_mark_as_read(
        self, user: User, notification_ids: list[uuid.UUID]
    ) -> int:
        if not notification_ids:
            return 0
        now = datetime.now(UTC)
        updated = (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user.id,
                Notification.id.in_(notification_ids),
                Notification.is_read.is_(False),
                Notification.deleted_at.is_(None),
            )
            .update({"is_read": True, "read_at": now}, synchronize_session=False)
        )
        self.db.commit()
        return updated

    def delete_notification(self, user: User, notification_id: uuid.UUID) -> None:
        notification = self._get_user_notification(user, notification_id)
        notification.deleted_at = datetime.now(UTC)
        self.db.commit()
