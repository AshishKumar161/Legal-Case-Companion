"""Add video_recordings and video_recording_consents tables

Revision ID: g1a2b3c4d5e6
Revises: f1a2b3c4d5e6
Create Date: 2026-09-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g1a2b3c4d5e6"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create video_recordings table
    op.create_table(
        "video_recordings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "consultation_id",
            sa.Uuid(),
            sa.ForeignKey("consultations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.Uuid(),
            sa.ForeignKey("cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "recording_type",
            sa.String(length=50),
            server_default="BROWSER_MEDIA_RECORDER",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "mime_type",
            sa.String(length=100),
            server_default="video/webm",
            nullable=False,
        ),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_video_recordings_consultation_id",
        "video_recordings",
        ["consultation_id"],
        unique=False,
    )
    op.create_index(
        "ix_video_recordings_case_id",
        "video_recordings",
        ["case_id"],
        unique=False,
    )
    op.create_index(
        "ix_video_recordings_status",
        "video_recordings",
        ["status"],
        unique=False,
    )

    # 2. Create video_recording_consents table
    op.create_table(
        "video_recording_consents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "consultation_id",
            sa.Uuid(),
            sa.ForeignKey("consultations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recording_id",
            sa.Uuid(),
            sa.ForeignKey("video_recordings.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("consented", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "consented_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "consultation_id", "user_id", name="uq_consultation_user_consent"
        ),
    )
    op.create_index(
        "ix_video_recording_consents_consultation_id",
        "video_recording_consents",
        ["consultation_id"],
        unique=False,
    )
    op.create_index(
        "ix_video_recording_consents_user_id",
        "video_recording_consents",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_video_recording_consents_recording_id",
        "video_recording_consents",
        ["recording_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("video_recording_consents")
    op.drop_table("video_recordings")
