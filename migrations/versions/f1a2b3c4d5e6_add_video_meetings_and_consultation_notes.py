"""Add video_meetings and consultation_notes tables and lawyer languages

Revision ID: f1a2b3c4d5e6
Revises: e5f6a1b2c3d4
Create Date: 2026-09-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e5f6a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create video_meetings table
    op.create_table(
        "video_meetings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("consultation_id", sa.Uuid(), sa.ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("room_id", sa.String(length=100), nullable=False, unique=True),
        sa.Column("provider", sa.String(length=50), server_default="internal_webrtc", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="SCHEDULED", nullable=False),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recording_url", sa.String(), nullable=True),
        sa.Column("meeting_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_video_meetings_consultation_id", "video_meetings", ["consultation_id"], unique=True)
    op.create_index("ix_video_meetings_room_id", "video_meetings", ["room_id"], unique=True)

    # 2. Create consultation_notes table
    op.create_table(
        "consultation_notes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("consultation_id", sa.Uuid(), sa.ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("action_items", sa.JSON(), nullable=True),
        sa.Column("client_shared", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_consultation_notes_consultation_id", "consultation_notes", ["consultation_id"], unique=False)
    op.create_index("ix_consultation_notes_author_user_id", "consultation_notes", ["author_user_id"], unique=False)

    # 3. Add languages column to lawyer_profiles
    with op.batch_alter_table("lawyer_profiles", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("languages", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("lawyer_profiles", schema=None) as batch_op:
        batch_op.drop_column("languages")

    op.drop_table("consultation_notes")
    op.drop_table("video_meetings")
