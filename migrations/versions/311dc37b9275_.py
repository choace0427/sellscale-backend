""" Remake prospect_uploads_raw_csv table to have JSONB instead of BYTEA

Revision ID: 311dc37b9275
Revises: 8bad6a70da12
Create Date: 2023-01-23 19:28:29.773189

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '311dc37b9275'
down_revision = '8bad6a70da12'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('prospect_uploads_raw_csv', 'csv_data')
    op.add_column('prospect_uploads_raw_csv', sa.Column('csv_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False))
    pass


def downgrade():
    pass
