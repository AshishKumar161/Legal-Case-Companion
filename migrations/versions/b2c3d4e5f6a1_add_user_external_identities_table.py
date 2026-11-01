"""Add user_external_identities table and make password_hash nullable

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-08-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a1"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create user_external_identities table
    op.create_table(
        "user_external_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", name="fk_user_external_identities_user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provider_metadata", sa.JSON(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_user_external_identity_provider_subject"),
    )

    op.create_index("ix_user_external_identities_user_id", "user_external_identities", ["user_id"])
    op.create_index("ix_user_external_identities_provider", "user_external_identities", ["provider"])
    op.create_index("ix_user_external_identities_provider_subject", "user_external_identities", ["provider_subject"])
    op.create_index("ix_user_external_identities_email", "user_external_identities", ["email"])

    # 2. Make password_hash nullable on users
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("password_hash", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("password_hash", existing_type=sa.String(), nullable=False)

    op.drop_index("ix_user_external_identities_email", table_name="user_external_identities")
    op.drop_index("ix_user_external_identities_provider_subject", table_name="user_external_identities")
    op.drop_index("ix_user_external_identities_provider", table_name="user_external_identities")
    op.drop_index("ix_user_external_identities_user_id", table_name="user_external_identities")
    op.drop_table("user_external_identities")
