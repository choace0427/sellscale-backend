"""Add Bio Summary Enum

Revision ID: ffb0db601585
Revises: 68ec1a54b4d1
Create Date: 2023-01-31 11:41:48.068795

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ffb0db601585"
down_revision = "68ec1a54b4d1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("COMMIT")
    op.execute("ALTER TYPE researchpointtype ADD VALUE 'LINKEDIN_BIO_SUMMARY'")


def downgrade():
    pass
