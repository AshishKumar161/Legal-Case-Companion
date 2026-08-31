"""enrich_legal_authorities_and_provisions

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-08-30 22:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5e6f7a8b9c0d"
down_revision: str | None = "4d5e6f7a8b9c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.engine.name == "postgresql"

    # Define enums
    authority_type_enum = sa.Enum(
        "PRIMARY_LEGISLATION",
        "SUBORDINATE_LEGISLATION",
        "JUDICIAL_DECISION",
        "OFFICIAL_NOTIFICATION",
        "OFFICIAL_CIRCULAR",
        "SECONDARY_MATERIAL",
        name="legalauthoritytype",
    )
    status_enum = sa.Enum(
        "IMPORTED",
        "VALIDATED",
        "PUBLISHED",
        "AMENDED",
        "REPEALED",
        "OVERRULED",
        name="legalsourcestatus",
    )

    if is_postgres:
        authority_type_enum.create(bind, checkfirst=True)
        status_enum.create(bind, checkfirst=True)

    with op.batch_alter_table("legal_sources") as batch_op:
        batch_op.add_column(
            sa.Column("canonical_identifier", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(sa.Column("short_title", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column(
                "source_type",
                authority_type_enum,
                nullable=False,
                server_default="PRIMARY_LEGISLATION",
            )
        )
        batch_op.add_column(
            sa.Column("authority_level", sa.Integer(), nullable=False, server_default="90")
        )
        batch_op.add_column(sa.Column("issuing_body", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("publication_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("effective_from", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("effective_to", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "status",
                status_enum,
                nullable=False,
                server_default="PUBLISHED",
            )
        )
        batch_op.add_column(sa.Column("citation_standard", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("canonical_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("metadata_", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            )
        )
        batch_op.create_index("ix_legal_sources_canonical_identifier", ["canonical_identifier"], unique=True)
        batch_op.create_index("ix_legal_sources_effective_from", ["effective_from"], unique=False)
        batch_op.create_index("ix_legal_sources_effective_to", ["effective_to"], unique=False)

    with op.batch_alter_table("legal_source_versions") as batch_op:
        batch_op.add_column(
            sa.Column("canonical_provision_id", sa.String(length=150), nullable=True)
        )
        batch_op.add_column(
            sa.Column("version_label", sa.String(length=100), nullable=False, server_default="Current")
        )
        batch_op.add_column(sa.Column("chapter_number", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("effective_from", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("effective_to", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column(
                "embedding",
                postgresql.ARRAY(sa.Float()) if is_postgres else sa.JSON(),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("metadata_", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            )
        )
        batch_op.create_index("ix_legal_source_versions_canonical_provision_id", ["canonical_provision_id"], unique=True)
        batch_op.create_index("ix_legal_source_versions_is_current", ["is_current"], unique=False)
        batch_op.create_index("ix_legal_source_versions_effective_from", ["effective_from"], unique=False)
        batch_op.create_index("ix_legal_source_versions_effective_to", ["effective_to"], unique=False)
        batch_op.create_unique_constraint(
            "uq_legal_source_section_version",
            ["source_id", "section_number", "version_label"],
        )


def downgrade() -> None:
    with op.batch_alter_table("legal_source_versions") as batch_op:
        batch_op.drop_constraint("uq_legal_source_section_version", type_="unique")
        batch_op.drop_index("ix_legal_source_versions_effective_to")
        batch_op.drop_index("ix_legal_source_versions_effective_from")
        batch_op.drop_index("ix_legal_source_versions_is_current")
        batch_op.drop_index("ix_legal_source_versions_canonical_provision_id")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("metadata_")
        batch_op.drop_column("embedding")
        batch_op.drop_column("is_current")
        batch_op.drop_column("effective_to")
        batch_op.drop_column("effective_from")
        batch_op.drop_column("chapter_number")
        batch_op.drop_column("version_label")
        batch_op.drop_column("canonical_provision_id")

    with op.batch_alter_table("legal_sources") as batch_op:
        batch_op.drop_index("ix_legal_sources_effective_to")
        batch_op.drop_index("ix_legal_sources_effective_from")
        batch_op.drop_index("ix_legal_sources_canonical_identifier")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("metadata_")
        batch_op.drop_column("canonical_url")
        batch_op.drop_column("citation_standard")
        batch_op.drop_column("status")
        batch_op.drop_column("effective_to")
        batch_op.drop_column("effective_from")
        batch_op.drop_column("publication_date")
        batch_op.drop_column("issuing_body")
        batch_op.drop_column("authority_level")
        batch_op.drop_column("source_type")
        batch_op.drop_column("short_title")
        batch_op.drop_column("canonical_identifier")
