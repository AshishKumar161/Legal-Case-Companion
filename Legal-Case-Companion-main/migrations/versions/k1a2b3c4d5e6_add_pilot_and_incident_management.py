"""add pilot allowlist, operator permissions, and production incident tables

Revision ID: k1a2b3c4d5e6
Revises: j1a2b3c4d5e6
Create Date: 2026-09-04 03:45:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k1a2b3c4d5e6"
down_revision: str | None = "j1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Pilot Allowlist
    op.create_table(
        "pilot_allowlist",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column(
            "identifier_type",
            sa.Enum("EMAIL", "DOMAIN", "USER_ID", "ORGANIZATION", name="allowlistidentifiertype"),
            nullable=False,
        ),
        sa.Column(
            "role_target",
            sa.Enum("CLIENT", "LAWYER", "ADMIN", name="userrole"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "REVOKED", "EXPIRED", name="allowliststatus"),
            nullable=False,
        ),
        sa.Column("added_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pilot_allowlist_identifier"), "pilot_allowlist", ["identifier"], unique=False)
    op.create_index(op.f("ix_pilot_allowlist_status"), "pilot_allowlist", ["status"], unique=False)

    # 2. User Operator Permissions
    op.create_table(
        "user_operator_permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "permission",
            sa.Enum(
                "USER_SUPPORT",
                "USER_MANAGEMENT",
                "SEC_OPS",
                "INCIDENT_MANAGE",
                "COMPLIANCE_OPERATIONS",
                "EVIDENCE_OPERATIONS",
                "BILLING_OPERATIONS",
                "SYSTEM_OPERATIONS",
                "PILOT_GOVERNANCE",
                name="operationalpermission",
            ),
            nullable=False,
        ),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_operator_permissions_permission"), "user_operator_permissions", ["permission"], unique=False)
    op.create_index(op.f("ix_user_operator_permissions_user_id"), "user_operator_permissions", ["user_id"], unique=False)

    # 3. Production Incidents
    op.create_table(
        "production_incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("SEV1_CRITICAL", "SEV2_HIGH", "SEV3_MEDIUM", "SEV4_LOW", name="incidentseverity"),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum(
                "SECURITY",
                "ABUSE",
                "SYSTEM_OUTAGE",
                "DATA_INTEGRITY",
                "AI_SAFETY",
                "COMPLIANCE",
                "PAYMENT",
                name="incidentcategory",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("DETECTED", "ACKNOWLEDGED", "INVESTIGATING", "MITIGATED", "RESOLVED", "CLOSED", name="incidentstatus"),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mitigated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("affected_scope", sa.String(length=500), nullable=True),
        sa.Column(
            "detected_by",
            sa.Enum("AUTOMATED_MONITOR", "OPERATOR", "USER_REPORT", "AUDIT_WATCHER", "EXTERNAL", name="incidentdetector"),
            nullable=False,
        ),
        sa.Column("assigned_to_user_id", sa.Uuid(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("mitigation", sa.Text(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("postmortem_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("postmortem_url", sa.String(length=500), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_production_incidents_category"), "production_incidents", ["category"], unique=False)
    op.create_index(op.f("ix_production_incidents_incident_id"), "production_incidents", ["incident_id"], unique=True)
    op.create_index(op.f("ix_production_incidents_severity"), "production_incidents", ["severity"], unique=False)
    op.create_index(op.f("ix_production_incidents_status"), "production_incidents", ["status"], unique=False)

    # 4. Incident Timeline Events
    op.create_table(
        "incident_timeline_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["production_incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_incident_timeline_events_incident_id"), "incident_timeline_events", ["incident_id"], unique=False)
    op.create_index(op.f("ix_incident_timeline_events_timestamp"), "incident_timeline_events", ["timestamp"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_incident_timeline_events_timestamp"), table_name="incident_timeline_events")
    op.drop_index(op.f("ix_incident_timeline_events_incident_id"), table_name="incident_timeline_events")
    op.drop_table("incident_timeline_events")

    op.drop_index(op.f("ix_production_incidents_status"), table_name="production_incidents")
    op.drop_index(op.f("ix_production_incidents_severity"), table_name="production_incidents")
    op.drop_index(op.f("ix_production_incidents_incident_id"), table_name="production_incidents")
    op.drop_index(op.f("ix_production_incidents_category"), table_name="production_incidents")
    op.drop_table("production_incidents")

    op.drop_index(op.f("ix_user_operator_permissions_user_id"), table_name="user_operator_permissions")
    op.drop_index(op.f("ix_user_operator_permissions_permission"), table_name="user_operator_permissions")
    op.drop_table("user_operator_permissions")

    op.drop_index(op.f("ix_pilot_allowlist_status"), table_name="pilot_allowlist")
    op.drop_index(op.f("ix_pilot_allowlist_identifier"), table_name="pilot_allowlist")
    op.drop_table("pilot_allowlist")
