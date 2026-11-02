"""add client profile kyc fields

Revision ID: z2a3b4c5d6e7
Revises: z1a2b3c4d5e6
Create Date: 2026-11-02 07:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'z2a3b4c5d6e7'
down_revision = 'z1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('client_profiles', sa.Column('phone', sa.String(length=20), nullable=True))
    op.add_column('client_profiles', sa.Column('date_of_birth', sa.String(length=20), nullable=True))
    op.add_column('client_profiles', sa.Column('gender', sa.String(length=20), nullable=True))
    op.add_column('client_profiles', sa.Column('id_type', sa.String(length=50), nullable=True))
    op.add_column('client_profiles', sa.Column('id_number', sa.String(length=100), nullable=True))
    op.add_column('client_profiles', sa.Column('address', sa.Text(), nullable=True))
    op.add_column('client_profiles', sa.Column('city', sa.String(length=100), nullable=True))
    op.add_column('client_profiles', sa.Column('state', sa.String(length=100), nullable=True))
    op.add_column('client_profiles', sa.Column('pincode', sa.String(length=20), nullable=True))
    op.add_column('client_profiles', sa.Column('kyc_document_storage_key', sa.String(length=512), nullable=True))
    op.add_column('client_profiles', sa.Column('kyc_document_filename', sa.String(length=255), nullable=True))
    op.add_column('client_profiles', sa.Column('kyc_status', sa.String(length=50), server_default='PENDING', nullable=False))
    op.add_column('client_profiles', sa.Column('kyc_submitted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('client_profiles', sa.Column('kyc_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('client_profiles', sa.Column('kyc_rejection_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('client_profiles', 'kyc_rejection_reason')
    op.drop_column('client_profiles', 'kyc_verified_at')
    op.drop_column('client_profiles', 'kyc_submitted_at')
    op.drop_column('client_profiles', 'kyc_status')
    op.drop_column('client_profiles', 'kyc_document_filename')
    op.drop_column('client_profiles', 'kyc_document_storage_key')
    op.drop_column('client_profiles', 'pincode')
    op.drop_column('client_profiles', 'state')
    op.drop_column('client_profiles', 'city')
    op.drop_column('client_profiles', 'address')
    op.drop_column('client_profiles', 'id_number')
    op.drop_column('client_profiles', 'id_type')
    op.drop_column('client_profiles', 'gender')
    op.drop_column('client_profiles', 'date_of_birth')
    op.drop_column('client_profiles', 'phone')
