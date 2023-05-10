"""Rename icp_matching_credits to ml_credits

Revision ID: 18b704e5ca8b
Revises: b27f5fac657d
Create Date: 2023-05-10 12:26:26.154070

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '18b704e5ca8b'
down_revision = 'b27f5fac657d'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add a new column with the desired character limit
    op.add_column('client_sdr', sa.Column('ml_credits', sa.Integer, nullable=True, default=5000))

    # 2. Copy data from old column to new column
    op.execute('UPDATE client_sdr SET ml_credits = icp_matching_credits')

    # 3. Drop the old column
    op.drop_column('client_sdr', 'icp_matching_credits')
    pass


def downgrade():
    # 1. Add a new column with the desired character limit
    op.add_column('client_sdr', sa.Column('icp_matching_credits', sa.Integer, nullable=True, default=5000))

    # 2. Copy data from old column to new column
    op.execute('UPDATE client_sdr SET icp_matching_credits = ml_credits')

    # 3. Drop the old column
    op.drop_column('client_sdr', 'ml_credits')
    pass
